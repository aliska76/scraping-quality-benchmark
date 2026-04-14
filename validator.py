"""
Validates extracted content quality.
Decides if content is good enough or needs fallback.
"""

from typing import Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of content validation."""
    is_valid: bool
    reason: str
    content: str
    score: float


class ContentValidator:
    """
    Validates extracted content quality.
    
    Checks:
    - Not empty
    - Not too short
    - Not a block page (CAPTCHA, Cloudflare)
    """
    
    def __init__(self, min_length: int = 200):
        self.min_length = min_length
        
        self.block_markers = [
            'cloudflare', 'captcha', 'access denied', 
            'verify you are human', 'bot detection', 
            'attention required', 'enable javascript'
        ]
    
    def _is_block_page(self, content: str) -> bool:
        if not content:
            return True
        content_lower = content.lower()
        return any(marker in content_lower for marker in self.block_markers)
    
    def validate(self, content: str, status_code: int) -> ValidationResult:
        """Validate extracted content."""
        
        if status_code >= 400:
            return ValidationResult(
                is_valid=False,
                reason=f"HTTP {status_code}",
                content="",
                score=0.0
            )
        
        if not content or len(content.strip()) == 0:
            return ValidationResult(
                is_valid=False,
                reason="Empty content",
                content="",
                score=0.0
            )
        
        if self._is_block_page(content):
            return ValidationResult(
                is_valid=False,
                reason="Block page detected",
                content=content[:500],
                score=0.0
            )
        
        if len(content) < self.min_length:
            return ValidationResult(
                is_valid=False,
                reason=f"Too short: {len(content)} chars",
                content=content,
                score=len(content) / self.min_length
            )
        
        return ValidationResult(
            is_valid=True,
            reason="OK",
            content=content,
            score=1.0
        )
    
    def needs_fallback(self, result: ValidationResult) -> bool:
        return not result.is_valid