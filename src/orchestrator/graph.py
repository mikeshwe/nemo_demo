"""LangGraph construction for ReAct agent"""
from langgraph.graph import StateGraph, END
from src.orchestrator.state import AgentState
from src.orchestrator.nodes import reasoning_node, tool_execution_node
from src.utils.logger import log_info, log_debug

def should_continue(state):
    """Determine whether to continue iterating or finish

    Args:
        state: Current AgentState

    Returns:
        "continue" or "end"
    """
    # Check max iterations
    if state["iteration_count"] >= state["max_iterations"]:
        log_info(f"Max iterations ({state['max_iterations']}) reached")
        return "end"

    # Check if final answer is ready
    if state["has_final_answer"]:
        log_info("Final answer ready")
        return "end"

    # Check if should continue (set by reasoning node)
    if state["should_continue"]:
        log_debug("Continuing to tool execution")
        return "continue"

    # Default to end
    return "end"


def create_agent_graph(llm_client, tool_registry):
    """Create the LangGraph agent

    Args:
        llm_client: NVIDIAClient instance
        tool_registry: ToolRegistry instance

    Returns:
        Compiled graph
    """
    log_info("Building LangGraph...")

    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes with bound parameters
    workflow.add_node(
        "reasoning",
        lambda state: reasoning_node(state, llm_client, tool_registry)
    )

    workflow.add_node(
        "tool_execution",
        lambda state: tool_execution_node(state, tool_registry)
    )

    # Set entry point
    workflow.set_entry_point("reasoning")

    # Add conditional edges from reasoning node
    workflow.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "continue": "tool_execution",
            "end": END
        }
    )

    # After tool execution, go back to reasoning
    workflow.add_edge("tool_execution", "reasoning")

    # Compile graph (no checkpointing for MVP)
    graph = workflow.compile()

    log_info("✓ LangGraph compiled successfully")

    return graph
