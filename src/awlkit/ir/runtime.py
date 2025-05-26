"""Runtime requirements for workflow tasks."""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class Runtime(BaseModel):
    """Runtime requirements for a task."""
    cpu: Optional[int] = None
    memory: Optional[str] = None  # e.g., "4G", "2048M"
    disk: Optional[str] = None    # e.g., "100G"
    docker: Optional[str] = None
    maxRetries: Optional[int] = None
    continueOnReturnCode: Optional[bool] = None
    gpu: Optional[bool] = None
    zones: Optional[list[str]] = None
    preemptible: Optional[int] = None
    
    # Additional custom runtime attributes
    custom_attributes: Dict[str, Any] = {}
    
    def to_cwl_requirements(self) -> list[dict]:
        """Convert to CWL requirements list."""
        requirements = []
        
        if self.docker:
            requirements.append({
                "class": "DockerRequirement",
                "dockerPull": self.docker
            })
        
        resource_req = {"class": "ResourceRequirement"}
        if self.cpu:
            resource_req["coresMin"] = self.cpu
        if self.memory:
            resource_req["ramMin"] = self._parse_memory_to_mb(self.memory)
        if self.disk:
            resource_req["outdirMin"] = self._parse_disk_to_mb(self.disk)
            
        if len(resource_req) > 1:  # Has more than just class
            requirements.append(resource_req)
            
        return requirements
    
    def to_wdl_runtime(self) -> dict:
        """Convert to WDL runtime section."""
        runtime = {}
        
        if self.cpu:
            runtime["cpu"] = self.cpu
        if self.memory:
            runtime["memory"] = self.memory
        if self.disk:
            runtime["disks"] = f"local-disk {self.disk} HDD"
        if self.docker:
            runtime["docker"] = self.docker
        if self.maxRetries is not None:
            runtime["maxRetries"] = self.maxRetries
        if self.preemptible is not None:
            runtime["preemptible"] = self.preemptible
            
        # Add custom attributes
        runtime.update(self.custom_attributes)
        
        return runtime
    
    @staticmethod
    def _parse_memory_to_mb(memory_str: str) -> int:
        """Parse memory string to MB."""
        memory_str = memory_str.strip()
        if memory_str.endswith("G"):
            return int(float(memory_str[:-1]) * 1024)
        elif memory_str.endswith("M"):
            return int(memory_str[:-1])
        else:
            return int(memory_str)
    
    @staticmethod
    def _parse_disk_to_mb(disk_str: str) -> int:
        """Parse disk string to MB."""
        disk_str = disk_str.strip()
        if disk_str.endswith("G"):
            return int(float(disk_str[:-1]) * 1024)
        elif disk_str.endswith("T"):
            return int(float(disk_str[:-1]) * 1024 * 1024)
        elif disk_str.endswith("M"):
            return int(disk_str[:-1])
        else:
            return int(disk_str)