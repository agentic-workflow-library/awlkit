"""Utility functions for LLM integration."""

import os
import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def check_ollama_installed() -> bool:
    """Check if Ollama is installed on the system."""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_ollama_model(model: str = "codellama:13b") -> bool:
    """Pull an Ollama model if not already available."""
    try:
        logger.info(f"Pulling Ollama model: {model}")
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Successfully pulled {model}")
            return True
        else:
            logger.error(f"Failed to pull {model}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error pulling Ollama model: {e}")
        return False


def get_recommended_models() -> Dict[str, Dict[str, str]]:
    """Get recommended Ollama models for SV analysis."""
    return {
        "codellama:13b": {
            "size": "7.4GB",
            "description": "Best for code generation and CWL writing",
            "use_case": "workflow_conversion"
        },
        "mixtral:8x7b": {
            "size": "26GB",
            "description": "Best overall performance for complex analysis",
            "use_case": "comprehensive_analysis"
        },
        "llama2:13b": {
            "size": "7.4GB",
            "description": "Good general purpose model",
            "use_case": "general_qa"
        },
        "phi-2": {
            "size": "1.7GB",
            "description": "Lightweight, fast responses",
            "use_case": "quick_responses"
        },
        "biomistral": {
            "size": "4.1GB",
            "description": "Fine-tuned for biomedical text",
            "use_case": "biomedical_qa"
        }
    }


def suggest_model_for_task(task: str) -> str:
    """Suggest the best Ollama model for a given task."""
    task_lower = task.lower()
    
    if any(keyword in task_lower for keyword in ["convert", "cwl", "wdl", "code"]):
        return "codellama:13b"
    elif any(keyword in task_lower for keyword in ["biomedical", "variant", "clinical"]):
        return "biomistral"
    elif any(keyword in task_lower for keyword in ["quick", "fast", "simple"]):
        return "phi-2"
    else:
        return "llama2:13b"


def format_prompt_for_sv_domain(prompt: str, context: Optional[str] = None) -> str:
    """Format prompt with SV-specific context."""
    # First try to load from sv_agent's prompts directory
    import os
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                     "sv_agent", "prompts", "system_prompt.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                     "prompts", "system_prompt.txt")
    ]
    
    system_context = None
    for path in possible_paths:
        try:
            with open(path, 'r') as f:
                system_context = f.read()
                break
        except FileNotFoundError:
            continue
    
    if not system_context:
        # Fallback to basic context
        system_context = """You are an AI assistant with expertise in structural variant (SV) analysis and the GATK-SV pipeline.
You have general knowledge about genomics, biology, and bioinformatics, plus specialized knowledge of:
- WDL and CWL workflow languages
- SV calling algorithms (Manta, MELT, Wham, etc.)
- Genomic data formats (VCF, BAM, CRAM)
- Best practices for SV discovery and genotyping
- GATK-SV module architecture and dependencies

You can answer both general biology/genomics questions and specific GATK-SV questions."""
    
    if context:
        full_prompt = f"{system_context}\n\nAdditional Context:\n{context}\n\nUser Question: {prompt}\n\nProvide a helpful and informative response:"
    else:
        full_prompt = f"{system_context}\n\nUser Question: {prompt}\n\nProvide a helpful and informative response:"
    
    return full_prompt


def estimate_token_count(text: str) -> int:
    """Rough estimation of token count."""
    # Approximate: 1 token ≈ 4 characters
    return len(text) // 4


class ConversationMemory:
    """Simple conversation memory for multi-turn interactions."""
    
    def __init__(self, max_turns: int = 10):
        self.history: List[Dict[str, str]] = []
        self.max_turns = max_turns
    
    def add_turn(self, user_input: str, assistant_response: str):
        """Add a conversation turn."""
        self.history.append({
            "user": user_input,
            "assistant": assistant_response
        })
        
        # Keep only recent history
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]
    
    def get_context(self, n_turns: int = 3) -> str:
        """Get recent conversation context."""
        if not self.history:
            return ""
        
        recent = self.history[-n_turns:]
        context_parts = []
        
        for turn in recent:
            context_parts.append(f"User: {turn['user']}")
            context_parts.append(f"Assistant: {turn['assistant']}")
        
        return "\n".join(context_parts)
    
    def clear(self):
        """Clear conversation history."""
        self.history = []