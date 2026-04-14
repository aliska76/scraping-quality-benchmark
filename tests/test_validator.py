"""
Tests for content validator using mocks from conftest.py.
"""

import pytest
from validator import ContentValidator, ValidationResult


class TestContentValidator:
    """Test suite for ContentValidator."""
    
    def setup_method(self):
        self.validator = ContentValidator(min_length=200)
    
    @pytest.mark.unit
    def test_validate_with_good_content_returns_valid(self):
        """Should return valid for content longer than min_length."""
        content = "A" * 300
        
        result = self.validator.validate(content, 200)
        
        assert result.is_valid is True
        assert result.reason == "OK"
    
    @pytest.mark.unit
    def test_validate_with_http_404_returns_invalid(self):
        """Should return invalid for HTTP 404 error."""
        result = self.validator.validate("some content", 404)
        
        assert result.is_valid is False
        assert "404" in result.reason
    
    @pytest.mark.unit
    def test_validate_with_http_403_returns_invalid(self):
        """Should return invalid for HTTP 403 error."""
        result = self.validator.validate("some content", 403)
        
        assert result.is_valid is False
        assert "403" in result.reason
    
    @pytest.mark.unit
    def test_validate_with_empty_content_returns_invalid(self):
        """Should return invalid for empty content."""
        result = self.validator.validate("", 200)
        
        assert result.is_valid is False
        assert result.reason == "Empty content"
    
    @pytest.mark.unit
    def test_validate_with_short_content_returns_invalid(self):
        """Should return invalid for content shorter than min_length."""
        content = "A" * 100
        
        result = self.validator.validate(content, 200)
        
        assert result.is_valid is False
        assert "Too short" in result.reason
    
    @pytest.mark.unit
    def test_validate_with_block_page_returns_invalid(self):
        """Should return invalid for block page content."""
        content = "This is a Cloudflare captcha page. Please verify you are human."
        
        result = self.validator.validate(content, 200)
        
        assert result.is_valid is False
        assert "Block page" in result.reason
    
    @pytest.mark.unit
    def test_needs_fallback_with_valid_result_returns_false(self):
        """Should return False when result is valid."""
        valid_result = ValidationResult(is_valid=True, reason="OK", content="test", score=1.0)
        
        assert self.validator.needs_fallback(valid_result) is False
    
    @pytest.mark.unit
    def test_needs_fallback_with_invalid_result_returns_true(self):
        """Should return True when result is invalid."""
        invalid_result = ValidationResult(is_valid=False, reason="Error", content="", score=0.0)
        
        assert self.validator.needs_fallback(invalid_result) is True