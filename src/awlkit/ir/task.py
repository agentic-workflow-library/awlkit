"""Task definition for workflow IR."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from .io import Input, Output
from .runtime import Runtime


class Task(BaseModel):
    """Task definition in workflow."""
    name: str
    inputs: List[Input] = []
    outputs: List[Output] = []
    command: str
    runtime: Optional[Runtime] = None
    description: Optional[str] = None
    
    def to_cwl_tool(self) -> dict:
        """Convert to CWL CommandLineTool."""
        tool = {
            "class": "CommandLineTool",
            "id": self.name,
            "baseCommand": [],
            "inputs": {},
            "outputs": {}
        }
        
        if self.description:
            tool["doc"] = self.description
        
        # Add inputs
        for inp in self.inputs:
            tool["inputs"][inp.name] = inp.to_cwl()
        
        # Add outputs  
        for out in self.outputs:
            tool["outputs"][out.name] = out.to_cwl()
        
        # Add requirements
        if self.runtime:
            tool["requirements"] = self.runtime.to_cwl_requirements()
        
        # Parse command
        tool["arguments"] = self._parse_command_to_cwl()
        
        return tool
    
    def to_wdl_task(self) -> str:
        """Convert to WDL task definition."""
        lines = [f"task {self.name} {{"]
        
        if self.description:
            lines.append(f'  meta {{')
            lines.append(f'    description: "{self.description}"')
            lines.append(f'  }}')
        
        # Input section
        if self.inputs:
            lines.append("  input {")
            for inp in self.inputs:
                lines.append(f"    {inp.to_wdl()}")
            lines.append("  }")
        
        # Command section
        lines.append("  command <<<")
        for cmd_line in self.command.strip().split('\n'):
            lines.append(f"    {cmd_line}")
        lines.append("  >>>")
        
        # Runtime section
        if self.runtime:
            lines.append("  runtime {")
            for key, value in self.runtime.to_wdl_runtime().items():
                if isinstance(value, str):
                    lines.append(f'    {key}: "{value}"')
                else:
                    lines.append(f'    {key}: {value}')
            lines.append("  }")
        
        # Output section
        if self.outputs:
            lines.append("  output {")
            for out in self.outputs:
                lines.append(f"    {out.to_wdl()}")
            lines.append("  }")
        
        lines.append("}")
        return "\n".join(lines)
    
    def _parse_command_to_cwl(self) -> List[str]:
        """Parse command template to CWL arguments."""
        # This is a simplified parser - real implementation would be more complex
        import re
        
        # Split command into tokens
        tokens = self.command.strip().split()
        cwl_args = []
        
        for token in tokens:
            # Check if token contains input reference
            if "~{" in token or "${" in token:
                # Extract variable name
                var_match = re.search(r'[~$]\{(\w+)\}', token)
                if var_match:
                    var_name = var_match.group(1)
                    # Replace with CWL input reference
                    token = token.replace(var_match.group(0), f"$(inputs.{var_name})")
            
            cwl_args.append(token)
        
        return cwl_args