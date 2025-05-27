"""
Hugging Face Transformers provider for local LLM inference.

This provider uses the transformers library to run models locally without
requiring a separate server like Ollama.
"""

import logging
from typing import Optional, Dict, Any

from . import LLMProvider

logger = logging.getLogger(__name__)


class HuggingFaceProvider(LLMProvider):
    """Hugging Face Transformers provider for local inference."""
    
    def __init__(
        self,
        model_id: str = "meta-llama/Llama-2-7b-chat-hf",
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        load_in_4bit: bool = False,
        trust_remote_code: bool = False,
        cache_dir: Optional[str] = None,
        auth_token: Optional[str] = None
    ):
        """
        Initialize Hugging Face provider.
        
        Args:
            model_id: Model identifier - can be:
                - HuggingFace model ID (e.g., "meta-llama/Llama-2-7b-chat-hf")
                - Local directory path containing model files
                - Local file path to model weights (e.g., "/path/to/model.bin")
            device: Device to use ("cuda", "cpu", or None for auto-detect)
            load_in_8bit: Use 8-bit quantization (requires bitsandbytes)
            load_in_4bit: Use 4-bit quantization (requires bitsandbytes)
            trust_remote_code: Trust remote code in model repo
            cache_dir: Directory to cache downloaded models
            auth_token: HuggingFace authentication token for gated models
        """
        self.model_id = model_id
        self.device = device
        self.load_in_8bit = load_in_8bit
        self.load_in_4bit = load_in_4bit
        self.trust_remote_code = trust_remote_code
        self.cache_dir = cache_dir
        self.auth_token = auth_token
        
        # Check if model_id is a local path
        from pathlib import Path
        model_path = Path(model_id)
        self.is_local = model_path.exists()
        
        # Device will be set when loading model
        self._device = None
        
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self._available = None
        
    def _load_model(self):
        """Lazy load the model when first needed."""
        if self.model is not None:
            return
        
        # Import here to avoid import errors when transformers not installed
        try:
            import torch
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                pipeline,
                BitsAndBytesConfig
            )
        except ImportError as e:
            raise ImportError(
                "Transformers library not installed. "
                "Install with: pip install transformers torch"
            ) from e
        
        # Set device if not already set
        if self._device is None:
            self._device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            
        model_desc = f"local model at {self.model_id}" if self.is_local else f"model {self.model_id}"
        logger.info(f"Loading {model_desc} on {self._device}")
        
        try:
            # Configure quantization if requested
            quantization_config = None
            if self.load_in_4bit:
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16
                )
            elif self.load_in_8bit:
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            
            # For local paths, we don't need auth token
            token = None if self.is_local else self.auth_token
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=self.trust_remote_code,
                cache_dir=None if self.is_local else self.cache_dir,
                token=token
            )
            
            # Set padding token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with appropriate settings
            model_kwargs = {
                "trust_remote_code": self.trust_remote_code,
                "cache_dir": None if self.is_local else self.cache_dir,
                "token": token,
                "torch_dtype": torch.float16 if self._device == "cuda" else torch.float32,
            }
            
            if quantization_config:
                model_kwargs["quantization_config"] = quantization_config
                model_kwargs["device_map"] = "auto"
            elif self._device != "cpu":
                # Only use device_map for GPU devices
                model_kwargs["device_map"] = self._device
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                **model_kwargs
            )
            
            # Create text generation pipeline
            # Don't specify device if model uses device_map="auto" (quantization or multi-GPU)
            pipeline_kwargs = {
                "model": self.model,
                "tokenizer": self.tokenizer,
            }
            # Only set device if we're not using device_map and it's a CPU model
            device_map_used = model_kwargs.get("device_map", None)
            if device_map_used is None and self._device == "cpu":
                pipeline_kwargs["device"] = self._device
                
            self.pipeline = pipeline(
                "text-generation",
                **pipeline_kwargs
            )
            
            logger.info(f"Model {self.model_id} loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load model {self.model_id}: {e}")
            raise
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate response using Hugging Face model.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
                - max_new_tokens: Maximum tokens to generate (default: 512)
                - temperature: Sampling temperature (default: 0.7)
                - top_p: Nucleus sampling parameter (default: 0.9)
                - do_sample: Whether to sample (default: True)
        """
        # Run synchronous generation in thread pool to avoid blocking
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_sync, prompt, kwargs)
    
    def _generate_sync(self, prompt: str, kwargs: dict) -> str:
        """Synchronous generation method."""
        # Load model if not already loaded
        self._load_model()
        
        # Set default generation parameters
        gen_kwargs = {
            "max_new_tokens": kwargs.get("max_new_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "do_sample": kwargs.get("do_sample", True),
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        
        # Format prompt for chat models (if applicable)
        formatted_prompt = self._format_prompt(prompt)
        
        # Generate response
        outputs = self.pipeline(
            formatted_prompt,
            **gen_kwargs
        )
        
        # Extract generated text
        generated_text = outputs[0]['generated_text']
        
        # Remove the input prompt from the response
        if generated_text.startswith(formatted_prompt):
            generated_text = generated_text[len(formatted_prompt):].strip()
        
        return generated_text
    
    def _format_prompt(self, prompt: str) -> str:
        """
        Format prompt according to model's expected format.
        
        Different models expect different prompt formats. This method
        handles common formats.
        """
        model_lower = self.model_id.lower()
        
        # Gemma instruction format
        if "gemma" in model_lower and ("it" in model_lower or "instruct" in model_lower):
            return f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
        
        # Llama 2 chat format
        elif "llama-2" in model_lower and "chat" in model_lower:
            return f"<s>[INST] {prompt} [/INST]"
        
        # Alpaca format
        elif "alpaca" in model_lower:
            return f"### Instruction:\n{prompt}\n\n### Response:\n"
        
        # Vicuna format
        elif "vicuna" in model_lower:
            return f"USER: {prompt}\nASSISTANT:"
        
        # Default format
        else:
            return prompt
    
    def is_available(self) -> bool:
        """Check if the provider is available."""
        if self._available is not None:
            return self._available
        
        try:
            # Check if transformers is installed
            import transformers
            
            # Check if model ID is valid
            if self.is_local:
                # For local paths, just check if it exists
                from pathlib import Path
                if not Path(self.model_id).exists():
                    logger.warning(f"Local model path does not exist: {self.model_id}")
                    self._available = False
                    return False
            else:
                # For HuggingFace IDs, check format
                if "/" not in self.model_id:
                    logger.warning(f"Invalid HuggingFace model ID format: {self.model_id}")
                    self._available = False
                    return False
            
            # Check for GPU if specified
            if self.device == "cuda":
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.warning("CUDA requested but not available")
                        self._available = False
                        return False
                except ImportError:
                    logger.warning("Cannot check CUDA availability without torch")
                    self._available = False
                    return False
            
            self._available = True
            logger.info(f"HuggingFace provider available with model {self.model_id}")
            
        except ImportError:
            logger.warning("transformers library not installed")
            self._available = False
        
        return self._available
    
    def list_recommended_models(self) -> Dict[str, Dict[str, Any]]:
        """List recommended models for SV analysis."""
        return {
            "meta-llama/Llama-2-7b-chat-hf": {
                "size": "7B",
                "memory": "13GB",
                "description": "Llama 2 7B Chat - Good balance of performance and quality",
                "requires_auth": True
            },
            "meta-llama/Llama-2-13b-chat-hf": {
                "size": "13B", 
                "memory": "26GB",
                "description": "Llama 2 13B Chat - Better quality, more memory needed",
                "requires_auth": True
            },
            "mistralai/Mistral-7B-Instruct-v0.2": {
                "size": "7B",
                "memory": "13GB", 
                "description": "Mistral 7B Instruct - Fast and efficient",
                "requires_auth": False
            },
            "microsoft/phi-2": {
                "size": "2.7B",
                "memory": "6GB",
                "description": "Phi-2 - Small but capable model",
                "requires_auth": False
            },
            "codellama/CodeLlama-7b-Instruct-hf": {
                "size": "7B",
                "memory": "13GB",
                "description": "Code Llama 7B - Optimized for code and technical content",
                "requires_auth": False
            }
        }