"""Workflow definition for IR."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import networkx as nx

from .task import Task
from .io import Input, Output
from .types import WorkflowType


class WorkflowCall(BaseModel):
    """A call to a task or subworkflow within a workflow."""
    call_id: str
    task_name: str
    inputs: Dict[str, Any] = {}  # Mapping of task input to workflow value
    scatter: Optional[str] = None  # Variable to scatter over
    conditional: Optional[str] = None  # Conditional expression


class Workflow(BaseModel):
    """Workflow definition."""
    name: str
    type: WorkflowType = WorkflowType.WORKFLOW
    inputs: List[Input] = []
    outputs: List[Output] = []
    tasks: Dict[str, Task] = {}  # Task name -> Task definition
    calls: List[WorkflowCall] = []
    imports: List[str] = []  # Import statements
    description: Optional[str] = None
    
    def add_task(self, task: Task) -> None:
        """Add a task to the workflow."""
        self.tasks[task.name] = task
    
    def add_call(self, call: WorkflowCall) -> None:
        """Add a call to the workflow."""
        self.calls.append(call)
    
    def get_dependency_graph(self) -> nx.DiGraph:
        """Build dependency graph of workflow calls."""
        graph = nx.DiGraph()
        
        # Add nodes for all calls
        for call in self.calls:
            graph.add_node(call.call_id)
        
        # Add edges based on data dependencies
        for call in self.calls:
            for input_name, input_value in call.inputs.items():
                # Check if input references another call's output
                if isinstance(input_value, str) and "." in input_value:
                    parts = input_value.split(".")
                    if len(parts) == 2:
                        dep_call_id = parts[0]
                        if dep_call_id in [c.call_id for c in self.calls]:
                            graph.add_edge(dep_call_id, call.call_id)
        
        return graph
    
    def to_cwl_workflow(self) -> dict:
        """Convert to CWL Workflow."""
        workflow = {
            "class": "Workflow",
            "id": self.name,
            "inputs": {},
            "outputs": {},
            "steps": {}
        }
        
        if self.description:
            workflow["doc"] = self.description
        
        # Add inputs
        for inp in self.inputs:
            workflow["inputs"][inp.name] = inp.to_cwl()
        
        # Add outputs
        for out in self.outputs:
            workflow["outputs"][out.name] = out.to_cwl()
        
        # Add steps (calls)
        for call in self.calls:
            step = {
                "run": f"#{call.task_name}",
                "in": {},
                "out": []
            }
            
            # Map inputs
            for inp_name, inp_value in call.inputs.items():
                if isinstance(inp_value, str) and "." in inp_value:
                    # Reference to another step's output
                    step["in"][inp_name] = inp_value.replace(".", "/")
                else:
                    # Direct input reference
                    step["in"][inp_name] = inp_value
            
            # Add outputs from task definition
            if call.task_name in self.tasks:
                task = self.tasks[call.task_name]
                step["out"] = [out.name for out in task.outputs]
            
            # Handle scatter
            if call.scatter:
                step["scatter"] = call.scatter
                step["scatterMethod"] = "dotproduct"
            
            workflow["steps"][call.call_id] = step
        
        # Add requirements for subworkflows
        if self.tasks:
            workflow["requirements"] = [{
                "class": "SubworkflowFeatureRequirement"
            }]
        
        return workflow
    
    def to_wdl_workflow(self) -> str:
        """Convert to WDL workflow definition."""
        lines = []
        
        # Add imports
        for imp in self.imports:
            lines.append(f'import "{imp}"')
        
        if self.imports:
            lines.append("")
        
        # Start workflow
        lines.append(f"workflow {self.name} {{")
        
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
        
        # Calls
        for call in self.calls:
            lines.append("")
            
            # Handle scatter
            if call.scatter:
                lines.append(f"  scatter ({call.scatter}) {{")
                indent = "    "
            else:
                indent = "  "
            
            # Handle conditional
            if call.conditional:
                lines.append(f"{indent}if ({call.conditional}) {{")
                indent += "  "
            
            # Call statement
            if call.inputs:
                lines.append(f"{indent}call {call.task_name} as {call.call_id} {{")
                lines.append(f"{indent}  input:")
                for inp_name, inp_value in call.inputs.items():
                    lines.append(f"{indent}    {inp_name} = {inp_value}")
                lines.append(f"{indent}}}")
            else:
                lines.append(f"{indent}call {call.task_name} as {call.call_id}")
            
            # Close conditional
            if call.conditional:
                lines.append(f"{indent[:-2]}}}")
            
            # Close scatter
            if call.scatter:
                lines.append("  }")
        
        # Output section
        if self.outputs:
            lines.append("")
            lines.append("  output {")
            for out in self.outputs:
                lines.append(f"    {out.to_wdl()}")
            lines.append("  }")
        
        lines.append("}")
        return "\n".join(lines)