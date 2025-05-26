"""Validation utilities for workflows."""

from typing import List, Tuple
import logging

from ..ir import Workflow, Task


class ValidationError:
    """Represents a validation error."""
    
    def __init__(self, level: str, message: str, location: str = ""):
        self.level = level  # ERROR, WARNING, INFO
        self.message = message
        self.location = location
    
    def __str__(self):
        if self.location:
            return f"[{self.level}] {self.location}: {self.message}"
        return f"[{self.level}] {self.message}"


class WorkflowValidator:
    """Validate workflow definitions."""
    
    def __init__(self, logger: logging.Logger = None):
        """Initialize validator."""
        self.logger = logger or logging.getLogger(__name__)
        self.errors: List[ValidationError] = []
    
    def validate_workflow(self, workflow: Workflow) -> Tuple[bool, List[ValidationError]]:
        """Validate a workflow definition."""
        self.errors = []
        
        # Basic validation
        if not workflow.name:
            self.errors.append(ValidationError("ERROR", "Workflow missing name"))
        
        # Validate calls
        for call in workflow.calls:
            self._validate_call(call, workflow)
        
        # Validate tasks
        for task in workflow.tasks.values():
            self._validate_task(task)
        
        # Check for cycles
        from .graph import WorkflowGraphAnalyzer
        analyzer = WorkflowGraphAnalyzer(workflow)
        cycles = analyzer.find_cycles()
        if cycles:
            for cycle in cycles:
                self.errors.append(ValidationError(
                    "ERROR", 
                    f"Circular dependency detected: {' -> '.join(cycle)}"
                ))
        
        # Check unused inputs
        used_inputs = set()
        for call in workflow.calls:
            for inp_value in call.inputs.values():
                if isinstance(inp_value, str) and not "." in inp_value:
                    used_inputs.add(inp_value)
        
        for inp in workflow.inputs:
            if inp.name not in used_inputs:
                self.errors.append(ValidationError(
                    "WARNING",
                    f"Input '{inp.name}' is not used by any call",
                    "workflow.inputs"
                ))
        
        # Check outputs reference valid calls
        for out in workflow.outputs:
            if out.expression and "." in out.expression:
                call_ref = out.expression.split(".")[0]
                if call_ref not in [c.call_id for c in workflow.calls]:
                    self.errors.append(ValidationError(
                        "ERROR",
                        f"Output '{out.name}' references unknown call '{call_ref}'",
                        "workflow.outputs"
                    ))
        
        has_errors = any(e.level == "ERROR" for e in self.errors)
        return not has_errors, self.errors
    
    def validate_task(self, task: Task) -> Tuple[bool, List[ValidationError]]:
        """Validate a task definition."""
        self.errors = []
        self._validate_task(task)
        
        has_errors = any(e.level == "ERROR" for e in self.errors)
        return not has_errors, self.errors
    
    def _validate_call(self, call, workflow):
        """Validate a workflow call."""
        # Check task exists
        if call.task_name not in workflow.tasks:
            # Could be external task, just warning
            self.errors.append(ValidationError(
                "WARNING",
                f"Call '{call.call_id}' references unknown task '{call.task_name}'",
                f"call.{call.call_id}"
            ))
            return
        
        task = workflow.tasks[call.task_name]
        
        # Check required inputs are provided
        for inp in task.inputs:
            if not inp.optional and inp.name not in call.inputs:
                self.errors.append(ValidationError(
                    "ERROR",
                    f"Call '{call.call_id}' missing required input '{inp.name}'",
                    f"call.{call.call_id}"
                ))
        
        # Check input types match
        for inp_name, inp_value in call.inputs.items():
            if inp_name not in [i.name for i in task.inputs]:
                self.errors.append(ValidationError(
                    "WARNING",
                    f"Call '{call.call_id}' provides unknown input '{inp_name}'",
                    f"call.{call.call_id}"
                ))
    
    def _validate_task(self, task):
        """Validate a task definition."""
        if not task.name:
            self.errors.append(ValidationError("ERROR", "Task missing name"))
        
        if not task.command:
            self.errors.append(ValidationError(
                "ERROR",
                f"Task '{task.name}' missing command",
                f"task.{task.name}"
            ))
        
        # Check command references valid inputs
        import re
        var_pattern = r'[~$]\{(\w+)\}'
        command_vars = set(re.findall(var_pattern, task.command))
        input_names = {inp.name for inp in task.inputs}
        
        for var in command_vars:
            if var not in input_names:
                self.errors.append(ValidationError(
                    "ERROR",
                    f"Task '{task.name}' command references unknown input '{var}'",
                    f"task.{task.name}.command"
                ))
        
        # Validate runtime
        if task.runtime:
            if task.runtime.memory:
                if not re.match(r'^\d+[MG]?$', task.runtime.memory):
                    self.errors.append(ValidationError(
                        "WARNING",
                        f"Task '{task.name}' has invalid memory format: {task.runtime.memory}",
                        f"task.{task.name}.runtime"
                    ))