"""
Workflow analysis utilities for AWLKit.

Provides generic workflow analysis capabilities that can be used by any domain agent.
"""

from pathlib import Path
from typing import Dict, Any, List, Set, Optional
import json
import logging
import re

logger = logging.getLogger(__name__)


class WorkflowAnalyzer:
    """Analyzes workflow structure and dependencies."""
    
    def __init__(self):
        """Initialize workflow analyzer."""
        self._cache = {}
    
    def analyze(self, workflow_path: str) -> Dict[str, Any]:
        """
        Analyze a workflow file.
        
        Args:
            workflow_path: Path to workflow file (WDL or CWL)
            
        Returns:
            Dictionary containing analysis results
        """
        workflow_path = str(workflow_path)
        
        # Check cache
        if workflow_path in self._cache:
            return self._cache[workflow_path]
        
        # Determine workflow type
        if workflow_path.endswith('.wdl'):
            analysis = self._analyze_wdl(workflow_path)
        elif workflow_path.endswith('.cwl'):
            analysis = self._analyze_cwl(workflow_path)
        else:
            # Try to detect from content
            analysis = self._analyze_generic(workflow_path)
        
        # Cache results
        self._cache[workflow_path] = analysis
        return analysis
    
    def _analyze_wdl(self, workflow_path: str) -> Dict[str, Any]:
        """Analyze a WDL workflow."""
        try:
            with open(workflow_path, 'r') as f:
                content = f.read()
            
            # Extract workflow name
            workflow_match = re.search(r'workflow\s+(\w+)', content)
            workflow_name = workflow_match.group(1) if workflow_match else Path(workflow_path).stem
            
            # Extract inputs
            inputs = self._extract_wdl_inputs(content)
            
            # Extract outputs
            outputs = self._extract_wdl_outputs(content)
            
            # Extract tasks
            tasks = self._extract_wdl_tasks(content)
            
            # Extract imports
            imports = self._extract_wdl_imports(content)
            
            # Build dependency graph
            dependencies = self._build_wdl_dependencies(content, tasks)
            
            return {
                'path': workflow_path,
                'type': 'WDL',
                'name': workflow_name,
                'inputs': inputs,
                'outputs': outputs,
                'tasks': tasks,
                'imports': imports,
                'dependencies': dependencies,
                'metadata': {
                    'version': self._extract_wdl_version(content),
                    'lines': len(content.splitlines()),
                    'size_bytes': len(content.encode())
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze WDL {workflow_path}: {e}")
            return self._error_analysis(workflow_path, str(e))
    
    def _analyze_cwl(self, workflow_path: str) -> Dict[str, Any]:
        """Analyze a CWL workflow."""
        try:
            import yaml
            
            with open(workflow_path, 'r') as f:
                cwl_doc = yaml.safe_load(f)
            
            # Extract basic info
            cwl_class = cwl_doc.get('class', 'Unknown')
            
            # Extract inputs
            inputs = []
            if 'inputs' in cwl_doc:
                for inp_id, inp_def in cwl_doc['inputs'].items():
                    if isinstance(inp_def, dict):
                        inputs.append(f"{inp_id}: {inp_def.get('type', 'Any')}")
                    else:
                        inputs.append(f"{inp_id}: {inp_def}")
            
            # Extract outputs
            outputs = []
            if 'outputs' in cwl_doc:
                for out_id, out_def in cwl_doc['outputs'].items():
                    if isinstance(out_def, dict):
                        outputs.append(f"{out_id}: {out_def.get('type', 'Any')}")
                    else:
                        outputs.append(f"{out_id}: {out_def}")
            
            # Extract steps (for workflows)
            tasks = []
            dependencies = {}
            if cwl_class == 'Workflow' and 'steps' in cwl_doc:
                for step_id, step_def in cwl_doc['steps'].items():
                    tasks.append(step_id)
                    # Track dependencies through inputs
                    deps = []
                    if 'in' in step_def:
                        for inp_binding in step_def['in'].values():
                            if isinstance(inp_binding, str) and '/' in inp_binding:
                                dep_step = inp_binding.split('/')[0]
                                if dep_step != step_id:
                                    deps.append(dep_step)
                    if deps:
                        dependencies[step_id] = deps
            
            return {
                'path': workflow_path,
                'type': 'CWL',
                'name': cwl_doc.get('id', Path(workflow_path).stem),
                'class': cwl_class,
                'inputs': inputs,
                'outputs': outputs,
                'tasks': tasks,
                'dependencies': dependencies,
                'metadata': {
                    'cwl_version': cwl_doc.get('cwlVersion', 'Unknown'),
                    'requirements': list(cwl_doc.get('requirements', {}).keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze CWL {workflow_path}: {e}")
            return self._error_analysis(workflow_path, str(e))
    
    def _analyze_generic(self, workflow_path: str) -> Dict[str, Any]:
        """Generic workflow analysis for unknown types."""
        try:
            with open(workflow_path, 'r') as f:
                content = f.read()
            
            # Try to detect type from content
            if 'workflow ' in content and 'task ' in content:
                return self._analyze_wdl(workflow_path)
            elif 'cwlVersion' in content or 'class:' in content:
                return self._analyze_cwl(workflow_path)
            else:
                return {
                    'path': workflow_path,
                    'type': 'Unknown',
                    'name': Path(workflow_path).stem,
                    'inputs': [],
                    'outputs': [],
                    'tasks': [],
                    'dependencies': {},
                    'metadata': {
                        'lines': len(content.splitlines()),
                        'size_bytes': len(content.encode())
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to analyze workflow {workflow_path}: {e}")
            return self._error_analysis(workflow_path, str(e))
    
    def _extract_wdl_inputs(self, content: str) -> List[str]:
        """Extract inputs from WDL content."""
        inputs = []
        
        # Look for workflow inputs
        workflow_match = re.search(r'workflow\s+\w+\s*{(.*?)^}', content, re.MULTILINE | re.DOTALL)
        if workflow_match:
            workflow_content = workflow_match.group(1)
            # Find input declarations
            input_pattern = r'^\s*(File|String|Int|Float|Boolean|Array\[.*?\]|Map\[.*?\])\???\s+(\w+)'
            for match in re.finditer(input_pattern, workflow_content, re.MULTILINE):
                var_type = match.group(1)
                var_name = match.group(2)
                inputs.append(f"{var_name}: {var_type}")
        
        return inputs
    
    def _extract_wdl_outputs(self, content: str) -> List[str]:
        """Extract outputs from WDL content."""
        outputs = []
        
        # Look for output section
        output_match = re.search(r'output\s*{(.*?)^}', content, re.MULTILINE | re.DOTALL)
        if output_match:
            output_content = output_match.group(1)
            # Find output declarations
            output_pattern = r'^\s*(File|String|Int|Float|Boolean|Array\[.*?\]|Map\[.*?\])\???\s+(\w+)'
            for match in re.finditer(output_pattern, output_content, re.MULTILINE):
                var_type = match.group(1)
                var_name = match.group(2)
                outputs.append(f"{var_name}: {var_type}")
        
        return outputs
    
    def _extract_wdl_tasks(self, content: str) -> List[str]:
        """Extract task names from WDL content."""
        tasks = []
        
        # Find all task declarations
        task_pattern = r'task\s+(\w+)\s*{'
        for match in re.finditer(task_pattern, content):
            tasks.append(match.group(1))
        
        return tasks
    
    def _extract_wdl_imports(self, content: str) -> List[str]:
        """Extract imports from WDL content."""
        imports = []
        
        # Find import statements
        import_pattern = r'import\s+"([^"]+)"(?:\s+as\s+(\w+))?'
        for match in re.finditer(import_pattern, content):
            import_path = match.group(1)
            alias = match.group(2)
            if alias:
                imports.append(f"{import_path} as {alias}")
            else:
                imports.append(import_path)
        
        return imports
    
    def _extract_wdl_version(self, content: str) -> str:
        """Extract WDL version from content."""
        version_match = re.search(r'version\s+([\d.]+|draft-\d+|development)', content)
        return version_match.group(1) if version_match else 'Unknown'
    
    def _build_wdl_dependencies(self, content: str, tasks: List[str]) -> Dict[str, List[str]]:
        """Build task dependency graph from WDL content."""
        dependencies = {}
        
        # Find call statements and their inputs
        call_pattern = r'call\s+(\w+)(?:\s+as\s+\w+)?\s*{'
        for match in re.finditer(call_pattern, content):
            called_task = match.group(1)
            if called_task in tasks:
                # Look for input assignments that reference other tasks
                # This is a simplified version - real implementation would be more complex
                dependencies[called_task] = []
        
        return dependencies
    
    def _error_analysis(self, workflow_path: str, error: str) -> Dict[str, Any]:
        """Return error analysis result."""
        return {
            'path': workflow_path,
            'type': 'Error',
            'error': error,
            'inputs': [],
            'outputs': [],
            'tasks': [],
            'dependencies': {},
            'metadata': {}
        }
    
    def get_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Get a text summary of the analysis.
        
        Args:
            analysis: Analysis dictionary from analyze()
            
        Returns:
            Formatted summary string
        """
        lines = [
            f"Workflow: {analysis.get('name', 'Unknown')}",
            f"Type: {analysis.get('type', 'Unknown')}",
            f"Path: {analysis.get('path', 'Unknown')}",
            "",
            f"Inputs: {len(analysis.get('inputs', []))}",
            f"Outputs: {len(analysis.get('outputs', []))}",
            f"Tasks: {len(analysis.get('tasks', []))}",
        ]
        
        if analysis.get('imports'):
            lines.append(f"Imports: {len(analysis['imports'])}")
        
        if analysis.get('metadata'):
            meta = analysis['metadata']
            if 'version' in meta:
                lines.append(f"Version: {meta['version']}")
            if 'lines' in meta:
                lines.append(f"Size: {meta['lines']} lines")
        
        return "\n".join(lines)