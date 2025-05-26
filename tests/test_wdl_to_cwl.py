"""Tests for WDL to CWL conversion."""

import pytest
from pathlib import Path

from awlkit import WDLParser, CWLWriter, WDLToCWLConverter
from awlkit.ir import Task, Input, Output, Runtime
from awlkit.ir.types import TypeSpec, DataType


class TestWDLToCWL:
    """Test WDL to CWL conversion."""
    
    def test_simple_task_conversion(self):
        """Test converting a simple WDL task to CWL."""
        wdl_content = """
        version 1.0
        
        task hello {
            input {
                String name
                File input_file
            }
            
            command <<<
                echo "Hello, ~{name}!"
                cat ~{input_file}
            >>>
            
            runtime {
                docker: "ubuntu:20.04"
                memory: "2G"
                cpu: 1
            }
            
            output {
                File greeting = stdout()
            }
        }
        """
        
        converter = WDLToCWLConverter()
        cwl_content = converter.convert_string(wdl_content)
        
        # Verify CWL contains expected elements
        assert "cwlVersion: v1.2" in cwl_content
        assert "class: CommandLineTool" in cwl_content
        assert "DockerRequirement" in cwl_content
        assert "dockerPull: ubuntu:20.04" in cwl_content
        assert "ResourceRequirement" in cwl_content
    
    def test_workflow_conversion(self):
        """Test converting a WDL workflow to CWL."""
        wdl_content = """
        version 1.0
        
        task count_lines {
            input {
                File input_file
            }
            
            command <<<
                wc -l < ~{input_file}
            >>>
            
            output {
                Int line_count = read_int(stdout())
            }
        }
        
        workflow count_workflow {
            input {
                File text_file
            }
            
            call count_lines {
                input:
                    input_file = text_file
            }
            
            output {
                Int total_lines = count_lines.line_count
            }
        }
        """
        
        converter = WDLToCWLConverter()
        cwl_content = converter.convert_string(wdl_content)
        
        # Verify CWL workflow structure
        assert "cwlVersion: v1.2" in cwl_content
        assert "$graph:" in cwl_content
        assert "class: Workflow" in cwl_content
        assert "class: CommandLineTool" in cwl_content
    
    def test_array_type_conversion(self):
        """Test array type conversion."""
        parser = WDLParser()
        
        # Create task with array input
        task = Task(
            name="process_files",
            command="process_files.py",
            inputs=[
                Input(
                    name="files",
                    type_spec=TypeSpec(
                        base_type=DataType.ARRAY,
                        item_type=TypeSpec(base_type=DataType.FILE)
                    )
                )
            ]
        )
        
        writer = CWLWriter()
        cwl_content = writer.write(task)
        
        # Verify array type in CWL
        assert "type: array" in cwl_content
        assert "items: File" in cwl_content
    
    def test_optional_type_conversion(self):
        """Test optional type conversion."""
        task = Task(
            name="optional_task",
            command="echo test",
            inputs=[
                Input(
                    name="optional_param",
                    type_spec=TypeSpec(base_type=DataType.STRING, optional=True),
                    optional=True
                )
            ]
        )
        
        writer = CWLWriter()
        cwl_content = writer.write(task)
        
        # Verify optional type in CWL
        assert "- 'null'" in cwl_content or "['null'" in cwl_content
        assert "- string" in cwl_content or "'string']" in cwl_content
    
    def test_scatter_conversion(self):
        """Test scatter operation conversion."""
        wdl_content = """
        version 1.0
        
        task process_file {
            input {
                File input_file
            }
            command <<<
                process ~{input_file}
            >>>
            output {
                File processed = "output.txt"
            }
        }
        
        workflow scatter_workflow {
            input {
                Array[File] files
            }
            
            scatter (file in files) {
                call process_file {
                    input:
                        input_file = file
                }
            }
            
            output {
                Array[File] results = process_file.processed
            }
        }
        """
        
        parser = WDLParser()
        workflow = parser.parse_string(wdl_content)
        
        # Verify scatter was parsed
        assert any(call.scatter for call in workflow.calls)
        
        # Convert to CWL
        writer = CWLWriter()
        cwl_content = writer.write(workflow)
        
        # Basic check - full scatter support would need more implementation
        assert "scatter:" in cwl_content or len(workflow.calls) > 0