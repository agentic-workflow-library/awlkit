"""
Base Agent class for AWLKit.

Provides common functionality for all domain-specific agents.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import logging

from awlkit.execution import LocalRunner, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class Agent(ABC):
    """Base class for all AWL domain agents."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize agent with optional configuration."""
        self.config = config or {}
        self._workflow_cache = {}
        self._setup_logging()
        self._setup_execution_engine()
    
    def _setup_logging(self):
        """Set up logging configuration."""
        log_level = self.config.get('log_level', 'INFO')
        logging.basicConfig(level=getattr(logging, log_level))
    
    def _setup_execution_engine(self):
        """Set up the execution engine."""
        execution_config = self.config.get('execution', {})
        self.execution_engine = LocalRunner(execution_config)
    
    def process_batch(self, batch_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic batch processing with validation.
        
        Args:
            batch_config: Configuration dictionary with batch processing parameters
            
        Returns:
            Results dictionary from batch processing
        """
        # Validate batch configuration
        self._validate_batch_config(batch_config)
        
        # Log batch processing start
        logger.info(f"Starting batch processing with {len(batch_config['samples'])} samples")
        
        try:
            # Call domain-specific implementation
            results = self._execute_batch(batch_config)
            
            # Add generic metadata
            results['_metadata'] = {
                'agent': self.__class__.__name__,
                'samples_requested': len(batch_config['samples']),
                'config': self.config
            }
            
            logger.info("Batch processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise
    
    def _validate_batch_config(self, batch_config: Dict[str, Any]):
        """Validate batch configuration."""
        if not isinstance(batch_config, dict):
            raise TypeError("batch_config must be a dictionary")
        
        if 'samples' not in batch_config:
            raise ValueError("batch_config must contain 'samples' key")
        
        if not isinstance(batch_config['samples'], list):
            raise ValueError("'samples' must be a list")
        
        if not batch_config['samples']:
            raise ValueError("'samples' list cannot be empty")
        
        # Validate each sample has required fields
        for i, sample in enumerate(batch_config['samples']):
            if not isinstance(sample, dict):
                raise ValueError(f"Sample {i} must be a dictionary")
            if 'id' not in sample:
                raise ValueError(f"Sample {i} missing required 'id' field")
    
    @abstractmethod
    def _execute_batch(self, batch_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Domain-specific batch execution to be implemented by subclasses.
        
        Args:
            batch_config: Validated batch configuration
            
        Returns:
            Domain-specific results dictionary
        """
        pass
    
    def analyze_workflow(self, workflow_path: str) -> Dict[str, Any]:
        """
        Analyze a workflow file (generic implementation).
        
        Args:
            workflow_path: Path to workflow file
            
        Returns:
            Analysis results including inputs, outputs, and structure
        """
        workflow_path = str(workflow_path)
        
        # Check cache first
        if workflow_path in self._workflow_cache:
            logger.debug(f"Returning cached analysis for {workflow_path}")
            return self._workflow_cache[workflow_path]
        
        # Use WorkflowAnalyzer for detailed analysis
        from awlkit.utils import WorkflowAnalyzer
        analyzer = WorkflowAnalyzer()
        
        try:
            analysis = analyzer.analyze(workflow_path)
            self._workflow_cache[workflow_path] = analysis
            return analysis
        except Exception as e:
            logger.error(f"Failed to analyze workflow {workflow_path}: {e}")
            raise
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Validate inputs against agent requirements.
        
        Args:
            inputs: Input dictionary to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        required_fields = self.config.get('required_inputs', [])
        
        for field in required_fields:
            if field not in inputs:
                raise ValueError(f"Missing required input: {field}")
        
        # Call domain-specific validation if available
        if hasattr(self, '_validate_domain_inputs'):
            self._validate_domain_inputs(inputs)
        
        return True
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of agent capabilities.
        
        Returns:
            List of capability strings
        """
        # Base capabilities all agents have
        base_capabilities = [
            'process_batch',
            'analyze_workflow',
            'validate_inputs',
            'execute_workflow',
            'validate_workflow'
        ]
        
        # Add domain-specific capabilities if defined
        domain_capabilities = getattr(self, 'domain_capabilities', [])
        
        return base_capabilities + domain_capabilities
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get agent metadata.
        
        Returns:
            Metadata dictionary
        """
        return {
            'name': self.__class__.__name__,
            'module': self.__class__.__module__,
            'capabilities': self.get_capabilities(),
            'config': self.config,
            'execution_engine': self.execution_engine.get_engine_info() if self.execution_engine else None
        }
    
    def execute_workflow(
        self,
        workflow_path: Path,
        inputs_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a CWL workflow using the configured execution engine.
        
        Args:
            workflow_path: Path to CWL workflow file
            inputs_path: Path to inputs YAML/JSON file
            output_dir: Optional output directory
            **kwargs: Additional execution options
            
        Returns:
            ExecutionResult with execution status and outputs
        """
        if not self.execution_engine or not self.execution_engine.is_available():
            logger.error("No execution engine available")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["No execution engine available. Install cwltool or configure Seven Bridges."]
            )
        
        # Convert paths to Path objects
        workflow_path = Path(workflow_path)
        inputs_path = Path(inputs_path)
        
        # Validate workflow exists
        if not workflow_path.exists():
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=[f"Workflow file not found: {workflow_path}"]
            )
        
        # Validate inputs exist
        if not inputs_path.exists():
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=[f"Inputs file not found: {inputs_path}"]
            )
        
        # Execute workflow
        logger.info(f"Executing workflow: {workflow_path.name}")
        return self.execution_engine.execute(
            workflow_path,
            inputs_path,
            output_dir,
            **kwargs
        )
    
    def validate_workflow(self, workflow_path: Path) -> bool:
        """
        Validate a CWL workflow file.
        
        Args:
            workflow_path: Path to CWL workflow file
            
        Returns:
            True if valid, False otherwise
        """
        if not self.execution_engine or not self.execution_engine.is_available():
            logger.error("No execution engine available for validation")
            return False
        
        workflow_path = Path(workflow_path)
        if not workflow_path.exists():
            logger.error(f"Workflow file not found: {workflow_path}")
            return False
        
        return self.execution_engine.validate_workflow(workflow_path)