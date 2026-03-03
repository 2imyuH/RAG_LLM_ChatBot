import re
from typing import List

class RecursiveCharacterTextSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, separators: List[str] = None):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = separators or ["\n\n", "\n", ".", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Split text into chunks."""
        final_chunks = []
        if not text:
            return []

        separator = self._separators[-1]
        for sep in self._separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        # If we reached the character level or empty separator
        if separator == "":
            # Simple character splitting
            return [text[i : i + self._chunk_size] for i in range(0, len(text), self._chunk_size - self._chunk_overlap)]

        splits = text.split(separator)
        good_splits = []
        
        # Merge splits if possible
        _separator = "" if separator == "" else separator
        current_chunk = []
        current_length = 0
        
        for split in splits:
            if current_length + len(split) + len(_separator) > self._chunk_size:
                if current_chunk:
                    doc = _separator.join(current_chunk)
                    if current_chunk:
                         good_splits.append(doc)
                    
                    # Start new chunk with overlap? 
                    # Simplified: just reset. Complex overlap logic is tricky without deque.
                    # For now, let's keep it simple: no strict overlap preservation on reset 
                    # unless we implement a sliding window.
                    # Re-implementing sliding window for simplicity:
                    
                    while current_length > self._chunk_overlap and current_chunk:
                         current_length -= (len(current_chunk[0]) + len(_separator))
                         current_chunk.pop(0)
                    
                    if current_length + len(split) + len(_separator) > self._chunk_size:
                         # Still too big even after popping? Force split?
                         # For now, just clear if it's too big, or if the single split is huge, we recurse on it.
                         current_chunk = []
                         current_length = 0

            # Check if individual split is too big
            if len(split) > self._chunk_size:
                # Recurse
                sub_chunks = self.split_text(split)
                good_splits.extend(sub_chunks)
            else:
                current_chunk.append(split)
                current_length += len(split) + len(_separator)
        
        if current_chunk:
            good_splits.append(_separator.join(current_chunk))

        return good_splits
