"""CWL Parser implementation."""

from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import ruamel.yaml as yaml

from ..ir import Workflow, Task, Input, Output, Runtime
from ..ir.types import TypeSpec, DataType


class CWLParser:
    """Parser for CWL (Common Workflow Language) files."""
    
    def __init__(self):
        """Initialize CWL parser."""
        self.yaml = yaml.YAML()
        self.yaml.preserve_quotes = True
    
    def parse_file(self, file_path: Path) -> Union[Workflow, Task]:
        """Parse a CWL file and return IR representation."""
        with open(file_path, 'r') as f:
            cwl_doc = self.yaml.load(f)
        
        return self.parse_dict(cwl_doc, str(file_path))
    
    def parse_dict(self, cwl_doc: dict, source_name: str = "dict") -> Union[Workflow, Task]:
        """Parse CWL from dictionary."""
        cwl_class = cwl_doc.get('class', '')
        
        if cwl_class == 'CommandLineTool':
            return self._parse_command_line_tool(cwl_doc)
        elif cwl_class == 'Workflow':
            return self._parse_workflow(cwl_doc)
        else:
            raise ValueError(f"Unknown CWL class: {cwl_class}")
    
    def _parse_command_line_tool(self, tool_doc: dict) -> Task:
        """Parse CWL CommandLineTool to Task."""
        task = Task(
            name=tool_doc.get('id', 'unnamed_tool'),
            command="",
            description=tool_doc.get('doc', '')
        )
        
        # Parse inputs
        inputs = tool_doc.get('inputs', {})
        for input_id, input_def in inputs.items():
            if isinstance(input_def, dict):
                inp = self._parse_input(input_id, input_def)
            else:
                # Simple type definition
                inp = Input(
                    name=input_id,
                    type_spec=self._parse_cwl_type(input_def)
                )
            task.inputs.append(inp)
        
        # Parse outputs
        outputs = tool_doc.get('outputs', {})
        for output_id, output_def in outputs.items():
            if isinstance(output_def, dict):
                out = self._parse_output(output_id, output_def)
            else:
                out = Output(
                    name=output_id,
                    type_spec=self._parse_cwl_type(output_def)
                )
            task.outputs.append(out)
        
        # Parse command
        base_command = tool_doc.get('baseCommand', [])
        if isinstance(base_command, str):
            base_command = [base_command]
        
        arguments = tool_doc.get('arguments', [])
        command_parts = base_command + arguments
        task.command = ' '.join(str(part) for part in command_parts)
        
        # Parse requirements
        requirements = tool_doc.get('requirements', [])
        task.runtime = self._parse_requirements(requirements)
        
        return task
    
    def _parse_workflow(self, wf_doc: dict) -> Workflow:
        """Parse CWL Workflow."""
        workflow = Workflow(
            name=wf_doc.get('id', 'unnamed_workflow'),
            description=wf_doc.get('doc', '')
        )
        
        # Parse inputs
        inputs = wf_doc.get('inputs', {})
        for input_id, input_def in inputs.items():
            if isinstance(input_def, dict):
                inp = self._parse_input(input_id, input_def)
            else:
                inp = Input(
                    name=input_id,
                    type_spec=self._parse_cwl_type(input_def)
                )
            workflow.inputs.append(inp)
        
        # Parse outputs
        outputs = wf_doc.get('outputs', {})
        for output_id, output_def in outputs.items():
            if isinstance(output_def, dict):
                out = self._parse_output(output_id, output_def)
            else:
                out = Output(
                    name=output_id,
                    type_spec=self._parse_cwl_type(output_def)
                )
            workflow.outputs.append(out)
        
        # Parse steps
        steps = wf_doc.get('steps', {})
        for step_id, step_def in steps.items():
            # Parse embedded tools if present
            if 'run' in step_def and isinstance(step_def['run'], dict):
                task = self._parse_command_line_tool(step_def['run'])
                task.name = step_id
                workflow.add_task(task)
                task_name = step_id
            else:
                task_name = step_def.get('run', step_id).lstrip('#')
            
            # Create workflow call
            call = WorkflowCall(
                call_id=step_id,
                task_name=task_name,
                inputs=self._parse_step_inputs(step_def.get('in', {}))
            )
            
            # Handle scatter
            if 'scatter' in step_def:
                call.scatter = step_def['scatter']
            
            workflow.add_call(call)
        
        return workflow
    
    def _parse_input(self, input_id: str, input_def: dict) -> Input:
        """Parse CWL input definition."""
        return Input(
            name=input_id,
            type_spec=self._parse_cwl_type(input_def.get('type')),
            description=input_def.get('doc', ''),
            default=input_def.get('default'),
            optional='null' in str(input_def.get('type', ''))
        )
    
    def _parse_output(self, output_id: str, output_def: dict) -> Output:
        """Parse CWL output definition."""
        output_binding = output_def.get('outputBinding', {})
        expression = output_binding.get('glob') if output_binding else None
        
        return Output(
            name=output_id,
            type_spec=self._parse_cwl_type(output_def.get('type')),
            description=output_def.get('doc', ''),
            expression=expression
        )
    
    def _parse_cwl_type(self, cwl_type: Any) -> TypeSpec:
        """Parse CWL type to TypeSpec."""
        if isinstance(cwl_type, str):
            return self._parse_simple_type(cwl_type)
        elif isinstance(cwl_type, list):
            # Union type, check for null (optional)
            non_null_types = [t for t in cwl_type if t != 'null']
            optional = 'null' in cwl_type
            
            if len(non_null_types) == 1:
                type_spec = self._parse_simple_type(non_null_types[0])
                type_spec.optional = optional
                return type_spec
            else:
                # Complex union, default to string
                return TypeSpec(base_type=DataType.STRING, optional=optional)
        elif isinstance(cwl_type, dict):
            if cwl_type.get('type') == 'array':
                item_type = self._parse_cwl_type(cwl_type.get('items', 'string'))
                return TypeSpec(
                    base_type=DataType.ARRAY,
                    item_type=item_type
                )
            else:
                # Complex type, default to string
                return TypeSpec(base_type=DataType.STRING)
        else:
            return TypeSpec(base_type=DataType.STRING)
    
    def _parse_simple_type(self, type_str: str) -> TypeSpec:
        """Parse simple CWL type string."""
        type_mapping = {
            'string': DataType.STRING,
            'int': DataType.INT,
            'long': DataType.INT,
            'float': DataType.FLOAT,
            'double': DataType.FLOAT,
            'boolean': DataType.BOOLEAN,
            'File': DataType.FILE,
            'Directory': DataType.DIRECTORY,
        }
        
        base_type = type_mapping.get(type_str, DataType.STRING)
        return TypeSpec(base_type=base_type)
    
    def _parse_requirements(self, requirements: List[dict]) -> Runtime:
        """Parse CWL requirements to Runtime."""
        runtime = Runtime()
        
        for req in requirements:
            req_class = req.get('class', '')
            
            if req_class == 'DockerRequirement':
                runtime.docker = req.get('dockerPull', '')
            elif req_class == 'ResourceRequirement':
                if 'coresMin' in req:
                    runtime.cpu = req['coresMin']
                if 'ramMin' in req:
                    runtime.memory = f"{req['ramMin']}M"
                if 'outdirMin' in req:
                    runtime.disk = f"{req['outdirMin']}M"
        
        return runtime
    
    def _parse_step_inputs(self, step_inputs: dict) -> Dict[str, Any]:
        """Parse step input mappings."""
        inputs = {}
        
        for inp_name, inp_value in step_inputs.items():
            if isinstance(inp_value, str):
                # Convert CWL reference format to WDL format
                inputs[inp_name] = inp_value.replace('/', '.')
            else:
                inputs[inp_name] = str(inp_value)
        
        return inputs