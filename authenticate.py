# import os
# import pickle
# from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow

# SCOPES = [ "https://mail.google.com/", "https://www.googleapis.com/auth/drive" ]

# flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
# creds = flow.run_local_server(port=0)
# print("this is creds from : ", creds)
# with open("token.json", "w") as token:
#     token.write(creds.to_json())

# service_gmail = build("gmail", "v1", credentials=creds)
# service_drive = build("drive", "v3", credentials=creds)

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [ "https://mail.google.com/", "https://www.googleapis.com/auth/drive" ]

from google.oauth2.credentials import Credentials
import os

def get_gmail_service(creds):
    """Create Gmail service once"""
    return build("gmail", "v1", credentials=creds)
def get_drive_service(creds):
    """Create Gmail service once"""
    return build("drive", "v3", credentials=creds)

def get_credentials():
    if os.path.exists("token1.json"):
        creds = Credentials.from_authorized_user_file("token1.json", SCOPES)
        # Check if expired and refresh if needed
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds
    else:
        # First time - need to authorize
        return authorize_user()

def authorize_user():
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES
    )
    creds = flow.run_local_server(port=0)
    with open("token1.json", "w") as token:
        token.write(creds.to_json())
    return creds

def start_watch(service):
    # service = build("gmail", "v1", credentials=creds)
    print("this is service froms tart_watch :" , service)

    request_body = {
        "topicName": "file_topic",
        "labelIds": ["INBOX"]
    }

    watch_response = service.users().watch(userId="me", body=request_body).execute()
    print("Watch response:", watch_response)
    # Save historyId for later
    return watch_response.get("historyId")


def main():
    creds = get_credentials()
    service = get_gmail_service(creds)
    # history_id = start_watch(service)

    return creds, service

if __name__ == "__main__":
    main()

