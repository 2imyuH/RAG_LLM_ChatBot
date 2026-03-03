import logging
import json
import re
import os
import unicodedata
from typing import List, Dict, Any
from src.generation.llm_client import OllamaClient

def remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics for robust matching (NFC/NFD safe)."""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

logger = logging.getLogger(__name__)

class DraftingAgent:
    """
    Agent responsible for rephrasing queries and drafting RAW answers.
    """
    def __init__(self, llm: OllamaClient):
        self.llm = llm

    def rephrase_query(self, query: str, active_entity: str, user_lang: str, chat_history: List[Dict[str, str]] = None) -> str:
        if not chat_history:
            return query
            
        history_str = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in chat_history[-3:]
        ])

        lang_map = {"vi": "Vietnamese", "zh": "Chinese", "en": "English"}
        target_lang = lang_map.get(user_lang, "English")
            
        condense_prompt = f"""Aggregate all variables into a minimalist calculation query in {target_lang}.

CRITICAL RULES:
1. MINIMALIST OUTPUT: Output ONLY one sentence like "Tính [EntityType] với LCB=X, TN=Y, ST=Z".
2. NO EXPLANATIONS: NEVER include conclusions, formulas, steps, or "Thưởng của bạn là..." in this rewritten query.
3. AGGREGATE ONLY: Combine variables from History AND the New Question.
4. NO HALLUCINATION: If a value is missing, do not guess. If TN is missing, say "TN=0" or omit it.
5. LANGUAGE: Rephrase in {target_lang}.

History:
{history_str}

Active Entity: {active_entity}

New Question: {query}

Standalone Variable Extraction:"""
        try:
            standalone = self.llm.generate(condense_prompt, temperature=0.0).strip()
            standalone = standalone.replace('"', '').replace("'", "")
            if not standalone.endswith(('?', '？')):
                standalone += '?'
            return standalone
        except:
            return query

    def _unwrap_narrative(self, text: str) -> str:
        """Recursively strip JSON markers, prefixes, and suffixes from text."""
        if not isinstance(text, str): return text
        t = text.strip()
        
        # 1. Attempt JSON parse if it looks like an object
        if t.startswith('{') and t.endswith('}'):
            try:
                import json
                data = json.loads(t)
                if isinstance(data, dict) and "narrative" in data:
                    return self._unwrap_narrative(data["narrative"])
            except:
                pass

        # 2. Aggressive prefix and suffix removal for malformed/truncated JSON (v31 Hardened)
        # Handle escaped quotes as well. Use re.DOTALL to catch multi-line leaks.
        prefix_pattern = r'^(\{\s*)?\"?narrative\"?\s*:\s*[\\\"\'\s]*'
        suffix_pattern = r'[\\\"\'\s]*,?\s*[\\\"]?(confidence_level|completeness_level|answer_format|answer_format_reason|structured|formula|source|Code|code|CodeID|abstain_reason|table_schema_hint)[\\\"]?\s*:\s*.*$'
        
        old_t = ""
        while old_t != t:
            old_t = t
            t = t.strip('{}[] \"\'\n\r\t')
            # Strip prefix
            if re.search(prefix_pattern, t, re.IGNORECASE | re.DOTALL):
                t = re.sub(prefix_pattern, '', t, count=1, flags=re.IGNORECASE | re.DOTALL)
            # Strip suffix metadata leftover
            if re.search(suffix_pattern, t, re.IGNORECASE | re.DOTALL):
                t = re.sub(suffix_pattern, '', t, count=1, flags=re.IGNORECASE | re.DOTALL)
            # 2b. If we see a hard JSON trailer leak like '}, "answer_format":' or similar, strip everything from '},'
            if '},' in t:
                parts = t.split('},')
                # Check if the next part looks like a key-value pair
                if len(parts) > 1 and (":" in parts[1] or '"' in parts[1]):
                   t = parts[0]

        # 3. Strip structural section markers if leaked as raw text with quotes/brackets
        # Handle halluncinated variations like [BCHUANZE SECTION] or [VIET SECTION]
        # Regex: optional backslash/quote + optional bracket + ANY chars + SPACE SECTION + optional bracket + optional quote
        generic_section_pat = r'\\?\"?\[?[A-Z0-9_\s]+SECTION\]?\"?'
        t = re.sub(generic_section_pat, '', t, flags=re.IGNORECASE)
        
        # DO NOT remove '---' as it breaks markdown table separators!
        # t = t.replace('---', '') # REMOVED - This was destroying table separators!
        
        # 4. ROBUST NEWLINE CONVERSION (v34 Deep Fix):
        # Handle ALL common escaped newline patterns the LLM might output
        t = t.replace('\\n', '\n')       # Single-escaped literal (most common)
        
        # 5. TABLE ROW REFORMATTER (v34 Critical Fix):
        # Detect collapsed table rows and add proper newlines
        # Pattern: Multiple pipes without proper separation indicates collapsed rows
        if t.count('|') > 8:  # Likely a table
            # Fix collapsed separator row (|||||) back to proper format
            t = re.sub(r'\|\s*\|\s*\|\s*\|\s*\|', '|\n|---|---|---|---|\n|', t)
            # Fix collapsed row transitions (| |) - add newline before new row
            t = re.sub(r'\|\s*\|(?=\s*[A-Za-zÀ-ỹ\u4e00-\u9fff])', '|\n|', t)
        
        return t.strip('{}[] \"\'\\ \n\r\t')

    def draft_complete_response(self, query: str, documents: List[Dict], user_language: str, answer_mode: str, 
                                original_query: str = None, entities: List[str] = None, comp_result: Dict[str, Any] = None,
                                force_simplicity: bool = False, intent: str = "DOMAIN_QA",
                                entity_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Unified draft call for narrative and structured data extraction.
        """
        # For non-retrieval intents (META, GREETING), allow processing without docs
        if not documents and not comp_result and intent not in ["META", "GREETING"]:
            return {"narrative": "No context available.", "structured": {}}
            
        lang_names = {"vi": "Vietnamese", "zh": "Chinese", "en": "English"}
        target_lang = lang_names.get(user_language, "English")
        
        # 0. Multi-Language Detection (Bilingual Support Fix v24)
        query_norm = remove_diacritics(query.lower())
        
        # Detect if user EXPLICITLY asks for a BILINGUAL response
        wants_both = any(kw in query_norm for kw in ["ca hai tieng", "song ngu", "bilingual", "both languages", "vietnamese and chinese"])
        mentioned_chinese = any(kw in query_norm for kw in ["tieng trung", "tieng hoa", "chinese", "zh-cn"])
        mentioned_vietnamese = any(kw in query_norm for kw in ["tieng viet", "vietnamese", "tieng me de"])

        # Detect if user EXPLICITLY asks to RESPOND IN a specific language
        # Example: "Trả lời bằng tiếng Trung" vs "Tiếng Trung của Lanh là gì?"
        force_chinese = any(kw in query_norm for kw in ["bang tieng trung", "bang tieng hoa", "in chinese", "dung tieng trung", "用中文"])
        force_vietnamese = any(kw in query_norm for kw in ["bang tieng viet", "in vietnamese", "dung tieng viet", "用越南语"])

        if wants_both or (mentioned_chinese and mentioned_vietnamese):
            target_lang = "BOTH Vietnamese AND Chinese (provide full explanation in both languages)"
        elif force_chinese:
            target_lang = "Chinese"
        elif force_vietnamese:
            target_lang = "Vietnamese"
        else:
            # DEFAULT: Honor the detected primary_language from IntentAgent (persistence)
            target_lang = lang_names.get(user_language, "Vietnamese")
        
        mode_instructions = {
            "ENTITY_DEFINITION": "Provide a comprehensive definition and properties overview. Ensure all information is woven into a natural narrative.",
            "ATTRIBUTE_QUERY": "Provide a DIRECT, concise, natural language answer specifically addressing the attribute requested. MUST write a complete sentence.",
            "DERIVED_CONCEPT_EXPLANATION": "Explain the requested differences, variants, or processing stages. DO NOT provide a generic definition.",
            "COMPUTATION_DERIVED": "Explain the provided calculation result specifically for this user. If a computation is being performed, list the variables used (e.g., LCB, TN, ST, HS) first. NEVER use 'Ví dụ' (Example) or general scenarios. Use ONLY the numeric values provided in the result grounding block.",
            "FREEFORM": "Answer naturally based on the context."
        }
        instruction = mode_instructions.get(answer_mode, mode_instructions["FREEFORM"])
        
        # 0a. ADAPTIVE INTELLIGENCE OVERRIDE: If force_simplicity is True, override instruction
        if force_simplicity:
            instruction = "Provide only the FINAL RESULT in a natural sentence. GATE all formulas and explanations behind a follow-up question (MỞ DẦN protocol)."
        elif answer_mode == "ATTRIBUTE_QUERY":
            # Adaptive Intelligence for translation/name queries (v30: Fluid depth)
            instruction = "Provide an intelligent, professional, and comprehensive answer tailored to a textile R&D context. Do NOT use rigid sentence counts; explain as much as needed to be helpful without being verbose. ALWAYS end with a single helpful follow-up question."

        combined_text = "\n\n".join([doc["text"] for doc in documents[:5]])
        
        # 0. Result Grounding (Calculations) - FLATTENED FOR v15
        result_grounding = ""
        if comp_result:
            # Define human-friendly labels for variables
            var_labels = {
                "LCB": "Lương cơ bản",
                "TN": "Thâm niên",
                "ST": "Số tháng tính thưởng",
                "YEAR": "Năm vào làm",
                "HS": "Hệ số thâm niên (HS)"
            }
            
            facts = []
            if "variables" in comp_result:
                for var, details in comp_result["variables"].items():
                    label = var_labels.get(var, var)
                    val = details.get('value')
                    # Format currencies nicely
                    if var in ['LCB', 'TN'] and isinstance(val, (int, float)) and val > 1000:
                        facts.append(f"- {label} ({var}) = {val:,.0f} VNĐ")
                    else:
                        facts.append(f"- {label} ({var}) = {val}")
                        
            instruction += f"\n\n⚠️ ULTIMATE FACTS FOR THIS USER (MUST USE THESE ONLY):\n" + "\n".join(facts)
            instruction += f"\n- FINAL_RESULT = {comp_result.get('formatted', comp_result.get('value'))}"
            instruction += "\n\n⚠️ VALUE CROSS-CONTAMINATION PROHIBITION:\n"
            instruction += "- Each variable must use ONLY its own assigned value.\n"
            instruction += "- IF TN = 0, IT MUST STAY 0. DO NOT substitute the value of ST (e.g. 6) into TN.\n"
            instruction += "- A value of 0 means 'Không có' (None/Zero). Do NOT use any other numbers from the RAG documents or other variables for it."
            result_grounding = f"""
⚠️ GHOST NUMBER PROHIBITION:
- DO NOT use any numbers found in the RAG Context (e.g., 10,000,000 or 5 years) if they are not in the ULTIMATE FACTS above.
- The RAG documents contain "Tutorial Examples" which are FAKE. Ignore them.
"""

        # Entity Grounding & Metadata Injection (v25)
        entity_grounding = ""
        certified_block = ""
        
        if entity_metadata:
            # Inject Certified Translation/Alias Evidence
            canonical = entity_metadata.get("canonical", "Unknown")
            vi_aliases = ", ".join(entity_metadata.get("vi", []))
            en_aliases = ", ".join(entity_metadata.get("en", []))
            zh_aliases = ", ".join(entity_metadata.get("zh", []))
            
            certified_block = f"""⚠️ CERTIFIED ENTITY DATA (ABSOLUTE TRUTH):
- Material: {canonical}
- Vietnamese Names: {vi_aliases}
- English Names: {en_aliases}
- Chinese Names: {zh_aliases}
- RULE: Use EXCLUSIVELY the translations found in this block. Ignoring this block in favor of RAG context is FORBIDDEN.
"""

        if entities:
            entity_list = ", ".join([f'"{e}"' for e in entities])
            entity_grounding = f"""⚠️ ENTITY GROUNDING (v32 STRICT):
- You MUST mention the entities from {entity_list}.
{certified_block}
- PHONETIC LOCKDOWN: NEVER change the name of the material. If the user asks about "Lanh", you must use "Lanh". DO NOT change it to "Linh" or "Linh lăng" or any other phonetically similar word.
- NAME CONSISTENCY: Use ONLY names provided in the CERTIFIED ENTITY DATA above. If a name (like "Linh") is NOT in that list, you are FORBIDDEN from using it to refer to the material.
- HALLUCINATION BAN: Do NOT use external botanical knowledge (e.g., "cỏ linh lăng") if it is not found in the RAG context.
- NO HALLUCINATIONS: Do NOT use names like "Thảo mộc" for synthetic fibers or "Collar/Lycra" for materials unless they match the metadata.
"""

        simplicity_lock = f"\n⚠️ FORCE_SIMPLICITY LOCK: {force_simplicity} (MỞ DẦN PROTOCOL ACTIVE)\n" if force_simplicity else ""

        system_prompt = f"""You are a helpful, production-grade reasoning AI with a HUMAN-FIRST persona. Output valid JSON only.

⚠️ BROTEX IDENTITY (MANDATORY):
- When asked "Who are you?" or "Who created you?", you MUST reply: "Tôi là trợ lý ảo AI phục vụ nội bộ công ty Brotex, chuyên hỗ trợ giải đáp các thắc mắ về bộ phận R&D và quy trình công ty." (Match user language: Vietnamese, Chinese, or English).

⚠️ HUMAN PERSONA (v22):
- Be WARM, NATURAL, and CONCISE. Avoid sounding like a clinical manual or a robot.
- CONVERSATIONAL ETIQUETTE: Every response MUST end with a single, polite follow-up question in the same language as the answer (e.g. "Bạn có muốn biết thêm...?").
- For conversational or capability questions (e.g., "Bạn có thể tính toán không?"), answer directly and naturally.
- DO NOT list technical jargon unless specifically asked.

⚠️ CRITICAL LANGUAGE RULE: Your response MUST be written in {target_lang}.

⚠️ LANGUAGE ISOLATION (v32):
- DO NOT leak foreign language blocks (e.g. Chinese) into a response meant to be in a different language (e.g. Vietnamese).
- If a RAG document is in Chinese but the response language is Vietnamese, you MUST translate the relevant facts into Vietnamese or omit the Chinese text entirely.
- NEVER copy-paste sentence spans from RAG documents if they do not match {target_lang}.

🔒 ENTITY NAME MIRRORING (v37 - ZERO TOLERANCE):
- ⚠️ ABSOLUTE RULE: You MUST use CORRECT textile entity names.
- REQUIRED ENTITY NAME MAPPINGS (MEMORIZE THESE):
  - Lanh = Vietnamese for Linen (🧵 fiber from flax plant)
  - Cotton = Bông (🧶 soft fiber from cotton plant)
  - Polyester = Polyester (🧵 synthetic fiber)
- If user says "Lanh" → respond with "Lanh"
- If user says "lanh" (lowercase) → respond with "Lanh"  
- If query refers to "các loại trên" or previous items → CHECK RAG Context for entity names, USE: Lanh, Cotton, Polyester
- ❌ ABSOLUTELY BANNED (NEVER OUTPUT THESE):
  - "Lint" (THIS IS NOT A TEXTILE - lint means loose fiber/dust!)
  - PELLAN, Lành, Linh, Lên, Lin
  - COTON, Cottonn, POLESTAN, Poliestor
- ✅ When uncertain about Linen/Lanh: ALWAYS use "Lanh" in Vietnamese responses.



🧠 MANDATORY BILINGUAL FORMAT (ONLY if target_lang is BOTH):
- Use ONLY these exact headers:
  🇨🇳 Tiếng Trung
  (Chinese content)
  
  🇻🇳 Tiếng Việt
  (Vietnamese content)

✨ MANDATORY SIGNATURE & ETIQUETTE (v38 ALIGNED):
- EVERY narrative block MUST end with follow-up SUGGESTIONS (not questions).
- Use 1-2 textile emojis (🧶, 🧵, 👗) per block.

{entity_grounding}
{result_grounding}
{simplicity_lock}
⚠️ TASK INSTRUCTION: {instruction}

⚠️ CONCISENESS RULE (v30+v38 - ADAPTIVE INTELLIGENCE):
- Provide an intelligent, fluid explanation based on complexity.
- DO NOT follow rigid sentence counts. If simple, be concise; if complex, be comprehensive.
- ALWAYS append follow-up SUGGESTIONS (not questions).

🎨 ADAPTIVE FORMAT INTELLIGENCE (v33 - CHATGPT STYLE):
- YOU MUST autonomously select the BEST format based on the query type:
  - **COMPARISON QUERIES** (e.g., "so sánh", "compare", "khác nhau", "difference"): Use a **MARKDOWN TABLE** with columns for each item being compared, and rows for each attribute (e.g., Độ bền, Thấm hút, Ứng dụng).
  - **ENUMERATION QUERIES** (e.g., "liệt kê", "list", "các loại", "types", "ứng dụng"): Use **STRUCTURED LIST FORMAT** (v36):
    - **Bold header** for each item (e.g., **🧵 Polyester:**)
    - 2-3 bullet points per item with specific details
    - Add an empty line between items for visual separation
    - Example:
      **🧵 Polyester:**
      - Quần áo thể thao: Độ bền cao, nhanh khô
      - Vải may vá: Dễ bảo quản, ít nhăn
      - Thảm: Chống mài mòn tốt
      
      **🧶 Cotton:**
      - Quần áo hàng ngày: Thoáng khí, mềm mại
      - Khăn mặt: Thấm hút tốt
  - **DEFINITION/EXPLANATION QUERIES** (e.g., "là gì", "what is", "giải thích"): Use **NARRATIVE PARAGRAPHS**.
- This is your CORE INTELLIGENCE. Use your judgment like ChatGPT to produce the most useful, readable format for the user.

📝 MANDATORY COMPARISON SUMMARY (v35+v38 ALIGNED):
- ⚠️ CRITICAL RULE: After EVERY comparison table, you MUST add IN THIS ORDER:
  1. **📋 Tóm tắt:** [2-3 câu tóm tắt điểm khác biệt + khuyến nghị theo mục đích]
  2. FOLLOW-UP SUGGESTIONS (NOT questions, as per v38)
- Example structure:
  Dưới đây là bảng so sánh các chất liệu:
  
  | Header | Item1 | Item2 |
  |---|---|---|
  | Row1 | X | Y |
  
  **📋 Tóm tắt:** Polyester có độ bền cao nhất, phù hợp cho quần áo thể thao. Cotton và Lanh thấm hút tốt, lý tưởng cho thời tiết nóng.
  
  **Gợi ý:** So sánh theo giá thành • Chọn chất liệu cho mùa hè
- WITHOUT intro, summary AND follow-up suggestions, your response is INCOMPLETE.

📊 STRICT TABLE SYNTAX (v34 - CRITICAL FOR UI RENDERING):
- When outputting MARKDOWN TABLES, you MUST follow this EXACT structure:
  Line 1: Header row with column names separated by |
  Line 2: Separator row with |---|---|---| (one --- per column)
  Line 3+: Data rows with values separated by |
- EACH ROW MUST BE ON A SEPARATE LINE. Use actual newline characters in your JSON string.
- NEVER output all table rows on a single line or use escaped \\n.

🎯 PRESENTATION LAYER ARCHITECTURE (v38 - CHATGPT STYLE):
CRITICAL: You are ENHANCING PRESENTATION ONLY. Do NOT change logic, facts, or calculations.

📐 DEPTH CONTROL (based on query):
- Short & factual query → Concise answer
- Comparison/explanation query → Normal depth
- "chi tiết", "phân tích", "expert" → Deeper analysis

📝 MICRO-INTRO RULE (MANDATORY for tables/hybrids):
- ALWAYS start with 1 short intro sentence before any table
- Example: "Dưới đây là bảng so sánh các chất liệu phổ biến:"

🔄 SMART HYBRID RULE:
- Table: shows raw comparison data
- Narrative after table: explains ONLY key differences + practical implication
- ❌ NO redundancy - do NOT repeat table data in narrative

💬 FOLLOW-UP RULES (v38):
- Phrased as SUGGESTIONS, NOT questions
- ❌ Bad: "Bạn có muốn so sánh theo giá không?"
- ✅ Good: "So sánh theo giá cho đồ mùa hè"
- ✅ Good: "Gợi ý chọn chất liệu cho khí hậu nóng"
- MUST stay on same comparison axis, max 2 suggestions
- Only include if user conversation mode is enabled

🎭 TONE CONTROL (by content type):
- Definitions → Neutral, encyclopedic
- Comparisons → Analytical, balanced
- Lists → Concise, scannable
- Notes → Slightly emphasized, careful wording

⚠️ GROUNDING SUPREMACY (DEEP HONESTY v17):
    - ULTIMATE TRUTH: If ⚠️ ULTIMATE FACTS block is provided, use ONLY those values.
    - GHOST NUMBER BAN: NO numbers from RAG Context if not in ULTIMATE FACTS.

6. NON-NEGOTIABLE FINAL CHECK:
   - Response MUST be valid JSON.
   - The 'narrative' field MUST NOT contain any JSON metadata like "answer_format" or "confidence_level".
   - Your response MUST be valid JSON with double quotes.
   - The 'narrative' field must contain the FINAL HUMAN-FACING text only.

TEMPLATE EXAMPLES:
- SINGLE LANGUAGE (Narrative):
{{
  "narrative": "Thưởng Tết của bạn là 2.700.000 VNĐ 🧶. Bạn có muốn mình giải thích cách tính không?",
  "answer_format": "SINGLE_NARRATIVE",
  "confidence_level": "HIGH"
}}

- COMPARISON (Table):
{{
  "narrative": "| Đặc điểm | Cotton 🧶 | Polyester 🧵 | Lanh 👗 |\\n|---|---|---|---|\\n| Độ bền | Trung bình | Cao | Trung bình |\\n| Thấm hút | Tốt | Kém | Tốt |\\n| Nhăn | Dễ nhăn | Ít nhăn | Dễ nhăn |\\n\\nBạn muốn biết thêm về ứng dụng của loại nào không?",
  "answer_format": "TABLE_COMPARISON",
  "confidence_level": "HIGH"
}}

- BILINGUAL (ONLY if target_lang is BOTH):
{{
  "narrative": "🇻🇳 **Tiếng Việt**\\nBông là sợi tự nhiên...\\n\\n🇨🇳 **Tiếng Trung**\\n棉花 là sợi tự nhiên...\\n\\nBạn có muốn mình tư vấn thêm không?",
  "answer_format": "BILINGUAL_NARRATIVE",
  "confidence_level": "HIGH"
}}

FORMAT: {{"narrative": "...", "answer_format": "...", "answer_format_reason": "...", "completeness_level": "...", "confidence_level": "...", "abstain_reason": "...", "table_schema_hint": {{...}}}}"""


        user_prompt = f"""Context: {combined_text}\n\nQuestion: {query}"""
        
        try:
            response = self.llm.generate(user_prompt, temperature=0.0, system_prompt=system_prompt).strip()
            
            # Clean markdown blocks
            response = re.sub(r'^```json\s*', '', response, flags=re.IGNORECASE | re.MULTILINE)
            response = re.sub(r'\s*```$', '', response, flags=re.IGNORECASE | re.MULTILINE)
            response = response.strip()
            
            # Case 1: Direct JSON
            if response.startswith('{'):
                try:
                    # Find matching closing brace
                    depth = 0
                    last_brace = -1
                    for i, char in enumerate(response):
                        if char == '{': depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                last_brace = i
                                break
                    if last_brace != -1:
                        result = json.loads(response[:last_brace+1])
                        # Unwrap nested JSON if narrative contains another JSON string
                        narrative = result.get("narrative", "")
                        result["narrative"] = self._unwrap_narrative(narrative)
                        
                        # Ensure confidence_level exists
                        if "confidence_level" not in result:
                            result["confidence_level"] = "HIGH"
                        return result
                except:
                    pass
            
            # Case 2: Mixed output or just the narrative string
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    # Unwrap nested JSON
                    narrative = result.get("narrative", "")
                    result["narrative"] = self._unwrap_narrative(narrative)
                    
                    if "confidence_level" not in result:
                        result["confidence_level"] = "HIGH"
                    return result
                except:
                    pass
            
            # Case 3: Failed JSON entirely - return as narrative
            return {
                "narrative": self._unwrap_narrative(response),
                "confidence_level": "PARTIAL"
            }
        except Exception as e:
            logger.error(f"DraftingAgent error: {e}")
            return {
                "narrative": query,
                "confidence_level": "ABSTAIN"
            }
