"""LLM provider for AWLKit - HuggingFace Transformers only.

This module provides local LLM inference using HuggingFace Transformers.
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional

from .utils import ConversationMemory, format_prompt_for_sv_domain

# Lazy import HuggingFaceProvider to avoid import errors
def get_huggingface_provider():
    """Get HuggingFaceProvider class, importing it lazily."""
    from .huggingface_provider import HuggingFaceProvider
    return HuggingFaceProvider

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


__all__ = [
    "LLMProvider",
    "get_huggingface_provider",
    "ConversationMemory",
    "format_prompt_for_sv_domain"
]