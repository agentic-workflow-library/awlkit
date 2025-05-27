# AWLKit - Agentic Workflow Language Kit

AWLKit provides the infrastructure for building domain-specific workflow automation agents.

## Architecture

```
awlkit/
├── agents/          # Base classes for agents
│   ├── base.py     # Agent base class with batch processing
│   ├── chat.py     # ChatInterface for interactive agents
│   └── notebook.py # NotebookInterface for Jupyter integration
├── llm/            # LLM integration layer
│   ├── __init__.py # LLM providers (Ollama, OpenAI, Anthropic, RuleBased)
│   └── utils.py    # ConversationMemory and utilities
└── utils/          # General utilities
    ├── workflow_analyzer.py # Workflow analysis tools
    └── batch_processor.py   # Batch processing utilities
```

## Key Features

### 1. Agent Base Class
- Standardized batch processing with validation
- Workflow analysis capabilities
- Metadata and capability management
- Extensible through inheritance

### 2. Chat Interface
- Generic chat loop with intent parsing
- Handler registration for domain-specific commands
- LLM integration with automatic fallback
- Conversation memory management

### 3. LLM Integration
- Multiple provider support (Ollama, OpenAI, Anthropic)
- Automatic provider detection
- Rule-based fallback when no LLM available
- Conversation memory for context

### 4. Utilities
- WorkflowAnalyzer: Parse and analyze WDL/CWL workflows
- BatchProcessor: Handle batch operations with validation

## Usage

Domain agents inherit from AWLKit base classes:

```python
from awlkit.agents import Agent, ChatInterface

class MyDomainAgent(Agent):
    def __init__(self):
        super().__init__()
        # Add domain-specific initialization
    
    def _execute_batch(self, batch_config):
        # Implement domain-specific batch processing
        pass

class MyDomainChat(ChatInterface):
    def __init__(self, agent):
        super().__init__(agent)
        # Register domain-specific handlers
        self.register_handler('my_command', self._handle_my_command)
```

## Design Principles

1. **Separation of Concerns**: AWLKit handles infrastructure, domain agents handle expertise
2. **Extensibility**: Easy to add new providers, handlers, and capabilities
3. **Graceful Degradation**: Falls back to rule-based responses when LLMs unavailable
4. **Consistency**: All agents share the same interface and behavior patterns