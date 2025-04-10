import os
import io
import tempfile
import shutil
from typing import Optional, Tuple
from utils.google_auth import get_google_credentials, get_drive_service

def create_drive_folder(folder_name="AutoRAG_Vectorstore"):
    """Create a folder in Google Drive to store vectorstore files.
    
    Returns:
        Tuple of (folder_id, error_message)
    """
    try:
        # Get Google credentials
        creds, error = get_google_credentials()
        if error:
            return None, error
            
        # Get Drive service
        drive_service = get_drive_service(creds)
        
        # Check if folder already exists
        response = drive_service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        if response.get('files'):
            # Folder already exists, return its ID
            return response['files'][0]['id'], None
            
        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = drive_service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id'), None
        
    except Exception as e:
        return None, f"Error creating folder in Google Drive: {str(e)}"

def upload_file_to_drive(local_path, file_name, folder_id=None, mime_type='application/octet-stream'):
    """Upload a file to Google Drive.
    
    Args:
        local_path: Path to the local file
        file_name: Name to use in Google Drive
        folder_id: Optional folder ID to upload to
        mime_type: MIME type of the file
        
    Returns:
        Tuple of (file_id, error_message)
    """
    try:
        # Get Google credentials
        creds, error = get_google_credentials()
        if error:
            return None, error
            
        # Get Drive service
        drive_service = get_drive_service(creds)
        
        # Prepare file metadata
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        # Upload file
        from googleapiclient.http import MediaFileUpload
        
        media = MediaFileUpload(
            local_path,
            mimetype=mime_type,
            resumable=True
        )
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        return file.get('id'), None
        
    except Exception as e:
        return None, f"Error uploading file to Google Drive: {str(e)}"

def download_file_from_drive(file_id, output_path):
    """Download a file from Google Drive.
    
    Args:
        file_id: ID of the file in Google Drive
        output_path: Local path to save the file
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Get Google credentials
        creds, error = get_google_credentials()
        if error:
            return False, error
            
        # Get Drive service
        drive_service = get_drive_service(creds)
        
        # Get file
        request = drive_service.files().get_media(fileId=file_id)
        
        # Download file
        from googleapiclient.http import MediaIoBaseDownload
        
        with open(output_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                
        return True, None
        
    except Exception as e:
        return False, f"Error downloading file from Google Drive: {str(e)}"

def list_vectorstore_files(folder_id=None):
    """List vectorstore files in Google Drive.
    
    Args:
        folder_id: Optional folder ID to search in
        
    Returns:
        Tuple of (files_list, error_message)
    """
    try:
        # Get Google credentials
        creds, error = get_google_credentials()
        if error:
            return None, error
            
        # Get Drive service
        drive_service = get_drive_service(creds)
        
        # Prepare query
        query = "trashed=false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
            
        # List files
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, createdTime)'
        ).execute()
        
        return response.get('files', []), None
        
    except Exception as e:
        return None, f"Error listing files in Google Drive: {str(e)}"

def save_vectorstore_to_drive(local_path, folder_name="AutoRAG_Vectorstore"):
    """Save the vectorstore from local path to Google Drive.
    
    Args:
        local_path: Path to the local vectorstore directory
        folder_name: Name of the folder in Google Drive
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Create Drive folder
        folder_id, error = create_drive_folder(folder_name)
        if error:
            return False, error
            
        # Compress vectorstore to a zip file
        import zipfile, datetime
        
        # Create a temporary zip file
        import tempfile
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_zip = tempfile.mktemp(suffix='.zip')
        
        # Check if required files exist
        index_path = os.path.join(local_path, "index.faiss")
        docstore_path = os.path.join(local_path, "index.pkl")
        
        if not os.path.exists(index_path) or not os.path.exists(docstore_path):
            return False, f"Required files not found in {local_path}. index.faiss or index.pkl missing."
        
        print(f"Creating zip file at {temp_zip} from {local_path}")
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_name in os.listdir(local_path):
                file_path = os.path.join(local_path, file_name)
                if os.path.isfile(file_path):
                    # Store directly at the root level of the zip
                    print(f"Adding {file_path} to zip as {file_name}")
                    zipf.write(file_path, file_name)
                    
        # Upload zip file to Drive
        file_id, error = upload_file_to_drive(
            temp_zip, 
            f"vectorstore_{timestamp}.zip",
            folder_id,
            'application/zip'
        )
        
        # Clean up temp file
        os.remove(temp_zip)
        
        if error:
            return False, error
            
        print(f"Successfully saved vectorstore to Google Drive folder: {folder_name}")
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error saving vectorstore to Google Drive: {str(e)}")
        traceback.print_exc()
        return False, f"Error saving vectorstore to Google Drive: {str(e)}"

def load_vectorstore_from_drive(file_id, local_path):
    """Load vectorstore from a Google Drive file.
    
    Args:
        file_id: ID of the file in Google Drive
        local_path: Local path to extract the vectorstore to
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Create a temporary zip file to download to
        import tempfile
        temp_zip = tempfile.mktemp(suffix='.zip')
        
        # Download file
        print(f"Downloading vectorstore from Google Drive to {temp_zip}")
        success, error = download_file_from_drive(file_id, temp_zip)
        if not success:
            return False, error
            
        # Create empty directory (clear existing if needed)
        import shutil
        if os.path.exists(local_path):
            print(f"Removing existing directory: {local_path}")
            shutil.rmtree(local_path)
        
        print(f"Creating directory: {local_path}")
        os.makedirs(local_path, exist_ok=True)
        
        # Extract zip file
        import zipfile
        print(f"Extracting zip to: {local_path}")
        with zipfile.ZipFile(temp_zip, 'r') as zipf:
            zipf.extractall(local_path)
            
        # Clean up temp file
        os.remove(temp_zip)
        
        # Verify index.faiss exists
        index_path = os.path.join(local_path, "index.faiss")
        print(f"Checking for index.faiss at: {index_path}")
        if not os.path.exists(index_path):
            # List contents of directory for debugging
            files_in_dir = os.listdir(local_path)
            print(f"Files in {local_path}: {files_in_dir}")
            
            # Check if index.faiss is in a subdirectory
            subdirs = [d for d in files_in_dir if os.path.isdir(os.path.join(local_path, d))]
            for subdir in subdirs:
                subdir_path = os.path.join(local_path, subdir)
                subdir_files = os.listdir(subdir_path)
                print(f"Files in {subdir_path}: {subdir_files}")
                
                # If index.faiss found in subdirectory, move files up
                if "index.faiss" in subdir_files:
                    print(f"Found index.faiss in subdirectory: {subdir_path}")
                    for file in subdir_files:
                        src = os.path.join(subdir_path, file)
                        dst = os.path.join(local_path, file)
                        print(f"Moving {src} to {dst}")
                        shutil.move(src, dst)
                    break
            
            # Check again after potential file movements
            if not os.path.exists(index_path):
                return False, f"index.faiss not found in downloaded vectorstore at {index_path}"
        
        print(f"Successfully loaded vectorstore from Google Drive to {local_path}")
        return True, None
        
    except Exception as e:
        import traceback
        print(f"Error loading vectorstore from Google Drive: {str(e)}")
        traceback.print_exc()
        return False, f"Error loading vectorstore from Google Drive: {str(e)}"

def get_latest_vectorstore_from_drive(folder_name="AutoRAG_Vectorstore", local_path="./vectorstore"):
    """Get the latest vectorstore from Google Drive.
    
    Args:
        folder_name: Name of the folder in Google Drive
        local_path: Path to the local vectorstore directory
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Create Drive folder (or get existing one)
        folder_id, error = create_drive_folder(folder_name)
        if error:
            return False, error
            
        # List files in folder
        files, error = list_vectorstore_files(folder_id)
        if error:
            return False, error
            
        # Filter only zip files
        zip_files = [f for f in files if f.get('name', '').endswith('.zip')]
        
        if not zip_files:
            return False, "No vectorstore files found in Google Drive"
            
        # Sort by creation time (newest first)
        zip_files.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
        
        # Get latest file
        latest_file = zip_files[0]
        
        # Download and extract
        return load_vectorstore_from_drive(latest_file['id'], local_path)
        
    except Exception as e:
        return False, f"Error getting latest vectorstore from Google Drive: {str(e)}" 