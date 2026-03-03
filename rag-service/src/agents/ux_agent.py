import logging
import json
import re
from typing import Dict, Any, List
from src.generation.llm_client import OllamaClient

logger = logging.getLogger(__name__)

class UXAgent:
    """
    Agent responsible for final user-facing formatting and localization.
    """
    def __init__(self, llm: OllamaClient):
        self.llm = llm
        self._label_cache = {}

    def translate_labels_batch(self, labels: List[str], target_lang: str) -> Dict[str, str]:
        """
        Translates a list of labels in one LLM call.
        """
        if not labels:
            return {}
            
        untranslated = [L for L in labels if f"{L}_{target_lang}" not in self._label_cache]
        if not untranslated:
            return {L: self._label_cache[f"{L}_{target_lang}"] for L in labels}
            
        lang_map = {"vi": "Vietnamese", "zh": "Chinese", "en": "English"}
        target = lang_map.get(target_lang, "English")
        
        prompt = f"""Translate these field labels to {target}. 
Output ONLY a JSON object mapping original label to translation.

Labels: {untranslated}

JSON Output:"""
        try:
            response = self.llm.generate(prompt, temperature=0.0).strip()
            # Clean JSON
            response = re.sub(r'^```json\s*', '', response)
            response = re.sub(r'\s*```$', '', response)
            translations = json.loads(response)
            
            for orig, trans in translations.items():
                self._label_cache[f"{orig}_{target_lang}"] = trans
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")
            
        return {L: self._label_cache.get(f"{L}_{target_lang}", L) for L in labels}

    def _should_render_field(self, key: str, user_lang: str, answer_mode: str) -> bool:
        """
        Enforce SOLP: Filter multilingual fields unless explicitly requested.
        """
        key_lower = key.lower()
        
        # Language indicators in keys
        lang_indicators = {
            "vi": ["vietnamese", "tiếng việt", "vn"],
            "zh": ["chinese", "tiếng trung", "trung", "zh"],
            "en": ["english", "tiếng anh", "en"]
        }
        
        # If the key is language-specific
        is_lang_specific = False
        target_lang_found = False
        
        for lang, indicators in lang_indicators.items():
            if any(ind in key_lower for ind in indicators):
                is_lang_specific = True
                if lang == user_lang:
                    target_lang_found = True
                break
        
        if not is_lang_specific:
            return True
            
        # If it is lang specific, only show if it matches user lang
        # OR if it's an ATTRIBUTE_QUERY (user might be asking for a translation)
        if target_lang_found:
            return True
        if answer_mode == "ATTRIBUTE_QUERY":
            return True
            
        return False

    def render_final(self, narrative_draft: str, formula: str = None, user_lang: str = "vi") -> str:
        """
        Enforce Section 13 & 22: Narrative-Only Rendering.
        Strictly prohibits structured blocks, raw entity dumps, or labels.
        
        NEW: Global Output Contract compliance - renders formula separately if provided.
        """
        # 1. CLEANING: Remove internal formatting/JSON leaks
        narrative = str(narrative_draft)
        
        # Strip [NARRATIVE] tags if present
        if "[NARRATIVE]" in narrative:
            parts = narrative.split("[NARRATIVE]")
            if len(parts) > 1:
                narrative = parts[1].split("[END_NARRATIVE]")[0].strip()
        
        # Strip [ENTITY] debug tags only (Rule 22.B)
        # DO NOT strip all {} as they may be part of formulas
        narrative = re.sub(r'\[ENTITY\].*', '', narrative, flags=re.DOTALL).strip()
        
        # Strip specific internal labels (Section 22-C) only if they start a line
        internal_labels = ["Thuộc tính:", "Mã:", "Tên:", "Property Name:", "Code:", "Attribute:"]
        for label in internal_labels:
            narrative = re.sub(rf'^{label}\s*.*$', '', narrative, flags=re.MULTILINE | re.IGNORECASE)

        # 2. Final Sanity Check: Minimally clean control tags but PRESERVE mathematical symbols like [], {}
        narrative = narrative.replace("[NARRATIVE]", "").replace("[END_NARRATIVE]", "").strip()
        narrative = narrative.replace("[ENTITY]", "").strip()
        
        # 2b. Mathematical consistency is handled in the formula component, 
        # NOT in the narrative to preserve Markdown syntax (bolding, italics).
        
        # 3. FORMULA RENDERING (Global Output Contract)
        # If formula is provided, render it separately with proper formatting
        if formula and formula.strip() and formula.lower() != "null":
            # Clean and convert * to × for proper math display
            formula_clean = formula.strip().replace("*", "×")
            
            # Render formula block
            formula_intro = {
                "vi": "Công thức:",
                "en": "Formula:",
                "zh": "公式:"
            }
            intro = formula_intro.get(user_lang, "Formula:")
            
            # Combine narrative with formula
            final_output = f"{intro}\n\n{formula_clean}\n\n{narrative}"
            return final_output
        
        return narrative
