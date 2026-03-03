import logging
from typing import Dict, List
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.router.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Production-grade RAG Entry Point.
    Following GPT/Gemini architecture: Control Plane (Orchestrator) + Data Plane (Specialized Agents).
    """
    def __init__(self):
        self.orchestrator = Orchestrator()
        logger.info("RAG Engine (Orchestrator Wrapper) initialized")

    def query(self, user_query: str, chat_history: List[Dict[str, str]] = None) -> str:
        """
        Coordinates the query through specialized agents.
        1. Detect intent, language, and entity lock.
        2. Rephrase query to standalone form.
        3. Retrieve relevant context.
        4. Draft internal RAW answer and extract structured data.
        5. Validate quality and self-correct if needed.
        6. Render final user-friendly output.
        """
        return self.orchestrator.handle_query(user_query, chat_history)