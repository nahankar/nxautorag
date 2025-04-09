from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from langserve import add_routes
from api import ingestion, retrieval, agent, google_auth_routes

# Initialize FastAPI app
app = FastAPI(title="AutoRAG Tool")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import API routers
app.include_router(ingestion.router)
app.include_router(retrieval.router)
app.include_router(agent.router)
app.include_router(google_auth_routes.router, prefix="/google")

# Import utils
from utils.vectorstore import load_vectorstore

# Load the vectorstore (will create an empty one if needed)
try:
    vectorstore = load_vectorstore()
    print("Vectorstore loaded successfully")
except Exception as e:
    print(f"Error loading vectorstore: {e}")
    from utils.vectorstore import create_empty_vectorstore
    vectorstore = create_empty_vectorstore()
    print("Created new empty vectorstore instead")

# Import retrieval chain for LangServe
from api.retrieval import rag_chain

# Add LangServe
add_routes(app, rag_chain, path="/rag")

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to AutoRAG Tool API"}

# Run the app if executed directly
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 