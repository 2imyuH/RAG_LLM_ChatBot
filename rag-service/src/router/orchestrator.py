import re
import json
import logging
import unicodedata
from typing import List, Dict, Any
from src.generation.llm_client import OllamaClient
from src.retrieval.retriever import Retriever
from src.agents.intent_agent import IntentAgent
from src.agents.drafting_agent import DraftingAgent
from src.agents.validation_agent import ValidationAgent
from src.agents.ux_agent import UXAgent
from src.agents.math_guard import compute as mathguard_compute
from src.agents.arithmetic_engine import ArithmeticEngine
from src.router.reasoning_layer import ReasoningLayer

def remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics for robust matching (NFC/NFD safe)."""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    The Control Plane: Coordinates all specialized agents.
    Does not generate user-facing text itself.
    """
    def __init__(self):
        self.llm = OllamaClient()
        self.retriever = Retriever()
        
        # Initialize Data Plane Agents
        self.intent_agent = IntentAgent(self.llm)
        self.drafting_agent = DraftingAgent(self.llm)
        self.validation_agent = ValidationAgent(self.llm)
        self.ux_agent = UXAgent(self.llm)
        self.reasoning_layer = ReasoningLayer()
        self.arithmetic_engine = ArithmeticEngine()
        
        # Slot-filling memory for MathGuard (session-level variable cache)
        self.mathguard_cache = {}
        
        logger.info("Orchestrator initialized successfully")

    def _arbitrate_intent(self, intent: str, query: str) -> str:
        """
        Deterministic arbitration of intent to prevent LLM routing errors.
        Ensures domain-specific nouns force business formula mode.
        """
        # Keyword list in normalized (no-diacritic) form
        domain_keywords = [
            "luong", "salary", "thue", "tax", "thuong", "bonus", 
            "kpi", "hop dong", "contract", "vat", "%", "bhxh", 
            "phu cap", "allowance", "he so", "hs", "tham nien", "tn",
            "so thang", "thang lam", "nam vao lam", "giai thich", "chi tiet", "cach tinh"
        ]
        
        # Normalize query (remove accents) for robust matching
        query_norm = remove_diacritics(query)
        has_business_kw = any(kw in query_norm for kw in domain_keywords)
        
        # 1. Force COMPUTATION_DERIVED if business keywords are found, regardless of LLM intent
        if has_business_kw:
            if intent != "COMPUTATION_DERIVED":
                logger.warning(f"Arbiter: Forcing COMPUTATION_DERIVED due to (normalized) domain keywords in query.")
            return "COMPUTATION_DERIVED"
            
        return intent

    def handle_query(self, user_query: str, chat_history: List[Dict[str, str]] = None, is_aborted=None) -> str:
        """
        Main entry point for handling a RAG query.
        is_aborted: a callable that returns True if the request should be cancelled.
        """
        def check_abort():
            if is_aborted and is_aborted():
                logger.warning("Orchestrator: Aborting query processing due to client disconnection.")
                raise InterruptedError("Query aborted by client")

        # CRITICAL: Preserve original query for MathGuard extraction
        original_query = str(user_query)
        
        # Step 1: Analysis
        check_abort()
        analysis = self.intent_agent.analyze_query(user_query, chat_history)
        
        # Language detection
        user_lang = analysis.get("primary_language", "vi")
        
        # Step 2: Intent Arbitration
        check_abort()
        intent = self._arbitrate_intent(analysis.get("intent", "GENERAL_QA"), user_query)
        answer_mode = analysis.get("mode", "FREEFORM")
        if intent == "COMPUTATION_DERIVED":
            answer_mode = "COMPUTATION_DERIVED"
        
        active_entity = str(analysis.get("entity", "None"))
        
        # Step 3: Reasoning Layer Enrichment
        check_abort()
        analysis = self.reasoning_layer.enrich_context(analysis, user_query)
        answer_mode = analysis.get("mode", answer_mode)
        
        # Step 4: Data Plane Execution
        check_abort()
        engine_res = None
        if intent == "SIMPLE_ARITHMETIC":
            engine_res = self.arithmetic_engine.compute(user_query)
        elif intent == "COMPUTATION_DERIVED":
            engine_res = mathguard_compute(original_query, formula_key=active_entity, cached_vars=self.mathguard_cache)
            if engine_res.get("status") == "SUCCESS":
                vars_found = engine_res.get("variables", {})
                for k, v in vars_found.items():
                    self.mathguard_cache[k] = v.get("value")

        # Step 5: Retrieval Phase
        check_abort()
        rephrased_query = user_query
        should_use_history = len(chat_history or []) > 0 and answer_mode != "ENTITY_DEFINITION"
        if should_use_history:
             rephrased_query = self.drafting_agent.rephrase_query(user_query, active_entity, user_lang, chat_history)

        # Step 5a: Adaptive Restraint Logic
        check_abort()
        force_simplicity = False
        if intent in ["SIMPLE_ARITHMETIC", "COMPUTATION_DERIVED"]:
            analytical_keywords = [
                "so sánh", "phân tích", "chi tiết", "bảng", "list", "compare", "analyze", "detail", "table",
                "giải thích", "hướng dẫn", "tại sao", "explain", "how", "why", "cách tính", "vi sao"
            ]
            if not any(kw in user_query.lower() for kw in analytical_keywords):
                force_simplicity = True

        docs = []
        can_retrieve = intent in ["DOMAIN_QA", "GENERAL_QA"] or (intent == "COMPUTATION_DERIVED" and not force_simplicity)
        if can_retrieve:
            docs = self.retriever.retrieve(rephrased_query, top_k=5)

        entity_meta = analysis.get("entity_metadata")

        # Step 6: Drafting Phase
        check_abort()
        draft_res = self.drafting_agent.draft_complete_response(
            user_query, docs, user_lang, answer_mode, 
            original_query=original_query, 
            entities=[e.strip() for e in active_entity.split(",") if e != "None"],
            comp_result=engine_res,
            force_simplicity=force_simplicity,
            intent=intent,
            entity_metadata=entity_meta
        )
        
        raw_narrative = draft_res.get("narrative", "")
        ans_format = draft_res.get("answer_format", "NARRATIVE")
        confidence = draft_res.get("confidence_level", "HIGH")
        structured_data = draft_res.get("structured", {})
        formula_meta = draft_res.get("formula", None)

        # Step 7: Validation Agent
        check_abort()
        v_status, reason = self.validation_agent.validate_answer(
            rephrased_query, active_entity, raw_narrative, structured_data, user_lang, answer_mode, docs,
            answer_format=ans_format
        )
        
        # Step 8: Decision Trace
        decision_trace = {
            "intent": intent,
            "engine": "MATH_GUARD" if intent == "COMPUTATION_DERIVED" else "RAG_ENGINE",
            "format_selected": ans_format,
            "ontology_check": "MISMATCH" if ("Ontology Conflict" in reason or "Table Header Guard" in reason) else "OK",
            "confidence_level": confidence,
        }
        logger.info(f"DECISION_TRACE: {json.dumps(decision_trace, ensure_ascii=False)}")

        # Step 9: Render
        check_abort()
        final_formula = formula_meta if not force_simplicity else None
        final_answer = self.ux_agent.render_final(raw_narrative, final_formula, user_lang)
        
        self.last_decision_trace = decision_trace
        return final_answer
