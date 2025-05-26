"""Graph analysis utilities for workflows."""

import networkx as nx
from typing import List, Set, Dict, Any

from ..ir import Workflow


class WorkflowGraphAnalyzer:
    """Analyze workflow structure and dependencies."""
    
    def __init__(self, workflow: Workflow):
        """Initialize analyzer with workflow."""
        self.workflow = workflow
        self.graph = workflow.get_dependency_graph()
    
    def get_execution_order(self) -> List[str]:
        """Get topological order of workflow calls."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            # Graph has cycles
            return []
    
    def find_cycles(self) -> List[List[str]]:
        """Find all cycles in the workflow."""
        return list(nx.simple_cycles(self.graph))
    
    def get_dependencies(self, call_id: str) -> Set[str]:
        """Get all dependencies of a call."""
        if call_id not in self.graph:
            return set()
        
        return set(nx.ancestors(self.graph, call_id))
    
    def get_dependents(self, call_id: str) -> Set[str]:
        """Get all calls that depend on this call."""
        if call_id not in self.graph:
            return set()
        
        return set(nx.descendants(self.graph, call_id))
    
    def get_parallel_groups(self) -> List[Set[str]]:
        """Get groups of calls that can execute in parallel."""
        groups = []
        remaining = set(self.graph.nodes())
        
        while remaining:
            # Find all nodes with no dependencies in remaining set
            parallel_group = set()
            
            for node in remaining:
                deps = self.get_dependencies(node)
                if not deps.intersection(remaining):
                    parallel_group.add(node)
            
            if parallel_group:
                groups.append(parallel_group)
                remaining -= parallel_group
            else:
                # Cycle detected, break
                break
        
        return groups
    
    def get_critical_path(self) -> List[str]:
        """Get the longest path through the workflow."""
        if not self.graph.nodes():
            return []
        
        # For DAGs, find longest path
        if nx.is_directed_acyclic_graph(self.graph):
            return nx.dag_longest_path(self.graph)
        
        return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        return {
            "total_calls": len(self.graph.nodes()),
            "total_dependencies": len(self.graph.edges()),
            "has_cycles": len(self.find_cycles()) > 0,
            "parallel_groups": len(self.get_parallel_groups()),
            "critical_path_length": len(self.get_critical_path()),
            "max_parallelism": max(len(g) for g in self.get_parallel_groups()) if self.get_parallel_groups() else 0
        }