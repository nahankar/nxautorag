import os
import json
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import FakeEmbeddings

# Add import for our Azure client
try:
    from utils.azure_openai_client import get_azure_embeddings
except ImportError:
    get_azure_embeddings = None

# Add import for Google Drive storage
try:
    from utils.google_drive_storage import (
        save_vectorstore_to_drive, 
        get_latest_vectorstore_from_drive,
        create_drive_folder
    )
except ImportError:
    save_vectorstore_to_drive = None
    get_latest_vectorstore_from_drive = None
    create_drive_folder = None

# Default embedding model
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def get_embeddings():
    """Get an embeddings model that works with the current setup"""
    # First try to load config from file if it exists
    try:
        if os.path.exists("./configs/latest.json"):
            with open("./configs/latest.json", "r") as f:
                config = json.loads(f.read())
                llm_config = config.get("llm_config", {})
                # If we have an API token, prefer using that provider's embeddings
                if llm_config.get("api_token") and llm_config.get("llm_provider") == "azure" and get_azure_embeddings:
                    # Use our Azure embeddings function
                    print("Attempting to use Azure embeddings...")
                    azure_embeddings = get_azure_embeddings()
                    if azure_embeddings:
                        print("Successfully created Azure embeddings")
                        return azure_embeddings
                    else:
                        print("Failed to create Azure embeddings, falling back to HuggingFace")
    except Exception as e:
        print(f"Error loading config for embeddings: {e}")
        
    # Try HuggingFace embeddings as the primary option
    try:
        print(f"Using HuggingFace embeddings with model {DEFAULT_EMBEDDING_MODEL}")
        return HuggingFaceEmbeddings(model_name=DEFAULT_EMBEDDING_MODEL)
    except Exception as e:
        print(f"Error loading HuggingFace embeddings: {e}")
        
    # Try using OpenAI embeddings as fallback if configured in environment
    try:
        return OpenAIEmbeddings(model="text-embedding-ada-002")
    except Exception as e:
        print(f"Error loading OpenAI embeddings: {e}")
    
    # Final fallback to fake embeddings for development
    print("Using fake embeddings for development. For production, configure a real embeddings model.")
    return FakeEmbeddings(size=384)  # 384 is typical for small models

def save_vectorstore(vectorstore, path="./vectorstore", storage_type="local", keep_local_copy=False):
    """Save the vectorstore to disk or Google Drive
    
    Args:
        vectorstore: The vectorstore to save
        path: Path for local storage
        storage_type: 'local' or 'google_drive'
        keep_local_copy: If False and using Google Drive, will delete local copy after upload
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # First save locally - always required because Google Drive upload needs local files
        vectorstore.save_local(path)
        print(f"Vectorstore saved successfully to local path: {path}")
        
        # Save embedding info for reference
        if hasattr(vectorstore, "_embedding_function") and hasattr(vectorstore._embedding_function, "_llm_type"):
            print(f"Saved with embedding type: {vectorstore._embedding_function._llm_type}")
        
        # If Google Drive is specified, upload to Drive
        if storage_type == "google_drive" and save_vectorstore_to_drive:
            print("Uploading vectorstore to Google Drive...")
            success, error = save_vectorstore_to_drive(path)
            if not success:
                print(f"Error saving to Google Drive: {error}")
                print("Note: Local vectorstore was still created as a temporary storage for Google Drive upload.")
                return False
            else:
                print("Vectorstore successfully uploaded to Google Drive")
                
                # Delete local copy if requested
                if not keep_local_copy:
                    try:
                        import shutil
                        print(f"Deleting local vectorstore copy at {path}...")
                        if os.path.exists(path):
                            shutil.rmtree(path)
                            print("Local vectorstore copy deleted successfully.")
                    except Exception as delete_error:
                        print(f"Warning: Failed to delete local vectorstore: {delete_error}")
                else:
                    print("Keeping local vectorstore copy as backup.")
        
        return True
    except Exception as e:
        print(f"Error saving vectorstore: {e}")
        return False

def load_vectorstore(path="./vectorstore", storage_type="local"):
    """Load the vectorstore from disk or Google Drive
    
    Args:
        path: Path for local storage
        storage_type: 'local' or 'google_drive'
    
    Returns:
        The loaded vectorstore or a new empty one
    """
    try:
        # If Google Drive is specified, download latest from Drive
        if storage_type == "google_drive" and get_latest_vectorstore_from_drive:
            print("Attempting to load vectorstore from Google Drive...")
            success, error = get_latest_vectorstore_from_drive(local_path=path)
            if not success:
                print(f"Error loading from Google Drive: {error}")
                if not os.path.exists(path):
                    print("Local vectorstore doesn't exist. Creating a new one.")
                    return create_empty_vectorstore()
                # Fall back to local if it exists
                print("Falling back to local vectorstore if it exists")
            else:
                print("Successfully loaded vectorstore from Google Drive")
        
        # Check if local vectorstore exists
        if not os.path.exists(path):
            print(f"Vectorstore path {path} does not exist. Creating a new vectorstore.")
            return create_empty_vectorstore()
        
        if not os.path.exists(os.path.join(path, "index.faiss")):
            print(f"FAISS index file not found at {path}/index.faiss. Creating a new vectorstore.")
            return create_empty_vectorstore()
            
        # Load from local path
        embeddings = get_embeddings()
        return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"Error loading vectorstore: {e}")
        print("Creating a new empty vectorstore instead.")
        return create_empty_vectorstore()

def create_empty_vectorstore():
    """Create an empty vectorstore"""
    try:
        embeddings = get_embeddings()
        print(f"Creating empty vectorstore with embedding type: {type(embeddings).__name__}")
        return FAISS.from_texts(["This is a placeholder document."], embeddings) 
    except Exception as e:
        print(f"Error creating empty vectorstore: {e}")
        # Last resort fallback to fake embeddings
        print("Using fake embeddings as last resort")
        return FAISS.from_texts(["This is a placeholder document."], FakeEmbeddings(size=384)) 

def check_google_drive_connection():
    """Check if Google Drive is properly connected and authorized.
    
    Returns:
        (is_connected, message)
    """
    if not create_drive_folder:
        return False, "Google Drive storage module not available"
        
    try:
        folder_id, error = create_drive_folder()
        if error:
            return False, f"Error connecting to Google Drive: {error}"
        return True, "Successfully connected to Google Drive"
    except Exception as e:
        return False, f"Error checking Google Drive connection: {str(e)}" 