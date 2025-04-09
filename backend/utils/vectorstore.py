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

def save_vectorstore(vectorstore, path="./vectorstore"):
    """Save the vectorstore to disk"""
    try:
        vectorstore.save_local(path)
        print(f"Vectorstore saved successfully to {path}")
        # Save embedding info for reference
        if hasattr(vectorstore, "_embedding_function") and hasattr(vectorstore._embedding_function, "_llm_type"):
            print(f"Saved with embedding type: {vectorstore._embedding_function._llm_type}")
        return True
    except Exception as e:
        print(f"Error saving vectorstore: {e}")
        return False

def load_vectorstore(path="./vectorstore"):
    """Load the vectorstore from disk if it exists"""
    try:
        if not os.path.exists(path):
            print(f"Vectorstore path {path} does not exist. Creating a new vectorstore.")
            return create_empty_vectorstore()
        
        if not os.path.exists(os.path.join(path, "index.faiss")):
            print(f"FAISS index file not found at {path}/index.faiss. Creating a new vectorstore.")
            return create_empty_vectorstore()
            
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