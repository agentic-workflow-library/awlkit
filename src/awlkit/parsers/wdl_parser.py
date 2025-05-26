"""WDL Parser implementation."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from lark import Lark, Tree, Token

from ..ir import Workflow, Task, Input, Output, Runtime, WorkflowCall
from ..ir.types import TypeSpec, DataType


class WDLParser:
    """Parser for WDL (Workflow Description Language) files."""
    
    def __init__(self):
        """Initialize WDL parser with grammar."""
        # Simplified WDL grammar for initial implementation
        self.grammar = r"""
        ?start: document
        
        document: version? import_doc* (workflow | task)*
        
        version: "version" VERSION_STRING
        
        import_doc: "import" string ("as" IDENTIFIER)?
        
        workflow: "workflow" IDENTIFIER "{" workflow_element* "}"
        
        task: "task" IDENTIFIER "{" task_element* "}"
        
        workflow_element: input_section
                        | output_section  
                        | call_statement
                        | scatter_statement
                        | conditional_statement
                        | meta_section
        
        task_element: input_section
                    | command_section
                    | runtime_section
                    | output_section
                    | meta_section
        
        input_section: "input" "{" declaration* "}"
        
        output_section: "output" "{" declaration* "}"
        
        declaration: type_spec IDENTIFIER ("=" expression)?
        
        type_spec: primitive_type
                 | array_type
                 | map_type
                 | optional_type
        
        primitive_type: "String" | "Int" | "Float" | "Boolean" | "File"
        
        array_type: "Array" "[" type_spec "]"
        
        map_type: "Map" "[" type_spec "," type_spec "]"
        
        optional_type: type_spec "?"
        
        command_section: "command" "<<<" COMMAND_STRING ">>>"
                       | "command" "{" COMMAND_STRING "}"
        
        runtime_section: "runtime" "{" runtime_attr* "}"
        
        runtime_attr: IDENTIFIER ":" expression
        
        call_statement: "call" IDENTIFIER ("as" IDENTIFIER)? call_body?
        
        call_body: "{" "input" ":" call_input ("," call_input)* "}"
        
        call_input: IDENTIFIER "=" expression
        
        scatter_statement: "scatter" "(" IDENTIFIER "in" expression ")" "{" workflow_element* "}"
        
        conditional_statement: "if" "(" expression ")" "{" workflow_element* "}"
        
        meta_section: "meta" "{" meta_attr* "}"
        
        meta_attr: IDENTIFIER ":" expression
        
        expression: string
                  | number
                  | boolean
                  | IDENTIFIER
                  | member_access
        
        member_access: IDENTIFIER "." IDENTIFIER
        
        string: ESCAPED_STRING
        
        number: SIGNED_NUMBER
        
        boolean: "true" | "false"
        
        IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
        VERSION_STRING: /[0-9]+\.[0-9]+/
        COMMAND_STRING: /[^>]+/
        
        %import common.ESCAPED_STRING
        %import common.SIGNED_NUMBER
        %import common.WS
        %ignore WS
        """
        
        self.parser = Lark(self.grammar, parser='lalr')
    
    def parse_file(self, file_path: Path) -> Workflow:
        """Parse a WDL file and return IR representation."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        return self.parse_string(content, str(file_path))
    
    def parse_string(self, content: str, source_name: str = "string") -> Workflow:
        """Parse WDL content from string."""
        # For now, use regex-based parsing as a simpler approach
        # Full implementation would use the Lark grammar
        
        workflow = None
        tasks = {}
        
        # Extract version
        version_match = re.search(r'version\s+(\S+)', content)
        version = version_match.group(1) if version_match else None
        
        # Extract imports
        imports = re.findall(r'import\s+"([^"]+)"', content)
        
        # Extract tasks
        task_pattern = r'task\s+(\w+)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        for match in re.finditer(task_pattern, content, re.DOTALL):
            task_name = match.group(1)
            task_body = match.group(2)
            task = self._parse_task(task_name, task_body)
            tasks[task_name] = task
        
        # Extract workflow
        workflow_pattern = r'workflow\s+(\w+)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}'
        workflow_match = re.search(workflow_pattern, content, re.DOTALL)
        
        if workflow_match:
            workflow_name = workflow_match.group(1)
            workflow_body = workflow_match.group(2)
            workflow = self._parse_workflow(workflow_name, workflow_body, tasks)
            workflow.imports = imports
        else:
            # If no workflow, create one containing just tasks
            workflow = Workflow(name=Path(source_name).stem)
            workflow.tasks = tasks
        
        return workflow
    
    def _parse_task(self, name: str, body: str) -> Task:
        """Parse a WDL task definition."""
        task = Task(name=name, command="")
        
        # Parse input section
        input_match = re.search(r'input\s*\{([^}]+)\}', body, re.DOTALL)
        if input_match:
            inputs_text = input_match.group(1)
            task.inputs = self._parse_declarations(inputs_text)
        
        # Parse command section
        command_match = re.search(r'command\s*<<<(.+?)>>>', body, re.DOTALL)
        if not command_match:
            command_match = re.search(r'command\s*\{(.+?)\}', body, re.DOTALL)
        if command_match:
            task.command = command_match.group(1).strip()
        
        # Parse runtime section
        runtime_match = re.search(r'runtime\s*\{([^}]+)\}', body, re.DOTALL)
        if runtime_match:
            runtime_text = runtime_match.group(1)
            task.runtime = self._parse_runtime(runtime_text)
        
        # Parse output section
        output_match = re.search(r'output\s*\{([^}]+)\}', body, re.DOTALL)
        if output_match:
            outputs_text = output_match.group(1)
            task.outputs = self._parse_output_declarations(outputs_text)
        
        return task
    
    def _parse_workflow(self, name: str, body: str, tasks: Dict[str, Task]) -> Workflow:
        """Parse a WDL workflow definition."""
        workflow = Workflow(name=name)
        workflow.tasks = tasks
        
        # Parse input section
        input_match = re.search(r'input\s*\{([^}]+)\}', body, re.DOTALL)
        if input_match:
            inputs_text = input_match.group(1)
            workflow.inputs = self._parse_declarations(inputs_text)
        
        # Parse calls
        call_pattern = r'call\s+(\w+)(?:\s+as\s+(\w+))?\s*(?:\{([^}]+)\})?'
        for match in re.finditer(call_pattern, body):
            task_name = match.group(1)
            alias = match.group(2) or task_name
            call_body = match.group(3) or ""
            
            call = WorkflowCall(
                call_id=alias,
                task_name=task_name,
                inputs=self._parse_call_inputs(call_body)
            )
            workflow.add_call(call)
        
        # Parse output section
        output_match = re.search(r'output\s*\{([^}]+)\}', body, re.DOTALL)
        if output_match:
            outputs_text = output_match.group(1)
            workflow.outputs = self._parse_output_declarations(outputs_text)
        
        return workflow
    
    def _parse_declarations(self, text: str) -> List[Input]:
        """Parse input declarations."""
        inputs = []
        
        # Simple pattern for type + name + optional default
        pattern = r'(\w+(?:\[[^\]]+\])?(?:\?)?)\s+(\w+)(?:\s*=\s*(.+?))?(?:\n|$)'
        
        for match in re.finditer(pattern, text):
            type_str = match.group(1)
            name = match.group(2)
            default = match.group(3)
            
            type_spec = self._parse_type(type_str)
            inp = Input(
                name=name,
                type_spec=type_spec,
                default=default.strip() if default else None,
                optional=type_spec.optional
            )
            inputs.append(inp)
        
        return inputs
    
    def _parse_output_declarations(self, text: str) -> List[Output]:
        """Parse output declarations."""
        outputs = []
        
        pattern = r'(\w+(?:\[[^\]]+\])?(?:\?)?)\s+(\w+)(?:\s*=\s*(.+?))?(?:\n|$)'
        
        for match in re.finditer(pattern, text):
            type_str = match.group(1)
            name = match.group(2)
            expression = match.group(3)
            
            type_spec = self._parse_type(type_str)
            out = Output(
                name=name,
                type_spec=type_spec,
                expression=expression.strip() if expression else None
            )
            outputs.append(out)
        
        return outputs
    
    def _parse_type(self, type_str: str) -> TypeSpec:
        """Parse WDL type string to TypeSpec."""
        optional = type_str.endswith("?")
        if optional:
            type_str = type_str[:-1]
        
        if type_str.startswith("Array["):
            # Extract item type
            item_type_str = type_str[6:-1]  # Remove "Array[" and "]"
            item_type = self._parse_type(item_type_str)
            return TypeSpec(
                base_type=DataType.ARRAY,
                item_type=item_type,
                optional=optional
            )
        
        # Map simple types
        type_mapping = {
            "String": DataType.STRING,
            "Int": DataType.INT,
            "Float": DataType.FLOAT,
            "Boolean": DataType.BOOLEAN,
            "File": DataType.FILE,
        }
        
        base_type = type_mapping.get(type_str, DataType.STRING)
        return TypeSpec(base_type=base_type, optional=optional)
    
    def _parse_runtime(self, text: str) -> Runtime:
        """Parse runtime section."""
        runtime = Runtime()
        
        # Parse key: value pairs
        pattern = r'(\w+)\s*:\s*"?([^"\n]+)"?'
        
        for match in re.finditer(pattern, text):
            key = match.group(1)
            value = match.group(2).strip()
            
            if key == "cpu":
                runtime.cpu = int(value)
            elif key == "memory":
                runtime.memory = value
            elif key == "docker":
                runtime.docker = value
            elif key == "disks":
                # Extract disk size from disks specification
                disk_match = re.search(r'(\d+\s*\w+)', value)
                if disk_match:
                    runtime.disk = disk_match.group(1).replace(" ", "")
            elif key == "preemptible":
                runtime.preemptible = int(value)
            elif key == "maxRetries":
                runtime.maxRetries = int(value)
            else:
                runtime.custom_attributes[key] = value
        
        return runtime
    
    def _parse_call_inputs(self, text: str) -> Dict[str, Any]:
        """Parse call input mappings."""
        inputs = {}
        
        if not text.strip():
            return inputs
        
        # Look for input: section
        input_match = re.search(r'input\s*:(.+)', text, re.DOTALL)
        if input_match:
            text = input_match.group(1)
        
        # Parse key = value pairs
        pattern = r'(\w+)\s*=\s*([^,\n]+)'
        
        for match in re.finditer(pattern, text):
            key = match.group(1)
            value = match.group(2).strip()
            inputs[key] = value
        
        return inputs