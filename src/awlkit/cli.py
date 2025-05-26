"""Command-line interface for AWLKit."""

import click
import logging
from pathlib import Path

from .converters import WDLToCWLConverter


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def cli(verbose):
    """AWLKit - Agentic Workflow Library Kit."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@cli.command()
@click.argument('wdl_file', type=click.Path(exists=True, path_type=Path))
@click.argument('cwl_file', type=click.Path(path_type=Path), required=False)
@click.option('--validate', is_flag=True, help='Validate the conversion')
def convert(wdl_file, cwl_file, validate):
    """Convert a WDL file to CWL format."""
    converter = WDLToCWLConverter()
    
    # Default output file if not specified
    if not cwl_file:
        cwl_file = wdl_file.with_suffix('.cwl')
    
    try:
        element = converter.convert_file(wdl_file, cwl_file)
        
        if validate:
            if converter.validate_conversion(element):
                click.echo(f"✓ Conversion validated successfully")
            else:
                click.echo(f"✗ Validation failed", err=True)
                raise click.Abort()
        
        click.echo(f"✓ Converted {wdl_file} to {cwl_file}")
        
    except Exception as e:
        click.echo(f"✗ Conversion failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('wdl_dir', type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument('cwl_dir', type=click.Path(file_okay=False, path_type=Path))
@click.option('--recursive/--no-recursive', default=True, help='Process subdirectories')
def convert_dir(wdl_dir, cwl_dir, recursive):
    """Convert all WDL files in a directory to CWL format."""
    converter = WDLToCWLConverter()
    
    try:
        converter.convert_directory(wdl_dir, cwl_dir, recursive=recursive)
        click.echo(f"✓ Conversion complete")
    except Exception as e:
        click.echo(f"✗ Conversion failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.argument('wdl_file', type=click.File('r'))
def parse(wdl_file):
    """Parse a WDL file and display its structure."""
    from pprint import pprint
    
    parser = WDLParser()
    
    try:
        content = wdl_file.read()
        element = parser.parse_string(content, wdl_file.name)
        
        click.echo(f"Parsed {type(element).__name__}: {element.name}")
        click.echo(f"\nInputs: {len(element.inputs)}")
        for inp in element.inputs:
            click.echo(f"  - {inp.name}: {inp.type_spec.to_wdl_string()}")
        
        if hasattr(element, 'tasks'):
            click.echo(f"\nTasks: {len(element.tasks)}")
            for task_name in element.tasks:
                click.echo(f"  - {task_name}")
        
        if hasattr(element, 'calls'):
            click.echo(f"\nCalls: {len(element.calls)}")
            for call in element.calls:
                click.echo(f"  - {call.call_id} -> {call.task_name}")
        
        click.echo(f"\nOutputs: {len(element.outputs)}")
        for out in element.outputs:
            click.echo(f"  - {out.name}: {out.type_spec.to_wdl_string()}")
            
    except Exception as e:
        click.echo(f"✗ Parse failed: {e}", err=True)
        raise click.Abort()


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()