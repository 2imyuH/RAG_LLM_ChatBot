import logging
import sys
import os

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.generation.rag import RAGEngine

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SystemTest")

def test_entity_purity():
    logger.info("TEST: Entity Purity (Rayon query)")
    engine = RAGEngine()
    
    query = "Rayon là gì ?"
    response = engine.query(query)
    
    logger.info(f"Response: {response}")
    
    if "polyester" in response.lower() or "poly" in response.lower():
        logger.error("FAILED: Polyester leaked into Rayon response!")
    elif "rayon" in response.lower() or "nhân tạo" in response.lower():
        logger.info("PASSED: Entity Purity Test")
    else:
        logger.warning("Response does not contain expected keywords, manual check required.")

if __name__ == "__main__":
    test_entity_purity()
