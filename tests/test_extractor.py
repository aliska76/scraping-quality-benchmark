# tests/test_extractor.py
"""
Tests for content extractor using mocks from conftest.py.
"""

import pytest
from extractor import ContentExtractor


class TestContentExtractor:
    """Test suite for ContentExtractor."""
    
    def setup_method(self):
        self.extractor = ContentExtractor()
    
    @pytest.mark.unit
    def test_extract_json_with_valid_json_returns_formatted_json(self, sample_json):
        """Should format valid JSON with indentation."""
        result = self.extractor.extract_json(sample_json)
        
        assert '"id": 1' in result
        assert '"name": "test"' in result
        assert '"items"' in result
    
    @pytest.mark.unit
    def test_extract_json_with_invalid_json_returns_empty_string(self):
        """Should return empty string for invalid JSON."""
        result = self.extractor.extract_json("not json")
        
        assert result == ""
    
    @pytest.mark.unit
    def test_extract_raw_text_removes_html_tags(self, sample_html):
        """Should remove all HTML tags from content."""
        result = self.extractor.extract_raw_text(sample_html)
        
        assert "Welcome to Test Page" in result
        assert "Item 1" in result
        assert "<h1>" not in result
        assert "<li>" not in result
    
    @pytest.mark.unit
    def test_extract_raw_text_with_empty_html_returns_empty_string(self):
        """Should return empty string for empty HTML."""
        result = self.extractor.extract_raw_text("")
        
        assert result == ""
    
    @pytest.mark.unit
    def test_extract_for_page_type_with_json_uses_json_extractor(self, sample_json):
        """Should use JSON extractor for JSON pages."""
        result = self.extractor.extract_for_page_type(sample_json, "json")
        
        assert '"id": 1' in result