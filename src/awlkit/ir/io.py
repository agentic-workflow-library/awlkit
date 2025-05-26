"""Input/Output definitions for workflow IR."""

from typing import Any, Optional
from pydantic import BaseModel

from .types import TypeSpec


class Input(BaseModel):
    """Input parameter definition."""
    name: str
    type_spec: TypeSpec
    description: Optional[str] = None
    default: Optional[Any] = None
    optional: bool = False
    
    def to_cwl(self) -> dict:
        """Convert to CWL input parameter."""
        cwl_input = {
            "id": self.name,
            "type": self.type_spec.to_cwl_type()
        }
        
        if self.description:
            cwl_input["doc"] = self.description
            
        if self.default is not None:
            cwl_input["default"] = self.default
            
        return cwl_input
    
    def to_wdl(self) -> str:
        """Convert to WDL input declaration."""
        type_str = self.type_spec.to_wdl_string()
        if self.default is not None:
            return f"{type_str} {self.name} = {self.default}"
        return f"{type_str} {self.name}"


class Output(BaseModel):
    """Output parameter definition."""
    name: str
    type_spec: TypeSpec
    description: Optional[str] = None
    expression: Optional[str] = None  # How to compute the output
    
    def to_cwl(self) -> dict:
        """Convert to CWL output parameter."""
        cwl_output = {
            "id": self.name,
            "type": self.type_spec.to_cwl_type()
        }
        
        if self.description:
            cwl_output["doc"] = self.description
            
        if self.expression:
            cwl_output["outputBinding"] = {
                "glob": self.expression
            }
            
        return cwl_output
    
    def to_wdl(self) -> str:
        """Convert to WDL output declaration."""
        type_str = self.type_spec.to_wdl_string()
        if self.expression:
            return f"{type_str} {self.name} = {self.expression}"
        return f"{type_str} {self.name}"