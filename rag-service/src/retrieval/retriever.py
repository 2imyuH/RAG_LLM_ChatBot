import logging
from typing import List, Dict, Tuple
from sentence_transformers import CrossEncoder
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src import config
from src.retrieval.vector_db import VectorDB

logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self, db: VectorDB = None):
        self.db = db if db else VectorDB()
        logger.info(f"Loading Reranker: {config.RERANKER_MODEL_NAME}")
        self.reranker = CrossEncoder(config.RERANKER_MODEL_NAME, max_length=512)
        logger.info("Reranker loaded successfully")

    def retrieve(self, query: str, top_k: int = None, skip_rerank: bool = False, top_k_rerank: int = None) -> List[Dict]:
        top_k = top_k or config.TOP_K_RETRIEVAL
        top_k_rerank = top_k_rerank or config.TOP_K_RERANK
        
        # 1. Vector Search
        results = self.db.query(query, n_results=top_k)
        
        if not results['documents'] or not results['documents'][0]:
            return []

        # Flatten results
        candidates = []
        try:
            num_docs = len(results['documents'][0])
            for i in range(num_docs):
                 doc_text = results['documents'][0][i]
                 
                 metadata = {}
                 if results.get('metadatas') and len(results['metadatas']) > 0 and results['metadatas'][0]:
                     if i < len(results['metadatas'][0]):
                        metadata = results['metadatas'][0][i]

                 candidates.append({
                     "text": doc_text,
                     "metadata": metadata
                 })
        except Exception as e:
            logger.error(f"Error parsing retrieval results: {e}")
            return []

        # 2. Reranking (Skip if requested or no candidates)
        if not candidates:
            return []
            
        if skip_rerank:
            logger.info(f"Skipping reranking for query: {query}")
            return candidates[:top_k_rerank]
            
        # CrossEncoder expects pairs of (query, doc_text)
        pairs = [[query, doc["text"]] for doc in candidates]
        scores = self.reranker.predict(pairs)
        
        # Attach scores
        for i, score in enumerate(scores):
            candidates[i]["score"] = float(score)  # Convert numpy float to native

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Filter top rerank
        final_results = candidates[:top_k_rerank]
        logger.info(f"Retrieved and reranked {len(final_results)} documents for query: {query}")
        
        return final_results
