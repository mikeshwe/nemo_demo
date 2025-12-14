"""Agent state definition for LangGraph"""
from typing import TypedDict, List, Dict, Annotated
from operator import add

class AgentState(TypedDict):
    """State that flows through the agent graph (MVP version)"""

    # User's query
    query: str

    # Messages in OpenAI format
    messages: Annotated[List[Dict], add]

    # Accumulated observations from tool executions
    observations: str

    # Tool execution results (using add operator for LangGraph state merging)
    # Note: This accumulates across graph cycles, so count may be higher than actual calls
    tool_results: Annotated[List[Dict], add]

    # Actual count of unique tool calls
    tool_call_count: int

    # Current iteration count
    iteration_count: int

    # Maximum iterations allowed
    max_iterations: int

    # Whether to continue iterating
    should_continue: bool

    # Whether we have a final answer
    has_final_answer: bool

    # Final answer text
    final_answer: str
