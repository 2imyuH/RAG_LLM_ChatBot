"""
Smart Sync Synchronizer - Incremental ingestion with state tracking.

This module provides MD5-based file change detection to enable
incremental updates to ChromaDB, avoiding full re-ingestion.
"""
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Set, Tuple

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src import config
from src.ingestion.loader import load_file
from src.ingestion.text_splitter import RecursiveCharacterTextSplitter
from src.retrieval.vector_db import VectorDB

logger = logging.getLogger(__name__)


def normalize_path(file_path: str, base_dir: Path = None) -> str:
    """
    Normalize a file path to a relative path with forward slashes.
    
    This ensures consistency between Windows dev and Linux/Docker production.
    Example: D:\\Project\\data\\file.pdf -> file.pdf
    """
    base_dir = base_dir or config.DATA_DIR
    try:
        rel_path = os.path.relpath(file_path, start=str(base_dir))
    except ValueError:
        # On Windows, relpath fails if paths are on different drives
        rel_path = Path(file_path).name
    
    # Convert backslashes to forward slashes
    return rel_path.replace("\\", "/")


def compute_file_hash(file_path: str) -> str:
    """
    Compute MD5 hash of a file's content.
    
    Args:
        file_path: Absolute path to the file.
        
    Returns:
        MD5 hex digest string.
        
    Raises:
        PermissionError: If file is locked/in use.
        OSError: If file cannot be read.
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class Synchronizer:
    """
    State-aware synchronizer for incremental document ingestion.
    
    Tracks file hashes in a persistent JSON state file and only
    processes files that are new, modified, or deleted.
    """
    
    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
    
    def __init__(
        self,
        data_dir: Path = None,
        state_file: Path = None,
        db: VectorDB = None
    ):
        self.data_dir = data_dir or config.DATA_DIR
        self.state_file = state_file or config.INGESTION_STATE_FILE
        self.db = db  # Lazy init if not provided
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
    
    def _ensure_db(self):
        """Lazily initialize VectorDB if not already provided."""
        if self.db is None:
            logger.info("Initializing VectorDB...")
            self.db = VectorDB()
    
    def scan_data_directory(self) -> Dict[str, str]:
        """
        Scan the data directory and compute hashes for all supported files.
        
        Returns:
            Dict mapping normalized relative paths to MD5 hashes.
        """
        current_state = {}
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return current_state
        
        for ext in self.SUPPORTED_EXTENSIONS:
            for file_path in self.data_dir.rglob(f"*{ext}"):
                try:
                    normalized = normalize_path(str(file_path), self.data_dir)
                    file_hash = compute_file_hash(str(file_path))
                    current_state[normalized] = file_hash
                    logger.debug(f"Scanned: {normalized} -> {file_hash[:8]}...")
                except PermissionError:
                    logger.warning(f"File in use, skipping scan: {file_path}")
                except OSError as e:
                    logger.error(f"Error reading file {file_path}: {e}")
        
        logger.info(f"Scanned {len(current_state)} files from {self.data_dir}")
        return current_state
    
    def load_state(self) -> Dict[str, str]:
        """
        Load the persisted state from JSON file.
        
        Returns:
            Dict mapping normalized paths to hashes, or empty dict if no state.
        """
        if not self.state_file.exists():
            logger.info("No existing state file found. Starting fresh.")
            return {}
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                logger.info(f"Loaded state with {len(state)} entries")
                return state
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading state file: {e}. Starting fresh.")
            return {}
    
    def save_state(self, state: Dict[str, str]):
        """
        Atomically save state to JSON file.
        
        Uses write-to-temp-then-rename pattern for crash safety.
        """
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            dir=str(self.state_file.parent)
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            
            # Atomic rename (on Windows, need to remove existing first)
            if self.state_file.exists():
                self.state_file.unlink()
            os.rename(temp_path, str(self.state_file))
            
            logger.debug(f"State saved: {len(state)} entries")
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    
    def categorize_changes(
        self,
        current_state: Dict[str, str],
        saved_state: Dict[str, str]
    ) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
        """
        Categorize files into new, modified, deleted, and unchanged.
        
        Returns:
            Tuple of (new, modified, deleted, unchanged) sets of normalized paths.
        """
        current_files = set(current_state.keys())
        saved_files = set(saved_state.keys())
        
        new_files = current_files - saved_files
        deleted_files = saved_files - current_files
        
        common_files = current_files & saved_files
        modified_files = {
            f for f in common_files
            if current_state[f] != saved_state[f]
        }
        unchanged_files = common_files - modified_files
        
        logger.info(
            f"Changes: {len(new_files)} new, {len(modified_files)} modified, "
            f"{len(deleted_files)} deleted, {len(unchanged_files)} unchanged"
        )
        
        return new_files, modified_files, deleted_files, unchanged_files
    
    def _get_absolute_path(self, normalized_path: str) -> Path:
        """Convert normalized relative path back to absolute path."""
        return self.data_dir / normalized_path
    
    def _ingest_file(self, normalized_path: str) -> bool:
        """
        Ingest a single file into ChromaDB.
        
        Args:
            normalized_path: Normalized relative path (forward slashes).
            
        Returns:
            True if successful, False otherwise.
        """
        abs_path = self._get_absolute_path(normalized_path)
        
        try:
            # Load and extract text
            text = load_file(str(abs_path))
            if not text:
                logger.warning(f"No text extracted from: {normalized_path}")
                return False
            
            # Split into chunks
            chunks = self.splitter.split_text(text)
            if not chunks:
                logger.warning(f"No chunks created for: {normalized_path}")
                return False
            
            # Prepare metadata and IDs using normalized path as source
            metadatas = [
                {"source": normalized_path, "chunk_id": i}
                for i in range(len(chunks))
            ]
            ids = [f"{normalized_path}_{i}" for i in range(len(chunks))]
            
            # Add to ChromaDB
            self.db.add_documents(documents=chunks, metadatas=metadatas, ids=ids)
            logger.info(f"Ingested: {normalized_path} ({len(chunks)} chunks)")
            return True
            
        except PermissionError:
            logger.warning(f"File in use, skipping: {normalized_path}")
            return False
        except Exception as e:
            logger.error(f"Error ingesting {normalized_path}: {e}")
            return False
    
    def run(self):
        """
        Execute the Smart Sync process.
        
        1. Scan data directory for current files and hashes
        2. Load saved state
        3. Categorize changes
        4. Process deletions, then new/modified files
        5. Save state after each successful operation
        """
        logger.info("=" * 50)
        logger.info("Starting Smart Sync...")
        logger.info(f"Data Directory: {self.data_dir}")
        logger.info(f"State File: {self.state_file}")
        logger.info("=" * 50)
        
        self._ensure_db()
        
        # Step 1: Scan current state
        current_state = self.scan_data_directory()
        
        # Step 2: Load saved state
        saved_state = self.load_state()
        
        # Step 3: Categorize changes
        new_files, modified_files, deleted_files, unchanged_files = \
            self.categorize_changes(current_state, saved_state)
        
        # Track working state (copy to modify)
        working_state = saved_state.copy()
        
        # Step 4a: Handle DELETED files
        for normalized_path in deleted_files:
            logger.info(f"[DELETED] Removing vectors for: {normalized_path}")
            try:
                self.db.delete_by_source(normalized_path)
                del working_state[normalized_path]
                self.save_state(working_state)  # Atomic save after each success
            except Exception as e:
                logger.error(f"Error deleting {normalized_path}: {e}")
        
        # Step 4b: Handle MODIFIED files (delete old, then ingest new)
        for normalized_path in modified_files:
            logger.info(f"[MODIFIED] Re-ingesting: {normalized_path}")
            try:
                # Delete old vectors first
                self.db.delete_by_source(normalized_path)
                
                # Ingest new content
                if self._ingest_file(normalized_path):
                    working_state[normalized_path] = current_state[normalized_path]
                    self.save_state(working_state)
            except Exception as e:
                logger.error(f"Error updating {normalized_path}: {e}")
        
        # Step 4c: Handle NEW files
        for normalized_path in new_files:
            logger.info(f"[NEW] Ingesting: {normalized_path}")
            if self._ingest_file(normalized_path):
                working_state[normalized_path] = current_state[normalized_path]
                self.save_state(working_state)
        
        # Log unchanged files
        for normalized_path in unchanged_files:
            logger.debug(f"[UNCHANGED] Skipping: {normalized_path}")
        
        if unchanged_files:
            logger.info(f"Skipped {len(unchanged_files)} unchanged files")
        
        logger.info("=" * 50)
        logger.info("Smart Sync complete.")
        logger.info("=" * 50)


if __name__ == "__main__":
    # Standalone test
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sync = Synchronizer()
    sync.run()
