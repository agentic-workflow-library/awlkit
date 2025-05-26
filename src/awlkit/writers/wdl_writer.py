"""WDL Writer implementation."""

from pathlib import Path
from typing import Union

from ..ir import Workflow, Task


class WDLWriter:
    """Writer for WDL (Workflow Description Language) files."""
    
    def __init__(self, version: str = "1.0"):
        """Initialize WDL writer."""
        self.version = version
    
    def write(self, element: Union[Workflow, Task]) -> str:
        """Write workflow element to WDL string."""
        lines = []
        
        # Add version header
        lines.append(f"version {self.version}")
        lines.append("")
        
        if isinstance(element, Task):
            lines.append(element.to_wdl_task())
        elif isinstance(element, Workflow):
            lines.extend(self._workflow_to_wdl_lines(element))
        else:
            raise ValueError(f"Unknown element type: {type(element)}")
        
        return "\n".join(lines)
    
    def write_file(self, element: Union[Workflow, Task], file_path: Path) -> None:
        """Write workflow element to WDL file."""
        content = self.write(element)
        
        with open(file_path, 'w') as f:
            f.write(content)
    
    def _workflow_to_wdl_lines(self, workflow: Workflow) -> list[str]:
        """Convert workflow to WDL lines."""
        lines = []
        
        # Add imports
        for imp in workflow.imports:
            lines.append(f'import "{imp}"')
        
        if workflow.imports:
            lines.append("")
        
        # Add tasks defined in this workflow
        for task in workflow.tasks.values():
            lines.append(task.to_wdl_task())
            lines.append("")
        
        # Add workflow definition
        lines.append(workflow.to_wdl_workflow())
        
        return lines