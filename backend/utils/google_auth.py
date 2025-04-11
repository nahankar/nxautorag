import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv
import io
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Define scopes needed for different Google services
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/photoslibrary.readonly'
]

# Google OAuth client configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8000/google/oauth-callback"]
    }
}

def create_authorization_url() -> Tuple[str, str]:
    """Create Google OAuth authorization URL.
    
    Returns:
        Tuple containing (auth_url, state)
    """
    # Create flow instance
    flow = Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=SCOPES
    )
    
    # Set the redirect URI
    flow.redirect_uri = CLIENT_CONFIG["web"]["redirect_uris"][0]
    
    # Generate URL for authorization
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force to show consent screen to get refresh_token
    )
    
    return authorization_url, state

def exchange_code_for_token(code: str, state: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Exchange authorization code for tokens.
    
    Args:
        code: Authorization code from Google
        state: State from authorization
        
    Returns:
        Tuple of (credentials_dict, error_message)
    """
    try:
        # Create flow instance
        flow = Flow.from_client_config(
            client_config=CLIENT_CONFIG,
            scopes=SCOPES,
            state=state
        )
        
        # Set the redirect URI
        flow.redirect_uri = CLIENT_CONFIG["web"]["redirect_uris"][0]
        
        # Exchange authorization code for tokens
        flow.fetch_token(code=code)
        
        # Get credentials
        credentials = flow.credentials
        
        # Save credentials to file
        token_path = "./configs/google_token.json"
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        
        with open(token_path, "w") as token_file:
            token_json = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes
            }
            json.dump(token_json, token_file)
        
        return token_json, None
        
    except Exception as e:
        return None, f"Error exchanging code: {str(e)}"

def get_google_credentials() -> Tuple[Optional[Credentials], Optional[str]]:
    """Get or refresh Google credentials.
    
    Returns:
        Tuple of (credentials, error_message)
    """
    creds = None
    token_path = "./configs/google_token.json"
    
    # Check if token file exists
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as token:
                token_data = json.load(token)
                creds = Credentials(
                    token=token_data.get("token"),
                    refresh_token=token_data.get("refresh_token"),
                    token_uri=token_data.get("token_uri"),
                    client_id=CLIENT_CONFIG["web"]["client_id"],
                    client_secret=CLIENT_CONFIG["web"]["client_secret"],
                    scopes=token_data.get("scopes")
                )
        except Exception as e:
            return None, f"Error loading credentials: {str(e)}"
    
    # If no valid credentials or if they're expired, we need to get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                
                # Update token file with refreshed credentials
                with open(token_path, 'w') as token:
                    token_json = {
                        "token": creds.token,
                        "refresh_token": creds.refresh_token,
                        "token_uri": creds.token_uri,
                        "client_id": creds.client_id,
                        "client_secret": creds.client_secret,
                        "scopes": creds.scopes
                    }
                    json.dump(token_json, token)
                    
            except Exception as e:
                return None, f"Error refreshing credentials: {str(e)}"
        else:
            return None, "No valid credentials. Please authenticate with Google."
    
    return creds, None

def get_drive_service(creds):
    """Build and return Google Drive service."""
    return build('drive', 'v3', credentials=creds)

def get_gmail_service(creds):
    """Build and return Gmail service."""
    return build('gmail', 'v1', credentials=creds)

def get_photos_service(creds):
    """Build and return Google Photos service."""
    return build('photoslibrary', 'v1', credentials=creds)

def list_drive_files(creds, max_files=50):
    """List files from Google Drive."""
    try:
        service = get_drive_service(creds)
        
        # First get all files at the root level
        results = service.files().list(
            pageSize=max_files,
            fields="nextPageToken, files(id, name, mimeType, description)"
        ).execute()
        
        files = results.get('files', [])
        
        # Identify folders
        folders = [file for file in files if file.get('mimeType') == 'application/vnd.google-apps.folder']
        
        # Recursively search inside each folder
        for folder in folders:
            folder_id = folder.get('id')
            folder_name = folder.get('name')
            print(f"Searching inside folder: {folder_name}")
            
            # Get files inside this folder
            folder_results = service.files().list(
                pageSize=max_files,
                q=f"'{folder_id}' in parents",
                fields="files(id, name, mimeType, description)"
            ).execute()
            
            folder_files = folder_results.get('files', [])
            
            # Add folder path to file names for clarity
            for file in folder_files:
                file['name'] = f"{folder_name}/{file['name']}"
            
            # Add these files to our results
            files.extend(folder_files)
            
            # Limit to max_files to avoid excessive recursion
            if len(files) >= max_files:
                break
                
        return files, None
    except Exception as e:
        return None, str(e)

def get_file_content(creds, file_id, mime_type):
    """Get file content from Google Drive."""
    try:
        # Create Drive service
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Handle Google Docs formats specially
        if mime_type.startswith('application/vnd.google-apps'):
            if mime_type == 'application/vnd.google-apps.document':
                # Google Doc
                docs_service = build('docs', 'v1', credentials=creds)
                doc = docs_service.documents().get(documentId=file_id).execute()
                text_content = ''
                for content in doc.get('body', {}).get('content', []):
                    if 'paragraph' in content:
                        for element in content['paragraph'].get('elements', []):
                            if 'textRun' in element:
                                text_content += element['textRun'].get('content', '')
                return text_content, None
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                # Google Sheet
                sheets_service = build('sheets', 'v4', credentials=creds)
                sheet = sheets_service.spreadsheets().get(spreadsheetId=file_id).execute()
                sheet_data = sheets_service.spreadsheets().values().get(
                    spreadsheetId=file_id,
                    range=sheet['sheets'][0]['properties']['title']
                ).execute()
                
                # Format as text
                text_content = ''
                if 'values' in sheet_data:
                    for row in sheet_data['values']:
                        text_content += ' | '.join([str(cell) for cell in row]) + '\n'
                return text_content, None
            else:
                # Export as text for other Google formats
                response = drive_service.files().export(
                    fileId=file_id,
                    mimeType='text/plain'
                ).execute()
                return response.decode('utf-8'), None
        else:
            # Handle normal files
            request = drive_service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            # Handle Excel files
            if mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                             'application/vnd.ms-excel',
                             'application/vnd.google-apps.spreadsheet']:
                try:
                    # Read into pandas and process completely differently to get meaningful content
                    excel_data = pd.read_excel(io.BytesIO(file_content), sheet_name=None)
                    
                    # More comprehensive extraction approach for Excel
                    processed_content = []
                    for sheet_name, df in excel_data.items():
                        # Add sheet name as heading
                        processed_content.append(f"--- Sheet: {sheet_name} ---")
                        
                        # If DataFrame is empty or has no data, note this
                        if df.empty or df.shape[0] == 0:
                            processed_content.append(f"Sheet '{sheet_name}' is empty.")
                            continue
                            
                        # Try to determine if there's a header row to use as column structure
                        # Get full values for each row with column names
                        for idx, row in df.iterrows():
                            # Limit to first 20 rows per sheet to avoid overwhelming context
                            if idx >= 20:
                                processed_content.append(f"... and {df.shape[0] - 20} more rows")
                                break
                                
                            # Build a meaningful row representation with column names
                            row_data = []
                            for col, val in row.items():
                                if pd.notna(val) and str(val).strip():  # Check if value exists and isn't just whitespace
                                    row_data.append(f"{col}: {val}")
                                    
                            if row_data:  # Only include rows that have actual data
                                processed_content.append(f"Row {idx+1}: " + " | ".join(row_data))
                    
                    # Concatenate processed content with proper structure
                    document_content = "\n".join(processed_content)
                    
                    return document_content, None
                except Exception as e:
                    print(f"Error processing Excel file: {e}")
                    # Fall back to more basic extraction if pandas processing fails
                    return "Error: Could not process Excel file content properly.", None
            
            # Handle PDF files properly
            elif mime_type == 'application/pdf':
                try:
                    print(f"Processing PDF file with size {len(file_content)} bytes")
                    
                    # First attempt: Use PyPDFLoader
                    try:
                        # Save PDF content to a temporary file
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                            temp_pdf.write(file_content)
                            temp_path = temp_pdf.name
                        
                        # Use PyPDFLoader to extract text properly
                        from langchain_community.document_loaders import PyPDFLoader
                        loader = PyPDFLoader(temp_path)
                        pages = loader.load()
                        
                        # Combine all page contents
                        pdf_text = "\n\n".join([page.page_content for page in pages])
                        
                        # Clean up temp file
                        import os
                        os.unlink(temp_path)
                        
                        print(f"Extracted {len(pdf_text)} characters from PDF using PyPDFLoader")
                        return pdf_text, None
                    except Exception as pdfloader_error:
                        print(f"PyPDFLoader failed: {pdfloader_error}, trying fallback method...")
                        
                        # Second attempt: Use PyPDF2 directly
                        try:
                            import io
                            import PyPDF2
                            
                            pdf_content = ""
                            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                            
                            # Extract text from each page
                            for page_num in range(len(pdf_reader.pages)):
                                page = pdf_reader.pages[page_num]
                                pdf_content += page.extract_text() + "\n\n"
                                
                            print(f"Extracted {len(pdf_content)} characters from PDF using PyPDF2 directly")
                            return pdf_content, None
                        except Exception as pypdf_error:
                            print(f"PyPDF2 direct extraction failed: {pypdf_error}")
                            # Continue to the fallback below
                    
                except Exception as e:
                    print(f"All PDF extraction methods failed: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Return a clear error message that will be visible in the context
                    return "Error: Could not extract text from PDF file. Please check that the file is a valid PDF and not password-protected.", None
            
            # Handle text-based files
            elif mime_type.startswith('text/') or \
                 mime_type == 'application/json' or \
                 mime_type == 'application/xml' or \
                 mime_type.endswith('+xml') or \
                 mime_type.endswith('+json'):
                try:
                    return file_content.decode('utf-8'), None
                except UnicodeDecodeError:
                    return "[Binary file: Unable to decode as text]", None
            else:
                # Return placeholder for binary files
                return f"[Binary file of type {mime_type}]", None
    except Exception as e:
        return None, str(e)

def list_gmail_messages(creds, max_messages=50):
    """List recent messages from Gmail."""
    try:
        service = get_gmail_service(creds)
        results = service.users().messages().list(userId='me', maxResults=max_messages).execute()
        return results.get('messages', []), None
    except Exception as e:
        return None, str(e)

def get_message_content(creds, message_id):
    """Get content of a specific Gmail message."""
    try:
        service = get_gmail_service(creds)
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        return message, None
    except Exception as e:
        return None, str(e)

def list_photos(creds, max_photos=50):
    """List recent photos from Google Photos."""
    try:
        service = get_photos_service(creds)
        results = service.mediaItems().list(pageSize=max_photos).execute()
        return results.get('mediaItems', []), None
    except Exception as e:
        return None, str(e)

def revoke_token():
    """Revoke the stored Google token."""
    if os.path.exists("google_token.json"):
        try:
            os.remove("google_token.json")
            return {"status": "success", "message": "Google token revoked successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to revoke token: {str(e)}"}
    else:
        return {"status": "success", "message": "No token to revoke"}

def test_connection():
    """Test connection to Google services."""
    try:
        # Get credentials
        creds, error = get_google_credentials()
        if error:
            return {"status": "error", "message": error, "authenticated": False}
        
        if not creds:
            return {"status": "error", "message": "Not authenticated with Google", "authenticated": False}
        
        # Test Drive API
        files, error = list_drive_files(creds, max_files=1)
        if error:
            return {"status": "error", "message": f"Error connecting to Google Drive: {error}", "authenticated": True}
        
        return {
            "status": "success", 
            "message": "Successfully connected to Google services",
            "authenticated": True,
            "file_count": len(files)
        }
    
    except Exception as e:
        return {"status": "error", "message": f"Failed to test connection: {str(e)}", "authenticated": False}

def check_auth_status():
    """Check Google authentication status.
    
    Returns:
        Dict with auth status information
    """
    try:
        # Get credentials
        creds, error = get_google_credentials()
        is_authenticated = creds is not None and creds.valid
        
        if error:
            return {
                "is_authenticated": False,
                "message": error
            }
        
        if is_authenticated:
            return {
                "is_authenticated": True,
                "message": "Authenticated with Google"
            }
        else:
            return {
                "is_authenticated": False,
                "message": "Not authenticated with Google"
            }
            
    except Exception as e:
        return {
            "is_authenticated": False,
            "message": f"Error checking authentication status: {str(e)}"
        } 