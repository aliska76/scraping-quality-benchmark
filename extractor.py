"""
Content extraction from HTML using trafilatura and readability.
"""

import re
import json


class ContentExtractor:
    """
    Extracts clean content from HTML.
    Multiple strategies: trafilatura, readability, raw text, JSON.
    """
    
    @staticmethod
    def extract_trafilatura(html: str) -> str:
        """Extract using trafilatura."""
        try:
            import trafilatura
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                include_formatting=False
            )
            return text or ""
        except Exception:
            return ""
    
    # extractor.py - исправленный метод

    @staticmethod
    def extract_readability(html: str) -> str:
        """Extract using readability-lxml with silent failure."""
        if not html or len(html.strip()) < 200:
            return ""
        
        try:
            from readability import Document
            import sys
            from io import StringIO
            
            # Подавляем stdout/stderr readability
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()
            
            try:
                doc = Document(html)
                text = doc.summary()
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            if not text:
                return ""
            
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception:
            return ""
    # @staticmethod
    # def extract_readability(html: str) -> str:
    #     """Extract using readability-lxml."""
    #     try:
    #         from readability import Document
    #         doc = Document(html)
    #         text = doc.summary()
    #         text = re.sub(r'<[^>]+>', ' ', text)
    #         text = re.sub(r'\s+', ' ', text).strip()
    #         return text
    #     except Exception:
    #         return ""
    
    @staticmethod
    def extract_raw_text(html: str) -> str:
        """Extract by stripping all HTML tags."""
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    @staticmethod
    def extract_json(html: str) -> str:
        """Extract and format JSON."""
        try:
            data = json.loads(html)
            return json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return ""
    
    def extract(self, html: str, strategy: str = "auto") -> str:
        """Extract with specified strategy."""
        if strategy == "trafilatura":
            return self.extract_trafilatura(html)
        if strategy == "readability":
            return self.extract_readability(html)
        if strategy == "raw":
            return self.extract_raw_text(html)
        if strategy == "json":
            return self.extract_json(html)
        
        # Auto: trafilatura → readability → raw
        content = self.extract_trafilatura(html)
        if len(content) < 200:
            content = self.extract_readability(html)
        if len(content) < 100:
            content = self.extract_raw_text(html)
        return content
    
    def extract_for_page_type(self, html: str, page_type: str) -> str:
        """Extract based on detected page type."""
        if page_type == "json":
            return self.extract_json(html)
        if page_type == "pdf":
            return self.extract_readability(html)
        
        # HTML, DOCS, ARTICLE, SPA
        return self.extract(html)