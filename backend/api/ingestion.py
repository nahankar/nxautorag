from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, TextLoader, WebBaseLoader
)
from langchain_community.document_loaders.sql_database import SQLDatabaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sqlalchemy import create_engine
from utils.vectorstore import get_embeddings, save_vectorstore, check_google_drive_connection
from langchain.schema import Document
from utils.google_auth import (
    get_google_credentials, 
    list_drive_files, 
    get_file_content,
    list_gmail_messages,
    get_message_content,
    list_photos
)

router = APIRouter()

# Global variables to store config and vectorstore
global_config = {}
vectorstore = None

# Pydantic models for request validation
class MySQLConfig(BaseModel):
    type: str
    host: str
    port: int
    user: str
    password: str
    database: str

class URLConfig(BaseModel):
    type: str
    url: str

class LLMConfig(BaseModel):
    llm_provider: str  # "local", "hf_free", "hf_paid", "azure"
    llm_model: str
    api_token: Optional[str] = None
    azure_endpoint: Optional[str] = None 
    azure_deployment: Optional[str] = None
    api_version: Optional[str] = "2024-05-01-preview"  # Default API version for Azure

class GoogleConfig(BaseModel):
    type: str  # 'google'
    services: List[str]  # List of services ['drive', 'gmail', 'photos']
    max_items: int = 50  # Maximum number of items to fetch from each service

class StorageConfig(BaseModel):
    type: str  # 'local' or 'google_drive'

# Handle MySQL ingestion
async def process_mysql(config: MySQLConfig):
    try:
        # Create SQLAlchemy connection string
        connection_string = f"mysql+pymysql://{config.user}:{config.password}@{config.host}:{config.port}/{config.database}"
        
        # Create engine
        engine = create_engine(connection_string)
        
        # Use SQLDatabaseLoader from LangChain
        loader = SQLDatabaseLoader(
            engine=engine,
            query="SELECT * FROM documents"
        )
        
        # Load documents
        documents = loader.load()
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MySQL ingestion error: {str(e)}")

# Handle file ingestion
async def process_files(files: List[UploadFile]):
    try:
        documents = []
        
        # Create uploads directory for permanent storage
        uploads_dir = "./uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)
        
        stored_files = []
        
        for file in files:
            # Save file to permanent storage
            upload_path = f"{uploads_dir}/{file.filename}"
            with open(upload_path, "wb") as stored_file:
                content = await file.read()
                stored_file.write(content)
                
            # Keep track of stored files
            stored_files.append({
                "filename": file.filename,
                "path": upload_path
            })
            
            # Reset file cursor for processing
            await file.seek(0)
            
            # Process for vectorstore
            file_path = f"temp/{file.filename}"
            
            # Save the uploaded file temporarily for processing
            with open(file_path, "wb") as temp_file:
                temp_file.write(await file.read())
            
            # Load based on file extension
            if file.filename.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file.filename.endswith(".docx"):
                loader = Docx2txtLoader(file_path)
            elif file.filename.endswith(".txt"):
                loader = TextLoader(file_path)
            else:
                # Clean up temp file but keep the uploaded one
                os.remove(file_path)
                continue
                
            documents.extend(loader.load())
            
            # Clean up temp file
            os.remove(file_path)
            
        return documents, stored_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File ingestion error: {str(e)}")

# Handle URL ingestion
async def process_url(config: URLConfig):
    try:
        loader = WebBaseLoader(config.url)
        documents = loader.load()
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL ingestion error: {str(e)}")

# Handle Google services ingestion
async def process_google(google_config: GoogleConfig):
    """Process Google services data."""
    import asyncio
    
    try:
        # Get Google credentials
        creds, error = get_google_credentials()
        if error:
            print(f"Error getting Google credentials: {error}")
            return []
        
        documents = []
        
        # Process Google Drive
        if 'drive' in google_config.services:
            try:
                print("Processing Google Drive...")
                # List Drive files
                files, error = list_drive_files(creds, max_files=google_config.max_items)
                if error:
                    print(f"Error listing Drive files: {error}")
                else:
                    # Log all files found for debugging
                    print("All files found in Google Drive:")
                    for i, file in enumerate(files):
                        print(f"  {i+1}. {file.get('name', 'Unknown')} - Type: {file.get('mimeType', 'Unknown')} - ID: {file.get('id', 'Unknown')}")
                    
                    # Filter to only keep PDF files
                    pdf_files = [file for file in files if 
                                file.get('mimeType') == 'application/pdf' or 
                                file.get('name', '').lower().endswith('.pdf')]
                    
                    print(f"Found {len(pdf_files)} PDF files out of {len(files)} total files in Google Drive")
                    
                    # Process each file
                    for file in pdf_files:
                        try:
                            file_id = file.get('id')
                            mime_type = file.get('mimeType')
                            file_name = file.get('name', 'Unknown file')
                            
                            # Skip folders
                            if mime_type == 'application/vnd.google-apps.folder':
                                continue
                                
                            # Get file content
                            content, error = get_file_content(creds, file_id, mime_type)
                            if error:
                                print(f"Error getting content for file {file_name}: {error}")
                                continue
                                
                            if content:
                                # Create document
                                doc = Document(
                                    page_content=content,
                                    metadata={
                                        "source": file_name,
                                        "file_id": file_id,
                                        "mime_type": mime_type
                                    }
                                )
                                documents.append(doc)
                                print(f"Added document: {file_name}")
                        except Exception as file_error:
                            print(f"Error processing file {file.get('name', 'Unknown')}: {str(file_error)}")
                            continue
            except Exception as drive_error:
                print(f"Error processing Google Drive files: {str(drive_error)}")
                
        # Process Gmail messages (simplified)
        if 'gmail' in google_config.services:
            # Implementation here...
            pass
            
        # Process Google Photos (simplified)
        if 'photos' in google_config.services:
            # Implementation here...
            pass
            
        return documents
    except Exception as e:
        print(f"Error processing Google services: {str(e)}")
        return []

@router.post("/ingest")
async def ingest(
    config: Optional[str] = Form(None),
    file_metadata: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    """Process and ingest data from various sources."""
    global vectorstore
    global global_config
    
    try:
        # Parse configuration JSON if provided
        config_data = {}
        if config:
            config_data = json.loads(config)
            
        # Save config for global use (e.g., by retrieval)
        global_config = config_data
        
        # Save config to file for persistence
        os.makedirs("./configs", exist_ok=True)
        with open("./configs/latest.json", "w") as f:
            json.dump(config_data, f)
        
        # Get embeddings model
        embeddings = get_embeddings()
        if not embeddings:
            raise HTTPException(status_code=500, detail="Failed to initialize embeddings model")
        
        # Initialize document list
        all_documents = []
        stored_files = []
        
        # Get storage configuration
        storage_config = config_data.get("storage_config", {"type": "local"})
        storage_type = storage_config.get("type", "local")
        
        # Check if Google Drive is selected and verify connection
        if storage_type == "google_drive":
            is_connected, message = check_google_drive_connection()
            if not is_connected:
                raise HTTPException(status_code=400, detail=f"Google Drive connection error: {message}")
        
        # Process different data sources
        data_sources = []
        
        # Process files if provided
        if files:
            file_docs, stored_file_info = await process_files(files)
            all_documents.extend(file_docs)
            stored_files.extend(stored_file_info)
            
            # Add file source to data sources list
            data_sources.append({
                "type": "files",
                "count": len(file_docs),
                "files": [f.filename for f in files]
            })
        
        # Process other sources from config
        if config_data:
            # MySQL
            mysql_config = config_data.get("mysql_config")
            if mysql_config:
                mysql_docs = await process_mysql(MySQLConfig(**mysql_config))
                all_documents.extend(mysql_docs)
                
                data_sources.append({
                    "type": "mysql",
                    "count": len(mysql_docs),
                    "database": mysql_config.get("database")
                })
            
            # URL
            url_config = config_data.get("url_config")
            if url_config:
                url_docs = await process_url(URLConfig(**url_config))
                all_documents.extend(url_docs)
                
                data_sources.append({
                    "type": "url",
                    "count": len(url_docs),
                    "url": url_config.get("url")
                })
                
            # Google services
            google_config = config_data.get("google_config")
            if google_config:
                google_docs = await process_google(GoogleConfig(**google_config))
                all_documents.extend(google_docs)
                
                data_sources.append({
                    "type": "google",
                    "count": len(google_docs),
                    "services": google_config.get("services", [])
                })
        
        # Check if we have any documents
        if not all_documents and config_data.get("sourceType") != "llm":
            raise HTTPException(status_code=400, detail="No valid documents found in the ingested data")
            
        # If sourceType is llm, skip the document processing part
        if config_data.get("sourceType") != "llm":
            # Text splitting for better chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            
            # Split documents into chunks
            split_documents = text_splitter.split_documents(all_documents)
            
            # Create or update vectorstore
            if vectorstore is None:
                # Create new vectorstore
                vectorstore = FAISS.from_documents(split_documents, embeddings)
            else:
                # Add documents to existing vectorstore
                vectorstore.add_documents(split_documents)
            
            # Save vectorstore
            save_result = save_vectorstore(vectorstore, storage_type=storage_type)
            if not save_result:
                raise HTTPException(status_code=500, detail="Failed to save vectorstore")
        
        # Process LLM configuration if provided
        llm_config = config_data.get("llm_config")
        
        # Return success with stats
        if config_data.get("sourceType") == "llm":
            return {
                "status": "success",
                "message": "LLM settings saved successfully"
            }
        else:
            return {
                "status": "success",
                "document_count": len(all_documents),
                "chunk_count": len(split_documents),
                "data_sources": data_sources,
                "stored_files": stored_files,
                "vector_store": "saved successfully",
                "storage_type": storage_type
            }
    
    except Exception as e:
        print(f"Error in ingestion: {str(e)}")
        # Print full traceback for debugging
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

@router.get("/get-latest-config")
async def get_latest_config():
    """Get the latest config used for ingestion."""
    try:
        # Check if config file exists
        if os.path.exists("./configs/latest.json"):
            with open("./configs/latest.json", "r") as f:
                config = json.load(f)
                
            # Check Google Drive connectivity
            storage_config = config.get("storage_config", {"type": "local"})
            storage_type = storage_config.get("type", "local")
            
            google_drive_status = {"connected": False, "message": "Not used"}
            if storage_type == "google_drive":
                connected, message = check_google_drive_connection()
                google_drive_status = {
                    "connected": connected,
                    "message": message
                }
            
            return {
                "status": "success",
                "config": config,
                "google_drive_status": google_drive_status
            }
        else:
            return {
                "status": "error",
                "message": "No configuration found",
                "google_drive_status": {"connected": False, "message": "No configuration found"}
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading configuration: {str(e)}",
            "google_drive_status": {"connected": False, "message": f"Error: {str(e)}"}
        }

@router.get("/storage-options")
async def get_storage_options():
    """Get available storage options and their status."""
    try:
        options = [
            {
                "id": "local",
                "name": "Local Storage",
                "description": "Store vectorstore on the local server",
                "available": True
            }
        ]
        
        # Check Google Drive availability
        google_drive_available, message = check_google_drive_connection()
        
        options.append({
            "id": "google_drive",
            "name": "Google Drive",
            "description": "Store vectorstore in your Google Drive account",
            "available": google_drive_available,
            "message": message
        })
        
        return {
            "status": "success",
            "options": options
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting storage options: {str(e)}"
        }

@router.post("/save-llm-settings")
async def save_llm_settings(request: Dict[str, Any]):
    """Save only LLM settings without requiring document ingestion."""
    try:
        # Extract the LLM config
        llm_config = request.get("llm_config")
        if not llm_config:
            raise HTTPException(status_code=400, detail="No LLM configuration provided")
        
        # Get existing config or create new one
        config_data = {}
        if os.path.exists("./configs/latest.json"):
            try:
                with open("./configs/latest.json", "r") as f:
                    config_data = json.load(f)
            except:
                pass
        
        # Update only the LLM config part
        config_data["llm_config"] = llm_config
        config_data["sourceType"] = "llm"
        
        # Include storage config if provided
        if "storage_config" in request:
            config_data["storage_config"] = request["storage_config"]
            
        # Save config to file for persistence
        os.makedirs("./configs", exist_ok=True)
        with open("./configs/latest.json", "w") as f:
            json.dump(config_data, f)
            
        # Recreate the RAG chain to use the new LLM settings
        from api.retrieval import recreate_rag_chain
        recreate_rag_chain()
        
        return {
            "status": "success",
            "message": "LLM settings saved successfully"
        }
    
    except Exception as e:
        print(f"Error saving LLM settings: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=f"Error saving LLM settings: {str(e)}") 