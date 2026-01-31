import gspread
from google.oauth2.service_account import Credentials
# from google.oauth2.credentials import Credentials
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]
      
creds = Credentials.from_service_account_file(
"service_account.json",
scopes=SCOPES )

client = gspread.authorize(creds)

# opening
sheet = client.open_by_key("file_id").sheet1

# reading
# sheet = client.open("Invoice Tracker").sheet1

# appending
