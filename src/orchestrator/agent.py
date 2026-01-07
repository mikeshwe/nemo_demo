"""Main GenAIOps Agent class"""
from src.orchestrator.graph import create_agent_graph
from src.utils.logger import log_info, log_debug

# OpenTelemetry imports
try:
    from src.observability import (
        get_tracer,
        is_initialized,
        AGENT_QUERY,
        AGENT_MAX_ITERATIONS,
        AGENT_FINAL_ITERATIONS,
        AGENT_TOOL_CALLS,
        AGENT_SUCCESS,
        EVENT_AGENT_START,
        EVENT_AGENT_COMPLETE,
        EVENT_AGENT_ERROR
    )
    from src.observability.tracer import add_span_attributes, record_exception
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# Langfuse imports
try:
    from src.observability.langfuse_integration import (
        trace_agent_run,
        is_langfuse_enabled,
        score_generation,
        set_trace_output
    )
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

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

        # Create Langfuse trace (wraps entire execution)
        if LANGFUSE_AVAILABLE and is_langfuse_enabled():
            with trace_agent_run(
                query=query,
                metadata={
                    "max_iterations": self.max_iterations,
                    "tool_count": len(self.tool_registry.tools)
                }
            ):
                return self._execute_agent(initial_state, query)
        else:
            return self._execute_agent(initial_state, query)

    def _execute_agent(self, initial_state, query):
        """Execute agent with both OTEL and Langfuse support"""
        # Create OpenTelemetry span for entire agent run
        if OTEL_AVAILABLE and is_initialized():
            tracer = get_tracer()
            with tracer.start_as_current_span("agent.run") as span:
                # Add initial attributes
                add_span_attributes(span, {
                    AGENT_QUERY: query[:200],  # Truncate for readability
                    AGENT_MAX_ITERATIONS: self.max_iterations
                })
                span.add_event(EVENT_AGENT_START)

                result = self._run_with_tracing(span, initial_state)

                # Add Langfuse scores after execution
                if LANGFUSE_AVAILABLE and is_langfuse_enabled():
                    self._add_langfuse_scores(result)

                return result
        else:
            # Run without OTEL tracing
            result = self._run_without_tracing(initial_state)

            # Add Langfuse scores after execution
            if LANGFUSE_AVAILABLE and is_langfuse_enabled():
                self._add_langfuse_scores(result)

            return result

    def _add_langfuse_scores(self, result):
        """Add quality and efficiency scores to Langfuse trace"""
        # Success score (1.0 if successful, 0.0 if failed)
        success_score = 1.0 if result.get("success", False) else 0.0
        score_generation("success", success_score)

        # Efficiency score (based on iterations used)
        iterations = result.get("iterations", 0)
        if iterations > 0:
            efficiency = 1.0 - (iterations / self.max_iterations)
            score_generation(
                "efficiency",
                efficiency,
                f"Used {iterations}/{self.max_iterations} iterations"
            )

        # Set final output
        set_trace_output({
            "answer": result.get("answer", ""),
            "tool_calls": result.get("tool_calls", 0),
            "iterations": iterations
        })

    def _run_with_tracing(self, span, initial_state):
        """Run agent with OpenTelemetry tracing

        Args:
            span: Current OpenTelemetry span
            initial_state: Initial agent state

        Returns:
            dict with results
        """
        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Extract results
            answer = final_state.get("final_answer", "Unable to generate answer")
            tool_calls = final_state.get("tool_call_count", 0)
            iterations = final_state.get("iteration_count", 0)
            observations = final_state.get("observations", "")

            # Add final attributes to span
            add_span_attributes(span, {
                AGENT_FINAL_ITERATIONS: iterations,
                AGENT_TOOL_CALLS: tool_calls,
                AGENT_SUCCESS: True
            })
            span.add_event(EVENT_AGENT_COMPLETE)

            log_info(f"✓ Agent completed: {iterations} iterations, {tool_calls} tool calls")

            return {
                "answer": answer,
                "tool_calls": tool_calls,
                "iterations": iterations,
                "observations": observations,
                "success": True
            }

        except Exception as e:
            # Record exception in span
            record_exception(span, e)
            span.add_event(EVENT_AGENT_ERROR, {"error": str(e)})

            log_debug(f"Agent execution failed: {e}")

            return {
                "answer": f"Error: {str(e)}",
                "tool_calls": 0,
                "iterations": 0,
                "observations": "",
                "success": False,
                "error": str(e)
            }

    def _run_without_tracing(self, initial_state):
        """Run agent without OpenTelemetry tracing

        Args:
            initial_state: Initial agent state

        Returns:
            dict with results
        """
        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)

            # Extract results
            answer = final_state.get("final_answer", "Unable to generate answer")
            tool_calls = final_state.get("tool_call_count", 0)
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
