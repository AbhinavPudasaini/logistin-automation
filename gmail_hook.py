# from main_agent import run_agent, classify_email
from flask import Flask, request, Response
import base64, json, os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from agent.gmail_client import extract_attachments
from agent.normalizer import normalize_email
from ocr2 import process_invoice_image

app = Flask(__name__)

creds = Credentials.from_authorized_user_file("token1.json")
# Build service once at module level (reused across requests)
gmail_service = build("gmail", "v1", credentials=creds)

# File to store the last processed history ID
HISTORY_FILE = "last_history_id.txt"

def start_watch(service=None):
    """Start Gmail push notification watch. Call on server startup."""
    svc = service or gmail_service
    print("Starting Gmail watch...")

    request_body = {
        "topicName": "topic",
        "labelIds": ["INBOX"]
    }

    watch_response = svc.users().watch(userId="me", body=request_body).execute()
    print("Watch response:", watch_response)
    # Save historyId for later
    return watch_response.get("historyId")


def get_last_history_id():
    """Load the last processed history ID from file"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return f.read().strip()
    return None

def save_history_id(history_id):
    """Save the current history ID to file"""
    with open(HISTORY_FILE, "w") as f:
        f.write(str(history_id))


def process_single_email(email: dict) -> dict:
    """
    Process a single email: classify it, extract OCR if needed, and run agent.
    
    Returns a dict with processing results.
    """
    subject = email.get('subject', '')
    body = email.get('body', '')
    attachments = email.get('attachments', [])
    
    print(f"\n{'='*50}")
    print(f"Processing email: {subject}")
    print(f"{'='*50}")
    
    # Step 1: Classify the email (lightweight LLM call)
    # --------------------------- My change -----------------------------------
    # is_invoice_related = classify_email(subject, body)
    
    # if not is_invoice_related:
    #     print(f"⏭️ Skipping: Email not invoice-related")
    #     return {
    #         "email": email,
    #         "processed": False,
    #         "reason": "Not invoice-related",
    #         "ocr_text": None
    #     }
    
    # print(f"✅ Email classified as invoice-related")
    # --------------------------- My change -----------------------------------
    
    # Step 2: Extract OCR from attachments (only for invoice-related emails)
    ocr_text = None
    if attachments:
        print(f"📎 Found {len(attachments)} attachment(s)")
        for index,attachment in enumerate(attachments):   # My Change -------------------------------------------
            path = attachment.get('path')
            mime_type = attachment.get('mime', '')
            
            # Only process image/PDF attachments
            if path and (mime_type.startswith('image/') or 
                        mime_type == 'application/pdf' or
                        path.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp'))):
                try:
                    print(f"🔍 Running OCR on: {attachment.get('filename')}")
                    ocr_text = process_invoice_image(path)
                    print(f"✅ OCR extracted successfully")
                    with open(f"{index}_no.txt","w", encoding="utf-8") as f:
                        f.write(ocr_text)
                except Exception as e:
                    print(f"❌ OCR failed for {path}: {e}")
    else:
        print("📭 No attachments found")
    
    # Step 3: Run the agent with email content and OCR text
    email_content = f"From: {email.get('from', 'Unknown')}\nSubject: {subject}\nDate: {email.get('date', 'Unknown')}\n\n{body}"
    print(email_content)
    
    # try:
    #     run_agent(email_content, ocr_text)
    #     return {
    #         "email": email,
    #         "processed": True,
    #         "reason": "Successfully processed",
    #         "ocr_text": ocr_text
    #     }
    # except Exception as e:
    #     print(f"❌ Agent failed: {e}")
    #     return {
    #         "email": email,
    #         "processed": False,
    #         "reason": f"Agent error: {e}",
    #         "ocr_text": ocr_text
    #     }


def fetch_changes(start_history_id,service):
    """
    Fetch new emails since the given history ID.
    Returns: (list of emails, final_history_id)
    """
    emails = []
    final_history_id = start_history_id
    page_token = None

    try:
        while True:
            params = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "historyTypes": ["messageAdded"],
            }
            if page_token:
                params["pageToken"] = page_token

            results = service.users().history().list(**params).execute()

            history = results.get("history", [])
            for record in history:
                for added in record.get("messagesAdded", []):
                    msg_id = added.get("message", {}).get("id")
                    if not msg_id:
                        continue
                    try:
                        msg = service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="full",
                        ).execute()

                        attachments = extract_attachments(msg)
                        email = normalize_email(msg, attachments)
                        emails.append(email)
                        print(f"📧 New mail: {msg.get('snippet', '')[:50]}...")
                    except Exception as e:
                        print(f"❌ Could not fetch message {msg_id}: {e}")

            # Track the latest historyId returned by the API for this page
            final_history_id = results.get("historyId", final_history_id)

            page_token = results.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"Failed to fetch history: {e}")
        # Return whatever we have and keep the existing history id
        return emails, final_history_id

    return emails, final_history_id


@app.route("/webhook/email", methods=["POST"])
def gmail_push():
    envelope = request.get_json(force=True)
    msg = envelope.get("message", {})
    data = msg.get("data")
    
    if not data:
        return Response("No data", status=400)

    decoded = base64.b64decode(data).decode("utf-8")
    notification = json.loads(decoded)

    print("\n" + "="*60)
    print("📬 Push notification received:", notification)
    print("="*60)
    
    # Get the NEW history ID from the notification
    new_history_id = notification.get("historyId")

    # Get the LAST PROCESSED history ID from storage
    last_history_id = get_last_history_id()
    
    if not last_history_id:
        print("⚠️ No previous history ID found. Using notification historyId.")
        save_history_id(new_history_id)
        return Response("Initialized", status=200)
    
    print(f"🔄 Fetching changes from {last_history_id} to {new_history_id}")
    emails, final_history_id = fetch_changes(last_history_id, gmail_service)
    
    print(f"\n📊 Found {len(emails)} new email(s)")
    
    # Process each email
    results = []
    for email in emails:
        result = process_single_email(email)
        results.append(result)
    
    # Summary
    processed_count = sum(1 for r in results if r['processed'])
    skipped_count = len(results) - processed_count
    print(f"\n📈 Summary: {processed_count} processed, {skipped_count} skipped")
    
    # Save the latest history ID observed to ensure progression
    try:
        nh = int(str(new_history_id)) if new_history_id is not None else 0
        fh = int(str(final_history_id)) if final_history_id is not None else 0
        to_save = max(nh, fh)
    except Exception:
        # Fallback if parsing fails
        to_save = final_history_id or new_history_id

    save_history_id(to_save)
    print(f"💾 Saved new history ID: {to_save} (notification: {new_history_id}, fetched: {final_history_id})")

    return Response("OK", status=200)


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return Response("OK", status=200)


if __name__ == "__main__":
    # Renew watch on startup (Gmail watch expires every 7 days)
    print("🚀 Starting server...")
    if not get_last_history_id():
        print("📡 No history ID found, starting Gmail watch...")
        history_id = start_watch(gmail_service)
        save_history_id(history_id)
        print(f"✅ Watch started with history ID: {history_id}")
    # else:
    #     # Optionally renew watch even if history exists (good practice)
    #     print("📡 Renewing Gmail watch...")
    #     start_watch(gmail_service)
    #     print("✅ Watch renewed")
    
    app.run(port=8080, debug=True)
