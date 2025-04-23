import os
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator

from agent import run_query

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
MAIN_SERVER_PORT = int(os.getenv("MAIN_SERVER_PORT", "8002"))

# Initialize FastAPI app
app = FastAPI(
    title="Context-Aware Assistant API",
    description="API for the context-aware assistant with RAG and MCP integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    final_answer: str
    rag_snippets: list
    tags: dict
    mcp_data: dict = None

@app.get("/")
async def root():
    """Root endpoint to check if the server is running."""
    return {"status": "ok", "message": "Context-Aware Assistant API is running"}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process a user query and return the response.
    
    Args:
        request: The query request
        
    Returns:
        The query response
    """
    user_query = request.query
    logger.info(f"Received query: {user_query}")
    
    try:
        # Process the query using the agent
        result = run_query(user_query)
        
        logger.info(f"Query processed successfully: {user_query}")
        return QueryResponse(
            query=result["query"],
            final_answer=result["final_answer"],
            rag_snippets=result["rag_snippets"],
            tags=result["tags"],
            mcp_data=result["mcp_data"]
        )
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Context-Aware Assistant API on port {MAIN_SERVER_PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=MAIN_SERVER_PORT, reload=True)
