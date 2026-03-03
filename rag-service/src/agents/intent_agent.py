import re
import json
import os
import logging
import unicodedata
from typing import List, Dict, Literal, Tuple, Any
from src.generation.llm_client import OllamaClient

def remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics for robust matching (NFC/NFD safe)."""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

logger = logging.getLogger(__name__)

class IntentAgent:
    """
    Agent responsible for detecting language, intent, and the active entity.
    """
    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def analyze_query(self, query: str, chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Combined analysis call to reduce latency.
        Detects Intent, Entity, and Answer Mode in one LLM request.
        """
        history_str = ""
        if chat_history:
            history_str = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in chat_history[-3:]
            ])
            
        analysis_prompt = f"""Analyze this textile R&D query and select EXACTLY ONE category for each field.

Primary Language (CRITICAL):
- Detect the CONVERSATIONAL language the user is using to ASK the question.
- IGNORE quoted foreign terms or entity names when determining language.
- Example: "Rayon tên tiếng Trung của nó là 人造丝 thôi hả?" → primary_language="vi" (Vietnamese sentence structure, just mentioning Chinese term)
- Example: "人造丝是什么?" → primary_language="zh" (Chinese sentence)
- Options: "vi" (Vietnamese), "zh" (Chinese), "en" (English)

Intent:
- DOMAIN_QA: Questions about textile materials, definitions, properties, or processes.
- META: Assistant identity ("Who are you?"), greeting, or language settings.
- OUT_OF_SCOPE: Any topic completely unrelated to textiles.

Mode:
- ENTITY_DEFINITION: General questions about WHAT a material is (e.g. "Cotton là gì?").
- ATTRIBUTE_QUERY: Questions asking for a SPECIFIC property, code, or translation (e.g. "Kí hiệu là gì?").
- DERIVED_CONCEPT_EXPLANATION: Comparative queries (e.g. "khác nhau", "so sánh", "vs") or queries about variants, processing stages, or states (e.g. "SW", "tẩy trắng").
- COMPUTATION_DERIVED: Queries requiring numeric calculation based on a BUSINESS formula (e.g. "tính thưởng", "bằng bao nhiêu tiền", providing LCB/TN/ST values).
- SIMPLE_ARITHMETIC: Simple math calculations like "100 + 100", "5 * 6 bằng bao nhiêu", "tính 10 cộng 20". NO business context required.
- FREEFORM: Non-retrieval chat or meta-questions.


RULES (HARD):
1. ENTITY PRECEDENCE: Always prioritize the entity as written by the USER in the CURRENT query. NEVER replace with translated names (e.g. 'Lanh' -> 'Linen' is FORBIDDEN).
2. DEFINITION SUPREMACY: Queries like "X là gì?" or "What is X?" MUST always be Mode=ENTITY_DEFINITION.
3. ENTITY CONTINUITY (PRONOUN INHERITANCE):
   - Detect object-referencing pronouns: "nó", "cái đó" (Vietnamese), "it", "that" (English), "它" (Chinese)
   - If ALL conditions are met:
     a) Current query does NOT explicitly introduce a new entity
     b) A single, unambiguous entity was locked in the immediately preceding turn
     c) The pronoun is grammatically referential (not idiomatic/abstract)
   - THEN: Inherit the previous entity WITHOUT modification
   - Apply answer mode selection AFTER pronoun resolution
   - If pronoun + attribute keyword (e.g. "kí hiệu của nó"), use Mode=ATTRIBUTE_QUERY
   - PROHIBITIONS:
     * DO NOT generalize into a definition of the attribute itself
     * DO NOT reinterpret the pronoun as a new concept
     * DO NOT hallucinate unrelated domains
   - FAILURE: If pronoun could refer to multiple entities, return entity="AMBIGUOUS"
4. DERIVED CONCEPT DETECTION: Use Mode=DERIVED_CONCEPT_EXPLANATION if the query asks about comparisons, differences, or variants of an entity.
5. ATTRIBUTE_QUERY VALIDITY: Mode=ATTRIBUTE_QUERY only if a SPECIFIC attribute keyword (e.g. symbol, code, color, "kí hiệu", "mã", "tên") is explicitly in the query. If missing, use ENTITY_DEFINITION.
6. NO INFERENCE: Do not assume the user wants attributes (like symbols) if they only ask for a definition.
7. If Mode=ENTITY_DEFINITION, IGNORE history and extract entity from 'Query'.
8. DERIVED CONCEPTS: Extract any comparative terms or variants into a list 'derived_concepts'.
9. OUT_OF_SCOPE SAFETY: DO NOT assign intent=OUT_OF_SCOPE if ANY part of the query matches retrievable domain knowledge. When uncertain, prefer DOMAIN_QA over OUT_OF_SCOPE.
10. AMBIGUOUS ENTITY CONSTRAINT: DO NOT use entity="AMBIGUOUS" when the subject noun is explicit (e.g. company name, material name). Multiple attributes ≠ ambiguous entity. AMBIGUOUS is a LAST RESORT.
11. COMPUTATION_DERIVED DETECTION (HIGHEST PRIORITY):
   - REQUIRES BOTH: (a) calculation keywords ("tính", "bao nhiêu tiền", "calculate") AND (b) BUSINESS/FINANCIAL context (thưởng, lương, LCB, TN, ST, năm vào làm, salary)
   - Example COMPUTATION_DERIVED: "tính thưởng tết LCB 5tr", "năm 2021, lương 6tr, tính thưởng"
   - ⚠️ NOT COMPUTATION_DERIVED: Asking for translations, names, or attributes like "tên tiếng Trung là gì", "kí hiệu là gì" → Use ATTRIBUTE_QUERY instead
12. SIMPLE_ARITHMETIC DETECTION:
   - IF query is a simple math expression like "100 + 100", "5 * 6", "10 cộng 20" WITHOUT business formula context -> MUST use Mode=SIMPLE_ARITHMETIC.
13. ATTRIBUTE_QUERY PRIORITY: If query asks for "tên", "kí hiệu", "mã", "tiếng Trung", "tiếng Anh", "Chinese name", "symbol" → MUST use Mode=ATTRIBUTE_QUERY (even if multiple entities are mentioned).
14. ⚠️ ENTITY SCOPE SEPARATION (CRITICAL):
   - ENTITY DOMAIN RULES:
     * Mode=COMPUTATION_DERIVED → Entity MUST be financial domain: "Thưởng tết", "Lương", "Tiền thưởng"
     * Mode=ENTITY_DEFINITION/ATTRIBUTE_QUERY → Entity MUST be textile/material domain: material names from query
   - CONTEXT ISOLATION: DO NOT carry over entity from previous queries when subject domain changes
     * Example: Previous query about "Cotton, rayon" → Current query about "tính thưởng tết" → Entity should be "Thưởng tết", NOT "Cotton, rayon"
   - ALWAYS detect entity from the CURRENT query only, treat each query independently for entity extraction

History:
{history_str}

Query: {query}

JSON Output structure:
{{
  "primary_language": "vi",
  "intent": "DOMAIN_QA", 
  "entity": "Material Name", 
  "mode": "DERIVED_CONCEPT_EXPLANATION",
  "derived_concepts": ["term1", "term2"]
}}"""
        
        try:
            # 1. Local Lookup (FAST PATH)
            local_entity = self._local_entity_lookup(query)
            
            # 2. LLM Analysis
            response = self.llm.generate(analysis_prompt, temperature=0.0).strip()
            # Clean JSON
            response = re.sub(r'^```json\s*', '', response, flags=re.MULTILINE)
            response = re.sub(r'\s*```$', '', response, flags=re.MULTILINE)
            
            # Find the first { and last } to isolate JSON if LLM added chatter
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end != -1:
                response = response[start:end+1]
                analysis = json.loads(response)
            else:
                raise ValueError("No JSON block found")
            
            # Ensure it is a dict
            if not isinstance(analysis, dict):
                raise ValueError("Analysis result is not a dictionary")
            
            # Normalize selections (take the first one if LLM provided multiple)
            for key in ["intent", "mode"]:
                val = str(analysis.get(key, ""))
                if "|" in val:
                    analysis[key] = val.split("|")[0].strip()
                elif "," in val:
                     analysis[key] = val.split(",")[0].strip()
            
            # If local found, override LLM (more reliable)
            if local_entity:
                analysis["entity"] = local_entity["canonical"]
                analysis["entity_metadata"] = local_entity
            
            # FIX #4: HEURISTIC MODE OVERRIDE (Fail-Safe)
            # Force COMPUTATION_DERIVED if user explicitly asks to calculate bonus
            query_norm = remove_diacritics(query)
            query_lower = query.lower()
            calc_keywords = ["tinh", "bao nhieu", "calculate", "how much", "nhan duoc", "giai thich", "explain", "huong dan"]
            bonus_keywords = ["thuong", "bonus", "luong", "lcb", "tn", "luong co ban"]
            has_calc = any(kw in query_norm for kw in calc_keywords)
            has_bonus = any(kw in query_norm for kw in bonus_keywords)
            if has_calc and has_bonus:
                logger.info("IntentAgent: Forced COMPUTATION_DERIVED via Heuristic Override (Fix #4)")
                analysis["mode"] = "COMPUTATION_DERIVED"
                # Always use internal key for bonus calculation to bypass mapping issues
                analysis["entity"] = "bonus_tet"
            
            # FIX #5: SIMPLE_ARITHMETIC DETECTION (New Heuristic)
            # Detect simple math: "100 + 100", "5 * 6 bằng bao nhiêu"
            simple_math_pattern = r'\d+\s*[\+\-\*\/\×\÷]\s*\d+'
            vn_math_pattern = r'\d+\s*(cộng|trừ|nhân|chia)\s*\d+'
            is_simple_math = re.search(simple_math_pattern, query) or re.search(vn_math_pattern, query_lower)
            
            if is_simple_math and not has_bonus:
                # Simple arithmetic WITHOUT business context
                logger.info("IntentAgent: Forced SIMPLE_ARITHMETIC via Heuristic Override (Fix #5)")
                analysis["mode"] = "SIMPLE_ARITHMETIC"
                analysis["intent"] = "SIMPLE_ARITHMETIC"
            
            # CANONICAL ENTITY RESOLUTION (MANDATORY)
            # Collapse descriptive phrases to nearest canonical entity
            entity_str = str(analysis.get("entity", "None"))

            if entity_str != "None":
                # If entity is a descriptive phrase or composite name, extract the canonical entity
                # Examples: "Brotex Company Location and Working Hours" -> "Brotex"
                #           "Cotton Properties and Uses" -> "Cotton"
                
                # Check if it's a descriptive phrase (contains "and", "location", "hours", etc.)
                descriptive_indicators = [
                    "and", "location", "working hours", "properties", "uses",
                    "comparison", "difference", "variant", "process"
                ]
                
                is_descriptive = any(ind.lower() in entity_str.lower() for ind in descriptive_indicators)
                
                if is_descriptive:
                    # Try to extract canonical entity from the phrase
                    # First, check if any known entity is in the phrase
                    canonical = self._local_entity_lookup(entity_str)
                    if canonical:
                        logger.info(f"IntentAgent: Collapsed descriptive entity '{entity_str}' -> '{canonical}'")
                        analysis["entity"] = canonical
                    else:
                        # Fallback: take the first significant word
                        words = entity_str.split()
                        if words:
                            analysis["entity"] = words[0]
                            logger.info(f"IntentAgent: Collapsed descriptive entity '{entity_str}' -> '{words[0]}'")
                
            return analysis
        except Exception as e:
            logger.error(f"Analysis failed: {e}. Response was: {response if 'response' in locals() else 'None'}")
            return {
                "intent": "DOMAIN_QA",
                "entity": local_entity if 'local_entity' in locals() and local_entity else "None",
                "mode": "ENTITY_DEFINITION"
            }

    def _local_entity_lookup(self, query: str) -> Dict[str, Any]:
        """Fast local lookup in entities file. Returns a dict with {canonical, vi, en, zh}."""
        try:
            entity_file = os.path.join(os.getcwd(), "data", "rag_entities.txt")
            if not os.path.exists(entity_file):
                return None
                
            with open(entity_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            blocks = content.split("[ENTITY]")
            # Map of Alias -> full block metadata
            meta_map = {} 
            
            for block in blocks:
                if not block.strip(): continue
                entity_match = re.search(r'Entity:\s*([^\n\r]+)', block)
                if not entity_match: continue
                canonical_name = entity_match.group(1).strip()
                
                block_meta = {
                    "canonical": canonical_name,
                    "vi": [], "en": [], "zh": []
                }
                
                for field, key in [("Vietnamese", "vi"), ("English", "en"), ("Chinese", "zh")]:
                    field_match = re.search(rf'{field}:\s*([^\n\r]+)', block)
                    if field_match:
                        val = field_match.group(1).strip()
                        if val.lower() != "none":
                            aliases = [a.strip() for a in val.split(",")]
                            block_meta[key] = aliases
                            for alias in aliases:
                                if alias:
                                    clean_alias = re.sub(r'\(.*?\)', '', alias).strip()
                                    if clean_alias: meta_map[clean_alias.lower()] = block_meta
                                    meta_map[alias.lower()] = block_meta
                
                meta_map[canonical_name.lower()] = block_meta

            sorted_aliases = sorted(meta_map.keys(), key=len, reverse=True)
            query_lower = query.lower()
            query_norm = remove_diacritics(query_lower)
            
            for alias in sorted_aliases:
                alias_norm = remove_diacritics(alias)
                if alias in query_lower or alias_norm in query_norm:
                    if len(alias) < 3:
                        if re.search(rf'\b{re.escape(alias)}\b', query_lower) or \
                           re.search(rf'\b{re.escape(alias_norm)}\b', query_norm):
                            return meta_map[alias]
                    else:
                        return meta_map[alias]
            return None
        except Exception as e:
            logger.error(f"Local lookup error: {e}")
            return None

    # Keep old methods for compatibility but mark as deprecated or relay to analyze_query
    def detect_language(self, text: str) -> Literal["vi", "zh", "en"]:
        # Priority: Vietnamese > Chinese > English
        # This ensures that a Vietnamese question about Chinese terms is still Vietnamese
        text = text.strip()
        
        vietnamese_chars = ['ă', 'â', 'đ', 'ê', 'ô', 'ơ', 'ư', 'á', 'à', 'ả', 'ã', 'ạ',
                           'ấ', 'ầ', 'ẩ', 'ẫ', 'ậ', 'ắ', 'ằ', 'ẳ', 'ẵ', 'ặ',
                           'é', 'è', 'ẻ', 'ẽ', 'ẹ', 'ế', 'ề', 'ể', 'ễ', 'ệ',
                           'í', 'ì', 'ỉ', 'ĩ', 'ị', 'ó', 'ò', 'ỏ', 'õ', 'ọ',
                           'ố', 'ồ', 'ổ', 'ỗ', 'ộ', 'ớ', 'ờ', 'ở', 'ỡ', 'ợ',
                           'ú', 'ù', 'ủ', 'ũ', 'ụ', 'ứ', 'ừ', 'ử', 'ữ', 'ự',
                           'ý', 'ỳ', 'ỷ', 'ỹ', 'ỵ']
        
        # Check Vietnamese FIRST (higher priority)
        if any(char in text.lower() for char in vietnamese_chars): return "vi"
        
        vietnamese_words = ['là', 'gì', 'của', 'các', 'được', 'có', 'trong', 'này', 'cho', 'và', 'tên', 'thôi', 'hả', 'không', 'sao']
        if any(word in text.lower().split() for word in vietnamese_words): return "vi"
        
        # Check Chinese only if no Vietnamese detected
        if re.search(r'[\u4e00-\u9fff]', text): return "zh"
        
        return "en"
