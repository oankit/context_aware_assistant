import os
import json
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Whoosh imports for keyword search
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHUNK_SIZE = 200  # words per chunk
COLLECTIONS = [
    "broadcast_transcripts",
    "production_metadata",
    "technical_docs",
    "industry_news"
]
DATA_DIR = Path("data")
WHOOSH_INDEX_DIR = Path("whoosh_index")

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

def create_collections(client: chromadb.HttpClient) -> Dict[str, Any]:
    """Create collections in ChromaDB if they don't exist."""
    collections = {}
    for collection_name in COLLECTIONS:
        collections[collection_name] = client.get_or_create_collection(collection_name)
        logger.info(f"Collection '{collection_name}' ready")
    return collections

def read_files(collection_dir: Path) -> List[Dict[str, Any]]:
    """Read files from a collection directory."""
    documents = []
    
    if not collection_dir.exists():
        logger.warning(f"Directory {collection_dir} does not exist")
        return documents
    
    for file_path in collection_dir.glob("**/*"):
        if file_path.is_file():
            try:
                # Handle different file types
                if file_path.suffix.lower() in ['.txt', '.md']:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                elif file_path.suffix.lower() == '.json':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = json.dumps(json.load(f))
                else:
                    logger.warning(f"Skipping unsupported file type: {file_path}")
                    continue
                
                # Extract metadata from filename or content
                # This is a simple implementation - enhance as needed
                metadata = {
                    "source": str(file_path),
                    "filename": file_path.name,
                    "date": file_path.stat().st_mtime,  # Use file modification time as a fallback
                    "category": collection_dir.name
                }
                
                documents.append({
                    "content": content,
                    "metadata": metadata
                })
                logger.info(f"Read file: {file_path}")
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
    
    return documents

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks of approximately chunk_size words."""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    
    return chunks

def setup_whoosh_index() -> None:
    """Set up Whoosh index for keyword search."""
    if not WHOOSH_INDEX_DIR.exists():
        WHOOSH_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    
    schema = Schema(
        id=ID(stored=True, unique=True),
        content=TEXT(stored=True),
        source=ID(stored=True),
        category=ID(stored=True)
    )
    
    if not any(WHOOSH_INDEX_DIR.iterdir()):
        create_in(str(WHOOSH_INDEX_DIR), schema)
        logger.info(f"Created new Whoosh index in {WHOOSH_INDEX_DIR}")
    else:
        logger.info(f"Using existing Whoosh index in {WHOOSH_INDEX_DIR}")

def add_to_whoosh_index(doc_id: str, content: str, metadata: Dict[str, Any]) -> None:
    """Add a document to the Whoosh index."""
    try:
        ix = open_dir(str(WHOOSH_INDEX_DIR))
        writer = ix.writer()
        
        writer.add_document(
            id=doc_id,
            content=content,
            source=metadata.get("source", ""),
            category=metadata.get("category", "")
        )
        
        writer.commit()
    except Exception as e:
        logger.error(f"Error adding document to Whoosh index: {e}")

def process_and_index_data() -> None:
    """Main function to process and index all data."""
    # Connect to ChromaDB
    client = connect_to_chroma()
    collections = create_collections(client)
    
    # Set up Whoosh index
    setup_whoosh_index()
    
    # Process each collection
    for collection_name in COLLECTIONS:
        collection_dir = DATA_DIR / collection_name
        documents = read_files(collection_dir)
        
        if not documents:
            logger.warning(f"No documents found in {collection_dir}")
            continue
        
        logger.info(f"Processing {len(documents)} documents for {collection_name}")
        
        # Process each document
        for doc in documents:
            content = doc["content"]
            metadata = doc["metadata"]
            
            # Chunk the document
            chunks = chunk_text(content)
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                # Generate a unique ID
                doc_id = str(uuid.uuid4())
                
                # Update metadata with chunk info
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                chunk_metadata["total_chunks"] = len(chunks)
                
                # Generate embedding
                embedding = model.encode(chunk)
                
                # Add to ChromaDB
                collections[collection_name].add(
                    ids=[doc_id],
                    embeddings=[embedding.tolist()],
                    metadatas=[chunk_metadata],
                    documents=[chunk]
                )
                
                # Add to Whoosh index
                add_to_whoosh_index(doc_id, chunk, chunk_metadata)
                
                logger.debug(f"Indexed chunk {i+1}/{len(chunks)} from {metadata['source']}")
        
        logger.info(f"Completed indexing for {collection_name}")

if __name__ == "__main__":
    logger.info("Starting data ingestion process")
    process_and_index_data()
    logger.info("Data ingestion complete")
