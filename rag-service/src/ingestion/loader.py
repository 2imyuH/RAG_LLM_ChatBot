import os
from pathlib import Path
import pypdf
import docx2txt
import logging

logger = logging.getLogger(__name__)

def load_file(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return ""

    try:
        if suffix == ".pdf":
            text = ""
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text
        
        elif suffix == ".docx":
            return docx2txt.process(file_path)
        
        elif suffix in [".txt", ".md"]:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
            
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return ""
            
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""
