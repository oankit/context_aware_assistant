import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Whoosh imports for keyword search
from whoosh.index import open_dir
from whoosh.qparser import QueryParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
WHOOSH_INDEX_DIR = "whoosh_index"
COLLECTIONS = [
    "broadcast_transcripts",
    "production_metadata",
    "technical_docs",
    "industry_news"
]

# Initialize embedder
model = SentenceTransformer('all-MiniLM-L6-v2')

def connect_to_chroma() -> chromadb.HttpClient:
    """Connect to ChromaDB instance."""
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        logger.info(f"Connected to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        raise

def get_collection(client: chromadb.HttpClient, collection_name: str) -> Any:
    """Get a collection from ChromaDB."""
    try:
        collection = client.get_collection(collection_name)
        return collection
    except Exception as e:
        logger.error(f"Failed to get collection '{collection_name}': {e}")
        return None

def vector_search(
    query_embedding: List[float],
    collection_name: str,
    k: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform vector search in ChromaDB.
    
    Args:
        query_embedding: The embedding vector of the query
        collection_name: The name of the collection to search in
        k: Number of results to return
        filter_metadata: Optional filter for metadata
        
    Returns:
        Dictionary containing search results
    """
    try:
        client = connect_to_chroma()
        collection = get_collection(client, collection_name)
        
        if collection is None:
            logger.warning(f"Collection '{collection_name}' not found")
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata
        )
        
        logger.info(f"Vector search in '{collection_name}' returned {len(results['ids'][0])} results")
        return results
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        return {"ids": [], "documents": [], "metadatas": [], "distances": []}

def keyword_search(query_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform keyword search using Whoosh.
    
    Args:
        query_text: The text query
        k: Number of results to return
        
    Returns:
        List of dictionaries containing search results
    """
    try:
        ix = open_dir(WHOOSH_INDEX_DIR)
        
        with ix.searcher() as searcher:
            query_parser = QueryParser("content", ix.schema)
            query = query_parser.parse(query_text)
            
            results = searcher.search(query, limit=k)
            
            search_results = []
            for result in results:
                search_results.append({
                    "id": result["id"],
                    "content": result["content"],
                    "source": result["source"],
                    "category": result["category"]
                })
            
            logger.info(f"Keyword search returned {len(search_results)} results")
            return search_results
    except Exception as e:
        logger.error(f"Error in keyword search: {e}")
        return []

def hybrid_search(
    query_text: str,
    collections: List[str] = COLLECTIONS,
    k: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining vector and keyword search.
    
    Args:
        query_text: The text query
        collections: List of collections to search in
        k: Number of results to return per collection
        filter_metadata: Optional filter for metadata
        
    Returns:
        List of dictionaries containing merged search results
    """
    try:
        # Generate embedding for the query
        query_embedding = model.encode(query_text).tolist()
        
        # Perform vector search across all specified collections
        vector_results = []
        for collection_name in collections:
            results = vector_search(query_embedding, collection_name, k, filter_metadata)
            
            # Process results
            if results["ids"] and results["documents"]:
                for i in range(len(results["ids"][0])):
                    vector_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None,
                        "source": "vector"
                    })
        
        # Perform keyword search
        keyword_results = keyword_search(query_text, k)
        processed_keyword_results = []
        for result in keyword_results:
            processed_keyword_results.append({
                "id": result["id"],
                "content": result["content"],
                "metadata": {
                    "source": result["source"],
                    "category": result["category"]
                },
                "distance": None,
                "source": "keyword"
            })
        
        # Merge results
        all_results = vector_results + processed_keyword_results
        
        # Remove duplicates based on ID
        unique_results = {}
        for result in all_results:
            if result["id"] not in unique_results:
                unique_results[result["id"]] = result
            elif result["source"] == "vector" and unique_results[result["id"]]["source"] == "keyword":
                # Prefer vector results if we have both
                unique_results[result["id"]] = result
        
        # Sort by distance (for vector results) and then by source
        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: (x["distance"] if x["distance"] is not None else float('inf'), x["source"])
        )
        
        # Limit to k results
        final_results = sorted_results[:k]
        
        logger.info(f"Hybrid search returned {len(final_results)} results")
        return final_results
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
        return []

def search_all_collections(
    query_text: str,
    k: int = 3,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search across all collections and return results grouped by collection.
    
    Args:
        query_text: The text query
        k: Number of results to return per collection
        filter_metadata: Optional filter for metadata
        
    Returns:
        Dictionary with collection names as keys and search results as values
    """
    results_by_collection = {}
    
    # Generate embedding for the query
    query_embedding = model.encode(query_text).tolist()
    
    for collection_name in COLLECTIONS:
        results = vector_search(query_embedding, collection_name, k, filter_metadata)
        
        # Process results
        processed_results = []
        if results["ids"] and results["documents"]:
            for i in range(len(results["ids"][0])):
                processed_results.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        
        results_by_collection[collection_name] = processed_results
    
    return results_by_collection

if __name__ == "__main__":
    # Simple test
    query = "example query"
    print(f"Testing hybrid search with query: '{query}'")
    results = hybrid_search(query)
    print(f"Found {len(results)} results")
    for i, result in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"Content: {result['content'][:100]}...")
        print(f"Source: {result['source']}")
        print(f"Distance: {result['distance']}")
        print(f"Metadata: {result['metadata']}")
