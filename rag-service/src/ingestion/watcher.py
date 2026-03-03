import time
import logging
import sys
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src import config
from src.ingestion.loader import load_file
from src.ingestion.text_splitter import RecursiveCharacterTextSplitter
from src.retrieval.vector_db import VectorDB

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IngestionHandler(FileSystemEventHandler):
    def __init__(self, db: VectorDB, splitter: RecursiveCharacterTextSplitter):
        self.db = db
        self.splitter = splitter
        self.supported_extensions = {".pdf", ".txt", ".md", ".docx"}

    def _process_file(self, file_path: str):
        path = Path(file_path)
        if path.suffix.lower() not in self.supported_extensions:
            return

        logger.info(f"Processing file: {file_path}")
        text = load_file(file_path)
        if not text:
            logger.warning(f"No text extracted from {file_path}")
            return

        chunks = self.splitter.split_text(text)
        if not chunks:
            logger.warning(f"No chunks created for {file_path}")
            return

        # Prepare metadata and IDs
        metadatas = [{"source": file_path, "chunk_id": i} for i in range(len(chunks))]
        ids = [f"{path.name}_{i}" for i in range(len(chunks))]

        # Delete existing first to avoid stale chunks (simple approach)
        self.db.delete_document(file_path)
        
        # Add new
        self.db.add_documents(documents=chunks, metadatas=metadatas, ids=ids)
        logger.info(f"Successfully processed {file_path}: {len(chunks)} chunks.")

    def on_created(self, event):
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        logger.info(f"File deleted: {event.src_path}")
        self.db.delete_document(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        logger.info(f"File moved from {event.src_path} to {event.dest_path}")
        self.db.delete_document(event.src_path)
        self._process_file(event.dest_path)

def start_watcher():
    # Ensure data directory exists
    if not config.DATA_DIR.exists():
        config.DATA_DIR.mkdir(parents=True)
        logger.info(f"Created data directory: {config.DATA_DIR}")

    logger.info("Initializing Vector DB...")
    db = VectorDB()
    
    logger.info("Initializing Text Splitter...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP
    )

    event_handler = IngestionHandler(db, splitter)
    observer = Observer()
    observer.schedule(event_handler, str(config.DATA_DIR), recursive=True)
    
    observer.start()
    logger.info(f"Watching directory: {config.DATA_DIR}")
    
    # Process existing files on startup
    logger.info("Scanning existing files...")
    for ext in event_handler.supported_extensions:
        for file_path in config.DATA_DIR.rglob(f"*{ext}"):
             event_handler._process_file(str(file_path))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watcher()
