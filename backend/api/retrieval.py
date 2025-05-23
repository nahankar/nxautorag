from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from typing import Dict, Any, Optional, List, Mapping
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub
from langchain_openai import AzureOpenAI, ChatOpenAI
import transformers
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
import torch
from utils.vectorstore import get_embeddings
from utils.azure_openai_client import get_azure_openai_client, create_error_chain
import json
from langchain.llms.base import LLM
from enum import Enum
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from utils.google_drive_storage import get_latest_vectorstore_from_drive

# Import global config from ingestion
from api.ingestion import global_config, vectorstore as ingestion_vectorstore

router = APIRouter()

# Define SearchOption enum for validation
class SearchOption(str, Enum):
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    RERANKING = "reranking"

# Define StorageType enum for validation
class StorageType(str, Enum):
    LOCAL = "local"
    GOOGLE_DRIVE = "google_drive"

# Pydantic model for query request
class QueryRequest(BaseModel):
    question: str
    include_sources: bool = False
    search_option: SearchOption = SearchOption.SEMANTIC
    storage_type: StorageType = StorageType.LOCAL

# Global variable declarations
rag_chain = None

# Define HFWrapper class at module level
class HFWrapper(LLM):
    """Wrapper around HuggingFace pipeline to make it compatible with LangChain."""
    
    pipeline: Any
    is_t5: bool = False
    
    @property
    def _llm_type(self) -> str:
        return "huggingface_pipeline"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
        """Call the HuggingFace pipeline with the prompt."""
        if self.is_t5:
            result = self.pipeline(prompt)[0]["generated_text"]
            return result.strip()
        else:
            result = self.pipeline(prompt)[0]["generated_text"]
            # Return only the newly generated text
            return result[len(prompt):].strip()
    
    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get identifying parameters."""
        return {"pipeline": str(self.pipeline), "is_t5": self.is_t5}

# Initialize LLM based on global_config
def get_llm():
    # Try to load the latest configuration if available
    config_to_use = global_config
    latest_config = None
    
    try:
        config_path = "./configs/latest.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = json.load(f)
                if "llm_config" in config_data:
                    llm_data = config_data["llm_config"]
                    latest_config = {
                        "provider": llm_data.get("llm_provider"),
                        "model": llm_data.get("llm_model"),
                        "token": llm_data.get("api_token"),
                        "azure_endpoint": llm_data.get("azure_endpoint"),
                        "azure_deployment": llm_data.get("azure_deployment"),
                        "api_version": llm_data.get("api_version")
                    }
    except Exception as e:
        print(f"Error loading latest config: {e}")
    
    # If we have a latest config, use it, otherwise fall back to global
    if latest_config:
        config_to_use = latest_config
    
    # Extract config values
    provider = config_to_use.get("provider", "local")
    model = config_to_use.get("model", "google/flan-t5-base")
    token = config_to_use.get("token", "")
    
    print(f"Using provider: {provider}, model: {model}")
    
    if provider == "local":
        # Use transformers pipeline for local hosting
        try:
            # Check if CUDA is available
            device = 0 if torch.cuda.is_available() else -1
            
            # Create HF pipeline
            pipe = transformers.pipeline(
                "text-generation",
                model=model,
                device=device,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                max_new_tokens=512
            )
            
            # Create an instance of our LangChain-compatible wrapper
            llm = HFWrapper(pipeline=pipe, is_t5="t5" in model.lower())
            return llm
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error loading local model: {str(e)}")
    
    elif provider in ["hf_free", "hf_paid"]:
        # Use HuggingFaceHub
        try:
            print(f"Using HuggingFace with token (first 4 chars): {token[:4] if token else 'None'}")
            
            # If no token provided or we're in a fallback situation, use local model
            if not token or model == "mistralai/Mixtral-8x7B-Instruct-v0.1":  # Always use local for Mixtral which requires auth
                print(f"Using local model fallback for {model}")
                # Fall back to a simpler local model that doesn't require auth
                fallback_model = "google/flan-t5-base"
                print(f"Falling back to local model: {fallback_model}")
                
                # Check if CUDA is available
                device = 0 if torch.cuda.is_available() else -1
                
                # Use text2text-generation for T5 models
                pipe = transformers.pipeline(
                    "text2text-generation",
                    model=fallback_model,
                    device=device,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    max_new_tokens=512
                )
                
                # Create an instance of our LangChain-compatible wrapper
                return HFWrapper(pipeline=pipe, is_t5=True)
            
            # If we have a token, try to use HuggingFaceHub
            return HuggingFaceHub(
                repo_id=model,
                huggingfacehub_api_token=token,
                model_kwargs={"temperature": 0.5, "max_length": 512}
            )
        except Exception as e:
            print(f"Error loading HuggingFace model: {e}, falling back to local model")
            # If HuggingFace fails, fall back to local model
            try:
                fallback_model = "google/flan-t5-base"
                print(f"Falling back to local model: {fallback_model}")
                
                # Check if CUDA is available
                device = 0 if torch.cuda.is_available() else -1
                
                # Use text2text-generation for T5 models
                pipe = transformers.pipeline(
                    "text2text-generation",
                    model=fallback_model,
                    device=device,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    max_new_tokens=512
                )
                
                # Create an instance of our LangChain-compatible wrapper
                return HFWrapper(pipeline=pipe, is_t5=True)
            except Exception as inner_e:
                raise HTTPException(status_code=500, detail=f"Error loading fallback model: {str(inner_e)}")
    
    elif provider == "azure":
        # Use our verified Azure OpenAI client
        try:
            from utils.azure_openai_client import get_azure_openai_client
            # Load the full config data to pass to our client
            with open(config_path, "r") as f:
                full_config = json.load(f)
            
            client = get_azure_openai_client(full_config.get("llm_config"))
            if client:
                return client
            else:
                raise HTTPException(status_code=500, detail="Failed to initialize Azure OpenAI client")
        except Exception as e:
            import traceback
            print(f"Error loading Azure OpenAI model: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error loading Azure OpenAI model: {str(e)}")
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported LLM provider: {provider}")

def load_vectorstore_by_storage_type(storage_type=StorageType.LOCAL):
    """Load the vectorstore based on storage type specified.
    
    Args:
        storage_type: Either 'local' or 'google_drive'
        
    Returns:
        The loaded vectorstore or None if it fails
    """
    try:
        from utils.vectorstore import get_embeddings
        embeddings = get_embeddings()
        
        if storage_type == StorageType.LOCAL:
            # Check if local vectorstore exists
            if not os.path.exists("./vectorstore") or not os.path.exists("./vectorstore/index.faiss"):
                print("Local vectorstore not found")
                return None
                
            # Load from local
            return FAISS.load_local("./vectorstore", embeddings, allow_dangerous_deserialization=True)
            
        elif storage_type == StorageType.GOOGLE_DRIVE:
            # Import Google Drive storage utilities
            from utils.google_drive_storage import get_latest_vectorstore_from_drive
            
            # Create a temporary directory for the downloaded vectorstore
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            # Try to download and load from Google Drive
            success, error = get_latest_vectorstore_from_drive(local_path=temp_dir)
            if not success:
                print(f"Error loading from Google Drive: {error}")
                return None
                
            # Load the downloaded vectorstore
            return FAISS.load_local(temp_dir, embeddings, allow_dangerous_deserialization=True)
            
    except Exception as e:
        print(f"Error loading vectorstore: {e}")
        import traceback
        traceback.print_exc()
        return None

# Create retriever based on search option and storage type
def get_retriever(search_option=SearchOption.SEMANTIC, storage_type=StorageType.LOCAL):
    """Create a retriever based on search option and storage type."""
    try:
        # Load vectorstore based on storage type
        vs = load_vectorstore_by_storage_type(storage_type)
        
        if vs is None:
            print(f"Failed to load vectorstore from {storage_type}")
            return None
        
        # Get embeddings model
        embeddings = get_embeddings()
        
        # If embeddings failed, create a basic HuggingFace one directly
        if embeddings is None:
            print("Failed to get embeddings, creating HuggingFace embeddings directly")
            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            except Exception as e:
                print(f"Error creating direct HuggingFace embeddings: {e}")
                return None
        
        # 1. Semantic Search (default KNN)
        if search_option == SearchOption.SEMANTIC:
            print("Using Semantic (KNN) search retriever")
            return vs.as_retriever(search_kwargs={"k": 3})
        
        # 2. Hybrid Search (Combined sparse and dense retrieval)
        elif search_option == SearchOption.HYBRID:
            print("Using Hybrid (Sparse+Dense) search retriever")
            try:
                # Get all documents from vectorstore to initialize BM25
                # This is a simplified approach; in production you might want to use a persistent BM25 index
                print("Loading documents for BM25 retriever...")
                docs = vs.similarity_search("", k=1000)  # Get a large sample of docs for BM25 index
                
                # Create BM25 retriever from documents
                bm25_retriever = BM25Retriever.from_documents(docs)
                bm25_retriever.k = 3  # Return top 3 results
                
                # Create vector retriever
                faiss_retriever = vs.as_retriever(search_kwargs={"k": 3})
                
                # Combine retrievers with equal weights (0.5 each)
                return EnsembleRetriever(
                    retrievers=[bm25_retriever, faiss_retriever], 
                    weights=[0.5, 0.5]
                )
            except Exception as e:
                print(f"Error setting up hybrid search: {e}, falling back to semantic search")
                return vs.as_retriever(search_kwargs={"k": 3})
        
        # 3. Re-ranking Search
        elif search_option == SearchOption.RERANKING:
            print("Using Re-ranking search retriever")
            try:
                # Import the MultiQueryRetriever for query expansion
                from langchain.retrievers.multi_query import MultiQueryRetriever
                from langchain_core.language_models import LLM as CoreLLM
                
                # First get a larger number of candidates using standard retrieval
                base_retriever = vs.as_retriever(search_kwargs={"k": 10})
                
                # Try to import the cross-encoder
                try:
                    from sentence_transformers import CrossEncoder
                    
                    # Create a reranking wrapper function using the cross-encoder
                    print("Loading cross-encoder model for reranking...")
                    cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                    
                    def reranker_retriever(query):
                        # Get documents from the base retriever
                        docs = base_retriever.get_relevant_documents(query)
                        
                        if not docs:
                            return []
                                
                        # Prepare document-query pairs for the cross-encoder
                        pairs = [(query, doc.page_content) for doc in docs]
                        
                        # Get scores from the cross-encoder
                        scores = cross_encoder.predict(pairs)
                        
                        # Sort documents by scores
                        scored_docs = list(zip(docs, scores))
                        sorted_docs = [doc for doc, score in sorted(scored_docs, key=lambda x: x[1], reverse=True)]
                        
                        # Return the top 3 reranked documents
                        return sorted_docs[:3]
                    
                    # Create a callable class to wrap the reranker function
                    class RerankerRetriever:
                        def get_relevant_documents(self, query):
                            return reranker_retriever(query)
                            
                    return RerankerRetriever()
                    
                except ImportError:
                    print("Cross-encoder not available, falling back to MultiQueryRetriever")
                    # If cross-encoder is not available, use MultiQueryRetriever for query expansion
                    # Get LLM for query generation
                    llm = get_llm()
                    
                    # Create and return the MultiQueryRetriever
                    return MultiQueryRetriever.from_llm(
                        retriever=base_retriever,
                        llm=llm
                    )
            except Exception as e:
                print(f"Error setting up reranking: {e}, falling back to semantic search")
                return vs.as_retriever(search_kwargs={"k": 3})
        
        # Default to semantic search if an unknown option is provided
        else:
            print(f"Unknown search option: {search_option}, defaulting to semantic search")
            return vs.as_retriever(search_kwargs={"k": 3})
            
    except Exception as e:
        print(f"Error in get_retriever: {e}")
        return None

# Create RAG chain
def create_rag_chain():
    """Create a RAG chain for question answering with the ingested documents"""
    print("\n----- Creating new RAG chain -----")
    
    # This creates a function that always returns the same message
    def create_error_message_chain(message):
        print(f"⚠️ Creating error chain with message: {message}")
        def error_fn(x):
            return message
        # Wrap the function in a RunnableLambda to make it compatible with LangServe
        return RunnableLambda(error_fn)
    
    try:
        # Get retriever (using default semantic search)
        print("Getting retriever from vectorstore...")
        retriever = get_retriever()
        
        if retriever is None:
            print("❌ Retriever is None - returning error chain")
            return create_error_message_chain("No documents have been ingested yet. Please ingest documents first.")
        else:
            print("✅ Retriever created successfully")
            
        # Determine number of documents to retrieve based on model
        num_docs = 3  # Default for most models
        try:
            if os.path.exists("./configs/latest.json"):
                with open("./configs/latest.json", "r") as f:
                    config_data = json.load(f)
                    llm_config = config_data.get("llm_config", {})
                    model_name = llm_config.get("llm_model", "").lower()
                    provider = llm_config.get("llm_provider", "").lower()
                    
                    # Adjust number of documents based on model capabilities
                    if provider == "azure":
                        if "gpt-4" in model_name:
                            num_docs = 5  # GPT-4 can handle more context
                        elif "gpt-35-turbo" in model_name or "gpt-3.5-turbo" in model_name:
                            num_docs = 4  # GPT-3.5 handles moderate context
                    elif "mistral" in model_name or "mixtral" in model_name:
                        num_docs = 4  # Mixtral has good context handling
        except Exception as e:
            print(f"Error determining number of documents from model: {e}")
        
        print(f"Retrieving {num_docs} documents based on model capabilities")
        
        # Wrap retriever in a function that formats the docs
        def retrieve_and_format(query):
            # Use get_relevant_documents instead of similarity_search for the retriever
            docs = retriever.get_relevant_documents(query)
            return format_docs(docs)
        
        # Get LLM
        llm = get_llm()
        
        # RAG prompt template
        template = """
        You are an AI assistant for question-answering tasks. Use the following pieces of retrieved context to answer the user's question. 
        If you don't know the answer or if the answer is not contained in the provided context, just say that you don't know.
        
        Use only the information provided in the context to answer the question. Do not use prior knowledge.
        
        IMPORTANT: Even if the context is brief or consists of Excel spreadsheet content, please provide a complete answer 
        with detailed explanation. If you see phrases or terms from spreadsheets, explain what they likely mean 
        based on the context.
        
        You have been provided with larger context than before, so make full use of all the information to give
        a comprehensive answer. Focus on detail and specifics from the context rather than general statements.
        
        Aim to provide a detailed 3-5 sentence response that fully explains the answer to the question.
        
        Question: {question} 
        
        Context: {context} 
        
        Answer:
        """
        
        # Create prompt
        rag_prompt = PromptTemplate.from_template(template)
        
        # Set up the RAG chain
        def format_docs(docs):
            # Check if we have any documents
            if not docs or len(docs) == 0:
                print("WARNING: No documents retrieved from the vectorstore")
                return "No relevant documents found in the knowledge base."
                
            # Load latest model config to determine context size
            model_name = "default"
            max_per_doc = 1000  # Default per-document limit
            max_total = 2400    # Default total limit
            
            try:
                if os.path.exists("./configs/latest.json"):
                    with open("./configs/latest.json", "r") as f:
                        config_data = json.load(f)
                        llm_config = config_data.get("llm_config", {})
                        model_name = llm_config.get("llm_model", "").lower()
                        provider = llm_config.get("llm_provider", "").lower()
                        
                        # Adjust limits based on model capabilities
                        if provider == "azure":
                            if "gpt-4" in model_name:
                                max_per_doc = 2000
                                max_total = 6000
                            elif "gpt-35-turbo" in model_name or "gpt-3.5-turbo" in model_name:
                                max_per_doc = 1500
                                max_total = 4000
                        elif "mistral" in model_name or "mixtral" in model_name:
                            max_per_doc = 1800
                            max_total = 5400
            except Exception as e:
                print(f"Error determining context size from model: {e}")
            
            # Extra logging to see exactly what's in each document
            print(f"Number of documents retrieved: {len(docs)}")
            print(f"Using model: {model_name}, max_per_doc: {max_per_doc}, max_total: {max_total}")
            
            for i, doc in enumerate(docs):
                print(f"Document {i+1} length: {len(doc.page_content)} characters")
                print(f"Document {i+1} snippet: {doc.page_content[:100]}...")
            
            # Extract text from each document with model-specific limits
            formatted_content = "\n\n".join([d.page_content[:max_per_doc] for d in docs])
            
            # Use model-specific total limit
            if len(formatted_content) > max_total:
                formatted_content = formatted_content[:max_total] + "..."
            
            # Debug logging
            print(f"Final context length: {len(formatted_content)} characters")
            
            # Validate minimum context size
            if len(formatted_content) < 200:
                print("WARNING: Context is too small, adding placeholder to prevent hallucinations")
                formatted_content += "\n\nNote: The context available is very limited. If you don't know the answer based on this context, please say so rather than guessing."
                
            return formatted_content
        
        # Create the RAG chain
        chain = (
            {"context": retrieve_and_format, "question": RunnablePassthrough()}
            | rag_prompt
            | llm
            | StrOutputParser()
        )
        
        return chain
    
    except Exception as e:
        # Return a Runnable that just returns the error message
        return create_error_message_chain(f"Error creating RAG chain: {str(e)}")

def recreate_rag_chain():
    """Force recreate the RAG chain - useful when vectorstore has changed"""
    global rag_chain
    print("\n===== FORCE RECREATING RAG CHAIN =====")
    rag_chain = create_rag_chain()
    return rag_chain

# Initialize rag_chain at module level
rag_chain = create_rag_chain()

# Query endpoint
@router.post("/query")
async def query(request: QueryRequest):
    global rag_chain
    try:
        # Get the appropriate retriever based on the search option and storage type
        print(f"Using search option: {request.search_option}, storage type: {request.storage_type}")
        retriever = get_retriever(request.search_option, request.storage_type)
        
        if retriever is None:
            storage_name = "local storage" if request.storage_type == StorageType.LOCAL else "Google Drive"
            return {"status": "error", "message": f"No vector store available in {storage_name}. Please ingest documents first."}
        
        # Define format_docs function
        def format_docs(docs):
            # Check if we have any documents
            if not docs or len(docs) == 0:
                print("WARNING: No documents retrieved from the vectorstore")
                return "No relevant documents found in the knowledge base."
                
            # Load latest model config to determine context size
            model_name = "default"
            max_per_doc = 1000  # Default per-document limit
            max_total = 2400    # Default total limit
            
            try:
                if os.path.exists("./configs/latest.json"):
                    with open("./configs/latest.json", "r") as f:
                        config_data = json.load(f)
                        llm_config = config_data.get("llm_config", {})
                        model_name = llm_config.get("llm_model", "").lower()
                        provider = llm_config.get("llm_provider", "").lower()
                        
                        # Adjust limits based on model capabilities
                        if provider == "azure":
                            if "gpt-4" in model_name:
                                max_per_doc = 2000
                                max_total = 6000
                            elif "gpt-35-turbo" in model_name or "gpt-3.5-turbo" in model_name:
                                max_per_doc = 1500
                                max_total = 4000
                        elif "mistral" in model_name or "mixtral" in model_name:
                            max_per_doc = 1800
                            max_total = 5400
            except Exception as e:
                print(f"Error determining context size from model: {e}")
            
            # Extra logging to see exactly what's in each document
            print(f"Number of documents retrieved: {len(docs)}")
            print(f"Using model: {model_name}, max_per_doc: {max_per_doc}, max_total: {max_total}")
            
            for i, doc in enumerate(docs):
                print(f"Document {i+1} length: {len(doc.page_content)} characters")
                print(f"Document {i+1} snippet: {doc.page_content[:100]}...")
            
            # Extract text from each document with model-specific limits
            formatted_content = "\n\n".join([d.page_content[:max_per_doc] for d in docs])
            
            # Use model-specific total limit
            if len(formatted_content) > max_total:
                formatted_content = formatted_content[:max_total] + "..."
            
            # Debug logging
            print(f"Final context length: {len(formatted_content)} characters")
            
            # Validate minimum context size
            if len(formatted_content) < 200:
                print("WARNING: Context is too small, adding placeholder to prevent hallucinations")
                formatted_content += "\n\nNote: The context available is very limited. If you don't know the answer based on this context, please say so rather than guessing."
                
            return formatted_content
        
        # Create a custom RAG chain for this specific search option
        def retrieve_and_format(query):
            # Use the specific retriever for this request
            docs = retriever.get_relevant_documents(query)
            return format_docs(docs)
        
        # Get LLM
        llm = get_llm()
        
        # RAG prompt template
        template = """
        You are an AI assistant for question-answering tasks. Use the following pieces of retrieved context to answer the user's question. 
        If you don't know the answer or if the answer is not contained in the provided context, just say that you don't know.
        
        Use only the information provided in the context to answer the question. Do not use prior knowledge.
        
        IMPORTANT: Even if the context is brief or consists of Excel spreadsheet content, please provide a complete answer 
        with detailed explanation. If you see phrases or terms from spreadsheets, explain what they likely mean 
        based on the context.
        
        You have been provided with larger context than before, so make full use of all the information to give
        a comprehensive answer. Focus on detail and specifics from the context rather than general statements.
        
        Aim to provide a detailed 3-5 sentence response that fully explains the answer to the question.
        
        Question: {question} 
        
        Context: {context} 
        
        Answer:
        """
        
        # Create prompt
        rag_prompt = PromptTemplate.from_template(template)
        
        # Create the custom RAG chain for this query
        custom_chain = (
            {"context": retrieve_and_format, "question": RunnablePassthrough()}
            | rag_prompt
            | llm
            | StrOutputParser()
        )
        
        # Execute the custom chain
        try:
            raw_answer = custom_chain.invoke(request.question)
            
            # Check if answer indicates no documents (probably an error chain response)
            if "no documents have been ingested" in raw_answer.lower():
                print("ERROR: chain returned 'no documents' error despite vectorstore existing")
                print("Attempting to recreate the retriever...")
                
                # Try with a different retriever
                retriever = get_retriever(SearchOption.SEMANTIC)
                if retriever is None:
                    return {"answer": "Sorry, no documents were found to answer your question."}
                    
                # Try again with the new retriever
                def retrieve_and_format_fallback(query):
                    docs = retriever.get_relevant_documents(query)
                    return format_docs(docs)
                    
                # Create a fallback chain
                fallback_chain = (
                    {"context": retrieve_and_format_fallback, "question": RunnablePassthrough()}
                    | rag_prompt
                    | llm
                    | StrOutputParser()
                )
                
                # Try again with the fallback chain
                raw_answer = fallback_chain.invoke(request.question)
        except Exception as model_error:
            # Handle model errors gracefully
            print(f"Model error: {str(model_error)}")
            return {"answer": "Sorry, there was an error processing your query. Please try a different question or check your documents."}
        
        # Debug log
        print(f"Raw answer type: {type(raw_answer)}, length: {len(raw_answer) if isinstance(raw_answer, str) else 'N/A'}")
        print(f"Raw answer content: {raw_answer[:100]}...")  # Print first 100 chars
        
        # Improved validation with better binary detection
        if not isinstance(raw_answer, str):
            return {"answer": "Sorry, the response was not a valid string. Please try a different question."}
            
        # Check for extremely long answers
        if len(raw_answer) > 2000:
            return {"answer": "Sorry, the generated response was too long. Please try a more specific question."}
            
        # Check for binary data patterns (like repeated zeros or non-printable characters)
        if "00x00" in raw_answer or "0x00" in raw_answer or "\x00" in raw_answer or "\\x00" in raw_answer:
            print("Binary data detected in response")
            return {"answer": "Sorry, the response contained binary data. Please try a different question."}
            
        # Check for suspiciously repetitive content - with more lenient thresholds
        is_repetitive = False
        if len(raw_answer) > 100:  # Only apply to longer responses (was 50)
            # For longer responses, check if there's not enough unique characters
            unique_char_ratio = len(set(raw_answer)) / len(raw_answer)
            if unique_char_ratio < 0.05:  # Less than 5% unique characters (was 0.1 or 10%)
                is_repetitive = True
                print(f"Low character diversity: {unique_char_ratio:.2f}")
            
            # Check for repeated patterns - more lenient check
            if raw_answer[:5] and len(raw_answer) > 100 and raw_answer.count(raw_answer[:5]) > 10:
                is_repetitive = True
                print(f"Repeated pattern found: '{raw_answer[:5]}' appears {raw_answer.count(raw_answer[:5])} times")

        if is_repetitive:
            print("Repetitive content detected")
            return {"answer": "Sorry, the response contained repetitive data. Please try a different question."}
            
        try:
            # Ensure the answer is valid UTF-8
            encoded_answer = raw_answer.encode('utf-8', errors='replace')
            decoded_answer = encoded_answer.decode('utf-8')
            
            # If we lost data in the encoding/decoding process, reject the response
            if len(decoded_answer) < len(raw_answer) * 0.9:  # Lost more than 10%
                print("Lost data during UTF-8 encoding/decoding")
                return {"answer": "Sorry, the response contained invalid characters. Please try a different question."}
                
            # Remove any control characters
            import re
            cleaned_answer = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', decoded_answer)
            
            # Use the cleaned answer
            raw_answer = cleaned_answer
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            return {"answer": "Sorry, there was an error processing the response. Please try a different question."}
        
        # Clean up the response - extract just the answer portion
        answer = raw_answer
        
        # If the response contains the prompt template, extract just the answer
        if "Answer:" in raw_answer:
            answer = raw_answer.split("Answer:")[-1].strip()
        
        # Only include sources if requested
        response = {"answer": answer}
        
        # Get the source documents for reference but don't include them by default
        if hasattr(request, 'include_sources') and request.include_sources:
            # Use the same retriever with the specified search option
            retriever = get_retriever(request.search_option)
            docs = retriever.get_relevant_documents(request.question)
            sources = [doc.page_content[:500] for doc in docs]  # Limit source length
            response["sources"] = sources
        
        return response
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

# LangServe compatible endpoint
@router.post("/rag")
async def rag(input_data: Dict[str, Any]):
    try:
        question = input_data.get("input", {}).get("question", "")
        if not question:
            return {"status": "error", "message": "No question provided"}
        
        # Use the same function as /query endpoint
        result = await query(QueryRequest(question=question))
        
        # Format response for LangServe
        if "answer" in result:
            return {"output": result["answer"]}
        else:
            return {"output": f"Error: {result.get('message', 'Unknown error')}"}
            
    except Exception as e:
        return {"output": f"Error: {str(e)}"} 