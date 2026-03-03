import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ReasoningLayer:
    """
    Concept Reasoning Layer (CRL): Lightweight layer to identify 
    relational, comparative, and derived-concept intent.
    """
    def __init__(self):
        pass

    def enrich_context(self, analysis: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Enriches the analysis result with derived concepts and relational metadata.
        Ensures domain-agnostic, language-driven reasoning.
        """
        mode = analysis.get("mode", "ENTITY_DEFINITION")
        derived_concepts = analysis.get("derived_concepts", [])
        
        # Language-driven signals for comparative/relational reasoning
        comparative_signals = ["khác nhau", "so sánh", "vs", "difference", "comparison"]
        
        query_lower = query.lower()
        if mode != "DERIVED_CONCEPT_EXPLANATION":
            if any(signal in query_lower for signal in comparative_signals):
                analysis["mode"] = "DERIVED_CONCEPT_EXPLANATION"
                logger.info(f"CRL: Upgraded mode to DERIVED_CONCEPT_EXPLANATION based on query signals")
        
        # Ensure derived_concepts is a list
        if not isinstance(derived_concepts, list):
            analysis["derived_concepts"] = []
            
        return analysis
