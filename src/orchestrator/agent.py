"""Main GenAIOps Agent class"""
from src.orchestrator.graph import create_agent_graph
from src.utils.logger import log_info, log_debug

class GenAIOpsAgent:
    """GenAIOps Documentation Assistant Agent

    This agent uses LangGraph to implement a ReAct loop:
    1. Reasoning: LLM decides what to do next
    2. Acting: Execute tools
    3. Repeat until final answer is ready
    """

    def __init__(self, llm_client, tool_registry, max_iterations=10):
        """Initialize the agent

        Args:
            llm_client: NVIDIAClient instance
            tool_registry: ToolRegistry instance
            max_iterations: Maximum ReAct iterations (default: 10)
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

        # Build the LangGraph
        self.graph = create_agent_graph(llm_client, tool_registry)

        log_info("✓ GenAIOpsAgent initialized")

    def run(self, query):
        """Run the agent on a user query

        Args:
            query: User's question or request

        Returns:
            dict with:
                - answer: Final answer text
                - tool_calls: Number of tool calls made
                - iterations: Number of reasoning iterations
                - observations: Tool execution observations
        """
        log_info(f"Running agent on query: {query[:100]}...")

        # Initialize state
        initial_state = {
            "query": query,
            "messages": [],
            "observations": "",
            "tool_results": [],
            "tool_call_count": 0,
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "should_continue": True,
            "has_final_answer": False,
            "final_answer": ""
        }

        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Extract results
            answer = final_state.get("final_answer", "Unable to generate answer")
            tool_calls = final_state.get("tool_call_count", 0)  # Use actual count instead of list length
            iterations = final_state.get("iteration_count", 0)
            observations = final_state.get("observations", "")

            log_info(f"✓ Agent completed: {iterations} iterations, {tool_calls} tool calls")

            return {
                "answer": answer,
                "tool_calls": tool_calls,
                "iterations": iterations,
                "observations": observations,
                "success": True
            }

        except Exception as e:
            log_debug(f"Agent execution failed: {e}")

            return {
                "answer": f"Error: {str(e)}",
                "tool_calls": 0,
                "iterations": 0,
                "observations": "",
                "success": False,
                "error": str(e)
            }

    def list_available_tools(self):
        """Get list of available tool names

        Returns:
            List of tool names
        """
        return self.tool_registry.list_tools()
