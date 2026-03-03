import os
from pathlib import Path
from typing import List

# Paths - Use environment variables with fallback to defaults
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
CHROMA_DB_DIR = Path(os.getenv("CHROMA_DB_DIR", str(PROJECT_ROOT / "chroma_db")))

# Model Settings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-base")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5:7b-instruct-q4_k_m")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Retrieval Settings
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "20"))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "5"))
MIN_RECALL_SCORE = float(os.getenv("MIN_RECALL_SCORE", "0.85"))

# Ingestion Settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
WATCH_PATTERNS = os.getenv("WATCH_PATTERNS", "*.pdf,*.txt,*.md,*.docx").split(",")
INGESTION_STATE_FILE = Path(os.getenv("INGESTION_STATE_FILE", str(PROJECT_ROOT / "ingestion_state.json")))

# API Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8005"))
