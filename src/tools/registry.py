"""Tool registry for managing agent tools"""
from src.utils.logger import log_info, log_debug

class ToolRegistry:
    """Registry to manage and execute agent tools"""

    def __init__(self):
        """Initialize empty registry"""
        self.tools = {}
        log_debug("Initialized ToolRegistry")

    def register(self, tool):
        """Register a tool

        Args:
            tool: BaseTool instance
        """
        self.tools[tool.name] = tool
        log_info(f"✓ Registered tool: {tool.name}")

    def get_tool(self, name):
        """Get a tool by name

        Args:
            name: Tool name

        Returns:
            BaseTool instance or None
        """
        return self.tools.get(name)

    def get_all_tools(self):
        """Get all registered tools

        Returns:
            List of BaseTool instances
        """
        return list(self.tools.values())

    def to_openai_tools(self):
        """Convert all tools to OpenAI function calling format

        Returns:
            List of tool definitions
        """
        return [tool.to_openai_tool() for tool in self.tools.values()]

    def execute_tool(self, name, **kwargs):
        """Execute a tool by name

        Args:
            name: Tool name
            **kwargs: Tool arguments

        Returns:
            Tool execution result dict
        """
        tool = self.get_tool(name)

        if not tool:
            log_debug(f"Tool not found: {name}")
            return {
                "success": False,
                "data": None,
                "error": f"Tool not found: {name}"
            }

        log_debug(f"Executing tool: {name} with args: {list(kwargs.keys())}")
        result = tool.execute(**kwargs)
        log_debug(f"Tool {name} returned: success={result['success']}")

        return result

    def list_tools(self):
        """Get list of registered tool names"""
        return list(self.tools.keys())
