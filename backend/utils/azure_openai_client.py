"""
Azure OpenAI client utilities - uses the modern API format for openai>=1.0.0
"""
from langchain_openai import AzureOpenAI, AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain.schema.runnable import RunnableLambda
import json
import os

def get_azure_openai_client(config=None):
    """
    Create an Azure OpenAI LLM client using the modern API format
    
    Args:
        config (dict, optional): Configuration dictionary with Azure settings.
                                If None, will load from latest.json
    
    Returns:
        AzureOpenAI or AzureChatOpenAI: The configured Azure OpenAI LLM client
    """
    if config is None:
        # Load config from latest.json
        try:
            if os.path.exists("./configs/latest.json"):
                with open("./configs/latest.json", "r") as f:
                    config_data = json.loads(f.read())
                    config = config_data.get("llm_config", {})
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    # Make sure we have all required configs
    if not config.get("api_token") or not config.get("azure_endpoint") or not config.get("azure_deployment"):
        print("Missing required Azure configuration")
        return None
    
    try:
        # Get deployment name to determine model type
        deployment = config.get("azure_deployment", "").lower()
        model_name = config.get("llm_model", "").lower()
        
        # Determine if this is a chat model or completion model
        is_chat_model = any(name in model_name for name in ["gpt-4", "gpt-3.5", "gpt4", "gpt35", "gpt-35", "gpt-4o"])
        
        print(f"Azure OpenAI: Using {'chat completion' if is_chat_model else 'completion'} model {model_name}")
        
        if is_chat_model:
            # Chat model - use AzureChatOpenAI
            client = AzureChatOpenAI(
                azure_endpoint=config.get("azure_endpoint", ""),
                api_key=config.get("api_token", ""),
                openai_api_version=config.get("api_version", "2023-05-15"),
                azure_deployment=config.get("azure_deployment", ""),
                temperature=0.5,
                max_tokens=512
            )
        else:
            # Completion model - use AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=config.get("azure_endpoint", ""),
                api_key=config.get("api_token", ""),
                openai_api_version=config.get("api_version", "2023-05-15"),
                azure_deployment=config.get("azure_deployment", ""),
                temperature=0.5,
                max_tokens=512
            )
        return client
    except Exception as e:
        print(f"Error creating Azure OpenAI client: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def get_azure_embeddings():
    """
    Attempt to create Azure OpenAI embeddings client if possible,
    otherwise return HuggingFace embeddings
    
    Returns:
        Embeddings object compatible with FAISS
    """
    # First check if we should use Azure
    try:
        if os.path.exists("./configs/latest.json"):
            with open("./configs/latest.json", "r") as f:
                config = json.loads(f.read())
                llm_config = config.get("llm_config", {})
                
                # Only proceed if we have Azure configuration
                if llm_config.get("llm_provider") == "azure" and llm_config.get("api_token"):
                    deployment_name = llm_config.get("azure_deployment", "").lower()
                    
                    # Chat models don't support embeddings - skip Azure entirely for these
                    if any(name in deployment_name for name in ["gpt-4", "gpt-3", "gpt4", "gpt35", "gpt-35"]):
                        print(f"Deployment {deployment_name} is a chat model that doesn't support embeddings")
                        print("Skipping Azure embeddings and using HuggingFace directly")
                        # Skip to HuggingFace
                        raise ValueError("Chat model detected, using HuggingFace instead")
                    
                    # Only try Azure for embeddings models
                    if "embedding" in deployment_name or "ada" in deployment_name:
                        print(f"Attempting Azure embeddings with deployment {deployment_name}")
                        try:
                            from langchain_openai import AzureOpenAIEmbeddings
                            
                            embeddings = AzureOpenAIEmbeddings(
                                azure_deployment=llm_config.get("azure_deployment"),
                                azure_endpoint=llm_config.get("azure_endpoint"),
                                api_key=llm_config.get("api_token"),
                                api_version=llm_config.get("api_version", "2023-05-15")
                            )
                            
                            # Test the embeddings with a simple example to ensure they work
                            embeddings.embed_query("test")
                            print("Successfully created Azure embeddings")
                            return embeddings
                        except Exception as e:
                            print(f"Error using Azure embeddings: {e}")
                    else:
                        print(f"Deployment {deployment_name} does not appear to be an embedding model")
    except Exception as e:
        print(f"Error in Azure embeddings check: {e}")
    
    # Use HuggingFace embeddings as our default/fallback
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        print("Using HuggingFace embeddings with sentence-transformers")
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return embeddings
    except Exception as hf_error:
        print(f"Error with HuggingFace embeddings: {hf_error}")
        
        # Last resort fallback
        from langchain_core.embeddings import FakeEmbeddings
        print("WARNING: Using fake embeddings as last resort - for development only")
        return FakeEmbeddings(size=384)

def create_error_chain(message):
    """Create a chain that returns an error message"""
    def error_fn(x):
        return message
    return RunnableLambda(error_fn)

