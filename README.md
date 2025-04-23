# Context-Aware Assistant

A sophisticated AI assistant with RAG (Retrieval-Augmented Generation) capabilities, content classification, and external API integration through MCP (Media Context Protocol).

## Features

- **Static RAG**: Retrieves relevant information from multiple collections of documents
- **Hybrid Search**: Combines vector search and keyword search for better results
- **Content Classification**: Automatically classifies content using zero-shot learning
- **External API Integration**: Connects to TheSportsDB API for live sports data
- **Modern Frontend**: React-based UI for interacting with the assistant
- **Containerized Deployment**: Docker and Docker Compose setup for easy deployment

## Project Structure

```
context_aware_assistant/
├── data/                      # Data directories for different collections
│   ├── broadcast_transcripts/
│   ├── production_metadata/
│   ├── technical_docs/
│   └── industry_news/
├── mcp_server/                # MCP server for external API integration
│   └── main.py
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── SearchBar.jsx
│   │   │   └── ResultsDisplay.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── whoosh_index/              # Directory for Whoosh keyword search index
├── ingest.py                  # Data processing and embedding script
├── retriever.py               # Retrieval logic for vector and keyword search
├── classifier.py              # Content classification using zero-shot learning
├── agent.py                   # Agent logic and LLM integration
├── main.py                    # Main backend API
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables
├── Dockerfile.backend         # Dockerfile for the backend
├── Dockerfile.mcp             # Dockerfile for the MCP server
├── Dockerfile.frontend        # Dockerfile for the frontend
└── docker-compose.yml         # Docker Compose configuration
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker and Docker Compose (for containerized deployment)

### Local Development Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd context_aware_assistant
   ```

2. Set up the Python virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Copy `.env.example` to `.env` (if available)
   - Update the `.env` file with your API keys and configuration

4. Run ChromaDB:
   ```
   docker run -d -p 8000:8000 --name chroma_db chromadb/chroma
   ```

5. Process and index data:
   ```
   python ingest.py
   ```

6. Start the MCP server:
   ```
   uvicorn mcp_server.main:app --reload --port 8001
   ```

7. Start the backend API:
   ```
   uvicorn main:app --reload --port 8002
   ```

8. Set up and run the frontend:
   ```
   cd frontend
   npm install
   npm run dev
   ```

### Docker Deployment

To deploy the entire application using Docker Compose:

```
docker-compose up -d
```

This will start all services:
- ChromaDB on port 8000
- MCP Server on port 8001
- Backend API on port 8002
- Frontend on port 80

## Usage

1. Open your browser and navigate to `http://localhost:3000` (for local development) or `http://localhost` (for Docker deployment)
2. Enter your query in the search bar
3. The assistant will retrieve relevant information, classify it, fetch live data if needed, and generate a response

## Adding Your Own Data

To add your own data to the system:

1. Place your text files, JSON files, or other supported formats in the appropriate data subdirectory:
   - `data/broadcast_transcripts/` for broadcast-related content
   - `data/production_metadata/` for production metadata
   - `data/technical_docs/` for technical documentation
   - `data/industry_news/` for news articles

2. Run the ingestion script to process and index the data:
   ```
   python ingest.py
   ```

## Customization

- **LLM Model**: You can change the LLM model in `agent.py` by updating the `model_name` variable
- **Embedding Model**: The embedding model can be changed in `ingest.py` and `retriever.py`
- **Classification Labels**: Update the `DEFAULT_LABELS` in `classifier.py` to customize content classification

## License

[MIT License](LICENSE)
