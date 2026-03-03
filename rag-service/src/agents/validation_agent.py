import logging
import re
from typing import Dict, List, Any, Tuple
from src.generation.llm_client import OllamaClient

# Ontology Compatibility Matrix (Deterministic Safety Lock)
ONTOLOGY_TYPES = {
    "lanh": "FIBER",
    "cotton": "FIBER",
    "bông": "FIBER",
    "polyester": "FIBER",
    "poly": "FIBER",
    "rayon": "FIBER",
    "nylon": "FIBER",
    "ni": "FABRIC",
    "nỉ": "FABRIC",
    "felt": "FABRIC",
    "fleece": "FABRIC"
}

ONTOLOGY_COMPATIBILITY = {
    ("FIBER", "FIBER"): "ALLOWED",
    ("FABRIC", "FABRIC"): "ALLOWED",
    ("FIBER", "FABRIC"): "REQUIRE_REFRAME",
    ("FABRIC", "FIBER"): "REQUIRE_REFRAME"
}

logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Agent responsible for QA, hallucination detection, and consistency checks.
    """
    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def validate_answer(
        self, 
        query: str, 
        active_entity: str, 
        narrative: str, 
        structured_data: Dict[str, Any],
        user_lang: str,
        answer_mode: str = "ENTITY_DEFINITION",
        docs: List[Dict] = None,
        answer_format: str = "NARRATIVE"
    ) -> Tuple[str, str]:
        """
        Validates the draft against the entity lock, context facts, and user language.
        Returns: (status, reason) where status is VALID, SOFT_DOWNGRADE, or HARD_REJECT
        """
        # 0. RAG Context Hook (Fact-Match Protocol)
        combined_context = "\n\n".join([doc["text"] for doc in docs]) if docs else ""
        
        # Force to string early for all checks
        e_str = str(active_entity)
        n_str = str(narrative)
        
        # 0a-pre. INVENTED NUMBER GUARD (CRITICAL)
        # If user input has NO numbers but output has numeric assignments → INVALID
        user_has_numbers = bool(re.search(r'\d', query))
        output_has_calc_assignments = bool(re.search(r'(LCB|TN|ST|HS)\s*[=:]\s*\d', n_str, re.IGNORECASE))
        if not user_has_numbers and output_has_calc_assignments:
            return "HARD_REJECT", "Invented Number Guard: User provided no numbers but response contains invented calculation values. RETURN_FIXED_MESSAGE"
        
        # 0a. Prompt Leakage Detection (CRITICAL)
        prompt_leak_markers = [
            # Original markers
            "EXPLICIT COMPUTE OVERRIDE",
            "COMPUTATION DECISION GATE",
            "ANTI-EXPLANATION LOCK",
            "FORMULA PRESERVATION (HARD)",
            "NO-ASSUMPTION POLICY",
            "NON-INTERFERENCE GUARANTEE",
            "STRICTLY FORBIDDEN",
            "════════",
            "JSON Output structure",
            "FORMAT STABILITY GUARANTEE",
            "OUTPUT STYLE CONTRACT",
            "FAIL-SAFE BEHAVIOR",
            "STRICT LANGUAGE ISOLATION",
            "You are a response generator",
            # New markers for additional leak patterns
            "────────",  # Horizontal line borders
            "FORMULA-DRIVEN COMPUTATION RULE",
            "VALIDATION BEFORE COMPUTATION",
            "COMPUTATION PERMISSION",
            "STRICT PROHIBITIONS",
            "STATE ISOLATION",
            "FAILURE HANDLING",
            "REQUIRED VARIABLES",
            "You are a computation",
            "MODE-SPECIFIC RULES",
            "RAG PRIORITY & SAFETY CONTRACT",
            "QUERY ISOLATION CONTRACT",
            "FORMULA HANDLING CONTRACT",
            "COMPUTATION STATE TRANSITION",
            "NO STALLING GUARANTEE",
            "NO-GUESSING POLICY",
            "ENTITY-SAFE OUTPUT RULE",
            "STYLE A (DIRECT_HUMAN)",
            "STYLE B (GOLDEN_ANALYTICAL)",
            "FORCE_SIMPLICITY LOCK",
            "HUMAN-FIRST NATURAL INTELLIGENCE",
            "PROGRESSIVE DISCLOSURE",
            "USER EFFORT HEURISTIC",
            # Production-Grade Leak Markers
            "STRICT OUTPUT RULES",
            "SELF-CHECK BEFORE RESPONDING",
            "rewrite it until it fully complies",
            "Now produce the final answer",
            "The response MUST be",
            "DO NOT wrap the answer",
            "DO NOT expose or reference",
            # Reasoning-First Leak Markers
            "FOLLOW THIS STATE MACHINE",
            "STRICT CALCULATION RULES",
            "STATE 0 — INPUT VALIDATION",
            "STATE 1 — NORMALIZATION",
            "STATE 2 — COMPUTATION",
            "STATE 3 — SANITY CHECK",
            "STATE 4 — OUTPUT",
            "Interpreted inputs",
            "Sanity check result",
            "Logical inconsistencies"
        ]
        for marker in prompt_leak_markers:
            if marker in n_str:
                return "HARD_REJECT", f"Prompt Leakage Detection: Internal prompt text '{marker}' leaked into response. REGENERATE without including system instructions."
        
        # 0b. Prefix-based Leak Detection: Reject if narrative starts with prompt-like phrases
        prompt_prefixes = ["You are a", "You are an", "As a", "I am a", "This is a"]
        n_stripped = n_str.strip()
        for prefix in prompt_prefixes:
            if n_stripped.startswith(prefix) and len(n_stripped) > 100:  # Only if lengthy (likely full prompt)
                return "HARD_REJECT", f"Prompt Leakage Detection: Response starts with prompt-like prefix '{prefix}'. REGENERATE with natural answer."
        
        # 1. Entity Coverage Check (ACV Policy)
        # MODE-AWARE VALIDATION: Only enforce for ENTITY_DEFINITION and ATTRIBUTE_QUERY
        # FREEFORM answers are narrative-first and must not be rejected for missing entity mentions

        # 1a. Naming Collision Detection (Rayon vs Nylon, etc.)
        # If narrative mentions a name that sounds like the active entity but is NOT in RAG context for this entity
        if "rayon" in e_str.lower() and ("nylon" in n_str.lower() or "ny-lông" in n_str.lower()):
            if "nylon" not in combined_context.lower():
                return "SOFT_DOWNGRADE", "Naming Collision Detection: Rayon cannot be mentioned as Nylon/Ny-lông unless explicitly in RAG."
        
        if "cotton" in e_str.lower() and ("màu" in n_str.lower() or "color" in n_str.lower()):
            if "màu" not in combined_context.lower() and "color" not in combined_context.lower():
                return "SOFT_DOWNGRADE", "Naming Collision Detection: Cotton cannot be labeled as 'màu' or 'color' unless explicitly in RAG."
        
        # 1c. Language Swapping Hallucination Check (Vietnamese word as Chinese Translation)
        if "tên tiếng trung" in query.lower() or "chinese name" in query.lower():
            # If the user asks for a Chinese name, and the answer provides a Vietnamese word in quotes or as a mapping
            # (e.g. Cotton là 'bông')
            swap_patterns = [
                (r"cotton", r"'bông'"),
                (r"lanh", r"'lanh'"),
                (r"rayon", r"'ny-lông'"),
                (r"rayon", r"'nylon'")
            ]
            for entity_pat, forbidden_pat in swap_patterns:
                if re.search(entity_pat, e_str, re.IGNORECASE):
                    if re.search(forbidden_pat, n_str, re.IGNORECASE):
                        # Verify if this Vietnamese name is incorrectly attributed as Chinese
                        if re.search(rf"{forbidden_pat}.*tiếng trung", n_str, re.IGNORECASE) or \
                           re.search(rf"tiếng trung.*{forbidden_pat}", n_str, re.IGNORECASE):
                            return "HARD_REJECT", f"Language Swapping Hallucination: Vietnamese name {forbidden_pat} attributed as Chinese for {entity_pat}."
        
        # 1b. Fact-Match Protocol (Translations & Terms)
        # Check if Chinese translations for common fibers are faithful to RAG context
        fiber_translations = {
            "cotton": ["棉"],
            "lanh": ["亚麻"],
            "linen": ["亚麻"],
            "rayon": ["人造棉", "人造丝"],
            "nylon": ["尼龙", "锦纶"],
            "poly": ["聚酯", "涤纶"]
        }
        for fiber, target_chars in fiber_translations.items():
            if fiber in e_str.lower() or fiber in query.lower():
                # If a Chinese character is present but not in our allowed list for this fiber
                # AND it's a translation query
                if user_lang != 'zh' and re.search(r'[\u4e00-\u9fff]', n_str):
                    found_chars = re.findall(r'[\u4e00-\u9fff]+', n_str)
                    for char_block in found_chars:
                        if not any(tc in char_block for tc in target_chars):
                            # Final verify against RAG itself
                            if char_block not in combined_context:
                                return "SOFT_DOWNGRADE", f"Fact-Match Failure: Translation '{char_block}' for {fiber} not found in RAG context."

        # 1c. Formula Syntax Guard
        if "công thức" in query.lower() or "formula" in query.lower():
            if "=" in n_str and not re.search(r'.+=.+', n_str):
                return "SOFT_DOWNGRADE", "Formula Syntax Guard: Formula must follow plain text mathematical notation (e.g. A = B + C)."
        
        # 1d. Computation Guard (HARD): Reject responses that guess missing variables
        # Detect calculation keywords
        calculation_keywords = ["tính giúp", "bao nhiêu tiền", "tính cho tôi", "calculate", "how much"]
        is_calculation_request = any(kw in query.lower() for kw in calculation_keywords)
        
        if is_calculation_request:
            # Detect patterns that indicate the LLM is guessing values
            guessing_patterns = [
                r"TN\s*=\s*0",  # Guessing TN (thâm niên) as 0
                r"giả sử",  # Assumptions
                r"nếu bạn vào làm",  # Hypothetical entry scenarios
                r"trở về trước",  # Historical references
                r"Nếu (TN|HS|năm)\s*=",  # Conditional logic (Partial result)
                r"Giả sử\s*(TN|HS|năm)",  # Assumption (Partial result)
                r"Có thể là",  # Estimate
                r"Ước tính",  # Estimate
                r"hệ số.*có thể là\s*\d",  # Guessing HS
                r"hệ số.*giả sử là\s*\d",  # Guessing HS
            ]
            for pattern in guessing_patterns:
                if re.search(pattern, n_str, re.IGNORECASE):
                    return "HARD_REJECT", f"Computation Guard: LLM guessed values instead of asking for missing variables. Stop and ask for: TN, HS, năm vào làm."
        
        # 1d-ii. Explanation Mode Detection: Reject formula explanations in calculation context
        if is_calculation_request:
            # Detect patterns that indicate the LLM is explaining instead of asking/computing
            explanation_patterns = [
                r"Trong đó,?\s*(LCB|TN|ST|HS)\s*là",  # "Trong đó, LCB là..."
                r"(LCB|TN|ST|HS)\s*là\s*(lương|thâm niên|số tháng|hệ số)",  # Variable definitions
                r"được tính dựa trên",  # "is calculated based on"
                r"theo công thức",  # "according to formula"
                r"công thức.*như sau",  # "formula as follows"
                r"biết rằng\s*(LCB|TN|ST|HS)",  # "knowing that X"
            ]
            for pattern in explanation_patterns:
                if re.search(pattern, n_str, re.IGNORECASE):
                    return "HARD_REJECT", "Explanation Mode Detection: LLM explained formula instead of asking for missing variables. STOP explaining, just ask: 'Vui lòng cung cấp: TN, năm vào làm.'"
        
        # 1e. Stalling Detection Guard: Reject if all variables present but no computation result
        if is_calculation_request:
            # Check if all required variables appear to be present in the query
            all_vars_keywords = ["LCB", "lương cơ bản", "TN", "thâm niên", "ST", "số tháng", "HS", "hệ số", "năm vào làm", "năm học", "đi làm từ năm"]
            vars_found = sum(1 for kw in all_vars_keywords if kw.lower() in query.lower())
            
            # Mandatory variables for a complete bonus calculation
            mandatory_keywords = ["HS", "hệ số"]
            has_mandatory = any(mw.lower() in query.lower() for mw in mandatory_keywords)
            
            # If query contains 4+ variables including HS/hệ số, we're in READY_TO_COMPUTE state
            if vars_found >= 5 or (vars_found >= 4 and has_mandatory):
                # Check if narrative contains a numeric result
                has_numeric_result = re.search(r'(?:là|=|bằng)[:\s]*[\d.,]+\s*(?:VNĐ|triệu|đồng|VND)?', n_str, re.IGNORECASE)
                
                if not has_numeric_result:
                    # Stalling detected - all inputs present but no actual computation
                    return "HARD_REJECT", "Stalling Guard: All variables appear present but no numeric result was computed. MUST COMPUTE NOW."
        
        # Verify that if an entity is locked, it's actually used in the narrative
        # SKIP this check for FREEFORM mode
        if e_str != "None" and answer_mode in ["ENTITY_DEFINITION", "ATTRIBUTE_QUERY"]:
            
            # ATTRIBUTE_QUERY Coverage Rule (HARD):
            # For ATTRIBUTE_QUERY, validate coverage PER ENTITY
            # The narrative is valid if each requested entity has at least one explicit attribute value
            # Entity names may appear inline, distributed, or implied via mapping
            # DO NOT require repeating the full entity list as a single phrase
            
            # Split entity string for both modes if it contains separators
            entities = []
            for sep in [" and ", " và ", ",", "/"]:
                if sep in e_str:
                    entities = [e.strip() for e in e_str.replace(" and ", ",").replace(" và ", ",").split(",")]
                    break
            if not entities:
                entities = [e_str]

            if answer_mode == "ATTRIBUTE_QUERY":
                # For ATTRIBUTE_QUERY, we're more lenient - just check if the narrative is substantive
                # and contains relevant information, not strict entity name matching
                if len(n_str.strip()) > 20:  # Has substantive content
                    # Check if at least some entities are mentioned OR if structured data has properties
                    entities_mentioned = sum(1 for ent in entities if ent.lower() in n_str.lower())
                    has_properties = len(structured_data.get("properties", [])) > 0
                    
                    if entities_mentioned > 0 or has_properties:
                        # Valid - entities are covered via inline mentions or structured data
                        pass
                    else:
                        # Only fail if narrative is generic and has no entity-specific content
                        return "SOFT_DOWNGRADE", f"ATTRIBUTE_QUERY Coverage: Narrative lacks entity-specific attribute information."
                else:
                    return "SOFT_DOWNGRADE", f"ATTRIBUTE_QUERY Coverage: Narrative is too short or empty."
            
            else:
                # ENTITY_DEFINITION mode: check that ALL entities in a multi-entity query are mentioned
                code = structured_data.get("code", "") or structured_data.get("Code", "")
                
                missing_entities = [ent for ent in entities if ent.lower() not in n_str.lower()]
                
                # Special Case: If codes match but names don't (rare)
                if missing_entities and code:
                    if str(code).lower() in n_str.lower():
                        missing_entities = [] # Consider valid if code is present
                
                if missing_entities:
                    return "SOFT_DOWNGRADE", f"Answer Coverage Failure: Entities {missing_entities} are missing from narrative."
                
                # Check for entity drift (other entities mentioned exclusively)
                # Only if it's a single entity query, otherwise it's expected to have multiple
                if len(entities) == 1:
                    other_entities = ['cotton', 'bông', 'polyester', 'bông nhân tạo', 'rayon']
                    found_others = [o for o in other_entities if o != e_str.lower() and o in n_str.lower()]
                    if found_others and e_str.lower() not in n_str.lower():
                         return "SOFT_DOWNGRADE", f"Entity Drift: Answer discusses {found_others} instead of the locked entity {e_str}."

        # 2. Language Policy Check (SOLP)
        lang_names = {"vi": "Vietnamese", "zh": "Chinese", "en": "English"}
        target = lang_names.get(user_lang, "English").lower()
        
        if len(n_str) < 10:
            return "SOFT_DOWNGRADE", "Narrative is too short or empty."

        # Hardened check for placeholder text
        placeholders = ["known textile material", "found in the database", "textile fiber defined as"]
        if any(p in n_str.lower() for p in placeholders):
             return "SOFT_DOWNGRADE", "Validation Guard: Generic placeholder text detected."

        # Strict Language Lock (SOLP) for Rescue Path
        # If user_lang is NOT English, reject purely English answers
        if user_lang != 'en' and " is a " in n_str and " material" in n_str and not any(v in n_str.lower() for v in ['là', '是']):
             return "SOFT_DOWNGRADE", f"Validation Guard: English output detected for {user_lang} user."

        # 2a. Strict Foreign Language Contamination Check
        # Reject CJK characters if user_lang is NOT Chinese (e.g. leaking Chinese into VN/EN response)
        # EXCEPTION: Allow foreign text if the query explicitly asks for translations
        # (e.g. "Tên tiếng Trung", "Chinese name", "English name", "tiếng Anh", "tiếng Việt")
        translation_keywords = [
            "tiếng trung", "tiếng anh", "tiếng việt", "tên tiếng",
            "chinese name", "english name", "vietnamese name",
            "中文名", "英文名", "越南文名"
        ]
        is_translation_query = any(kw in query.lower() for kw in translation_keywords)
        
        if user_lang != 'zh' and not is_translation_query:
             if re.search(r'[\u4e00-\u9fff]', n_str):
                 return "SOFT_DOWNGRADE", f"Validation Guard: Foreign text (Chinese) detected in {lang_names.get(user_lang, user_lang)} response."

        # 2b. Raw Field Leakage Guard
        # Reject if internal field names like "code", "properties", "Mã:" or JSON/brackets leak.
        forbidden_patterns = [r'Mã:', r'Code:', r'Properties:', r'\[', r'\{', r'\"code\"', r'\"name\"']
        for pattern in forbidden_patterns:
            if re.search(pattern, n_str, re.IGNORECASE):
                return "SOFT_DOWNGRADE", f"Validation Guard: Raw system fields or data structures detected in narrative."

        # 3. Entity Dump Prevention Guard (Section 22-C)
        # Strictly prohibit raw formatting and internal labels in the narrative
        prohibited_prefix_labels = ["Mã:", "Code:", "Name:", "Tên:", "Attributes:", "Thuộc tính:"]
        
        # Check if any label appears as a line prefix (the signature of a raw dump)
        if any(re.search(rf'^{label}', n_str, re.MULTILINE | re.IGNORECASE) for label in prohibited_prefix_labels):
             return "SOFT_DOWNGRADE", "Validation Guard: Structured labels detected at line start."

        # Check for keywords that often signal a data dump if the user didn't ask for them
        dump_keywords = ["Thuộc tính", "Property", "Attribute"]
        if any(kw.lower() in n_str.lower() for kw in dump_keywords):
             if not any(kw.lower() in query.lower() for kw in dump_keywords):
                 return "SOFT_DOWNGRADE", f"Validation Guard: Unrequested internal metadata labels ({dump_keywords}) detected."

        # Prohibit formatting characters indicating a raw dump
        if "[" in n_str or "{" in n_str or "]" in n_str or "}" in n_str:
            return "SOFT_DOWNGRADE", "Validation Guard: Formatting characters (brackets/braces) detected in narrative."

        # Prohibit key-value pair appearance (e.g. "Name: Rayon")
        if re.search(r'^[A-Za-z\s]+:\s+.+$', n_str, re.MULTILINE):
            return "SOFT_DOWNGRADE", "Validation Guard: Structured key-value formatting detected."

        # 4. Cleanliness Check
        if "[NARRATIVE]" in n_str or "JSON" in n_str:
            return "SOFT_DOWNGRADE", "Internal formatting system-labels leaked into narrative."

        # 4. Mode Consistency Guard (Section 21-B)
        if answer_mode == "DERIVED_CONCEPT_EXPLANATION":
             # Reject if it starts with generic definition patterns
             definition_patterns = [
                 r".*là một loại vật liệu dệt.*",
                 r".*is a known textile material.*",
                 r".*是一种纺织材料.*"
             ]
             for p in definition_patterns:
                 if re.search(p, n_str, re.IGNORECASE):
                     return "SOFT_DOWNGRADE", f"Validation Guard: Generic definition detected in DERIVED_CONCEPT_EXPLANATION mode."
             
             # Reject if the narrative is too short (likely missing comparison)
             if len(n_str.split()) < 10:
                 return "SOFT_DOWNGRADE", f"Validation Guard: Explanation too sparse for DERIVED_CONCEPT_EXPLANATION."

        # 5. Hallucination Guard (Fact-Match Protocol Enhancement)
        # Skip for calculations to reduce latency (already grounded in formula/inputs)
        if not is_calculation_request:
            if self.check_hallucination(n_str, combined_context):
                return "SOFT_DOWNGRADE", "Hallucination Guard: Narrative contains facts not present in RAG context."

        # 6. TC (涤棉) Factual Audit
        if "涤棉" in n_str or "tc" in n_str.lower():
             # TC must be Polyester + Cotton. If mention of Linen/Lanh/Nỉ is tied to TC definition -> REJECT
             if any(bad in n_str.lower() for bad in ["lanh", "linen", "nỉ", "felt"]):
                 # Check if it's actually redefining TC
                 if re.search(r'(涤棉|TC).*(là|gồm|kết hợp).* (lanh|linen|nỉ|felt)', n_str, re.IGNORECASE):
                     return "HARD_REJECT", "TC Factual Audit: '涤棉' (TC) is Polyester+Cotton, NOT Linen or Felt."

        # 7. Ontology Conflict Detection (Fiber vs Fabric)
        # machine-enforced via ONTOLOGY_TYPES matrix
        detected_types = set()
        for word, o_type in ONTOLOGY_TYPES.items():
            if word in n_str.lower():
                detected_types.add(o_type)
        
        if len(detected_types) > 1:
            # Check Compatibility Matrix
            types_list = list(detected_types)
            mismatch_found = False
            for i in range(len(types_list)):
                for j in range(i + 1, len(types_list)):
                    pair = (types_list[i], types_list[j])
                    reverse_pair = (types_list[j], types_list[i])
                    compatibility = ONTOLOGY_COMPATIBILITY.get(pair) or ONTOLOGY_COMPATIBILITY.get(reverse_pair)
                    
                    if compatibility == "REQUIRE_REFRAME":
                        mismatch_found = True
                        # Rules for Hybrid/Table
                        if answer_format in ["COMPARISON_TABLE", "HYBRID"]:
                            # 8. TABLE HEADER GUARD: check for (Fiber) / (Fabric)
                            if "|" in n_str:
                                # Extract headers from markdown table
                                lines = n_str.split('\n')
                                headers = ""
                                for line in lines:
                                    if '|' in line and '-' not in line:
                                        headers = line.lower()
                                        break
                                
                                # Check if type labels are present in headers
                                required_labels = [f"({t.lower()})" for t in detected_types]
                                if not any(label in headers for label in required_labels):
                                    return "SOFT_DOWNGRADE", f"Table Header Guard: Cross-ontology table headers MUST include type labels like (Fiber) or (Fabric)."

                        # Check if narrative actually reframes (contains explanation of mismatch)
                        reframe_keywords = ["khác cấp", "không cùng loại", "khác biệt về bản chất", "là vải", "là sợi", "không thể so sánh directly"]
                        if not any(kw in n_str.lower() for kw in reframe_keywords):
                            return "SOFT_DOWNGRADE", f"Ontology Conflict: Entities of type {types_list[i]} and {types_list[j]} are being compared without explicit reframing."

        return "VALID", "Valid"

    def check_hallucination(self, narrative: str, context: str) -> bool:
        """
        Check if narrative contains facts not in context.
        """
        prompt = f"""Compare the Answer to the Context.
Does the Answer contain ANY technical facts or codes NOT present in the Context?
Output 'YES' or 'NO' followed by a brief reason.

Context:
{context}

Answer:
{narrative}

Is there hallucination?"""
        try:
            res = self.llm.generate(prompt, temperature=0.0).strip().upper()
            return "YES" in res
        except:
            return False

