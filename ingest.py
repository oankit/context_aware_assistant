import os
import json
import logging
import uuid
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    JSONLoader,
    PyPDFLoader
)
from google.cloud import bigquery

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
    """Read files from a collection directory using LangChain document loaders."""
    documents = []
    
    if not collection_dir.exists():
        logger.warning(f"Directory {collection_dir} does not exist")
        return documents
    
    for file_path in collection_dir.glob("**/*"):
        if file_path.is_file():
            try:
                # Use appropriate LangChain loader based on file type
                file_str = str(file_path)
                
                if file_path.suffix.lower() == '.txt':
                    loader = TextLoader(file_str, encoding='utf-8')
                    langchain_docs = loader.load()
                    content = langchain_docs[0].page_content
                    logger.info(f"Loaded text file with TextLoader: {file_path}")
                    
                elif file_path.suffix.lower() == '.md':
                    loader = UnstructuredMarkdownLoader(file_str)
                    langchain_docs = loader.load()
                    content = langchain_docs[0].page_content
                    logger.info(f"Loaded markdown file with UnstructuredMarkdownLoader: {file_path}")
                    
                elif file_path.suffix.lower() == '.json':
                    # For JSON, we need to specify a jq-like string to identify the content
                    # This example assumes a simple structure, adjust as needed for your JSON files
                    loader = JSONLoader(
                        file_path=file_str,
                        jq_schema='.',
                        text_content=False
                    )
                    try:
                        langchain_docs = loader.load()
                        content = json.dumps(langchain_docs[0].page_content)
                        logger.info(f"Loaded JSON file with JSONLoader: {file_path}")
                    except Exception as json_err:
                        # Fallback to simple JSON loading if the structure doesn't match
                        logger.warning(f"JSONLoader failed, falling back to simple loading: {json_err}")
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = json.dumps(json.load(f))
                
                elif file_path.suffix.lower() == '.pdf':
                    # Load PDF files
                    loader = PyPDFLoader(file_str)
                    langchain_docs = loader.load()
                    
                    # Combine all pages into one document
                    content = "\n\n".join([doc.page_content for doc in langchain_docs])
                    
                    # Add page numbers to metadata
                    page_count = len(langchain_docs)
                    logger.info(f"Loaded PDF file with PyPDFLoader: {file_path} ({page_count} pages)")
                else:
                    logger.warning(f"Skipping unsupported file type: {file_path}")
                    continue
                
                # Extract metadata from filename or content
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
                logger.info(f"Successfully processed file: {file_path}")
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
    
    return documents

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks using LangChain's RecursiveCharacterTextSplitter."""
    # Convert chunk size from words to characters (approximate)
    avg_word_length = 5  # Average English word length
    char_size = chunk_size * avg_word_length
    
    # Create a text splitter with appropriate settings
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=char_size,
        chunk_overlap=50,  # Some overlap to maintain context between chunks
        length_function=len,
        separators=["\n\n", "\n", " ", ""]  # Try to split on paragraphs first, then newlines, then spaces
    )
    
    # Split the text
    chunks = text_splitter.split_text(text)
    logger.info(f"Split text into {len(chunks)} chunks using LangChain's RecursiveCharacterTextSplitter")
    
    return chunks

def fetch_hacker_news_data(limit: int = 1000) -> List[Dict[str, Any]]:
    """Fetches recent stories from the BigQuery Hacker News dataset."""
    logger.info("Fetching data from BigQuery Hacker News dataset...")
    documents = []
    try:
        client = bigquery.Client()
        # Example: Fetch titles and URLs of stories from the last 7 days
        # Adjust the query as needed (e.g., different table, columns, filters)
        query = f"""
            SELECT id, title, url, text, time_ts
            FROM `bigquery-public-data.hacker_news.stories`
            WHERE time_ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
              AND title IS NOT NULL
              AND url IS NOT NULL
            ORDER BY time_ts DESC
            LIMIT {limit}
        """
        query_job = client.query(query)  # Make an API request.

        logger.info(f"Executing BigQuery query: {query}")
        results = query_job.result()  # Waits for the job to complete.
        logger.info(f"Fetched {results.total_rows} rows from BigQuery.")

        for row in results:
            content = f"Title: {row.title}\n"
            if row.text:
                content += f"Text: {row.text}\n"
            if row.url:
                 content += f"URL: {row.url}"
                 
            # Convert timestamp to seconds since epoch
            story_time_unix = int(time.mktime(row.time_ts.timetuple())) if row.time_ts else int(time.time())

            metadata = {
                "source": f"bigquery-hacker_news-stories-{row.id}",
                "filename": str(row.id), # Use story ID as filename
                "title": row.title,
                "url": row.url,
                "date": story_time_unix, # Use story timestamp
                "category": "industry_news"
            }
            documents.append({
                "content": content.strip(),
                "metadata": metadata
            })

    except Exception as e:
        logger.error(f"Failed to fetch data from BigQuery: {e}")
        # Depending on requirements, you might want to raise the exception
        # or return an empty list / handle gracefully.

    logger.info(f"Formatted {len(documents)} documents from Hacker News.")
    return documents

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
        documents = [] # Initialize documents list
        if collection_name == "industry_news":
            # Fetch from BigQuery instead of local files for industry_news
            documents = fetch_hacker_news_data()
        else:
            # Process other collections from local files as before
            collection_dir = DATA_DIR / collection_name
            documents = read_files(collection_dir)

        if not documents:
            logger.warning(f"No documents found or fetched for {collection_name}")
            continue
        
        logger.info(f"Processing {len(documents)} documents for {collection_name}")
        
        # Process each document (common logic for all sources)
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
