#!/bin/bash
# Startup script for RAG API (Linux/Mac)
# For Windows, use: python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

export PROJECT_ROOT=$(pwd)
export DATA_DIR="${PROJECT_ROOT}/../data"
export CHROMA_DB_DIR="${PROJECT_ROOT}/../chroma_db"
export OLLAMA_BASE_URL="http://localhost:11434"

python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
