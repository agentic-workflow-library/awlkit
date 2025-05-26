"""Type definitions for intermediate representation."""

from enum import Enum
from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel


class WorkflowType(str, Enum):
    """Type of workflow element."""
    WORKFLOW = "workflow"
    TASK = "task"
    SUBWORKFLOW = "subworkflow"


class DataType(str, Enum):
    """Supported data types in workflows."""
    STRING = "String"
    INT = "Int"
    FLOAT = "Float"
    BOOLEAN = "Boolean"
    FILE = "File"
    DIRECTORY = "Directory"
    ARRAY = "Array"
    MAP = "Map"
    OBJECT = "Object"
    OPTIONAL = "Optional"


class TypeSpec(BaseModel):
    """Type specification for workflow inputs/outputs."""
    base_type: DataType
    item_type: Optional["TypeSpec"] = None  # For Array types
    key_type: Optional["TypeSpec"] = None   # For Map types
    value_type: Optional["TypeSpec"] = None  # For Map types
    optional: bool = False
    
    def to_wdl_string(self) -> str:
        """Convert to WDL type string."""
        if self.base_type == DataType.ARRAY:
            return f"Array[{self.item_type.to_wdl_string()}]"
        elif self.base_type == DataType.MAP:
            return f"Map[{self.key_type.to_wdl_string()},{self.value_type.to_wdl_string()}]"
        elif self.optional:
            return f"{self.base_type.value}?"
        return self.base_type.value
    
    def to_cwl_type(self) -> Union[str, Dict[str, Any]]:
        """Convert to CWL type specification."""
        cwl_mapping = {
            DataType.STRING: "string",
            DataType.INT: "int",
            DataType.FLOAT: "float", 
            DataType.BOOLEAN: "boolean",
            DataType.FILE: "File",
            DataType.DIRECTORY: "Directory",
        }
        
        if self.base_type == DataType.ARRAY:
            return {
                "type": "array",
                "items": self.item_type.to_cwl_type()
            }
        elif self.base_type in cwl_mapping:
            base = cwl_mapping[self.base_type]
            if self.optional:
                return ["null", base]
            return base
        
        return "Any"  # Fallback


TypeSpec.model_rebuild()  # Enable forward references