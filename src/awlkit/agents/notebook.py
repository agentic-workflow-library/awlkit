"""
Generic notebook interface for AWLKit agents.

Provides Jupyter notebook integration for domain agents.
"""

from typing import Dict, Any, Optional, List
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class NotebookInterface:
    """Generic notebook interface for domain agents."""
    
    def __init__(self, agent):
        """
        Initialize notebook interface.
        
        Args:
            agent: Domain agent instance
        """
        self.agent = agent
        self._setup_display()
    
    def _setup_display(self):
        """Set up notebook display capabilities."""
        try:
            from IPython.display import display, Markdown, HTML, JSON
            self.display = display
            self.Markdown = Markdown
            self.HTML = HTML
            self.JSON = JSON
            self._has_display = True
        except ImportError:
            self._has_display = False
            logger.warning("IPython not available - display features disabled")
    
    def display_markdown(self, content: str):
        """Display markdown content."""
        if self._has_display:
            self.display(self.Markdown(content))
        else:
            print(content)
    
    def display_html(self, content: str):
        """Display HTML content."""
        if self._has_display:
            self.display(self.HTML(content))
        else:
            print(content)
    
    def display_json(self, data: Dict[str, Any]):
        """Display JSON data."""
        if self._has_display:
            self.display(self.JSON(data))
        else:
            print(json.dumps(data, indent=2))
    
    def analyze_workflow_interactive(self, workflow_path: str):
        """
        Analyze workflow with interactive display.
        
        Args:
            workflow_path: Path to workflow file
        """
        self.display_markdown(f"## Analyzing Workflow: `{workflow_path}`")
        
        try:
            analysis = self.agent.analyze_workflow(workflow_path)
            
            # Display results in sections
            self.display_markdown("### Workflow Type")
            self.display_markdown(f"**{analysis.get('type', 'Unknown')}**")
            
            self.display_markdown("### Inputs")
            inputs = analysis.get('inputs', [])
            if inputs:
                input_list = "\n".join([f"- `{inp}`" for inp in inputs])
                self.display_markdown(input_list)
            else:
                self.display_markdown("*No inputs found*")
            
            self.display_markdown("### Outputs")
            outputs = analysis.get('outputs', [])
            if outputs:
                output_list = "\n".join([f"- `{out}`" for out in outputs])
                self.display_markdown(output_list)
            else:
                self.display_markdown("*No outputs found*")
            
            self.display_markdown("### Tasks")
            tasks = analysis.get('tasks', [])
            if tasks:
                self.display_markdown(f"Total tasks: **{len(tasks)}**")
                task_list = "\n".join([f"- `{task}`" for task in tasks[:10]])
                self.display_markdown(task_list)
                if len(tasks) > 10:
                    self.display_markdown(f"*... and {len(tasks) - 10} more*")
            else:
                self.display_markdown("*No tasks found*")
            
            # Display full analysis as JSON
            self.display_markdown("### Full Analysis")
            self.display_json(analysis)
            
        except Exception as e:
            self.display_markdown(f"**Error:** {e}")
    
    def process_batch_interactive(self, batch_config: Dict[str, Any]):
        """
        Process batch with interactive progress display.
        
        Args:
            batch_config: Batch configuration dictionary
        """
        self.display_markdown("## Batch Processing")
        self.display_markdown(f"Processing **{len(batch_config['samples'])}** samples")
        
        # Display configuration
        self.display_markdown("### Configuration")
        config_display = {k: v for k, v in batch_config.items() if k != 'samples'}
        self.display_json(config_display)
        
        # Display sample summary
        self.display_markdown("### Samples")
        samples = batch_config['samples']
        if len(samples) <= 5:
            for sample in samples:
                self.display_markdown(f"- {sample.get('id', 'Unknown ID')}")
        else:
            for sample in samples[:3]:
                self.display_markdown(f"- {sample.get('id', 'Unknown ID')}")
            self.display_markdown(f"- *... and {len(samples) - 3} more*")
        
        # Process batch
        self.display_markdown("### Processing...")
        try:
            results = self.agent.process_batch(batch_config)
            
            self.display_markdown("### Results")
            self.display_json(results)
            
            self.display_markdown("**✓ Processing completed successfully**")
            
        except Exception as e:
            self.display_markdown(f"**✗ Processing failed:** {e}")
    
    def display_capabilities(self):
        """Display agent capabilities."""
        self.display_markdown("## Agent Capabilities")
        
        capabilities = self.agent.get_capabilities()
        metadata = self.agent.get_metadata()
        
        self.display_markdown(f"### Agent: **{metadata['name']}**")
        
        self.display_markdown("### Available Operations")
        for cap in capabilities:
            self.display_markdown(f"- `{cap}`")
        
        if metadata.get('config'):
            self.display_markdown("### Configuration")
            self.display_json(metadata['config'])
    
    def create_batch_config_template(self, num_samples: int = 2) -> Dict[str, Any]:
        """
        Create a template batch configuration.
        
        Args:
            num_samples: Number of sample entries to include
            
        Returns:
            Template configuration dictionary
        """
        template = {
            "samples": [
                {
                    "id": f"sample_{i+1}",
                    "input_file": f"/path/to/sample_{i+1}.bam",
                    "metadata": {
                        "description": f"Sample {i+1} description"
                    }
                }
                for i in range(num_samples)
            ],
            "output_dir": "/path/to/output",
            "reference": "/path/to/reference.fa",
            "options": {
                "threads": 4,
                "memory": "8G"
            }
        }
        
        self.display_markdown("## Batch Configuration Template")
        self.display_json(template)
        
        return template
    
    def visualize_workflow(self, workflow_path: str):
        """
        Visualize workflow structure (requires graphviz).
        
        Args:
            workflow_path: Path to workflow file
        """
        try:
            from awlkit.utils import WorkflowVisualizer
            visualizer = WorkflowVisualizer()
            
            self.display_markdown(f"## Workflow Visualization: `{workflow_path}`")
            
            # Generate visualization
            dot_graph = visualizer.generate_dot(workflow_path)
            
            if self._has_display:
                # Display as SVG in notebook
                svg = visualizer.render_svg(dot_graph)
                self.display_html(svg)
            else:
                # Save as file
                output_path = f"{workflow_path}.png"
                visualizer.save_png(dot_graph, output_path)
                print(f"Visualization saved to: {output_path}")
                
        except ImportError:
            self.display_markdown("**Note:** Workflow visualization requires the graphviz package")
        except Exception as e:
            self.display_markdown(f"**Error visualizing workflow:** {e}")