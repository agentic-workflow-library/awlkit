"""WDL to CWL converter."""

from pathlib import Path
from typing import Optional, Union
import logging

from ..parsers import WDLParser
from ..writers import CWLWriter
from ..ir import Workflow, Task


class WDLToCWLConverter:
    """Converter from WDL to CWL format."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize converter."""
        self.parser = WDLParser()
        self.writer = CWLWriter()
        self.logger = logger or logging.getLogger(__name__)
    
    def convert_file(self, 
                    wdl_path: Path, 
                    cwl_path: Optional[Path] = None) -> Union[Workflow, Task]:
        """Convert WDL file to CWL file.
        
        Args:
            wdl_path: Path to input WDL file
            cwl_path: Path to output CWL file (optional)
            
        Returns:
            The parsed workflow/task IR object
        """
        self.logger.info(f"Parsing WDL file: {wdl_path}")
        
        # Parse WDL
        element = self.parser.parse_file(wdl_path)
        
        # Write CWL if output path provided
        if cwl_path:
            self.logger.info(f"Writing CWL file: {cwl_path}")
            self.writer.write_file(element, cwl_path)
        
        return element
    
    def convert_string(self, wdl_content: str) -> str:
        """Convert WDL string to CWL string.
        
        Args:
            wdl_content: WDL content as string
            
        Returns:
            CWL content as string
        """
        # Parse WDL
        element = self.parser.parse_string(wdl_content)
        
        # Write CWL
        return self.writer.write(element)
    
    def convert_directory(self,
                         wdl_dir: Path,
                         cwl_dir: Path,
                         recursive: bool = True) -> None:
        """Convert all WDL files in a directory to CWL.
        
        Args:
            wdl_dir: Input directory containing WDL files
            cwl_dir: Output directory for CWL files
            recursive: Whether to process subdirectories
        """
        # Create output directory
        cwl_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all WDL files
        pattern = "**/*.wdl" if recursive else "*.wdl"
        wdl_files = list(wdl_dir.glob(pattern))
        
        self.logger.info(f"Found {len(wdl_files)} WDL files to convert")
        
        # Convert each file
        for wdl_file in wdl_files:
            # Compute relative path
            rel_path = wdl_file.relative_to(wdl_dir)
            
            # Create output path with .cwl extension
            cwl_file = cwl_dir / rel_path.with_suffix('.cwl')
            
            # Create parent directory if needed
            cwl_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                self.convert_file(wdl_file, cwl_file)
                self.logger.info(f"Converted: {rel_path}")
            except Exception as e:
                self.logger.error(f"Failed to convert {rel_path}: {e}")
    
    def validate_conversion(self, element: Union[Workflow, Task]) -> bool:
        """Validate that the conversion was successful.
        
        Args:
            element: The converted workflow/task
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation
        if isinstance(element, Workflow):
            # Check workflow has name
            if not element.name:
                self.logger.warning("Workflow missing name")
                return False
            
            # Check all referenced tasks exist
            for call in element.calls:
                if call.task_name not in element.tasks:
                    self.logger.warning(f"Call references unknown task: {call.task_name}")
                    return False
        
        elif isinstance(element, Task):
            # Check task has name and command
            if not element.name:
                self.logger.warning("Task missing name")
                return False
            if not element.command:
                self.logger.warning("Task missing command")
                return False
        
        return True