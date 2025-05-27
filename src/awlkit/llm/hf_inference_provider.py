"""
Hugging Face Inference API provider for fast cloud-based inference.

This provider uses the Hugging Face Inference API instead of loading models locally.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
import aiohttp
import requests

from . import LLMProvider

logger = logging.getLogger(__name__)


class HFInferenceProvider(LLMProvider):
    """Hugging Face Inference API provider."""
    
    def __init__(
        self,
        model_id: str = "mistralai/Mixtral-8x7B-Instruct-v0.1",
        api_token: Optional[str] = None,
        base_url: str = "https://api-inference.huggingface.co/models"
    ):
        """
        Initialize HF Inference API provider.
        
        Args:
            model_id: Model ID on Hugging Face Hub
            api_token: Hugging Face API token (or set HF_TOKEN env var)
            base_url: Base URL for the inference API
        """
        self.model_id = model_id
        self.api_token = api_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
        self.base_url = base_url
        self._available = None
        
        if not self.api_token:
            logger.warning(
                "No Hugging Face API token provided. "
                "Set HF_TOKEN environment variable or pass api_token parameter. "
                "You can get a free token at https://huggingface.co/settings/tokens"
            )
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate response using HF Inference API.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
                - max_new_tokens: Maximum tokens to generate (default: 512)
                - temperature: Sampling temperature (default: 0.7)
                - top_p: Nucleus sampling parameter (default: 0.95)
                - do_sample: Whether to sample (default: True)
        """
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        # Format prompt based on model
        formatted_prompt = self._format_prompt(prompt)
        
        # Prepare parameters
        parameters = {
            "max_new_tokens": kwargs.get("max_new_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.95),
            "do_sample": kwargs.get("do_sample", True),
            "return_full_text": False
        }
        
        payload = {
            "inputs": formatted_prompt,
            "parameters": parameters
        }
        
        url = f"{self.base_url}/{self.model_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        # Extract generated text
                        if isinstance(result, list) and len(result) > 0:
                            return result[0].get("generated_text", "")
                        return str(result)
                    else:
                        error_text = await response.text()
                        raise Exception(f"API request failed ({response.status}): {error_text}")
        except Exception as e:
            logger.error(f"HF Inference API error: {e}")
            raise
    
    def _format_prompt(self, prompt: str) -> str:
        """Format prompt according to model's expected format."""
        model_lower = self.model_id.lower()
        
        # Phi-3 format
        if "phi-3" in model_lower:
            return f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        
        # Mixtral/Mistral instruct format
        elif "mixtral" in model_lower or "mistral" in model_lower:
            return f"<s>[INST] {prompt} [/INST]"
        
        # Llama 2 chat format
        elif "llama-2" in model_lower and "chat" in model_lower:
            return f"<s>[INST] <<SYS>>\nYou are a helpful assistant.\n<</SYS>>\n\n{prompt} [/INST]"
        
        # Falcon instruct format
        elif "falcon" in model_lower and "instruct" in model_lower:
            return f"User: {prompt}\nAssistant:"
        
        # Default: return as-is
        else:
            return prompt
    
    def is_available(self) -> bool:
        """Check if the provider is available."""
        if self._available is not None:
            return self._available
        
        if not self.api_token:
            logger.warning("No API token available for Hugging Face Inference API")
            self._available = False
            return False
        
        # Test the API with a simple request
        try:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            url = f"{self.base_url}/{self.model_id}"
            
            response = requests.post(
                url,
                headers=headers,
                json={"inputs": "test", "parameters": {"max_new_tokens": 1}}
            )
            
            if response.status_code == 200:
                self._available = True
                logger.info(f"HF Inference API available with model {self.model_id}")
            else:
                logger.warning(f"HF Inference API returned status {response.status_code}")
                self._available = False
        except Exception as e:
            logger.warning(f"Failed to check HF Inference API availability: {e}")
            self._available = False
        
        return self._available
    
    def list_recommended_models(self) -> Dict[str, Dict[str, Any]]:
        """List recommended models available via HF Inference API."""
        return {
            "mistralai/Mixtral-8x7B-Instruct-v0.1": {
                "description": "Mixtral 8x7B - Excellent performance, fast inference",
                "context_length": 32768,
                "free_tier": True
            },
            "mistralai/Mistral-7B-Instruct-v0.2": {
                "description": "Mistral 7B - Fast and efficient",
                "context_length": 32768,
                "free_tier": True
            },
            "google/flan-t5-xxl": {
                "description": "FLAN-T5 XXL - Good for specific tasks",
                "context_length": 512,
                "free_tier": True
            },
            "bigscience/bloom": {
                "description": "BLOOM - Multilingual model",
                "context_length": 2048,
                "free_tier": True
            },
            "meta-llama/Llama-2-13b-chat-hf": {
                "description": "Llama 2 13B Chat - Requires Pro subscription",
                "context_length": 4096,
                "free_tier": False
            }
        }