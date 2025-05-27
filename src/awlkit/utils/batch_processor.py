"""
Batch processing utilities for AWLKit.

Provides generic batch processing capabilities for domain agents.
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Generic batch processing utilities."""
    
    @staticmethod
    def validate_batch_config(config: Dict[str, Any], required_fields: Optional[List[str]] = None) -> bool:
        """
        Validate batch configuration.
        
        Args:
            config: Batch configuration dictionary
            required_fields: Optional list of required fields beyond 'samples'
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        # Basic validation
        if not isinstance(config, dict):
            raise ValueError("Batch configuration must be a dictionary")
        
        # Check required fields
        base_required = ['samples']
        if required_fields:
            base_required.extend(required_fields)
        
        for field in base_required:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate samples
        if not isinstance(config['samples'], list):
            raise ValueError("'samples' must be a list")
        
        if not config['samples']:
            raise ValueError("'samples' list cannot be empty")
        
        # Validate each sample
        for i, sample in enumerate(config['samples']):
            if not isinstance(sample, dict):
                raise ValueError(f"Sample {i} must be a dictionary")
            if 'id' not in sample:
                raise ValueError(f"Sample {i} missing required 'id' field")
        
        # Check for duplicate sample IDs
        sample_ids = [s['id'] for s in config['samples']]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("Duplicate sample IDs found")
        
        return True
    
    @staticmethod
    def split_batch(samples: List[Dict[str, Any]], batch_size: int = 50) -> List[List[Dict[str, Any]]]:
        """
        Split samples into smaller batches.
        
        Args:
            samples: List of sample dictionaries
            batch_size: Maximum samples per batch
            
        Returns:
            List of sample batches
        """
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")
        
        batches = []
        for i in range(0, len(samples), batch_size):
            batches.append(samples[i:i + batch_size])
        
        logger.info(f"Split {len(samples)} samples into {len(batches)} batches of size {batch_size}")
        return batches
    
    @staticmethod
    def merge_batch_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge results from multiple batches.
        
        Args:
            results: List of result dictionaries from each batch
            
        Returns:
            Merged results dictionary
        """
        if not results:
            return {}
        
        # Start with first result as base
        merged = results[0].copy()
        
        # Merge additional results
        for result in results[1:]:
            for key, value in result.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    # Concatenate lists
                    merged[key].extend(value)
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    # Merge dictionaries
                    merged[key].update(value)
                elif isinstance(value, (int, float)) and isinstance(merged[key], (int, float)):
                    # Sum numeric values
                    merged[key] += value
                else:
                    # Create list of values for other types
                    if not isinstance(merged[key], list):
                        merged[key] = [merged[key]]
                    merged[key].append(value)
        
        return merged
    
    @staticmethod
    def process_parallel(
        items: List[Any],
        process_func: Callable[[Any], Any],
        max_workers: int = 4,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        Process items in parallel.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            max_workers: Maximum number of parallel workers
            progress_callback: Optional callback for progress updates (completed, total)
            
        Returns:
            List of results in same order as input items
        """
        results = [None] * len(items)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(process_func, item): i
                for i, item in enumerate(items)
            }
            
            # Process completed tasks
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, len(items))
                        
                except Exception as e:
                    logger.error(f"Failed to process item {index}: {e}")
                    results[index] = {'error': str(e)}
                    completed += 1
                    
                    if progress_callback:
                        progress_callback(completed, len(items))
        
        return results
    
    @staticmethod
    def load_batch_config(config_path: str) -> Dict[str, Any]:
        """
        Load batch configuration from file.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            Configuration dictionary
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        if config_path.suffix not in ['.json', '.yaml', '.yml']:
            raise ValueError("Configuration file must be JSON or YAML")
        
        try:
            if config_path.suffix == '.json':
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                # YAML support
                import yaml
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
                    
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    @staticmethod
    def save_batch_results(results: Dict[str, Any], output_path: str):
        """
        Save batch results to file.
        
        Args:
            results: Results dictionary
            output_path: Path to save results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            raise
    
    @staticmethod
    def generate_batch_report(results: Dict[str, Any]) -> str:
        """
        Generate a text report from batch results.
        
        Args:
            results: Batch processing results
            
        Returns:
            Formatted report string
        """
        lines = ["Batch Processing Report", "=" * 50]
        
        # Add metadata if present
        if '_metadata' in results:
            meta = results['_metadata']
            lines.extend([
                f"Agent: {meta.get('agent', 'Unknown')}",
                f"Samples: {meta.get('samples_requested', 'Unknown')}",
                ""
            ])
        
        # Add timing information if present
        if 'start_time' in results and 'end_time' in results:
            duration = results['end_time'] - results['start_time']
            lines.extend([
                f"Start Time: {results['start_time']}",
                f"End Time: {results['end_time']}",
                f"Duration: {duration:.2f} seconds",
                ""
            ])
        
        # Add summary statistics
        if 'summary' in results:
            lines.append("Summary:")
            for key, value in results['summary'].items():
                lines.append(f"  {key}: {value}")
            lines.append("")
        
        # Add sample results if present
        if 'sample_results' in results:
            lines.append(f"Sample Results: {len(results['sample_results'])} samples")
            
            # Show first few samples
            for i, sample_result in enumerate(results['sample_results'][:5]):
                sample_id = sample_result.get('id', f'Sample {i}')
                status = sample_result.get('status', 'Unknown')
                lines.append(f"  - {sample_id}: {status}")
            
            if len(results['sample_results']) > 5:
                lines.append(f"  ... and {len(results['sample_results']) - 5} more")
        
        return "\n".join(lines)