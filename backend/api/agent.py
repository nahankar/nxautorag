from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.tools import tool
from langchain_community.vectorstores import FAISS
import os
import json
from api.ingestion import global_config, vectorstore as ingestion_vectorstore
from api.retrieval import get_llm
from utils.vectorstore import get_embeddings

router = APIRouter()

# Pydantic model for agent query
class AgentQueryRequest(BaseModel):
    question: str

# Tool for retrieving information from the vector store
@tool
def search_documents(query: str) -> str:
    """Search for information in the document database."""
    try:
        # Don't rely on the global variable - always load from disk for consistency
        if not os.path.exists("./vectorstore"):
            return "No documents found in the database. Please ingest documents first."
        
        embeddings = get_embeddings()
        vs = FAISS.load_local("./vectorstore", embeddings, allow_dangerous_deserialization=True)
        
        # Query for relevant documents
        docs = vs.similarity_search(query, k=4)
        
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
    try:
        # Check if we have a vector store
        if not os.path.exists("./vectorstore") and ingestion_vectorstore is None:
            return {"answer": "No documents have been ingested yet. Please ingest documents first."}
        
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