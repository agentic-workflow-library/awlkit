"""
Local execution runner that auto-selects the best available engine.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from .base import ExecutionEngine, ExecutionResult, ExecutionStatus
from .cwltool_runner import CWLToolRunner
from .sevenbridges_runner import SevenBridgesRunner

logger = logging.getLogger(__name__)


class LocalRunner(ExecutionEngine):
    """
    Smart local runner that automatically selects the best available execution engine.
    
    Priority order:
    1. CWLTool (if available)
    2. Seven Bridges (if configured)
    3. Error if none available
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize with optional preferred engine."""
        # Set preferred_engine before calling super().__init__
        config = config or {}
        self.preferred_engine = config.get('preferred_engine', 'auto')
        self._engine = None
        super().__init__(config)
        self._initialize_engine()
    
    def _validate_config(self):
        """Validate configuration."""
        valid_engines = ['auto', 'cwltool', 'sevenbridges']
        if self.preferred_engine not in valid_engines:
            raise ValueError(f"Invalid preferred_engine: {self.preferred_engine}")
    
    def _initialize_engine(self):
        """Initialize the execution engine based on availability and preference."""
        engines = []
        
        # Check preferred engine first
        if self.preferred_engine == 'cwltool':
            cwltool = CWLToolRunner(self.config.get('cwltool_config', {}))
            if cwltool.is_available():
                self._engine = cwltool
                logger.info("Using CWLTool as execution engine")
                return
            else:
                logger.warning("CWLTool requested but not available")
        
        elif self.preferred_engine == 'sevenbridges':
            sb = SevenBridgesRunner(self.config.get('sevenbridges_config', {}))
            if sb.is_available():
                self._engine = sb
                logger.info("Using Seven Bridges as execution engine")
                return
            else:
                logger.warning("Seven Bridges requested but not available")
        
        # Auto mode - try all engines
        if self.preferred_engine == 'auto':
            # Try CWLTool first (local execution)
            try:
                cwltool = CWLToolRunner(self.config.get('cwltool_config', {}))
                if cwltool.is_available():
                    engines.append(('cwltool', cwltool))
            except Exception as e:
                logger.debug(f"CWLTool not available: {e}")
            
            # Try Seven Bridges (cloud execution)
            try:
                sb = SevenBridgesRunner(self.config.get('sevenbridges_config', {}))
                if sb.is_available():
                    engines.append(('sevenbridges', sb))
            except Exception as e:
                logger.debug(f"Seven Bridges not available: {e}")
            
            # Select first available engine
            if engines:
                name, engine = engines[0]
                self._engine = engine
                logger.info(f"Auto-selected {name} as execution engine")
                return
        
        # No engine available
        self._engine = None
        logger.error("No execution engine available")
    
    def is_available(self) -> bool:
        """Check if any execution engine is available."""
        return self._engine is not None
    
    def validate_workflow(self, workflow_path: Path) -> bool:
        """Validate workflow using the selected engine."""
        if not self._engine:
            raise RuntimeError("No execution engine available")
        return self._engine.validate_workflow(workflow_path)
    
    def execute(
        self,
        workflow_path: Path,
        inputs_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> ExecutionResult:
        """Execute workflow using the selected engine."""
        if not self._engine:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["No execution engine available. Install cwltool or configure Seven Bridges."]
            )
        
        logger.info(f"Executing workflow with {self._engine.__class__.__name__}")
        return self._engine.execute(workflow_path, inputs_path, output_dir, **kwargs)
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about available engines."""
        info = super().get_engine_info()
        
        # Check all engines
        available_engines = []
        
        try:
            cwltool = CWLToolRunner({})
            if cwltool.is_available():
                available_engines.append({
                    'name': 'cwltool',
                    'info': cwltool.get_engine_info()
                })
        except:
            pass
        
        try:
            sb = SevenBridgesRunner(self.config.get('sevenbridges_config', {}))
            if sb.is_available():
                available_engines.append({
                    'name': 'sevenbridges',
                    'info': sb.get_engine_info()
                })
        except:
            pass
        
        info['available_engines'] = available_engines
        info['selected_engine'] = self._engine.__class__.__name__ if self._engine else None
        info['preferred_engine'] = self.preferred_engine
        
        return info
    
    @classmethod
    def list_available_engines(cls) -> List[str]:
        """List all available execution engines."""
        available = []
        
        try:
            if CWLToolRunner({}).is_available():
                available.append('cwltool')
        except:
            pass
        
        try:
            # Seven Bridges needs config, so just check if CLI exists
            import subprocess
            result = subprocess.run(['sb', '--version'], capture_output=True, check=False)
            if result.returncode == 0:
                available.append('sevenbridges')
        except:
            pass
        
        return available