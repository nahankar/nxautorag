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
from utils.vectorstore import get_embeddings
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
                    pdf_files = [file for file in files if file.get('mimeType') == 'application/pdf' or 
                                               (file.get('name', '').lower().endswith('.pdf'))]
                    
                    print(f"Found {len(pdf_files)} PDF files out of {len(files)} total files in Google Drive")
                    
                    # Process each file
                    for file in pdf_files:
                        try:
                            file_id = file.get('id')
                            mime_type = file.get('mimeType')
                            file_name = file.get('name', 'Unknown file')
                            
                            # Skip folders and unsupported formats
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
                                        "type": "google_drive",
                                        "mime_type": mime_type
                                    }
                                )
                                documents.append(doc)
                                print(f"Added document: {file_name}")
                        except Exception as e:
                            print(f"Error processing Drive file {file.get('name', 'unknown')}: {str(e)}")
            except Exception as e:
                print(f"Error processing Google Drive: {str(e)}")
        
        # Process Gmail messages
        if 'gmail' in google_config.services:
            try:
                print("Processing Gmail messages...")
                messages, error = list_gmail_messages(creds, max_messages=google_config.max_items)
                if error:
                    print(f"Error listing Gmail messages: {error}")
                
                # Process is skipped for now - Gmail not needed for PDF-only processing
                
            except Exception as e:
                print(f"Error processing Gmail: {str(e)}")
        
        # Process Photos (metadata only, not actual images)
        if 'photos' in google_config.services:
            try:
                print("Processing Google Photos...")
                photos, error = list_photos(creds, max_photos=google_config.max_items)
                if error:
                    print(f"Error listing Photos: {error}")
                
                # Process is skipped for now - Photos not needed for PDF-only processing
                
            except Exception as e:
                print(f"Error processing Google Photos: {str(e)}")
        
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google services ingestion error: {str(e)}")

# Ingestion endpoint
@router.post("/ingest")
async def ingest(
    config: Optional[str] = Form(None),
    file_metadata: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    global global_config, vectorstore
    
    try:
        # Process config
        saved_config = {}
        if config:
            config_data = json.loads(config)
            saved_config = config_data
            
            # Extract LLM config
            if "llm_config" in config_data:
                llm_data = config_data["llm_config"]
                
                # Clean up token if present by stripping any whitespace
                if llm_data.get("api_token"):
                    llm_data["api_token"] = llm_data["api_token"].strip()
                    # Update the cleaned token in the config
                    config_data["llm_config"]["api_token"] = llm_data["api_token"]
                    saved_config = config_data
                
                # Save LLM config globally
                global_config = {
                    "provider": llm_data.get("llm_provider"),
                    "model": llm_data.get("llm_model"),
                    "token": llm_data.get("api_token"),
                    "azure_endpoint": llm_data.get("azure_endpoint"),
                    "azure_deployment": llm_data.get("azure_deployment"),
                    "api_version": llm_data.get("api_version", "2024-05-01-preview")
                }
        
        # Collect documents from different sources
        documents = []
        stored_files_info = []
        
        # Process based on source type
        source_type = saved_config.get("sourceType", "")
        
        # Process MySQL config if provided
        if source_type == "mysql" and "mysql_config" in saved_config:
            mysql_data = saved_config["mysql_config"]
            mysql = MySQLConfig(**mysql_data)
            documents.extend(await process_mysql(mysql))
        
        # Process URL config if provided
        if source_type == "url" and "url_config" in saved_config:
            url_data = saved_config["url_config"]
            url = URLConfig(**url_data)
            documents.extend(await process_url(url))
        
        # Process files if provided
        if source_type == "file" and files:
            # Clear previous uploads directory to ensure we don't mix old data
            if os.path.exists("./uploads"):
                import shutil
                shutil.rmtree("./uploads")
            
            # Also clear previous vectorstore if it exists
            if os.path.exists("./vectorstore"):
                import shutil
                shutil.rmtree("./vectorstore")
            
            file_results = await process_files(files)
            documents.extend(file_results[0])
            stored_files_info = file_results[1]
            
            # Add file info to config
            saved_config["stored_files"] = stored_files_info
        
        # Process Google services if provided
        if source_type == "google" and "google_config" in saved_config:
            google_data = saved_config["google_config"]
            google_config = GoogleConfig(**google_data)
            documents.extend(await process_google(google_config))
        
        # Save the complete configuration to a JSON file
        config_dir = "./configs"
        os.makedirs(config_dir, exist_ok=True)
        
        # Save the updated config with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_path = f"{config_dir}/config_{timestamp}.json"
        
        # Also save as latest.json for quick access
        latest_path = f"{config_dir}/latest.json"
        
        # Write to both files
        with open(config_path, "w") as f:
            json.dump(saved_config, f, indent=2)
            
        with open(latest_path, "w") as f:
            json.dump(saved_config, f, indent=2)
        
        # If no documents were processed, return error
        if not documents:
            return {"status": "Config saved", "message": "No documents were processed for ingestion"}
        
        # Chunk the documents with larger size
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        
        # Log chunk information
        print(f"Created {len(chunks)} chunks from {len(documents)} documents")
        print(f"Average chunk size: {sum(len(c.page_content) for c in chunks) / len(chunks) if chunks else 0} characters")
        
        # Create embeddings
        embeddings = get_embeddings()
        
        # Create vector store
        vectorstore = FAISS.from_documents(chunks, embeddings)
        
        # Save vector store to disk
        vectorstore.save_local("./vectorstore")
        
        # Force recreate the RAG chain since vectorstore has changed
        from api.retrieval import recreate_rag_chain
        recreate_rag_chain()
        
        return {
            "status": "success", 
            "message": "File(s) ingested successfully",
            "config_saved": True,
            "files_stored": len(stored_files_info)
        }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Add endpoint to get latest configuration
@router.get("/get-latest-config")
async def get_latest_config():
    """Get the latest configuration that was saved"""
    try:
        config_path = "./configs/latest.json"
        if not os.path.exists(config_path):
            return {"status": "error", "message": "No configuration found"}
        
        with open(config_path, "r") as f:
            config = json.load(f)
        
        return config
    except Exception as e:
        return {"status": "error", "message": str(e)} 