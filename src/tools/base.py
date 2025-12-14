"""Base tool interface for agent tools (MVP version)"""

class BaseTool:
    """Base class for all agent tools"""

    @property
    def name(self):
        """Tool name for LLM"""
        raise NotImplementedError

    @property
    def description(self):
        """Tool description for LLM"""
        raise NotImplementedError

    @property
    def parameters(self):
        """JSON schema for parameters"""
        raise NotImplementedError

    def execute(self, **kwargs):
        """Execute tool logic

        Returns:
            dict with keys: success (bool), data (any), error (str or None)
        """
        raise NotImplementedError

    def to_openai_tool(self):
        """Convert to OpenAI function calling format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
