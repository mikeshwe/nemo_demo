"""Main GenAIOps Agent class"""
import uuid
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

# OpenLineage imports
try:
    from src.observability.lineage import (
        set_lineage_context,
        clear_lineage_context,
        get_current_run_id,
        is_lineage_enabled,
        emit_job_event
    )
    from opentelemetry import trace
    LINEAGE_AVAILABLE = True
except ImportError:
    LINEAGE_AVAILABLE = False

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

        # Set lineage context for this agent run
        if LINEAGE_AVAILABLE and is_lineage_enabled():
            run_id = str(uuid.uuid4())
            set_lineage_context(run_id, "agent_query")
            log_debug(f"Lineage context set: run_id={run_id[:8]}...")

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
        finally:
            # Clear lineage context
            if LINEAGE_AVAILABLE and is_lineage_enabled():
                clear_lineage_context()

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

                # Add lineage context attributes for correlation
                if LINEAGE_AVAILABLE and is_lineage_enabled():
                    run_id = get_current_run_id()
                    if run_id:
                        span.set_attribute("lineage.run_id", run_id)
                        span.set_attribute("lineage.job_name", "agent_query")
                        log_debug(f"OTel span tagged with lineage run_id: {run_id[:8]}...")

                span.add_event(EVENT_AGENT_START)

                result = self._run_with_tracing(span, initial_state)

                # Capture span attributes for debugging/display
                if hasattr(span, 'attributes') and span.attributes:
                    result['_otel_span_attributes'] = dict(span.attributes)

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

            # Emit OpenLineage COMPLETE event with input datasets
            if LINEAGE_AVAILABLE and is_lineage_enabled():
                self._emit_agent_lineage_event(span, final_state)

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

            # Emit OpenLineage COMPLETE event with input datasets
            if LINEAGE_AVAILABLE and is_lineage_enabled():
                self._emit_agent_lineage_event(None, final_state)

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

    def _emit_agent_lineage_event(self, span, final_state):
        """Emit OpenLineage event for agent run with input datasets

        Requires OpenTelemetry to be initialized for span attributes.

        Args:
            span: Current OpenTelemetry span (required)
            final_state: Final state after agent execution
        """
        try:
            # Extract input run IDs from OTel span attributes
            if not span or not hasattr(span, 'attributes'):
                log_debug("No OTel span available - cannot emit lineage event")
                log_debug("OpenTelemetry must be initialized for lineage correlation")
                return

            input_run_ids_str = span.attributes.get("lineage.input_run_ids", "")
            if not input_run_ids_str:
                log_debug("No input datasets accessed by agent, skipping lineage event")
                return

            input_run_ids_set = set(input_run_ids_str.split(","))

            # Build input datasets list
            inputs = []
            for producer_run_id in input_run_ids_set:
                inputs.append({
                    "namespace": "chromadb",
                    "name": "internal_docs.chunks",
                    "facets": {
                        "producerRunId": {
                            "_producer": "https://github.com/OpenLineage/OpenLineage/tree/1.2.0/client/python",
                            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ProducerRunIdFacet.json",
                            "producerRunId": producer_run_id.strip()
                        }
                    }
                })

            # Get current run ID
            run_id = get_current_run_id()
            if not run_id:
                log_debug("No lineage run_id set, skipping lineage event")
                return

            # Emit COMPLETE event
            emit_job_event(
                job_name="agent_query",
                run_id=run_id,
                event_type="COMPLETE",
                inputs=inputs,
                metadata={
                    "iterations": final_state.get("iteration_count", 0),
                    "tool_calls": final_state.get("tool_call_count", 0),
                    "query": final_state.get("query", "")[:200]
                }
            )

            log_debug(f"Emitted OpenLineage event for agent run with {len(inputs)} input datasets")

        except Exception as e:
            log_debug(f"Failed to emit agent lineage event: {e}")

    def list_available_tools(self):
        """Get list of available tool names

        Returns:
            List of tool names
        """
        return self.tool_registry.list_tools()
