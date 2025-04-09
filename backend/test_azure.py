"""Test script for our Azure OpenAI client"""
import os
import sys
import json

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.azure_openai_client import get_azure_openai_client, get_azure_embeddings

def main():
    """Test the Azure OpenAI client"""
    print("Testing Azure OpenAI client...")
    
    try:
        # Load the configuration
        with open("./configs/latest.json", "r") as f:
            config = json.load(f)
            llm_config = config.get("llm_config", {})
        
        # Print the configuration
        print(f"Configuration: provider={llm_config.get('llm_provider')}, api_version={llm_config.get('api_version')}")
        
        # Test the client
        client = get_azure_openai_client(llm_config)
        print(f"Client initialized: {client is not None}")
        
        # Test the embeddings
        embeddings = get_azure_embeddings()
        print(f"Embeddings initialized: {embeddings is not None}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 