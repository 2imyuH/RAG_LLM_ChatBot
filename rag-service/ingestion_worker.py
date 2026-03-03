#!/usr/bin/env python3
"""
Ingestion Worker - Standalone service for file watching and document ingestion.
This runs as a separate process/container to avoid blocking the main RAG API.

Usage:
    python ingestion_worker.py          # Start real-time file watcher
    python ingestion_worker.py --sync   # Run one-shot incremental sync
"""
import sys
import os
import logging
import argparse

# Add src to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from src.ingestion.watcher import start_watcher
from src.ingestion.synchronizer import Synchronizer
from src import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="RAG Ingestion Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python ingestion_worker.py          # Start real-time watcher
    python ingestion_worker.py --sync   # Run incremental sync once
        """
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run one-shot Smart Sync (incremental) instead of real-time watcher"
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Starting Ingestion Worker...")
    logger.info(f"Data Directory: {config.DATA_DIR}")
    logger.info(f"ChromaDB Directory: {config.CHROMA_DB_DIR}")
    logger.info("=" * 50)

    if args.sync:
        # One-shot incremental sync mode
        logger.info("Mode: Smart Sync (Incremental)")
        try:
            sync = Synchronizer()
            sync.run()
            logger.info("Smart Sync complete.")
        except Exception as e:
            logger.error(f"Error during sync: {e}", exc_info=True)
            sys.exit(1)
    else:
        # Real-time watcher mode
        logger.info("Mode: Real-time File Watcher")
        try:
            start_watcher()
        except KeyboardInterrupt:
            logger.info("Ingestion Worker stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in Ingestion Worker: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()

