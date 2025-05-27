"""
CWLTool execution engine wrapper.
"""

import subprocess
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import time

from .base import ExecutionEngine, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class CWLToolRunner(ExecutionEngine):
    """Wrapper for cwltool - the reference CWL implementation."""
    
    def _validate_config(self):
        """Validate cwltool configuration."""
        # Set default options if not provided
        self.config.setdefault('parallel', True)
        self.config.setdefault('cachedir', None)
        self.config.setdefault('tmpdir_prefix', None)
        self.config.setdefault('outdir', None)
        self.config.setdefault('leave_tmpdir', False)
        self.config.setdefault('enable_pull', True)
        self.config.setdefault('no_container', False)
        self.config.setdefault('singularity', False)
        self.config.setdefault('podman', False)
    
    def is_available(self) -> bool:
        """Check if cwltool is installed."""
        try:
            result = subprocess.run(
                ['cwltool', '--version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                logger.info(f"cwltool is available: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        logger.warning("cwltool is not installed")
        return False
    
    def validate_workflow(self, workflow_path: Path) -> bool:
        """Validate a CWL workflow using cwltool."""
        if not self.is_available():
            raise RuntimeError("cwltool is not available")
        
        cmd = ['cwltool', '--validate', str(workflow_path)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                logger.info(f"Workflow validation successful: {workflow_path}")
                return True
            else:
                logger.error(f"Workflow validation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def execute(
        self,
        workflow_path: Path,
        inputs_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a CWL workflow using cwltool.
        
        Args:
            workflow_path: Path to CWL workflow file
            inputs_path: Path to inputs YAML/JSON file
            output_dir: Optional output directory
            **kwargs: Additional cwltool options
            
        Returns:
            ExecutionResult with execution details
        """
        if not self.is_available():
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["cwltool is not installed"]
            )
        
        # Prepare output directory
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path.cwd()
        
        # Build command
        cmd = ['cwltool']
        
        # Add configuration options
        if self.config.get('parallel'):
            cmd.append('--parallel')
        
        if self.config.get('no_container'):
            cmd.append('--no-container')
        elif self.config.get('singularity'):
            cmd.append('--singularity')
        elif self.config.get('podman'):
            cmd.append('--podman')
        
        if self.config.get('cachedir'):
            cmd.extend(['--cachedir', str(self.config['cachedir'])])
        
        if self.config.get('tmpdir_prefix'):
            cmd.extend(['--tmpdir-prefix', str(self.config['tmpdir_prefix'])])
        
        if self.config.get('leave_tmpdir'):
            cmd.append('--leave-tmpdir')
        
        if not self.config.get('enable_pull', True):
            cmd.append('--disable-pull')
        
        # Add output directory
        cmd.extend(['--outdir', str(output_dir)])
        
        # Add any additional kwargs as command line options
        for key, value in kwargs.items():
            if value is True:
                cmd.append(f'--{key.replace("_", "-")}')
            elif value is not False and value is not None:
                cmd.extend([f'--{key.replace("_", "-")}', str(value)])
        
        # Add workflow and inputs
        cmd.extend([str(workflow_path), str(inputs_path)])
        
        # Execute
        logger.info(f"Executing: {' '.join(cmd)}")
        start_time = time.time()
        
        try:
            # Create temporary file for stdout
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_out:
                tmp_out_path = Path(tmp_out.name)
            
            # Run cwltool
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            duration = time.time() - start_time
            
            # Parse results
            if result.returncode == 0:
                # Try to parse output JSON
                outputs = {}
                try:
                    # cwltool writes JSON output to stdout
                    if result.stdout:
                        outputs = json.loads(result.stdout)
                except json.JSONDecodeError:
                    logger.warning("Could not parse cwltool output as JSON")
                
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    outputs=outputs,
                    logs=result.stderr,
                    duration_seconds=duration
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    errors=[result.stderr],
                    logs=result.stderr,
                    duration_seconds=duration
                )
        
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=[str(e)],
                duration_seconds=time.time() - start_time
            )
        finally:
            # Cleanup
            if 'tmp_out_path' in locals() and tmp_out_path.exists():
                tmp_out_path.unlink()
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about cwltool."""
        info = super().get_engine_info()
        
        if self.is_available():
            try:
                result = subprocess.run(
                    ['cwltool', '--version'],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    info['version'] = result.stdout.strip()
            except:
                pass
        
        info['capabilities'] = [
            'local_execution',
            'docker_support',
            'singularity_support',
            'podman_support',
            'parallel_execution',
            'caching'
        ]
        
        return info