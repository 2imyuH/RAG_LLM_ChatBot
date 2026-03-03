"""
Arithmetic Engine - Safe Deterministic Calculator
==================================================
Layer 3 of the 3-layer arithmetic architecture.

Provides safe evaluation of simple math expressions without using eval().
Uses AST parsing for security and determinism.
"""

import ast
import operator
import logging
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Safety limits to prevent logic DoS
MAX_EXPR_LENGTH = 100
MAX_POWER_EXPONENT = 1000  # Avoid huge numbers (e.g., 2**1000000)
MAX_POWER_DEPTH = 2        # Avoid deep chains like 2**3**4

logger = logging.getLogger(__name__)


# ============================================================================
# SUPPORTED OPERATIONS
# ============================================================================
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,  # Unary minus
}

# Vietnamese operator mappings
VIETNAMESE_OPERATORS = {
    "cộng": "+",
    "cong": "+",
    "cộng với": "+",
    "trừ": "-",
    "tru": "-",
    "trừ đi": "-",
    "nhân": "*",
    "nhan": "*",
    "nhân với": "*",
    "chia": "/",
    "chia cho": "/",
    "lũy thừa": "**",
    "lũ thừa": "**",
    "lu thua": "**",
    "mũ": "**",
}

# Vietnamese number words
VIETNAMESE_NUMBERS = {
    "không": 0, "một": 1, "hai": 2, "ba": 3, "bốn": 4,
    "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9,
    "mười": 10, "trăm": 100, "nghìn": 1000, "ngàn": 1000,
    "triệu": 1_000_000, "tỷ": 1_000_000_000,
}


# ============================================================================
# ERROR CODES
# ============================================================================
class ArithmeticErrorCodes(str, Enum):
    PARSE_ERROR = "PARSE_ERROR"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    OVERFLOW = "OVERFLOW"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    INVALID_EXPRESSION = "INVALID_EXPRESSION"
    DEPTH_LIMIT = "DEPTH_LIMIT"
    EXPR_TOO_COMPLEX = "EXPR_TOO_COMPLEX"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"


# ============================================================================
# INTERMEDIATE REPRESENTATION
# ============================================================================
@dataclass
class ArithmeticIR:
    """Intermediate Representation for arithmetic expressions."""
    original_query: str
    normalized_expression: str  # e.g., "100 + 100"
    operands: list
    operators: list
    confidence: float = 1.0


# ============================================================================
# EXPRESSION NORMALIZER
# ============================================================================
class ExpressionNormalizer:
    """Converts natural language to normalized math expression."""
    
    def normalize(self, query: str) -> Tuple[str, float]:
        """
        Convert query to normalized expression.
        Returns (expression, confidence).
        """
        normalized = query.lower().strip()
        confidence = 1.0
        
        # Step 1: Replace Vietnamese operators
        # Sort by length descending to match longer phrases first (e.g., "nhân với" before "nhân")
        sorted_operators = sorted(VIETNAMESE_OPERATORS.items(), key=lambda x: len(x[0]), reverse=True)
        for vn_op, math_op in sorted_operators:
            if vn_op in normalized:
                normalized = normalized.replace(vn_op, f" {math_op} ")
                confidence = min(confidence, 0.9)
        
        # Step 1.5: Handle special power patterns like "lũy thừa {exp} của {base}" -> "{base} ** {exp}"
        # Matches: "** 2 của 4" (after step 1 operator replacement)
        power_pattern = r'(\*\*)\s*(\d+(?:\.\d+)?)\s*của\s*(\d+(?:\.\d+)?)'
        normalized = re.sub(power_pattern, r'\3 \1 \2', normalized)
        
        # Handle "với" as noise (e.g., "nhân 4 với 6" or "nhân 4 * với 6")
        normalized = normalized.replace(" với ", " ")
        
        # Step 2: Remove question words and noise
        noise_patterns = [
            r'bằng bao nhiêu\s*\??',
            r'là bao nhiêu\s*\??',
            r'bằng mấy\s*\??',
            r'là mấy\s*\??',
            r'kết quả\s*(?:là)?\s*\??',
            r'tính\s*(?:giúp tôi)?\s*',
            r'cho tôi\s*',
            r'\?\s*$',
            r'=\s*$',
        ]
        for pattern in noise_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Step 3: Extract just the math expression
        # Look for pattern: number operator number (operator number)*
        math_pattern = r'(-?\d+(?:\.\d+)?)\s*([\+\-\*\/\^])\s*(-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\^]\s*-?\d+(?:\.\d+)?)*)'
        match = re.search(math_pattern, normalized)
        
        if match:
            expression = match.group(0).strip()
            # Replace ^ with ** for Python
            expression = expression.replace('^', '**')
            return expression, confidence
        
        # Fallback: try to extract any numbers and operators
        tokens = re.findall(r'-?\d+(?:\.\d+)?|\*\*|[\+\-\*\/]', normalized)
        if len(tokens) >= 3:
            expression = ' '.join(tokens)
            return expression, confidence * 0.8
        
        return "", 0.0


# ============================================================================
# SAFE AST EVALUATOR
# ============================================================================
class SafeEvaluator:
    """Safely evaluate math expressions using AST parsing."""
    
    def evaluate(self, expression: str) -> dict:
        """
        Safe evaluation using AST.
        Returns: {"status": "SUCCESS"|"ERROR", "value": float, "formatted": str, "error_code": str, "message": str, "engine": str}
        """
        if not expression:
            return {
                "status": "ERROR",
                "error_code": ArithmeticErrorCodes.INVALID_EXPRESSION,
                "message": "Empty expression",
                "engine": "ARITHMETIC_ENGINE"
            }

        # 1. Length check
        if len(expression) > MAX_EXPR_LENGTH:
            return {
                "status": "ERROR",
                "error_code": ArithmeticErrorCodes.EXPR_TOO_COMPLEX,
                "message": f"Expression too long (max {MAX_EXPR_LENGTH} chars)",
                "engine": "ARITHMETIC_ENGINE"
            }

        try:
            tree = ast.parse(expression)
            
            # 2. Complexity check: Walk the tree to detect nested power chains or prohibited nodes
            power_depth = 0
            for node in ast.walk(tree):
                # Prohibit function calls entirely for safety
                if isinstance(node, ast.Call):
                    return {
                        "status": "ERROR",
                        "error_code": ArithmeticErrorCodes.UNSUPPORTED_OPERATION,
                        "message": "Function calls are not allowed",
                        "engine": "ARITHMETIC_ENGINE"
                    }
                
                # Check for power operator depth
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                    power_depth += 1
                    # Check for large exponents if they are literals
                    if isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)):
                        if node.right.value > MAX_POWER_EXPONENT:
                            return {
                                "status": "ERROR",
                                "error_code": ArithmeticErrorCodes.OVERFLOW,
                                "message": f"Exponent too large (max {MAX_POWER_EXPONENT})",
                                "engine": "ARITHMETIC_ENGINE"
                            }
            
            if power_depth > MAX_POWER_DEPTH:
                return {
                    "status": "ERROR",
                    "error_code": ArithmeticErrorCodes.DEPTH_LIMIT,
                    "message": f"Exponentiation depth too deep (max {MAX_POWER_DEPTH})",
                    "engine": "ARITHMETIC_ENGINE"
                }

            # 3. Safe evaluation
            result = self._safe_eval(tree.body[0].value)
            
            # 4. Range check for final result
            if abs(result) > 1e15:  # Avoid scientific notation overflow in some contexts
                 return {
                    "status": "ERROR",
                    "error_code": ArithmeticErrorCodes.OVERFLOW,
                    "message": "Result exceeds safe magnitude",
                    "engine": "ARITHMETIC_ENGINE"
                }

            return {
                "status": "SUCCESS",
                "value": float(result),
                "formatted": str(result),
                "expression": expression,
                "confidence_level": "HIGH",
                "engine": "ARITHMETIC_ENGINE"
            }
        except ZeroDivisionError:
            return {
                "status": "ERROR",
                "error_code": ArithmeticErrorCodes.DIVISION_BY_ZERO,
                "message": "Phép chia cho 0",
                "engine": "ARITHMETIC_ENGINE"
            }
        except Exception as e:
            logger.error(f"ArithmeticEngine Eval Error: {e}")
            error_code = ArithmeticErrorCodes.INVALID_EXPRESSION
            msg = str(e)
            if "too deep" in msg: error_code = ArithmeticErrorCodes.DEPTH_LIMIT
            elif "ZeroDivisionError" in msg: error_code = ArithmeticErrorCodes.DIVISION_BY_ZERO
            
            return {
                "status": "ERROR",
                "error_code": error_code,
                "message": msg,
                "engine": "ARITHMETIC_ENGINE"
            }

    def _safe_eval(self, node):
        """Recursively evaluate AST nodes with limited depth."""
        # Use a localized operator map
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7 compatibility
            return float(node.n)
        elif isinstance(node, ast.BinOp):
            left = self._safe_eval(node.left)
            right = self._safe_eval(node.right)
            return operators[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._safe_eval(node.operand)
            return operators[type(node.op)](operand)
        elif isinstance(node, ast.Expression):
            return self._safe_eval(node.body)
        else:
            raise TypeError(f"Unsupported AST node: {type(node)}")


# ============================================================================
# MAIN ENGINE
# ============================================================================
class ArithmeticEngine:
    """
    Main entry point for arithmetic evaluation.
    Combines normalization and safe evaluation.
    """
    
    def __init__(self):
        self.normalizer = ExpressionNormalizer()
        self.evaluator = SafeEvaluator()
    
    def compute(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language arithmetic query.
        Returns a normalized Result Schema.
        """
        logger.info(f"ArithmeticEngine: Processing query: '{query}'")
        
        # Step 1: Normalize to math expression
        expression, confidence = self.normalizer.normalize(query)
        logger.debug(f"ArithmeticEngine: Normalized to '{expression}' (confidence={confidence})")
        
        if not expression or confidence < 0.5:
            return {
                "status": "ERROR",
                "error_code": ArithmeticErrorCodes.PARSE_ERROR,
                "message": "Could not extract expression",
                "engine": "ARITHMETIC_ENGINE"
            }
        
        # Step 2: Evaluate safely
        res = self.evaluator.evaluate(expression)
        
        # Merge confidence from normalization
        if res.get("status") == "SUCCESS":
             res["confidence"] = confidence
        
        return res


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_engine_instance = None

def get_engine() -> ArithmeticEngine:
    """Get singleton instance of ArithmeticEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ArithmeticEngine()
    return _engine_instance


def compute(query: str) -> Dict[str, Any]:
    """Convenience function to compute arithmetic."""
    return get_engine().compute(query)
