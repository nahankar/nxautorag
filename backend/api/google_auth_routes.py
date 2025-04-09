from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
import os
import json
import shutil
from typing import Dict, Optional, List
from pydantic import BaseModel
from fastapi.security import OAuth2AuthorizationCodeBearer
from utils.google_auth import (
    create_authorization_url, 
    exchange_code_for_token,
    check_auth_status,
    test_connection,
    revoke_token
)

router = APIRouter()

# Manage OAuth2 state
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="",
    tokenUrl="",
    auto_error=False
)

# Session state storage (in-memory for simplicity)
# In production, use a proper session store
oauth_states = {}

class GoogleAuthStatus(BaseModel):
    is_authenticated: bool
    message: str
    user_info: Optional[Dict] = None

# Create a class for the ingest request
class GoogleIngestRequest(BaseModel):
    services: List[str]
    max_items: int = 50

@router.post("/upload-google-credentials")
async def upload_credentials(file: UploadFile = File(...)):
    """Upload Google OAuth credentials.json file."""
    try:
        # Ensure directory exists
        os.makedirs("./configs", exist_ok=True)
        
        # Check if file is JSON
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="File must be a JSON file")
        
        # Save file to configs directory
        file_path = f"./configs/google_credentials.json"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Validate that it's a proper Google OAuth credentials file
        try:
            with open(file_path, "r") as f:
                creds_data = json.load(f)
                
            # Basic validation - check for expected fields
            if not all(k in creds_data for k in ("installed", "web")):
                if "installed" not in creds_data and "web" not in creds_data:
                    raise ValueError("Invalid Google OAuth credentials format")
            
            # If file exists, remove any existing token to force re-authentication
            if os.path.exists("./configs/google_token.json"):
                os.remove("./configs/google_token.json")
                
            return {"status": "success", "message": "Google credentials uploaded successfully"}
        
        except (json.JSONDecodeError, ValueError) as e:
            # Remove invalid file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"Invalid credentials file: {str(e)}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload credentials: {str(e)}")

@router.get("/login")
async def login_with_google():
    """Start the Google OAuth flow by generating authorization URL."""
    try:
        from utils.google_auth import create_authorization_url
        
        # Generate authorization URL and state
        auth_url, state = create_authorization_url()
        
        # Store state for verification (in production, use secure session/cookie)
        oauth_states[state] = True
        
        # Return URL for frontend to redirect
        return {
            "auth_url": auth_url,
            "state": state
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate login URL: {str(e)}")

@router.get("/oauth-callback")
async def oauth_callback(code: str, state: str, response: Response):
    """Handle the OAuth callback from Google."""
    try:
        # Comment this out for now
        # if state not in oauth_states:
        #     raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Remove the used state
        # oauth_states.pop(state, None)
        
        from utils.google_auth import exchange_code_for_token
        
        # Exchange code for token
        token_data, error = exchange_code_for_token(code, state)
        if error:
            raise HTTPException(status_code=400, detail=error)
        
        # Get user info (optional)
        user_info = {"name": "Google User"}
        
        # Set a cookie to indicate successful authentication
        response.set_cookie(
            key="google_auth", 
            value="authenticated", 
            httponly=True,
            max_age=3600,
            samesite="lax"
        )
        
        # Redirect back to the frontend app - update the URL to match what the frontend expects
        return RedirectResponse(url="http://localhost:3000?auth=success")
    
    except Exception as e:
        return RedirectResponse(url=f"http://localhost:3000?auth=error&message={str(e)}")

@router.get("/auth-status")
async def auth_status():
    """Check if Google authentication is available/valid."""
    try:
        from utils.google_auth import get_google_credentials
        
        # Check if we have valid credentials
        creds, error = get_google_credentials()
        is_authenticated = creds is not None and creds.valid
        
        if error:
            return GoogleAuthStatus(
                is_authenticated=False,
                message=error
            )
        
        if is_authenticated:
            # Get user info (simplified)
            user_info = {"authenticated": True}
            return GoogleAuthStatus(
                is_authenticated=True,
                message="Authenticated with Google",
                user_info=user_info
            )
        else:
            return GoogleAuthStatus(
                is_authenticated=False,
                message="Not authenticated with Google"
            )
            
    except Exception as e:
        return GoogleAuthStatus(
            is_authenticated=False,
            message=f"Error checking authentication status: {str(e)}"
        )

@router.post("/logout")
async def logout(response: Response):
    """Log out from Google by invalidating the token."""
    try:
        token_path = "./configs/google_token.json"
        
        # Remove token file if it exists
        if os.path.exists(token_path):
            os.remove(token_path)
        
        # Clear authentication cookie
        response.delete_cookie(key="google_auth")
        
        return {"status": "success", "message": "Logged out successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to logout: {str(e)}")

@router.post("/test-connection")
async def test_google_connection():
    try:
        result = test_connection()
        if result.get("status") == "success":
            return result
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "Unknown error testing connection"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing connection: {str(e)}")

@router.post("/ingest")
async def ingest_google_data(request: GoogleIngestRequest):
    try:
        # Import necessary modules
        from api.ingestion import process_google
        from utils.vectorstore import get_embeddings
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import FAISS
        
        # Create Google config from request
        from api.ingestion import GoogleConfig
        google_config = GoogleConfig(
            type="google",
            services=request.services,
            max_items=request.max_items
        )
        
        # Process Google data
        documents = await process_google(google_config)
        
        if not documents:
            return {"status": "error", "message": "No documents were processed"}
            
        # Filter to only keep PDF documents - ignore all other file types
        pdf_documents = []
        for doc in documents:
            # Check if file is PDF based on metadata
            mime_type = doc.metadata.get("mime_type", "")
            file_path = doc.metadata.get("source", "")
            
            if mime_type == "application/pdf" or file_path.lower().endswith(".pdf"):
                pdf_documents.append(doc)
            else:
                print(f"Skipping non-PDF file: {file_path}")
        
        documents = pdf_documents
        
        if not documents:
            return {"status": "error", "message": "No PDF documents were found. Only PDF files are supported for ingestion."}
        
        # Clean document content to ensure no binary data
        cleaned_documents = []
        for doc in documents:
            # Get the text content
            content = doc.page_content
            
            # Skip excessively large content
            if len(content) > 10000:
                content = content[:10000] + "... (truncated)"
                
            # Ensure there's no binary data by filtering characters
            try:
                # Try to encode and decode to ensure UTF-8 compatibility
                cleaned_content = content.encode('utf-8', errors='replace').decode('utf-8')
                
                # Remove any characters that might cause issues
                import re
                # Remove control characters except newline, tab, etc.
                cleaned_content = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned_content)
                
                # Create a new document with the cleaned content
                from langchain.schema import Document
                cleaned_doc = Document(
                    page_content=cleaned_content,
                    metadata=doc.metadata
                )
                cleaned_documents.append(cleaned_doc)
                
            except Exception as e:
                print(f"Error cleaning document: {str(e)}")
                # Skip this document
                continue
                
        # Use the cleaned documents moving forward
        documents = cleaned_documents
        
        # Check if we have any valid documents after cleaning
        if not documents:
            return {"status": "error", "message": "No valid documents remained after cleaning"}
        
        # Chunk documents with larger chunk size to ensure more content is available for queries
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        
        # Log chunk sizes to verify we're getting proper data
        print(f"Created {len(chunks)} chunks from {len(documents)} documents")
        print(f"Average chunk size: {sum(len(c.page_content) for c in chunks) / len(chunks) if chunks else 0} characters")
        
        # Create embeddings
        embeddings = get_embeddings()
        
        # Check if vectorstore exists and load it
        import os
        if os.path.exists("./vectorstore"):
            # Load existing vectorstore
            vectorstore = FAISS.load_local("./vectorstore", embeddings, allow_dangerous_deserialization=True)
            # Add new documents
            vectorstore.add_documents(chunks)
        else:
            # Create new vectorstore
            vectorstore = FAISS.from_documents(chunks, embeddings)
        
        # Save vector store to disk
        vectorstore.save_local("./vectorstore")
        
        # Force recreate the RAG chain since vectorstore has changed
        from api.retrieval import recreate_rag_chain
        recreate_rag_chain()
        
        return {
            "status": "success", 
            "message": "Google data ingested successfully",
            "items_count": len(documents)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error ingesting Google data: {str(e)}"} 