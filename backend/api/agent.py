from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.tools import tool
from langchain_community.vectorstores import FAISS
import os
import json
from api.ingestion import global_config, vectorstore as ingestion_vectorstore
from api.retrieval import get_llm, get_retriever, SearchOption, StorageType
from utils.vectorstore import get_embeddings

router = APIRouter()

# Pydantic model for agent query
class AgentQueryRequest(BaseModel):
    question: str
    search_option: SearchOption = SearchOption.SEMANTIC
    storage_type: StorageType = StorageType.LOCAL

# Global variables to store the search options for the tool
current_search_option = SearchOption.SEMANTIC
current_storage_type = StorageType.LOCAL

# Tool for retrieving information from the vector store
@tool
def search_documents(query: str) -> str:
    """Search for information in the document database."""
    try:
        # Use the retriever with the specified search option and storage type
        retriever = get_retriever(current_search_option, current_storage_type)
        
        if retriever is None:
            storage_name = "local storage" if current_storage_type == StorageType.LOCAL else "Google Drive"
            return f"No documents found in {storage_name}. Please ingest documents first."
        
        # Get relevant documents
        docs = retriever.get_relevant_documents(query)
        
        # Format results
        results = []
        for i, doc in enumerate(docs):
            results.append(f"Document {i+1}:\n{doc.page_content}\n")
        
        return "\n".join(results)
    
    except Exception as e:
        return f"Error searching documents: {str(e)}"

# Agent query endpoint
@router.post("/agent-query")
async def agent_query(request: AgentQueryRequest):
    global current_search_option, current_storage_type
    try:
        # Set the current search and storage options for the tool
        current_search_option = request.search_option
        current_storage_type = request.storage_type
        print(f"Using search option for agent: {current_search_option}, storage type: {current_storage_type}")
        
        # Verify the vectorstore exists for the selected storage type
        retriever = get_retriever(current_search_option, current_storage_type)
        if retriever is None:
            storage_name = "local storage" if current_storage_type == StorageType.LOCAL else "Google Drive"
            return {"answer": f"No documents found in {storage_name}. Please ingest documents first."}
        
        # Get LLM based on config
        llm = get_llm()
        
        # Define tools
        tools = [search_documents]
        
        # Initialize agent
        agent = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # Run agent
        result = agent.run(request.question)
        
        return {"answer": result}
    
    except Exception as e:
        return {"status": "error", "message": str(e)} 