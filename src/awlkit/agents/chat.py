"""
Generic chat interface for AWLKit agents.

Provides a base chat interface that domain agents can extend with custom handlers.
"""

from typing import Dict, Any, Optional, Callable, List
import logging
from pathlib import Path
import json

from awlkit.llm import ConversationMemory, detect_available_provider

logger = logging.getLogger(__name__)


class ChatInterface:
    """Generic chat interface for domain agents."""
    
    def __init__(self, agent, llm_provider=None):
        """
        Initialize chat interface.
        
        Args:
            agent: Domain agent instance
            llm_provider: Optional LLM provider instance
        """
        self.agent = agent
        self.llm = llm_provider or detect_available_provider()
        self.handlers: Dict[str, Callable] = {}
        self.memory = ConversationMemory()
        self._register_generic_handlers()
        
        logger.info(f"Initialized chat interface with {self.llm.__class__.__name__}")
    
    def _register_generic_handlers(self):
        """Register handlers that work for all agents."""
        self.register_handler('help', self._handle_help)
        self.register_handler('analyze', self._handle_analyze)
        self.register_handler('list', self._handle_list)
        self.register_handler('convert', self._handle_convert)
        self.register_handler('process', self._handle_process)
    
    def register_handler(self, intent: str, handler: Callable):
        """
        Register a domain-specific handler.
        
        Args:
            intent: Intent keyword to trigger handler
            handler: Callable that takes query and returns response
        """
        self.handlers[intent] = handler
        logger.debug(f"Registered handler for intent: {intent}")
    
    def process_query(self, query: str) -> str:
        """
        Process a user query.
        
        Args:
            query: User input string
            
        Returns:
            Agent response string
        """
        # Parse intent
        intent = self._parse_intent(query)
        logger.debug(f"Detected intent: {intent}")
        
        # Get response
        if intent in self.handlers:
            response = self.handlers[intent](query)
        else:
            # Use LLM for general queries
            response = self._handle_general_query(query)
        
        # Add to memory as a complete turn
        self.memory.add_turn(query, response)
        
        return response
    
    def _parse_intent(self, query: str) -> str:
        """
        Parse intent from user query.
        
        Args:
            query: User input
            
        Returns:
            Intent string or 'general'
        """
        query_lower = query.lower()
        
        # Check each registered handler
        for intent in self.handlers:
            if intent in query_lower:
                return intent
        
        # Check for common patterns
        if any(word in query_lower for word in ['help', 'what can you', 'how do i']):
            return 'help'
        elif any(word in query_lower for word in ['analyze', 'analysis', 'examine']):
            return 'analyze'
        elif any(word in query_lower for word in ['list', 'show', 'available']):
            return 'list'
        elif any(word in query_lower for word in ['convert', 'transform']):
            return 'convert'
        elif any(word in query_lower for word in ['process', 'run', 'execute']):
            return 'process'
        
        return 'general'
    
    def _handle_help(self, query: str) -> str:
        """Generic help handler."""
        capabilities = self.agent.get_capabilities()
        handlers = list(self.handlers.keys())
        
        help_text = [
            "I can help you with:",
            "\nCapabilities:",
            *[f"  - {cap}" for cap in capabilities],
            "\nAvailable commands:",
            *[f"  - {handler}" for handler in handlers],
            "\nTry asking about specific workflows or tasks!"
        ]
        
        return "\n".join(help_text)
    
    def _handle_analyze(self, query: str) -> str:
        """Generic analyze handler."""
        # Extract workflow name from query
        words = query.split()
        workflow_candidates = [w for w in words if w.endswith('.wdl') or w.endswith('.cwl')]
        
        if workflow_candidates:
            workflow = workflow_candidates[0]
            try:
                analysis = self.agent.analyze_workflow(workflow)
                return self._format_analysis(analysis)
            except Exception as e:
                return f"Failed to analyze {workflow}: {e}"
        else:
            return "Please specify a workflow file to analyze (e.g., 'analyze workflow.wdl')"
    
    def _handle_list(self, query: str) -> str:
        """Generic list handler."""
        # This should be overridden by domain agents
        return "The list command should be implemented by the specific agent."
    
    def _handle_convert(self, query: str) -> str:
        """Generic convert handler."""
        return "The convert command should be implemented by the specific agent."
    
    def _handle_process(self, query: str) -> str:
        """Generic process handler."""
        return "To process a batch, please provide a batch configuration file."
    
    def _handle_general_query(self, query: str) -> str:
        """
        Handle general queries using LLM.
        
        Args:
            query: User query
            
        Returns:
            LLM-generated response
        """
        # Build context from conversation memory
        context = self.memory.get_context()
        
        # Create prompt with context
        prompt = f"""You are a helpful workflow automation assistant.

Previous context:
{context}

User query: {query}

Please provide a helpful response:"""
        
        try:
            response = self.llm.generate(prompt)
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "I'm having trouble generating a response. Please try rephrasing your question."
    
    def _format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format workflow analysis results."""
        lines = [
            f"Workflow: {analysis.get('path', 'Unknown')}",
            f"Type: {analysis.get('type', 'Unknown')}",
            f"\nInputs ({len(analysis.get('inputs', []))}):",
            *[f"  - {inp}" for inp in analysis.get('inputs', [])],
            f"\nOutputs ({len(analysis.get('outputs', []))}):",
            *[f"  - {out}" for out in analysis.get('outputs', [])],
            f"\nTasks ({len(analysis.get('tasks', []))}):",
            *[f"  - {task}" for task in analysis.get('tasks', [])]
        ]
        
        return "\n".join(lines)
    
    def chat_loop(self):
        """Run interactive chat loop."""
        print("\n" + "="*50)
        print("Interactive Chat Interface")
        print("Type 'help' for available commands or 'quit' to exit")
        print("="*50 + "\n")
        
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()
                
                # Check for exit
                if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                    print("\nGoodbye!")
                    break
                
                # Skip empty input
                if not user_input:
                    continue
                
                # Process query
                response = self.process_query(user_input)
                
                # Display response
                print(f"\nAgent: {response}")
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}", exc_info=True)
                print(f"\nError: {e}")
                print("Please try again or type 'quit' to exit.")