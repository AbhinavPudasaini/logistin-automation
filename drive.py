import os.path
import io
from typing import Optional, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive"]

# ============================================
# CREDENTIAL MANAGEMENT (DRY Principle)
# ============================================

def get_service():
    """
    Get or create Google Drive service.
    Single responsibility: credential handling & service creation.
    
    Returns:
        Google Drive service object
        
    Raises:
        FileNotFoundError: If token.json doesn't exist
    """
    if not os.path.exists("token1.json"):

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    else:
        creds = Credentials.from_authorized_user_file("token1.json", SCOPES)
    
    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build("drive", "v3", credentials=creds)


def main():
  """Shows basic usage of the Drive v3 API.
  Prints the names and ids of the first 10 files the user has access to.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("drive", "v3", credentials=creds)

    # Call the Drive v3 API
    results = (
        service.files()
        .list(pageSize=10, fields="nextPageToken, files(id, name)")
        .execute()
    )
    items = results.get("files", [])

    if not items:
      print("No files found.")
      return
    print("Files:")
    for item in items:
      print(f"{item['name']} ({item['id']})")
  except HttpError as error:
    # TODO(developer) - Handle errors from drive API.
    print(f"An error occurred: {error}")



def find_all_files(page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve all files from Google Drive.
    
    Args:
        page_size: Number of results per page (default 20)
        
    Returns:
        List of file dictionaries with id, name, mimeType
    """
    try:
        service = get_service()
        files = service.files().list(
            pageSize=page_size,
            orderBy="modifiedTime desc",
            fields="files(id, name, mimeType)"
        ).execute().get('files', [])
        return files
    except HttpError as error:
        print(f"❌ Error retrieving files: {error}")
        return []

def find_file_by_content(content: str, page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Search for files by content in Google Drive.
    Uses fullText search - searches document contents.
    
    Args:
        content: Content/text to search for
        page_size: Number of results per page (default 20)
        
    Returns:
        List of matching file dictionaries
    """
    try:
        service = get_service()
        files = service.files().list(
            q=f"fullText contains '{content}'",
            orderBy="modifiedTime desc",
            pageSize=page_size,
            fields="files(id, name, mimeType)"
        ).execute().get('files', [])
        return files
    except HttpError as error:
        print(f"❌ Error searching by content: {error}")
        return []
  

def find_file_by_name(file_name: str, page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Search for files by name in Google Drive.
    
    Args:
        file_name: Partial or full file name to search for
        page_size: Number of results per page (default 20)
        
    Returns:
        List of matching file dictionaries
    """
    try:
        service = get_service()
        files = service.files().list(
            q=f"name contains '{file_name}'",
            orderBy="modifiedTime desc",
            pageSize=page_size,
            fields="files(id, name, mimeType)"
        ).execute().get('files', [])
        return files
    except HttpError as error:
        print(f"❌ Error searching by name: {error}")
        return []

def find_files_by_type(mime_type: str, page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Search for files by MIME type.
    
    Args:
        mime_type: MIME type to filter by (e.g., 'application/pdf', 'image/png', 'image/*')
        page_size: Number of results per page (default 20)
        
    Returns:
        List of matching file dictionaries
        
    Examples:
        find_files_by_type('application/pdf')      # All PDFs
        find_files_by_type('image/*')               # All images
        find_files_by_type('application/vnd.google-apps.document')  # Google Docs
    """
    try:
        service = get_service()
        # Use exact MIME type matching
        query = f"mimeType='{mime_type}'" if '*' not in mime_type else f"mimeType contains '{mime_type.replace('/*', '')}'"
        
        files = service.files().list(
            q=query,
            pageSize=page_size,
            orderBy="modifiedTime desc",
            fields="files(id, name, mimeType)"
        ).execute().get('files', [])
        return files
    except HttpError as error:
        print(f"❌ Error searching by type: {error}")
        return []


def find_images(page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Convenience function to find all images.
    
    Args:
        page_size: Number of results per page (default 20)
        
    Returns:
        List of image file dictionaries
    """
    return find_files_by_type('image/*', page_size)

# ============================================
# DOWNLOAD FUNCTIONALITY
# ============================================

def download_file(file_id: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Download a file from Google Drive.
    Handles both regular files and Google Docs (exports to PDF/CSV).
    
    Args:
        file_id: Google Drive file ID
        output_path: Optional custom output path. If None, uses original filename.
        
    Returns:
        Path to downloaded file, or None if download failed
        
    Raises:
        HttpError: If file metadata cannot be retrieved
    """
    try:
        service = get_service()
        
        # Get file metadata
        meta = service.files().get(
            fileId=file_id,
            fields="name, mimeType"
        ).execute()

        name = meta.get("name", "downloaded_file")
        mime = meta.get("mimeType", "")

        # Handle Google Docs (export to standard formats)
        if mime.startswith("application/vnd.google-apps"):
            export_map = {
                "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
                "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
                "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
            }

            export_mime, ext = export_map.get(mime, ("application/pdf", ".pdf"))
            request = service.files().export_media(
                fileId=file_id,
                mimeType=export_mime
            )
            filename = output_path or (name + ext)
        else:
            # Regular file download
            request = service.files().get_media(fileId=file_id)
            filename = output_path or name

        # Download in chunks
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"⬇️ Download progress: {int(status.progress() * 100)}%")

        # Write to file
        with open(filename, "wb") as f:
            f.write(fh.getvalue())

        print(f"✅ File downloaded: {filename}")
        return filename
        
    except HttpError as error:
        print(f"❌ Download error: {error}")
        return None
    except Exception as error:
        print(f"❌ Unexpected error during download: {error}")
        return None
