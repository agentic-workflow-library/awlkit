"""
Base classes for workflow execution engines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Result of workflow execution."""
    status: ExecutionStatus
    outputs: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    logs: Optional[str] = None
    execution_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.SUCCESS


class ExecutionEngine(ABC):
    """Abstract base class for workflow execution engines."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize execution engine.
        
        Args:
            config: Engine-specific configuration
        """
        self.config = config or {}
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """Validate engine-specific configuration."""
        pass
    
    @abstractmethod
    def execute(
        self,
        workflow_path: Path,
        inputs_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a CWL workflow.
        
        Args:
            workflow_path: Path to CWL workflow file
            inputs_path: Path to inputs YAML/JSON file
            output_dir: Optional output directory
            **kwargs: Engine-specific execution options
            
        Returns:
            ExecutionResult with status and outputs
        """
        pass
    
    @abstractmethod
    def validate_workflow(self, workflow_path: Path) -> bool:
        """
        Validate a CWL workflow file.
        
        Args:
            workflow_path: Path to CWL workflow file
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this execution engine is available.
        
        Returns:
            True if engine is installed and configured
        """
        pass
    
    def get_engine_info(self) -> Dict[str, Any]:
        """
        Get information about the execution engine.
        
        Returns:
            Dictionary with engine name, version, capabilities
        """
        return {
            "name": self.__class__.__name__,
            "available": self.is_available(),
            "config": self.config
        }