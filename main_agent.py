from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
# from langgraph.prebuilt import create_react_agent
from flask import Flask, request, Response
from langchain.agents import create_agent
from langchain_core.tools import tool
from Vapi_tools.spreedsheet import sheet
from langgraph.checkpoint.memory import InMemorySaver  



app = Flask(__name__)


model = ChatGroq(
    model="moonshotai/kimi-k2-instruct-0905", 
    api_key="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"
)

# Lightweight model for classification
classifier_model = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key="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"
)

SYSTEM_PROMPT = """You are an intelligent invoice processing agent. Your job is to extract structured data from invoice/receipt content and push it to a Google Spreadsheet.

## Your Task:
1. Analyze the email content and OCR-extracted text from invoice attachments
2. Extract the following fields from the invoice:
   - **invoice_no**: The invoice or receipt number (e.g., "INV-2024-001", "REC-12345")
   - **carrier**: The shipping/logistics carrier name (e.g., "FedEx", "UPS", "DHL", "USPS")
   - **delivery_date**: When the item was/will be delivered (format: YYYY-MM-DD)
   - **received_date**: When the invoice/order was received (format: YYYY-MM-DD)
   - **total_amount**: The total amount on the invoice (include currency, e.g., "$150.00")
   - **status**: The current status (e.g., "Delivered", "In Transit", "Pending", "Paid")

3. Use the `push_to_sheet` tool to save the extracted data

## Rules:
- If a field cannot be found, use "N/A" as the value
- Always extract dates in YYYY-MM-DD format when possible
- Be thorough - scan the entire document for information
- After successfully pushing data, confirm what was saved

## Example Output Before Tool Call:
"I found the following invoice details:
- Invoice No: INV-2024-001
- Carrier: FedEx
- Delivery Date: 2024-01-20
- Received Date: 2024-01-15
- Total Amount: $245.50
- Status: Delivered

Pushing to spreadsheet..."
"""

system_prompt2 = """
You are Riley, an appointment scheduling.
Your role is to book an appointment , asking every required and necessary details from patient.

To book an appointment , ask for following details:
1. name :  name of patient
2. address :  the address of patient where patient live
3. book_time :  the time for which to book an appointment
4. doctor :  the name of doctor to visit
5. type :  the type of visit (consultation, operation,etc)

NOTE: For every consultation the fee is 500.
IMPORTANT : DOn't ask any other detail except the provided one.
## Tools
You have access to the following tools:

1. push_sheet - You will use this to push the data of user to book an appointment. 
2. read_from_sheet - You will use this to read the data from google spreedsheets regarding appointment.

IMPORTANT: Ask each details one by one, not all at one time.
"""

CLASSIFICATION_PROMPT = """Analyze this email and determine if it is related to invoices, receipts, shipping, logistics, delivery confirmations, or billing.

Email Subject: {subject}
Email Body: {body}

Respond with ONLY one word:
- "INVOICE" if this email is about invoices, receipts, shipping, logistics, delivery, or billing
- "OTHER" if this email is about something else (newsletters, promotions, personal messages, etc.)

Your response:"""


# @tool
@app.route("/update/invoice", methods=["POST"])
def push_to_sheet(invoice_no: str, carrier: str, delivery_date: str, received_date: str, total_amount: str, status: str):
    """
    Push extracted invoice data to Google Spreadsheet.
    
    Args:
        invoice_no: The invoice or receipt number
        carrier: The shipping/logistics carrier name (FedEx, UPS, DHL, etc.)
        delivery_date: When the item was/will be delivered (YYYY-MM-DD format)
        received_date: When the invoice/order was received (YYYY-MM-DD format)
        total_amount: The total amount on the invoice (include currency symbol)
        status: Current status (Delivered, In Transit, Pending, Paid, etc.)
    
    Returns:
        Success message confirming the data was pushed
    """
    row = [
        invoice_no,
        carrier,
        delivery_date,
        received_date,
        total_amount,
        status    
    ]
    sheet.append_row(row)
    return f"Successfully pushed invoice {invoice_no} to spreadsheet with total amount {total_amount}"


@app.route("/update/appointment", methods=["POST"])
def push_sheet():
    """
    Handle Vapi tool call for pushing appointment data to Google Spreadsheet.
    
    Expected Vapi tool call format with parameters:
    - name: The name of the patient
    - address: The address of patient  
    - book_time: The booking time for appointment
    - doctor: The name of Doctor
    - fee: The fee for appointment
    - type: The type of visit (consultation, operation, etc)
    
    Returns:
    JSON response with results array for Vapi
    """
    try:
        # Get the JSON data from Vapi's request
        data = request.get_json()
        
        # Extract tool call information
        tool_call_list = data.get("message", {}).get("toolCallList", [])
        
        if not tool_call_list:
            return {"error": "No tool calls found"}, 400
            
        results = []
        
        # Process each tool call
        for tool_call in tool_call_list:
            tool_call_id = tool_call.get("id")
            arguments = tool_call.get("arguments", {})
            
            # Extract the parameters from the tool call arguments
            name = arguments.get("name", "")
            address = arguments.get("address", "")
            book_time = arguments.get("book_time", "")
            doctor = arguments.get("doctor", "")
            fee = arguments.get("fee", "")
            appointment_type = arguments.get("type", "")
            print("THis is name : ", name)
            print("THis is address : ", address)
            print("THis is book : ", book_time)
            print("THis is doctor : ", doctor)
            print("THis is fee : ", fee)
            print("THis is appointment : ", appointment_type)
            
            # Validate required fields
            if not all([name, book_time, doctor]):
                results.append({
                    "toolCallId": tool_call_id,
                    "result": "Error: Missing required fields (name, book_time, doctor)"
                })
                continue
            
            # Create the row data
            row = [name, address, book_time, doctor, fee, appointment_type]
            
            # Push to Google Sheets
            sheet.append_row(row)
            
            # Add successful result
            results.append({
                "toolCallId": tool_call_id,
                "result": f"Successfully booked appointment for {name} with Dr. {doctor} on {book_time}"
            })
        
        return {"results": results}
        
    except Exception as e:
        # Handle any errors
        return {
            "results": [{
                "toolCallId": tool_call_list[0].get("id") if tool_call_list else "unknown",
                "result": f"Error booking appointment: {str(e)}"
            }]
        }, 500


# @tool
@app.route("/appointment", methods=["POST"])
def read_from_sheet():
    """
    Handle Vapi tool call for reading appointment data from Google Spreadsheet.
    
    Returns:
    JSON response with results array containing appointment data for Vapi
    """
    try:
        # Get the JSON data from Vapi's request
        print(" i am in this toll -----------")
        data = request.get_json()
        
        # Extract tool call information
        tool_call_list = data.get("message", {}).get("toolCallList", [])
        
        if not tool_call_list:
            return {"error": "No tool calls found"}, 400
            
        results = []
        
        # Process each tool call
        for tool_call in tool_call_list:
            tool_call_id = tool_call.get("id")
            
            try:
                # Get all records from the sheet
                records = sheet.get_all_records()
                
                if not records:
                    results.append({
                        "toolCallId": tool_call_id,
                        "result": "No appointments found in the system."
                    })
                    continue
                
                # Format the appointments data for the assistant
                appointment_list = []
                for record in records:
                    appointment_info = f"Patient: {record.get('name', 'N/A')}, Doctor: {record.get('doctor', 'N/A')}, Time: {record.get('book_time', 'N/A')}, Type: {record.get('type', 'N/A')}"
                    appointment_list.append(appointment_info)
                
                # Join all appointments into a single string
                appointments_text = "; ".join(appointment_list)
                
                results.append({
                    "toolCallId": tool_call_id,
                    "result": f"Found {len(records)} appointments: {appointments_text}"
                })
                
            except Exception as e:
                results.append({
                    "toolCallId": tool_call_id,
                    "result": f"Error reading appointments: {str(e)}"
                })
        
        return {"results": results}
        
    except Exception as e:
        # Handle any errors
        return {
            "results": [{
                "toolCallId": tool_call_list[0].get("id") if tool_call_list else "unknown",
                "result": f"Error accessing appointment data: {str(e)}"
            }]
        }, 500




def classify_email(email_subject: str, email_body: str) -> bool:
    """
    Classify if an email is invoice-related using a lightweight LLM.
    Returns True if invoice-related, False otherwise.
    """
    prompt = CLASSIFICATION_PROMPT.format(subject=email_subject, body=email_body)
    
    try:
        response = classifier_model.invoke([HumanMessage(content=prompt)])
        classification = response.content.strip().upper()
        print(f"Email classification: {classification}")
        return "INVOICE" in classification
    except Exception as e:
        print(f"Classification failed, defaulting to True: {e}")
        return True  # Default to processing if classification fails


def run_agent(email_content, ocr_text):
    """
    Run the invoice processing agent.
    
    Args:
        email_content: The email body/snippet
        ocr_text: OCR-extracted text from attachments (optional)
    """
    # Build the human message with all available context
    human_message_parts = ["## Email Content:\n", email_content]
    
    if ocr_text:
        human_message_parts.extend([
            "\n\n## OCR-Extracted Text from Attachment:\n",
            ocr_text
        ])
    
    human_message = "".join(human_message_parts)
    
    # Create the agent with tools
    agent = create_agent(
        model=model,
        tools=[push_sheet,read_from_sheet],
        checkpointer=InMemorySaver()
    )
    
    # Build messages list with system prompt and human message
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_message)
    ]
    
    while True:
        user_query = input("User : ")

        if user_query == "exit":
            break

        messages = [
        SystemMessage(content=system_prompt2),
        HumanMessage(content=user_query)
        ]

        output = agent.invoke({"messages":messages},{"configurable": {"thread_id": "1"}})
        ai_messages = output.get("messages", [])
        if ai_messages:
            # Use the latest AI message instead of echoing the user input
            print("Ai :", ai_messages[-1].content)
        else:
            print("Ai : (no response)")


if __name__ == "__main__":
#     # Test with sample data
#     test_email = "Your invoice #INV-2024-001 has been processed. Total: $150.00"
#     test_ocr = """
#     INVOICE
#     Invoice Number: INV-2024-001
#     Date: 2024-01-15
#     Carrier: FedEx
#     Delivery Date: 2024-01-20
#     Total Amount: $150.00
#     Status: Delivered
#     """
    # run_agent()
    app.run(port=8080, debug=True)
