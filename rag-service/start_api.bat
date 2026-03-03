@echo off
REM Startup script for RAG API (Windows)

set PROJECT_ROOT=%~dp0
set DATA_DIR=%PROJECT_ROOT%..\data
set CHROMA_DB_DIR=%PROJECT_ROOT%..\chroma_db
set OLLAMA_BASE_URL=http://localhost:11434

python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8005
