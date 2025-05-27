"""
Seven Bridges Platform execution engine wrapper.
"""

import subprocess
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from .base import ExecutionEngine, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class SevenBridgesRunner(ExecutionEngine):
    """Wrapper for Seven Bridges Platform CLI (sb)."""
    
    def _validate_config(self):
        """Validate Seven Bridges configuration."""
        # Required configuration
        if 'project' not in self.config:
            raise ValueError("Seven Bridges project ID is required in config")
        
        # Optional configuration with defaults
        self.config.setdefault('platform', 'https://api.sbgenomics.com')
        self.config.setdefault('profile', 'default')
        self.config.setdefault('instance_type', 'c5.xlarge')
        self.config.setdefault('spot_instance', True)
        self.config.setdefault('monitoring', True)
        
        # Check for auth token
        if 'auth_token' not in self.config:
            # Try to get from environment
            self.config['auth_token'] = os.environ.get('SB_AUTH_TOKEN')
            if not self.config['auth_token']:
                logger.warning("No Seven Bridges auth token found. Set SB_AUTH_TOKEN or provide in config.")
    
    def is_available(self) -> bool:
        """Check if sb CLI is installed and configured."""
        try:
            # Check if sb CLI is installed
            result = subprocess.run(
                ['sb', '--version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                return False
            
            # Check if we have authentication
            if not self.config.get('auth_token'):
                return False
            
            logger.info(f"Seven Bridges CLI is available: {result.stdout.strip()}")
            return True
            
        except FileNotFoundError:
            logger.warning("Seven Bridges CLI (sb) is not installed")
            return False
    
    def validate_workflow(self, workflow_path: Path) -> bool:
        """Validate a CWL workflow for Seven Bridges compatibility."""
        if not self.is_available():
            raise RuntimeError("Seven Bridges CLI is not available")
        
        # Seven Bridges validation is done during app creation
        # For now, just check if file exists and is valid CWL
        if not workflow_path.exists():
            return False
        
        # Use cwltool for validation if available
        try:
            result = subprocess.run(
                ['cwltool', '--validate', str(workflow_path)],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            # If cwltool not available, assume valid
            logger.warning("cwltool not available for validation, assuming workflow is valid")
            return True
    
    def _create_app(self, workflow_path: Path, app_id: str) -> bool:
        """Create or update an app on Seven Bridges."""
        cmd = [
            'sb', 'apps', 'install',
            '--profile', self.config['profile'],
            '--project', self.config['project'],
            '--appid', app_id,
            str(workflow_path)
        ]
        
        if self.config.get('auth_token'):
            env = os.environ.copy()
            env['SB_AUTH_TOKEN'] = self.config['auth_token']
        else:
            env = None
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully created/updated app: {app_id}")
            return True
        else:
            logger.error(f"Failed to create app: {result.stderr}")
            return False
    
    def _create_task(self, app_id: str, inputs: Dict[str, Any], task_name: str) -> Optional[str]:
        """Create a task (job) on Seven Bridges."""
        # Prepare task configuration
        task_config = {
            'name': task_name,
            'app': f"{self.config['project']}/{app_id}",
            'inputs': inputs,
            'instance_type': self.config['instance_type'],
            'use_spot_instances': self.config['spot_instance']
        }
        
        # Write task config to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(task_config, f)
            config_file = f.name
        
        try:
            cmd = [
                'sb', 'tasks', 'create',
                '--profile', self.config['profile'],
                '--file', config_file
            ]
            
            if self.config.get('auth_token'):
                env = os.environ.copy()
                env['SB_AUTH_TOKEN'] = self.config['auth_token']
            else:
                env = None
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False
            )
            
            if result.returncode == 0:
                # Parse task ID from output
                try:
                    output = json.loads(result.stdout)
                    task_id = output.get('id')
                    logger.info(f"Created task: {task_id}")
                    return task_id
                except:
                    logger.error("Failed to parse task creation output")
                    return None
            else:
                logger.error(f"Failed to create task: {result.stderr}")
                return None
                
        finally:
            # Cleanup temp file
            Path(config_file).unlink(missing_ok=True)
    
    def _run_task(self, task_id: str) -> bool:
        """Run a task on Seven Bridges."""
        cmd = [
            'sb', 'tasks', 'run',
            '--profile', self.config['profile'],
            task_id
        ]
        
        if self.config.get('auth_token'):
            env = os.environ.copy()
            env['SB_AUTH_TOKEN'] = self.config['auth_token']
        else:
            env = None
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False
        )
        
        return result.returncode == 0
    
    def _monitor_task(self, task_id: str) -> ExecutionResult:
        """Monitor task execution until completion."""
        start_time = time.time()
        
        while True:
            cmd = [
                'sb', 'tasks', 'get',
                '--profile', self.config['profile'],
                task_id
            ]
            
            if self.config.get('auth_token'):
                env = os.environ.copy()
                env['SB_AUTH_TOKEN'] = self.config['auth_token']
            else:
                env = None
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False
            )
            
            if result.returncode != 0:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    errors=[f"Failed to get task status: {result.stderr}"],
                    duration_seconds=time.time() - start_time
                )
            
            try:
                task_info = json.loads(result.stdout)
                status = task_info.get('status', {}).get('message', 'UNKNOWN')
                
                if status == 'COMPLETED':
                    # Get outputs
                    outputs = task_info.get('outputs', {})
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        outputs=outputs,
                        execution_id=task_id,
                        duration_seconds=time.time() - start_time
                    )
                elif status in ['FAILED', 'ABORTED']:
                    errors = [task_info.get('status', {}).get('error', 'Unknown error')]
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        errors=errors,
                        execution_id=task_id,
                        duration_seconds=time.time() - start_time
                    )
                
                # Still running
                logger.info(f"Task {task_id} status: {status}")
                time.sleep(30)  # Check every 30 seconds
                
            except json.JSONDecodeError:
                logger.error("Failed to parse task info")
                time.sleep(30)
    
    def execute(
        self,
        workflow_path: Path,
        inputs_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a CWL workflow on Seven Bridges Platform.
        
        Args:
            workflow_path: Path to CWL workflow file
            inputs_path: Path to inputs YAML/JSON file
            output_dir: Not used for Seven Bridges (outputs stored on platform)
            **kwargs: Additional options (app_name, task_name)
            
        Returns:
            ExecutionResult with execution details
        """
        if not self.is_available():
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["Seven Bridges CLI is not available or not configured"]
            )
        
        # Generate app and task names
        app_name = kwargs.get('app_name', workflow_path.stem)
        task_name = kwargs.get('task_name', f"{app_name}_run_{int(time.time())}")
        
        # Step 1: Create/update app
        logger.info(f"Creating app: {app_name}")
        if not self._create_app(workflow_path, app_name):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["Failed to create app on Seven Bridges"]
            )
        
        # Step 2: Load inputs
        try:
            with open(inputs_path, 'r') as f:
                if inputs_path.suffix == '.json':
                    inputs = json.load(f)
                else:
                    # Assume YAML
                    import yaml
                    inputs = yaml.safe_load(f)
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=[f"Failed to load inputs: {e}"]
            )
        
        # Step 3: Create task
        logger.info(f"Creating task: {task_name}")
        task_id = self._create_task(app_name, inputs, task_name)
        if not task_id:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["Failed to create task on Seven Bridges"]
            )
        
        # Step 4: Run task
        logger.info(f"Running task: {task_id}")
        if not self._run_task(task_id):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                errors=["Failed to start task on Seven Bridges"],
                execution_id=task_id
            )
        
        # Step 5: Monitor execution
        if self.config.get('monitoring', True):
            logger.info(f"Monitoring task: {task_id}")
            return self._monitor_task(task_id)
        else:
            # Return immediately without monitoring
            return ExecutionResult(
                status=ExecutionStatus.RUNNING,
                execution_id=task_id,
                logs=f"Task submitted: {task_id}. Check platform for status."
            )
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about Seven Bridges engine."""
        info = super().get_engine_info()
        
        info['platform'] = self.config.get('platform', 'Unknown')
        info['project'] = self.config.get('project', 'Not configured')
        
        if self.is_available():
            try:
                result = subprocess.run(
                    ['sb', '--version'],
                    capture_output=True,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    info['cli_version'] = result.stdout.strip()
            except:
                pass
        
        info['capabilities'] = [
            'cloud_execution',
            'scalable_compute',
            'data_management',
            'collaborative_projects',
            'workflow_versioning',
            'execution_monitoring'
        ]
        
        return info