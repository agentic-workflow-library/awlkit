"""CWL Writer implementation."""

from pathlib import Path
from typing import Union, Dict, Any
import ruamel.yaml as yaml

from ..ir import Workflow, Task


class CWLWriter:
    """Writer for CWL (Common Workflow Language) files."""
    
    def __init__(self):
        """Initialize CWL writer."""
        self.yaml = yaml.YAML()
        self.yaml.default_flow_style = False
        self.yaml.width = 120
        self.yaml.indent(mapping=2, sequence=4, offset=2)
    
    def write(self, element: Union[Workflow, Task]) -> str:
        """Write workflow element to CWL string."""
        cwl_dict = self._element_to_cwl(element)
        
        # Convert to YAML string
        import io
        stream = io.StringIO()
        self.yaml.dump(cwl_dict, stream)
        return stream.getvalue()
    
    def write_file(self, element: Union[Workflow, Task], file_path: Path) -> None:
        """Write workflow element to CWL file."""
        cwl_dict = self._element_to_cwl(element)
        
        with open(file_path, 'w') as f:
            self.yaml.dump(cwl_dict, f)
    
    def _element_to_cwl(self, element: Union[Workflow, Task]) -> dict:
        """Convert workflow element to CWL dictionary."""
        # Add CWL version
        cwl_dict = {
            'cwlVersion': 'v1.2'
        }
        
        if isinstance(element, Task):
            cwl_dict.update(element.to_cwl_tool())
        elif isinstance(element, Workflow):
            cwl_dict.update(self._workflow_to_cwl(element))
        else:
            raise ValueError(f"Unknown element type: {type(element)}")
        
        return cwl_dict
    
    def _workflow_to_cwl(self, workflow: Workflow) -> dict:
        """Convert workflow to CWL dictionary with embedded tools."""
        wf_dict = workflow.to_cwl_workflow()
        
        # If workflow contains task definitions, embed them
        if workflow.tasks:
            # Create $graph with all components
            graph = []
            
            # Add main workflow
            main_wf = wf_dict.copy()
            main_wf['id'] = 'main'
            graph.append(main_wf)
            
            # Add all tasks as tools
            for task in workflow.tasks.values():
                tool_dict = task.to_cwl_tool()
                tool_dict['id'] = task.name
                graph.append(tool_dict)
            
            # Update step references in main workflow
            for step_id, step in main_wf.get('steps', {}).items():
                if 'run' in step and step['run'].startswith('#'):
                    # Keep the reference as is
                    pass
            
            # Return document with $graph
            return {
                '$graph': graph
            }
        else:
            return wf_dict
    
    def _format_cwl_type(self, type_spec) -> Any:
        """Format type specification for CWL."""
        cwl_type = type_spec.to_cwl_type()
        
        # Handle optional types
        if isinstance(cwl_type, list) and 'null' in cwl_type:
            # Put null first for readability
            cwl_type = ['null'] + [t for t in cwl_type if t != 'null']
        
        return cwl_type