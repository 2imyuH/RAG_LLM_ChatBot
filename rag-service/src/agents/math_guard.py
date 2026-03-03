"""
MathGuard: Platform-Grade Deterministic Calculation Engine
Version: 2.0 (16-Point Architecture)

DESIGN PHILOSOPHY:
- LLM: Intent & Explanation ONLY. NO arithmetic.
- MathGuard: Single source of truth for all numeric computation.
- Orchestrator: Routing based on structured error codes.

CORE PRINCIPLES:
1. Grammar-independent tokenization (plugin-based)
2. Scoring-based role mapping (weighted proximity)
3. Type-safe variable assignment
4. Deterministic pure-function execution
5. Structured I/O contracts
"""

import re
import math
import logging
import unicodedata
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================================
# ERROR CODES (Structured Response Contract)
# ============================================================================
class ErrorCode(Enum):
    MISSING_VAR = "MISSING_VAR"
    AMBIGUOUS_VAR = "AMBIGUOUS_VAR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNKNOWN_FORMULA = "UNKNOWN_FORMULA"


# ============================================================================
# VALUE TYPES & TOKEN STRUCTURE
# ============================================================================
class TokenType(Enum):
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    INTEGER = "INTEGER"
    YEAR = "YEAR"
    DECIMAL = "DECIMAL"


@dataclass
class Token:
    """Grammar-independent numeric token with position tracking."""
    raw: str                    # Original string: "6tr9"
    value: float                # Normalized absolute value: 6_900_000
    token_type: TokenType       # CURRENCY, YEAR, INTEGER, etc.
    position: int               # Index in query string
    confidence: float = 1.0     # Extraction confidence
    unit: str = ""              # Original unit hint: "triệu", "%"
    
    def __repr__(self):
        return f"Token({self.raw}={self.value:,.0f}, type={self.token_type.value}, pos={self.position})"


@dataclass
class MappedVariable:
    """A token mapped to a formula variable."""
    var_name: str
    token: Token
    score: float                # Mapping confidence score
    keyword_matched: str = ""   # Which keyword triggered the match


# ============================================================================
# TOKENIZER PLUGINS (Grammar-Independent Extraction)
# ============================================================================
class TokenizerPlugin(ABC):
    """Base class for domain-specific tokenizers."""
    
    @abstractmethod
    def extract(self, query: str) -> List[Token]:
        """Extract tokens from query. Must return list of Token objects."""
        pass


class CurrencyTokenizer(TokenizerPlugin):
    """Extracts Vietnamese currency values (triệu, tr, nghìn, k)."""
    
    PATTERNS = [
        # "6tr9" -> 6.9 triệu = 6,900,000
        (r'(\d+)\s*(?:tr|triệu)\s*(\d)', 
         lambda m: (float(m.group(1)) + float(m.group(2)) / 10) * 1_000_000),
        # "6.9tr" or "6,9tr" -> 6,900,000
        (r'(\d+)[.,](\d+)\s*(?:tr|triệu)', 
         lambda m: float(f"{m.group(1)}.{m.group(2)}") * 1_000_000),
        # "6tr" -> 6,000,000
        (r'(\d+)\s*(?:tr|triệu)(?!\d)', 
         lambda m: float(m.group(1)) * 1_000_000),
        # "500k" or "500 nghìn" -> 500,000
        (r'(\d+)\s*(?:k|nghìn|nghin)', 
         lambda m: float(m.group(1)) * 1_000),
    ]
    
    def extract(self, query: str) -> List[Token]:
        tokens = []
        query_lower = query.lower()
        
        for pattern, converter in self.PATTERNS:
            for match in re.finditer(pattern, query_lower):
                try:
                    value = converter(match)
                    tokens.append(Token(
                        raw=match.group(0),
                        value=value,
                        token_type=TokenType.CURRENCY,
                        position=match.start(),
                        unit="VNĐ"
                    ))
                except (ValueError, IndexError):
                    continue
        
        return tokens


class YearTokenizer(TokenizerPlugin):
    """Extracts 4-digit years (2000-2099)."""
    
    PATTERN = r'\b(20\d{2})\b'
    
    def extract(self, query: str) -> List[Token]:
        tokens = []
        for match in re.finditer(self.PATTERN, query):
            year = int(match.group(1))
            tokens.append(Token(
                raw=match.group(0),
                value=float(year),
                token_type=TokenType.YEAR,
                position=match.start(),
                unit="năm"
            ))
        return tokens


class IntegerTokenizer(TokenizerPlugin):
    """Extracts small integers (1-99) for quantities like months."""
    
    PATTERN = r'\b(\d{1,2})\b'
    
    def extract(self, query: str) -> List[Token]:
        tokens = []
        # Exclude positions already matched by other tokenizers
        for match in re.finditer(self.PATTERN, query):
            val = int(match.group(1))
            # Only consider reasonable small integers (1-99)
            if 1 <= val <= 99:
                tokens.append(Token(
                    raw=match.group(0),
                    value=float(val),
                    token_type=TokenType.INTEGER,
                    position=match.start(),
                    unit=""
                ))
        return tokens


class PercentageTokenizer(TokenizerPlugin):
    """Extracts percentage values."""
    
    PATTERN = r'(\d+(?:[.,]\d+)?)\s*%'
    
    def extract(self, query: str) -> List[Token]:
        tokens = []
        for match in re.finditer(self.PATTERN, query):
            try:
                val_str = match.group(1).replace(',', '.')
                value = float(val_str) / 100  # Normalize to 0-1
                tokens.append(Token(
                    raw=match.group(0),
                    value=value,
                    token_type=TokenType.PERCENTAGE,
                    position=match.start(),
                    unit="%"
                ))
            except ValueError:
                continue
        return tokens


# ============================================================================
# ZERO VALUE TOKENIZER (Negation Patterns)
# ============================================================================
class ZeroValueTokenizer(TokenizerPlugin):
    """
    Extracts zero values from negation phrases.
    Examples:
    - "không có thâm niên" → TN = 0
    - "chưa có tiền thâm niên" → TN = 0
    - "thâm niên bằng 0" → TN = 0
    """
    
    # Patterns: (regex, variable_hint)
    # variable_hint helps RoleMapper know which variable this zero belongs to
    PATTERNS = [
        # "không có thâm niên", "chưa có thâm niên", "không có tiền thâm niên"
        (r'(không|chưa|chua|ko)\s+có\s+(?:tiền\s+)?(?:thâm\s*niên|tham\s*nien|tn)', 'TN'),
        # "thâm niên bằng 0", "TN = 0"
        (r'(?:thâm\s*niên|tham\s*nien|tn)\s*(?:là|bằng|=|:)\s*0(?!\d)', 'TN'),
        # "không có lương cơ bản" (rare but possible)
        (r'(không|chưa|chua|ko)\s+có\s+(?:lương\s*cơ\s*bản|luong\s*co\s*ban|lcb)', 'LCB'),
    ]
    
    def extract(self, query: str) -> List[Token]:
        tokens = []
        query_lower = remove_diacritics(query.lower())
        
        for pattern, var_hint in self.PATTERNS:
            pattern_normalized = remove_diacritics(pattern)
            for match in re.finditer(pattern_normalized, query_lower):
                tokens.append(Token(
                    raw=match.group(0),
                    value=0.0,
                    token_type=TokenType.CURRENCY,  # Treat as currency for TN/LCB
                    position=match.start(),
                    unit="VNĐ"
                ))
        return tokens


# ============================================================================
# TOKENIZER ENGINE (Plugin Pipeline)
# ============================================================================
class TokenizerEngine:
    """Runs all tokenizer plugins and deduplicates results."""
    
    DEFAULT_PLUGINS = [
        ZeroValueTokenizer(),  # Run first to catch negation patterns
        CurrencyTokenizer(),
        YearTokenizer(),
        PercentageTokenizer(),
        IntegerTokenizer(),  # Run last to avoid conflicts
    ]
    
    def __init__(self, plugins: List[TokenizerPlugin] = None):
        self.plugins = plugins or self.DEFAULT_PLUGINS
    
    def tokenize(self, query: str) -> List[Token]:
        """Extract all tokens from query using plugins."""
        all_tokens = []
        used_positions = set()
        
        for plugin in self.plugins:
            tokens = plugin.extract(query)
            for token in tokens:
                # Avoid overlapping tokens (first match wins)
                if token.position not in used_positions:
                    all_tokens.append(token)
                    # Mark all character positions as used
                    for i in range(token.position, token.position + len(token.raw)):
                        used_positions.add(i)
        
        # Sort by position for consistent processing
        all_tokens.sort(key=lambda t: t.position)
        
        logger.debug(f"Tokenizer: Found {len(all_tokens)} tokens: {all_tokens}")
        return all_tokens


# ============================================================================
# TEXT NORMALIZATION (Unicode-Safe)
# ============================================================================
def remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics for keyword matching."""
    # NFD decomposition separates base chars from combining marks
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining marks (accents, tones)
    result = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return result.lower()


def normalize_query(query: str) -> str:
    """Normalize query for internal matching."""
    return remove_diacritics(query.lower())


# ============================================================================
# FORMULA REGISTRY (Versioned, Data-Driven)
# ============================================================================
# Formula Aliases (Natural Language to Internal Key mapping)
FORMULA_ALIASES = {
    "thưởng tết": "bonus_tet",
    "thuong tet": "bonus_tet",
    "tính thưởng": "bonus_tet",
    "tinh thuong": "bonus_tet",
    "bonus": "bonus_tet",
    "thưởng": "bonus_tet",
    "thuong": "bonus_tet"
}

FORMULA_REGISTRY = {
    "bonus_tet": {
        "id": "bonus_tet@v1",
        "name": "Thưởng Tết",
        "formula": "((LCB + TN) / 12) * ST * HS",
        "required_vars": ["LCB", "TN", "ST", "HS"],
        "derived_vars": {
            "HS": {"from": "YEAR", "lookup": "HS_TABLE"}
        },
        "var_config": {
            "LCB": {
                "type": TokenType.CURRENCY,
                "min": 0,
                "max": 1_000_000_000_000,  # 1 trillion guard
                "keywords": ["luong co ban", "luong", "lcb"],
                "keyword_weights": {"luong co ban": 1.5, "luong": 1.0, "lcb": 1.2}
            },
            "TN": {
                "type": TokenType.CURRENCY,
                "min": 0,
                "max": 100_000_000_000,
                "keywords": ["tham nien", "tn"],
                "keyword_weights": {"tham nien": 1.5, "tn": 1.2}
            },
            "ST": {
                "type": TokenType.INTEGER,
                "min": 1,
                "max": 12,
                "keywords": ["so thang", "thang lam", "thang", "st"],
                "keyword_weights": {"so thang": 1.5, "thang lam": 1.3, "thang": 1.0, "st": 1.2}
            },
            "YEAR": {
                "type": TokenType.YEAR,
                "min": 2000,
                "max": 2100,
                "keywords": ["nam vao lam", "vao lam", "nam"],
                "keyword_weights": {"nam vao lam": 1.5, "vao lam": 1.3, "nam": 1.0}
            },
            "HS": {
                "type": TokenType.DECIMAL,
                "min": 0,
                "max": 10,
                "keywords": ["he so", "hs"],
                "keyword_weights": {"he so": 1.5, "hs": 1.2}
            }
        },
        "validators": {
            "result_max_ratio": 100  # Result must be < 100x (LCB+TN)
        },
        "output_type": TokenType.CURRENCY
    }
}

# Static lookup tables (versioned data)
HS_TABLE = {
    2016: 1.8, 2017: 1.7, 2018: 1.6, 2019: 1.5, 2020: 1.4,
    2021: 1.3, 2022: 1.2, 2023: 1.1, 2024: 1.05, 2025: 1.0
}

LOOKUP_TABLES = {
    "HS_TABLE": HS_TABLE
}


# ============================================================================
# SCORING-BASED ROLE MAPPER
# ============================================================================
class RoleMapper:
    """Maps tokens to formula variables using weighted proximity scoring."""
    
    # Scoring weights
    W_DISTANCE = -0.1       # Penalty per character distance
    W_KEYWORD = 2.0         # Base keyword match bonus
    W_DIRECTION = 0.5       # Bonus if token follows keyword
    W_TYPE_MATCH = 3.0      # Bonus for correct type
    
    CONFIDENCE_THRESHOLD = 1.0  # Minimum score to accept mapping
    MAX_DISTANCE = 50           # Max chars between keyword and token
    
    def __init__(self, formula_config: Dict):
        self.var_config = formula_config.get("var_config", {})
    
    def find_keyword_positions(self, normalized_query: str) -> Dict[str, List[Tuple[int, str, float]]]:
        """Find all keyword positions in query for each variable."""
        keyword_positions = {}
        
        for var_name, config in self.var_config.items():
            keywords = config.get("keywords", [])
            weights = config.get("keyword_weights", {})
            positions = []
            
            for keyword in keywords:
                idx = 0
                while True:
                    pos = normalized_query.find(keyword, idx)
                    if pos == -1:
                        break
                    weight = weights.get(keyword, 1.0)
                    positions.append((pos, keyword, weight))
                    idx = pos + 1
            
            keyword_positions[var_name] = positions
        
        return keyword_positions
    
    def calculate_score(self, token: Token, keyword_pos: int, keyword_end: int, 
                       keyword_weight: float, expected_type: TokenType) -> float:
        """Calculate mapping score for a token-keyword pair."""
        score = 0.0
        
        # Type match (critical)
        if token.token_type == expected_type:
            score += self.W_TYPE_MATCH
        elif expected_type == TokenType.DECIMAL and token.token_type in [TokenType.CURRENCY, TokenType.INTEGER]:
            score += self.W_TYPE_MATCH * 0.5  # Partial match
        else:
            return -999  # Type mismatch = disqualify
        
        # Distance calculation
        if token.position >= keyword_end:
            distance = token.position - keyword_end
            score += self.W_DIRECTION  # Token follows keyword
        else:
            distance = keyword_pos - (token.position + len(token.raw))
        
        if distance > self.MAX_DISTANCE:
            return -999  # Too far
        
        score += self.W_DISTANCE * distance
        
        # Keyword strength
        score += self.W_KEYWORD * keyword_weight
        
        return score
    
    def map_tokens(self, tokens: List[Token], normalized_query: str) -> Tuple[Dict[str, MappedVariable], Dict[str, List[Token]]]:
        """
        Map tokens to variables using scoring algorithm.
        Returns: (mapped_vars, ambiguous_vars)
        """
        keyword_positions = self.find_keyword_positions(normalized_query)
        
        # Calculate scores for all token-variable pairs
        candidates: Dict[str, List[Tuple[Token, float, str]]] = {var: [] for var in self.var_config}
        
        for var_name, config in self.var_config.items():
            expected_type = config.get("type", TokenType.DECIMAL)
            kw_positions = keyword_positions.get(var_name, [])
            
            for token in tokens:
                best_score = -999
                best_keyword = ""
                
                for kw_pos, keyword, kw_weight in kw_positions:
                    keyword_end = kw_pos + len(keyword)
                    score = self.calculate_score(token, kw_pos, keyword_end, kw_weight, expected_type)
                    if score > best_score:
                        best_score = score
                        best_keyword = keyword
                
                if best_score > self.CONFIDENCE_THRESHOLD:
                    candidates[var_name].append((token, best_score, best_keyword))
        
        # Greedy assignment: best score first, each token used once
        used_tokens = set()
        mapped_vars = {}
        ambiguous_vars = {}
        
        # Sort all candidates by score (descending)
        all_candidates = []
        for var_name, cands in candidates.items():
            for token, score, keyword in cands:
                all_candidates.append((score, var_name, token, keyword))
        
        all_candidates.sort(reverse=True, key=lambda x: x[0])
        
        for score, var_name, token, keyword in all_candidates:
            # Skip if token already used by another variable (this is normal, not ambiguous)
            if id(token) in used_tokens:
                continue
            
            if var_name in mapped_vars:
                # Check for ambiguity (another strong UNUSED candidate for the same variable)
                existing_score = mapped_vars[var_name].score
                if score > existing_score * 0.9:  # Within 10% of best (stricter threshold)
                    if var_name not in ambiguous_vars:
                        ambiguous_vars[var_name] = [mapped_vars[var_name].token]
                    ambiguous_vars[var_name].append(token)
                continue
            
            mapped_vars[var_name] = MappedVariable(
                var_name=var_name,
                token=token,
                score=score,
                keyword_matched=keyword
            )
            used_tokens.add(id(token))
        
        # Post-processing: Clean up false ambiguities
        # A token flagged as "ambiguous" for var A is NOT truly ambiguous if it was
        # later assigned to var B (its correct home). Remove such false positives.
        correct_assignments = {id(m.token): var for var, m in mapped_vars.items()}
        cleaned_ambiguous = {}
        
        for var_name, tokens_list in ambiguous_vars.items():
            truly_ambiguous = []
            for token in tokens_list:
                token_id = id(token)
                # Keep in ambiguous list ONLY if:
                # 1. Token was NOT assigned to any variable, OR
                # 2. Token was assigned to THIS variable (genuine ambiguity within same var)
                if token_id not in correct_assignments or correct_assignments[token_id] == var_name:
                    truly_ambiguous.append(token)
            
            if len(truly_ambiguous) >= 2:  # Need at least 2 for true ambiguity
                cleaned_ambiguous[var_name] = truly_ambiguous
        
        ambiguous_vars = cleaned_ambiguous
        
        # Fallback: Assign standalone YEAR tokens without keyword proximity
        # YEAR tokens (4-digit 20xx) are inherently unambiguous and don't always need keywords
        if "YEAR" in self.var_config and "YEAR" not in mapped_vars:
            year_tokens = [t for t in tokens if t.token_type == TokenType.YEAR and id(t) not in used_tokens]
            if len(year_tokens) == 1:
                year_token = year_tokens[0]
                mapped_vars["YEAR"] = MappedVariable(
                    var_name="YEAR",
                    token=year_token,
                    score=5.0,  # Medium confidence for keywordless match
                    keyword_matched="(standalone)"
                )
                used_tokens.add(id(year_token))
                logger.info(f"RoleMapper: Fallback - assigned standalone YEAR={year_token.value}")
        
        logger.debug(f"RoleMapper: Mapped {list(mapped_vars.keys())}, Ambiguous: {list(ambiguous_vars.keys())}")
        return mapped_vars, ambiguous_vars


# ============================================================================
# DERIVATION ENGINE
# ============================================================================
def resolve_derived_vars(mapped_vars: Dict[str, MappedVariable], formula_config: Dict) -> Dict[str, MappedVariable]:
    """Derive secondary variables (e.g., YEAR → HS)."""
    derived_vars = formula_config.get("derived_vars", {})
    
    for target_var, config in derived_vars.items():
        if target_var in mapped_vars:
            continue  # Already directly mapped
        
        source_var = config.get("from")
        lookup_table_name = config.get("lookup")
        
        if source_var in mapped_vars and lookup_table_name:
            source_val = int(mapped_vars[source_var].token.value)
            lookup_table = LOOKUP_TABLES.get(lookup_table_name, {})
            
            if source_val in lookup_table:
                derived_val = lookup_table[source_val]
                # Create synthetic token for derived value
                derived_token = Token(
                    raw=f"derived_from_{source_var}={source_val}",
                    value=derived_val,
                    token_type=TokenType.DECIMAL,
                    position=-1,
                    confidence=1.0
                )
                mapped_vars[target_var] = MappedVariable(
                    var_name=target_var,
                    token=derived_token,
                    score=10.0,  # High confidence for lookup
                    keyword_matched=f"lookup({source_var})"
                )
                logger.info(f"Derived {target_var}={derived_val} from {source_var}={source_val}")
    
    return mapped_vars


# ============================================================================
# VALIDATION ENGINE
# ============================================================================
def validate_inputs(mapped_vars: Dict[str, MappedVariable], formula_config: Dict) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate all mapped values against formula constraints."""
    var_config = formula_config.get("var_config", {})
    
    for var_name, mapped in mapped_vars.items():
        if var_name not in var_config:
            continue
        
        config = var_config[var_name]
        value = mapped.token.value
        
        # Check finite
        if not math.isfinite(value):
            return False, ErrorCode.VALIDATION_FAILED.value, f"{var_name} must be a finite number"
        
        # Check bounds
        if "min" in config and value < config["min"]:
            return False, ErrorCode.VALIDATION_FAILED.value, f"{var_name} must be >= {config['min']}"
        
        if "max" in config and value > config["max"]:
            return False, ErrorCode.VALIDATION_FAILED.value, f"{var_name} must be <= {config['max']}"
    
    return True, None, None


def validate_result(result: float, mapped_vars: Dict[str, MappedVariable], formula_config: Dict) -> Tuple[bool, Optional[str]]:
    """Sanity check on the final result."""
    validators = formula_config.get("validators", {})
    
    # Result max ratio check
    if "result_max_ratio" in validators:
        ratio = validators["result_max_ratio"]
        lcb = mapped_vars.get("LCB", MappedVariable("", Token("", 0, TokenType.CURRENCY, 0), 0)).token.value
        tn = mapped_vars.get("TN", MappedVariable("", Token("", 0, TokenType.CURRENCY, 0), 0)).token.value
        base = lcb + tn
        if base > 0 and result > base * ratio:
            return False, f"Result {result:,.0f} exceeds {ratio}x base ({base:,.0f})"
    
    return True, None


# ============================================================================
# DETERMINISTIC EXECUTOR
# ============================================================================
def execute_formula(mapped_vars: Dict[str, MappedVariable], formula_config: Dict) -> Dict[str, Any]:
    """Execute formula with pure Python arithmetic."""
    formula_id = formula_config.get("id", "unknown")
    formula_str = formula_config.get("formula", "")
    
    try:
        # Extract normalized values
        lcb = mapped_vars["LCB"].token.value
        tn = mapped_vars["TN"].token.value
        st = mapped_vars["ST"].token.value
        hs = mapped_vars["HS"].token.value
        
        # Deterministic calculation (no intermediate rounding)
        result = ((lcb + tn) / 12) * st * hs
        
        # Final rounding for currency
        result_int = int(round(result))
        
        # Sanity validation
        is_valid, error_msg = validate_result(result_int, mapped_vars, formula_config)
        if not is_valid:
            return {
                "success": False,
                "error_code": ErrorCode.VALIDATION_FAILED.value,
                "error_detail": error_msg
            }
        
        return {
            "status": "SUCCESS",
            "formula_key": formula_id,
            "value": result_int,
            "formatted": f"{result_int:,} VNĐ",
            "confidence_level": "HIGH",
            "engine": "MATH_GUARD",
            "variables": {
                var: {
                    "value": m.token.value,
                    "raw": m.token.raw,
                    "score": m.score
                }
                for var, m in mapped_vars.items()
            }
        }
        
    except KeyError as e:
        return {
            "status": "ERROR",
            "error_code": ErrorCode.MISSING_VAR.value,
            "engine": "MATH_GUARD",
            "missing_vars": [str(e).strip("'")]
        }


# ============================================================================
# MAIN ENTRY POINT (Structured I/O Contract)
# ============================================================================
def compute(original_query: str, formula_key: str = "bonus_tet", cached_vars: Dict[str, float] = None) -> Dict[str, Any]:
    """
    MathGuard Main Entry Point.
    
    Input Contract:
        original_query: str - The raw user query (never rephrased)
        formula_key: str - Formula identifier (e.g., "bonus_tet")
        cached_vars: Dict[str, float] - Previously cached variable values for slot-filling
    
    Output Contract (Success):
        {
            "success": true,
            "formula_key": "bonus_tet@v1",
            "result": {"value": 14220000, "formatted": "14,220,000 VNĐ"},
            "variables": {"LCB": {...}, "TN": {...}, ...}
        }
    
    Output Contract (Error):
        {
            "success": false,
            "error_code": "MISSING_VAR" | "AMBIGUOUS_VAR" | "VALIDATION_FAILED",
            "missing_vars": [...] | "ambiguous_vars": {...} | "error_detail": "..."
        }
    """
    logger.info(f"MathGuard: Processing query for formula '{formula_key}'")
    logger.debug(f"MathGuard: Original query = '{original_query}'")
    if cached_vars:
        logger.info(f"MathGuard: Using cached vars = {cached_vars}")
    
    # Step -0.5: Resolve Aliases (Natural Language to Key)
    normalized_key = formula_key.lower().strip()
    resolved_key = FORMULA_ALIASES.get(normalized_key, normalized_key)
    # Also try without accents
    if resolved_key == normalized_key:
        resolved_key = FORMULA_ALIASES.get(remove_diacritics(normalized_key), resolved_key)

    # Step 0: Get formula config
    formula_config = FORMULA_REGISTRY.get(resolved_key)
    if not formula_config:
        return {
            "success": False,
            "error_code": ErrorCode.UNKNOWN_FORMULA.value,
            "error_detail": f"Unknown formula: {formula_key} (resolved to: {resolved_key})"
        }
    
    # Step 1: Tokenize (grammar-independent)
    tokenizer = TokenizerEngine()
    tokens = tokenizer.tokenize(original_query)
    logger.info(f"MathGuard: Extracted {len(tokens)} tokens")
    
    # Step 2: Normalize query for keyword matching
    normalized_query = normalize_query(original_query)
    
    # Step 3: Map tokens to variables (scoring-based)
    mapper = RoleMapper(formula_config)
    mapped_vars, ambiguous_vars = mapper.map_tokens(tokens, normalized_query)
    logger.info(f"MathGuard: Mapped variables from query = {list(mapped_vars.keys())}")
    
    # Step 3.5: SLOT-FILLING MEMORY - Merge cached vars with newly extracted vars
    # New extracted vars OVERRIDE cached ones (user explicitly provided new value)
    if cached_vars:
        # Get derived var mappings (e.g., HS is derived from YEAR)
        derived_vars = formula_config.get("derived_vars", {})
        derived_targets = set(derived_vars.keys())  # e.g., {"HS"}
        derived_sources = {cfg.get("from") for cfg in derived_vars.values()}  # e.g., {"YEAR"}
        
        # Check if any source var was newly extracted (e.g., new YEAR means recalculate HS)
        newly_extracted_sources = derived_sources & set(mapped_vars.keys())
        vars_to_skip = set()
        if newly_extracted_sources:
            # If YEAR was newly extracted, don't slot-fill HS - let it re-derive
            for target_var, config in derived_vars.items():
                if config.get("from") in newly_extracted_sources:
                    vars_to_skip.add(target_var)
            logger.info(f"MathGuard: Skipping slot-fill for {vars_to_skip} (source vars re-extracted)")
        
        for var_name, cached_value in cached_vars.items():
            if var_name not in mapped_vars and var_name not in vars_to_skip:
                # Create a synthetic MappedVariable from cache
                cached_token = Token(
                    raw=f"[cached:{cached_value}]",
                    value=float(cached_value),
                    token_type=TokenType.CURRENCY if var_name in ['LCB', 'TN'] else TokenType.INTEGER,
                    position=-1,  # Synthetic
                    unit=""
                )
                mapped_vars[var_name] = MappedVariable(
                    var_name=var_name,
                    token=cached_token,
                    score=10.0,  # High score for cached (trusted)
                    keyword_matched="[slot-fill]"
                )
                logger.info(f"MathGuard: Slot-filled {var_name} = {cached_value} from cache")

    # Step 3.6: Early exit check (MOVED AFTER SLOT-FILL for v16)
    # If we have no tokens AND no cache resulted in a calculation, then we fail
    if not tokens and not mapped_vars:
        logger.info("MathGuard: No tokens found and no variables in cache. Aborting.")
        return {
            "status": "ERROR",
            "error_code": ErrorCode.MISSING_VAR.value,
            "engine": "MATH_GUARD",
            "missing_vars": formula_config.get("required_vars", []),
            "extracted": {}
        }
    
    # Step 4: Check for ambiguity
    if ambiguous_vars:
        return {
            "status": "ERROR",
            "error_code": ErrorCode.AMBIGUOUS_VAR.value,
            "engine": "MATH_GUARD",
            "ambiguous_vars": {
                var: [t.raw for t in tokens_list]
                for var, tokens_list in ambiguous_vars.items()
            }
        }
    
    # Step 5: Derive secondary variables (YEAR → HS)
    mapped_vars = resolve_derived_vars(mapped_vars, formula_config)
    logger.info(f"MathGuard: After derivation = {list(mapped_vars.keys())}")
    
    # Step 6: Check completeness
    required_vars = set(formula_config.get("required_vars", []))
    mapped_var_names = set(mapped_vars.keys())
    missing_vars = list(required_vars - mapped_var_names)
    
    if missing_vars:
        logger.info(f"MathGuard: Missing variables = {missing_vars}")
        return {
            "status": "ERROR",
            "error_code": ErrorCode.MISSING_VAR.value,
            "engine": "MATH_GUARD",
            "missing_vars": missing_vars,
            "extracted": {
                var: m.token.value for var, m in mapped_vars.items()
            }
        }
    
    # Step 6.5: Check overall mapping confidence
    # If average score is too low, refuse to calculate (better to ask than guess wrong)
    MIN_AVERAGE_SCORE = 3.0
    scores = [m.score for m in mapped_vars.values()]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    if avg_score < MIN_AVERAGE_SCORE:
        logger.warning(f"MathGuard: Low confidence - avg score {avg_score:.2f} < {MIN_AVERAGE_SCORE}")
        return {
            "status": "ERROR",
            "error_code": ErrorCode.LOW_CONFIDENCE.value,
            "engine": "MATH_GUARD",
            "error_detail": f"Average mapping confidence ({avg_score:.2f}) is below threshold ({MIN_AVERAGE_SCORE})",
            "extracted": {
                var: {"value": m.token.value, "score": m.score}
                for var, m in mapped_vars.items()
            }
        }
    
    # Step 7: Validate inputs
    is_valid, error_code, error_detail = validate_inputs(mapped_vars, formula_config)
    if not is_valid:
        return {
            "status": "ERROR",
            "error_code": error_code,
            "engine": "MATH_GUARD",
            "error_detail": error_detail
        }
    
    # Step 8: Execute deterministically
    result = execute_formula(mapped_vars, formula_config)
    logger.info(f"MathGuard: Result = {result.get('formatted', 'ERROR')}")
    
    return result
