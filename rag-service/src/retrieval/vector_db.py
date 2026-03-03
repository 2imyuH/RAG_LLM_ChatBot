import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import logging
from typing import List, Dict, Optional
import sys
import os

# Add project root to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src import config

import os

logger = logging.getLogger(__name__)

from chromadb import EmbeddingFunction, Documents, Embeddings

class BGEM3EmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_name: str = None):
        model_name = model_name or config.EMBEDDING_MODEL_NAME
        logger.info(f"Loading embedding model: {model_name}")
        try:
            # Try loading from local cache first to avoid OfflineModeIsEnabled errors
            self.model = SentenceTransformer(model_name, local_files_only=True)
            logger.info("Embedding model loaded successfully (Local Cache)")
        except Exception as e:
            logger.warning(f"Local model load failed, attempting download: {e}")
            self.model = SentenceTransformer(model_name, local_files_only=False)
            logger.info("Embedding model loaded successfully (Downloaded)")
    
    def __call__(self, input: Documents) -> Embeddings:
        # BGE-M3 returns a dictionary for dense/sparse, but Chroma expects a list of floats (dense)
        # SentenceTransformer('BAAI/bge-m3').encode(sentences) returns dense embeddings by default
        embeddings = self.model.encode(input, normalize_embeddings=True)
        
        # Ensure it is a list of lists (2D)
        if len(embeddings.shape) == 1:
             embeddings = embeddings.reshape(1, -1)
             
        # Explicitly convert to python list of lists of floats
        result = embeddings.tolist()
        return result

    def name(self) -> str:
        return "BGEM3EmbeddingFunction"



class VectorDB:
    def __init__(self):
        logger.info(f"Initializing ChromaDB at: {config.CHROMA_DB_DIR}")
        # Ensure directory exists
        config.CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
        self.embedding_fn = BGEM3EmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="rag_documents",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("VectorDB initialized successfully")
    
    def add_documents(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        if not documents:
            return
        
        # ChromaDB requires batches for large inputs, but let's assume ingestion does batching or Chroma handles it
        # Actually Chroma handles 40kb+ batches reasonably well, but safe to batch if huge.
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Upserted {len(documents)} documents.")

    def delete_document(self, file_path: str):
        # We need to find chunks associated with this file_path.
        # We assume metadata contains 'source'
        self.collection.delete(
            where={"source": file_path}
        )
        logger.info(f"Deleted documents for source: {file_path}")

    def delete_by_source(self, source: str):
        """
        Delete all vectors associated with a source file.
        
        This is an alias for delete_document with clearer naming.
        The source should be a normalized path (relative, forward slashes).
        """
        self.collection.delete(where={"source": source})
        logger.info(f"Deleted vectors for source: {source}")

    def query(self, query_text: str, n_results: int = None) -> Dict:
        n_results = n_results or config.TOP_K_RETRIEVAL
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

if __name__ == "__main__":
    # Test
    db = VectorDB()
    print("VectorDB initialized.")
