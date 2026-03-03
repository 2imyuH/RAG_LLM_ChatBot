# RAG Service

Python FastAPI microservice for RAG (Retrieval-Augmented Generation) operations.

## Structure

```
rag-service/
├── src/
│   ├── api/           # FastAPI server
│   ├── generation/     # RAG engine and LLM client
│   ├── retrieval/      # Vector DB and retriever
│   ├── ingestion/     # File loading and text splitting
│   └── config.py      # Configuration (environment-based)
├── ingestion_worker.py # Standalone ingestion service
├── requirements.txt
├── Dockerfile
└── README.md
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATA_DIR`: Directory to watch for documents
- `CHROMA_DB_DIR`: ChromaDB persistence directory
- `OLLAMA_BASE_URL`: Ollama API endpoint (use `host.docker.internal:11434` in Docker)
- `EMBEDDING_MODEL_NAME`: Embedding model (default: BAAI/bge-m3)
- `LLM_MODEL_NAME`: LLM model name for Ollama

## Running Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables or create `.env` file

3. Run the API server:
```bash
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
```

4. Run ingestion worker (separate terminal):
```bash
python ingestion_worker.py
```

## Docker

Build:
```bash
docker build -t rag-service .
```

Run:
```bash
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  rag-service
```

## API Endpoints

- `GET /health` - Health check with status details
- `POST /chat` - Submit a query and get RAG response
- `GET /` - API information

## Notes

- Models are loaded once at startup (not per request)
- Ingestion worker should run separately to avoid blocking the API
- Ensure Ollama is running and accessible before starting the service
