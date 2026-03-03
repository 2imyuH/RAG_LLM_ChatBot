"""
MathGuard Comprehensive Test Suite
===================================
Tests for the platform-grade deterministic calculation engine.

Categories:
1. Positive Tests - Normal usage variations
2. Edge Cases - Boundary conditions
3. Negative Tests - Malicious/invalid inputs
4. Regression Tests - Previously failing cases
"""

import sys
import pytest
sys.path.insert(0, '.')

from src.agents.math_guard import (
    compute, 
    TokenizerEngine, 
    normalize_query,
    ErrorCode
)


# ============================================================================
# POSITIVE TESTS - Normal usage variations
# ============================================================================
class TestPositiveCases:
    """Test that valid inputs produce correct results."""
    
    # Expected result for LCB=6.9tr, TN=1tr, ST=12, HS=1.8 (2016)
    EXPECTED_RESULT = 14_220_000
    
    def test_standard_query(self):
        """Basic query with all variables in standard format."""
        result = compute("luong 6tr9, so thang 12, tham nien 1tr, nam 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_different_word_order(self):
        """Variables in different order should still parse correctly."""
        result = compute("Tham nien 1tr, luong co ban 6tr9, 12 thang, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_abbreviations(self):
        """Using short forms: lcb, tn, st."""
        result = compute("lcb 6.9tr, st 12, tn 1tr, nam 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_decimal_format_dot(self):
        """Decimal with dot: 6.9tr."""
        result = compute("luong 6.9tr, thang 12, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_decimal_format_tr(self):
        """Decimal with tr suffix: 6tr9."""
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_with_filler_words(self):
        """Query with Vietnamese filler words between keyword and value."""
        result = compute("luong cua toi la 6tr9, lam 12 thang, tham nien la 1tr, vao lam nam 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_standalone_year(self):
        """YEAR token without 'nam' keyword should still be matched."""
        result = compute("lcb 6tr9, tn 1tr, st 12, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == self.EXPECTED_RESULT
    
    def test_year_2017_hs_17(self):
        """Year 2017 with HS=1.7."""
        # ((6.9M + 1M) / 12) * 12 * 1.7 = 7.9M * 1.7 = 13.43M
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2017", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == 13_430_000
    
    def test_year_2025_hs_10(self):
        """Year 2025 with HS=1.0."""
        # ((6.9M + 1M) / 12) * 12 * 1.0 = 7.9M
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2025", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == 7_900_000
    
    def test_partial_months(self):
        """Working only 6 months."""
        # ((6.9M + 1M) / 12) * 6 * 1.8 = 7.11M
        result = compute("luong 6tr9, thang 6, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == 7_110_000


# ============================================================================
# EDGE CASES - Boundary conditions
# ============================================================================
class TestEdgeCases:
    """Test boundary and unusual but valid inputs."""
    
    def test_minimum_salary(self):
        """Minimum reasonable salary (1tr)."""
        result = compute("luong 1tr, thang 12, tham nien 0tr, 2016", "bonus_tet")
        # ((1M + 0) / 12) * 12 * 1.8 = 1.8M
        assert result["success"] is True
        assert result["result"]["value"] == 1_800_000
    
    def test_zero_tham_nien(self):
        """Zero thâm niên is valid."""
        result = compute("luong 6tr9, thang 12, tn 0, 2016", "bonus_tet")
        # ((6.9M + 0) / 12) * 12 * 1.8 = 12.42M
        assert result["success"] is True
        assert result["result"]["value"] == 12_420_000
    
    def test_single_month(self):
        """Working only 1 month (minimum)."""
        result = compute("luong 6tr9, thang 1, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is True
        # ((6.9M + 1M) / 12) * 1 * 1.8 = ~1.185M
        assert result["result"]["value"] == 1_185_000
    
    def test_high_salary(self):
        """High salary value (100tr)."""
        result = compute("luong 100tr, thang 12, tham nien 10tr, 2016", "bonus_tet")
        # ((100M + 10M) / 12) * 12 * 1.8 = 198M
        assert result["success"] is True
        assert result["result"]["value"] == 198_000_000
    
    def test_year_boundary_2016(self):
        """First year in HS table (2016)."""
        result = compute("lcb 10tr, tn 0, st 12, 2016", "bonus_tet")
        assert result["success"] is True
        # HS = 1.8
        assert result["result"]["value"] == 18_000_000
    
    def test_year_boundary_2025(self):
        """Last year in HS table (2025)."""
        result = compute("lcb 10tr, tn 0, st 12, 2025", "bonus_tet")
        assert result["success"] is True
        # HS = 1.0
        assert result["result"]["value"] == 10_000_000


# ============================================================================
# NEGATIVE TESTS - Invalid/malicious inputs
# ============================================================================
class TestNegativeCases:
    """Test that invalid inputs are properly rejected."""
    
    def test_missing_lcb(self):
        """Query missing LCB should return MISSING_VAR."""
        result = compute("thang 12, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
        assert "LCB" in result["missing_vars"]
    
    def test_missing_tn(self):
        """Query missing TN should return MISSING_VAR."""
        result = compute("luong 6tr9, thang 12, 2016", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
        assert "TN" in result["missing_vars"]
    
    def test_missing_st(self):
        """Query missing ST should return MISSING_VAR."""
        result = compute("luong 6tr9, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
        assert "ST" in result["missing_vars"]
    
    def test_missing_year_and_hs(self):
        """Query missing both YEAR and HS should return MISSING_VAR for HS."""
        result = compute("luong 6tr9, thang 12, tham nien 1tr", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
        assert "HS" in result["missing_vars"]
    
    def test_unknown_formula(self):
        """Unknown formula key should return UNKNOWN_FORMULA."""
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2016", "unknown_formula")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.UNKNOWN_FORMULA.value
    
    def test_invalid_st_too_high(self):
        """ST > 12 should fail validation."""
        result = compute("luong 6tr9, thang 15, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.VALIDATION_FAILED.value
    
    def test_empty_query(self):
        """Empty query should return MISSING_VAR."""
        result = compute("", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
    
    def test_garbage_input(self):
        """Random garbage should return MISSING_VAR."""
        result = compute("asdfghjkl qwerty", "bonus_tet")
        assert result["success"] is False
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
    
    def test_year_not_in_table(self):
        """Year not in HS_TABLE should fail to derive HS."""
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2010", "bonus_tet")
        assert result["success"] is False
        # YEAR is extracted but HS cannot be derived
        assert result["error_code"] == ErrorCode.MISSING_VAR.value
        assert "HS" in result["missing_vars"]


# ============================================================================
# REGRESSION TESTS - Previously failing cases
# ============================================================================
class TestRegressionCases:
    """Tests for bugs that were fixed."""
    
    def test_tn_extraction_with_filler(self):
        """
        Regression: TN wasn't extracted when followed by 'của tôi'
        Root cause: \\w+ didn't match Vietnamese diacritics
        """
        result = compute("Tham nien cua toi la 1tr, luong co ban 6tr9, 12 thang, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == 14_220_000
    
    def test_ambiguity_false_positive(self):
        """
        Regression: Multiple CURRENCY tokens were falsely flagged as ambiguous
        Root cause: Ambiguity check happened before used_token check
        """
        result = compute("lcb 6tr9, tn 1tr, st 12, 2016", "bonus_tet")
        assert result["success"] is True
        # Should not have AMBIGUOUS_VAR error
    
    def test_year_without_keyword(self):
        """
        Regression: YEAR wasn't mapped when 'nam' keyword was missing
        Root cause: Scoring required keyword proximity for all variables
        """
        result = compute("luong 6tr9, thang 12, tham nien 1tr, 2016", "bonus_tet")
        assert result["success"] is True
        assert result["result"]["value"] == 14_220_000


# ============================================================================
# TOKENIZER UNIT TESTS
# ============================================================================
class TestTokenizer:
    """Unit tests for the tokenizer engine."""
    
    def test_currency_6tr9(self):
        """Parse 6tr9 → 6,900,000."""
        tokenizer = TokenizerEngine()
        tokens = tokenizer.tokenize("luong 6tr9")
        currency_tokens = [t for t in tokens if t.token_type.value == "CURRENCY"]
        assert len(currency_tokens) == 1
        assert currency_tokens[0].value == 6_900_000
    
    def test_currency_6_9tr(self):
        """Parse 6.9tr → 6,900,000."""
        tokenizer = TokenizerEngine()
        tokens = tokenizer.tokenize("luong 6.9tr")
        currency_tokens = [t for t in tokens if t.token_type.value == "CURRENCY"]
        assert len(currency_tokens) == 1
        assert currency_tokens[0].value == 6_900_000
    
    def test_year_extraction(self):
        """Parse 2016 as YEAR token."""
        tokenizer = TokenizerEngine()
        tokens = tokenizer.tokenize("vao lam 2016")
        year_tokens = [t for t in tokens if t.token_type.value == "YEAR"]
        assert len(year_tokens) == 1
        assert year_tokens[0].value == 2016
    
    def test_integer_extraction(self):
        """Parse small integers like 12 for months."""
        tokenizer = TokenizerEngine()
        tokens = tokenizer.tokenize("lam 12 thang")
        int_tokens = [t for t in tokens if t.token_type.value == "INTEGER"]
        assert any(t.value == 12 for t in int_tokens)
    
    def test_multiple_tokens(self):
        """Extract multiple different token types."""
        tokenizer = TokenizerEngine()
        tokens = tokenizer.tokenize("luong 6tr9, thang 12, nam 2016")
        types = {t.token_type.value for t in tokens}
        assert "CURRENCY" in types
        assert "YEAR" in types


# ============================================================================
# QUERY NORMALIZATION TESTS
# ============================================================================
class TestNormalization:
    """Unit tests for query normalization (diacritics removal)."""
    
    def test_remove_vietnamese_diacritics(self):
        """Vietnamese diacritics should be removed."""
        result = normalize_query("thâm niên của tôi")
        assert result == "tham nien cua toi"
    
    def test_lowercase(self):
        """Query should be lowercased."""
        result = normalize_query("LUONG CO BAN")
        assert result == "luong co ban"
    
    def test_mixed_case_diacritics(self):
        """Mixed case with diacritics."""
        result = normalize_query("Thưởng Tết 2016")
        assert result == "thuong tet 2016"


# ============================================================================
# RUN TESTS
# ============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
