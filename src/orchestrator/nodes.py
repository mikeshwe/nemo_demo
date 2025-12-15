"""Node functions for the LangGraph agent"""
import json
from src.utils.logger import log_info, log_debug, log_warning, log_verbose
from src.llm.prompts import SYSTEM_PROMPT
from src.guardrails.nemo_guardrails import NemoGuardrailsWrapper

# OpenTelemetry imports
try:
    from src.observability import (
        get_tracer,
        is_initialized,
        ITERATION_NUMBER,
        ITERATION_TYPE,
        LLM_TOOL_CALLS_COUNT,
        LLM_HAS_FINAL_ANSWER,
        LLM_MESSAGE_COUNT,
        TOOL_NAME,
        TOOL_ARGUMENTS,
        TOOL_SUCCESS,
        TOOL_RESULT_SIZE
    )
    from src.observability.tracer import add_span_attributes, record_exception
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# Initialize guardrails (lazy-loaded)
_guardrails = None

def get_guardrails():
    """Lazy-load guardrails instance"""
    global _guardrails
    if _guardrails is None:
        _guardrails = NemoGuardrailsWrapper()
    return _guardrails

def reasoning_node(state, llm_client, tool_registry):
    """LLM decides next action (call tool or provide final answer)

    Args:
        state: Current AgentState
        llm_client: NVIDIAClient instance
        tool_registry: ToolRegistry instance

    Returns:
        Updated state
    """
    log_info(f"Reasoning iteration {state['iteration_count'] + 1}")

    # Create OpenTelemetry span for reasoning iteration
    if OTEL_AVAILABLE and is_initialized():
        tracer = get_tracer()
        with tracer.start_as_current_span("agent.iteration") as span:
            add_span_attributes(span, {
                ITERATION_NUMBER: state['iteration_count'] + 1,
                ITERATION_TYPE: "reasoning"
            })
            return _execute_reasoning(state, llm_client, tool_registry, span)
    else:
        return _execute_reasoning(state, llm_client, tool_registry, None)


def _execute_reasoning(state, llm_client, tool_registry, span=None):
    """Execute reasoning logic with optional tracing

    Args:
        state: Current AgentState
        llm_client: NVIDIAClient instance
        tool_registry: ToolRegistry instance
        span: Optional OpenTelemetry span

    Returns:
        Updated state
    """

    # Check input guardrails on first iteration
    if state["iteration_count"] == 0:
        guardrails = get_guardrails()
        passed, reason = guardrails.check_input(state["query"])

        if not passed:
            log_warning(f"Input blocked by guardrails: {reason}")
            return {
                "should_continue": False,
                "has_final_answer": True,
                "final_answer": f"I cannot process this request. {reason}",
                "iteration_count": state["iteration_count"] + 1
            }

    # Build messages
    messages = state.get("messages", [])

    # Add system prompt if this is the first message
    if not messages or messages[0]["role"] != "system":
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    # Add user query if not already present
    if not any(m.get("role") == "user" for m in messages):
        messages.append({"role": "user", "content": state["query"]})

    # Get tools
    tools = tool_registry.to_openai_tools()

    log_verbose(f"Preparing LLM call with {len(messages)} messages")
    log_verbose(f"Available tools: {[t['function']['name'] for t in tools]}")

    # Show message contents in very verbose mode
    for i, msg in enumerate(messages):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        has_tool_calls = 'tool_calls' in msg

        if has_tool_calls:
            tool_call_names = [tc['function']['name'] for tc in msg['tool_calls']]
            log_verbose(f"  Message {i+1} [{role}]: (tool calls: {tool_call_names})")
        else:
            content_preview = content[:80] + '...' if len(content) > 80 else content
            log_verbose(f"  Message {i+1} [{role}]: {content_preview}")

    try:
        # Call NVIDIA NIM
        response = llm_client.chat_completion(
            messages=messages,
            tools=tools if tools else None,
            temperature=0.2,
            max_tokens=1024
        )

        assistant_message = response.choices[0].message

        log_verbose(f"LLM response - has tool_calls: {bool(assistant_message.tool_calls)}")

        # Show full LLM response in very verbose mode
        log_verbose("=" * 60)
        log_verbose("VERBATIM LLM RESPONSE:")
        log_verbose("-" * 60)

        if assistant_message.content:
            log_verbose(f"Content: {assistant_message.content}")
        else:
            log_verbose("Content: (empty)")

        if assistant_message.tool_calls:
            log_verbose(f"\nTool Calls ({len(assistant_message.tool_calls)}):")
            for idx, tc in enumerate(assistant_message.tool_calls, 1):
                log_verbose(f"  [{idx}] ID: {tc.id}")
                log_verbose(f"      Type: {tc.type}")
                log_verbose(f"      Function Name: {tc.function.name}")
                log_verbose(f"      Function Arguments: {tc.function.arguments}")

        log_verbose("=" * 60)

        # Convert to dict format
        # NVIDIA API requires content to be non-empty, use placeholder if None
        message_dict = {
            "role": "assistant",
            "content": assistant_message.content if assistant_message.content else "Calling tools..."
        }

        # Check if there are tool calls
        if assistant_message.tool_calls:
            log_info(f"LLM requested {len(assistant_message.tool_calls)} tool call(s)")

            # Add tool calls to message
            message_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]

            state["should_continue"] = True
            state["has_final_answer"] = False

            # Add span attributes if available
            if span is not None:
                add_span_attributes(span, {
                    LLM_TOOL_CALLS_COUNT: len(assistant_message.tool_calls),
                    LLM_HAS_FINAL_ANSWER: False,
                    LLM_MESSAGE_COUNT: len(messages)
                })

        else:
            # No tool calls, this is the final answer
            log_info("LLM provided final answer")

            # Add span attributes if available
            if span is not None:
                add_span_attributes(span, {
                    LLM_TOOL_CALLS_COUNT: 0,
                    LLM_HAS_FINAL_ANSWER: True,
                    LLM_MESSAGE_COUNT: len(messages)
                })

            # Check output guardrails
            guardrails = get_guardrails()
            passed, reason = guardrails.check_output(message_dict["content"])

            if not passed:
                log_warning(f"Output blocked by guardrails: {reason}")
                # Return a safe message instead
                message_dict["content"] = "I cannot provide this response as it violates our safety policies."
                state["final_answer"] = message_dict["content"]
            else:
                state["final_answer"] = message_dict["content"]

            # Show final answer clearly in verbose mode
            if message_dict["content"]:
                log_verbose("=" * 60)
                log_verbose("FINAL ANSWER:")
                log_verbose("-" * 60)
                log_verbose(message_dict["content"])
                log_verbose("=" * 60)

            state["should_continue"] = False
            state["has_final_answer"] = True

        # Update state - return only NEW messages for LangGraph to merge
        state["iteration_count"] += 1
        return {
            "messages": [message_dict],
            "iteration_count": state["iteration_count"],
            "should_continue": state["should_continue"],
            "has_final_answer": state["has_final_answer"],
            "final_answer": state.get("final_answer", "")
        }

    except Exception as e:
        log_warning(f"Reasoning node failed: {e}")
        return {
            "should_continue": False,
            "has_final_answer": True,
            "final_answer": f"Error: Unable to process request. {str(e)}"
        }


def tool_execution_node(state, tool_registry):
    """Execute tool calls from the last message

    Args:
        state: Current AgentState
        tool_registry: ToolRegistry instance

    Returns:
        Updated state
    """
    log_info("Executing tools")

    messages = state["messages"]
    last_message = messages[-1]

    # Check if there are tool calls
    if "tool_calls" not in last_message or not last_message["tool_calls"]:
        log_debug("No tool calls to execute")
        return state

    tool_calls = last_message["tool_calls"]
    observations = []
    new_messages = []

    # Increment actual tool call count
    new_tool_call_count = state.get("tool_call_count", 0) + len(tool_calls)

    # Create OpenTelemetry span for tool execution
    if OTEL_AVAILABLE and is_initialized():
        tracer = get_tracer()
        with tracer.start_as_current_span("agent.tool_execution") as parent_span:
            _execute_tools(tool_calls, tool_registry, observations, new_messages, tracer)
    else:
        _execute_tools(tool_calls, tool_registry, observations, new_messages, None)

    # Return only new messages and updates for LangGraph to merge
    new_observations = "\n".join(observations) + "\n"
    return {
        "messages": new_messages,
        "observations": state.get("observations", "") + new_observations,
        "tool_call_count": new_tool_call_count
    }


def _execute_tools(tool_calls, tool_registry, observations, new_messages, tracer=None):
    """Execute tools with optional tracing

    Args:
        tool_calls: List of tool calls to execute
        tool_registry: ToolRegistry instance
        observations: List to append observations to
        new_messages: List to append new messages to
        tracer: Optional OpenTelemetry tracer

    Returns:
        None (modifies observations and new_messages in place)
    """
    for tool_call in tool_calls:
        tool_name = tool_call["function"]["name"]
        tool_args_str = tool_call["function"]["arguments"]

        log_info(f"Executing tool: {tool_name}")

        # Create span for individual tool execution if tracer available
        if tracer is not None:
            with tracer.start_as_current_span(f"tool.{tool_name}") as tool_span:
                _execute_single_tool(
                    tool_call, tool_name, tool_args_str,
                    tool_registry, observations, new_messages, tool_span
                )
        else:
            _execute_single_tool(
                tool_call, tool_name, tool_args_str,
                tool_registry, observations, new_messages, None
            )


def _execute_single_tool(tool_call, tool_name, tool_args_str, tool_registry,
                         observations, new_messages, span=None):
    """Execute a single tool with optional tracing

    Args:
        tool_call: Tool call information
        tool_name: Name of the tool
        tool_args_str: JSON string of tool arguments
        tool_registry: ToolRegistry instance
        observations: List to append observations to
        new_messages: List to append new messages to
        span: Optional OpenTelemetry span
    """
    try:
        # Parse arguments
        tool_args = json.loads(tool_args_str) if tool_args_str else {}
        log_verbose(f"Tool arguments: {tool_args}")

        # Add span attributes if available
        if span is not None:
            add_span_attributes(span, {
                TOOL_NAME: tool_name,
                TOOL_ARGUMENTS: json.dumps(tool_args)
            })

        # Execute tool
        result = tool_registry.execute_tool(tool_name, **tool_args)
        log_verbose(f"Tool result success: {result['success']}")

        # Add result attributes to span
        if span is not None:
            add_span_attributes(span, {
                TOOL_SUCCESS: result["success"],
                TOOL_RESULT_SIZE: len(json.dumps(result))
            })

        # Format observation
        if result["success"]:
            observation = f"Tool '{tool_name}' returned: {json.dumps(result['data'], indent=2)}"
            log_info(f"✓ {tool_name} succeeded")
        else:
            observation = f"Tool '{tool_name}' failed: {result['error']}"
            log_warning(f"✗ {tool_name} failed: {result['error']}")

        observations.append(observation)

        # Add tool result message to new messages list
        new_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": json.dumps(result)
        })

    except Exception as e:
        log_warning(f"Tool execution failed: {e}")

        # Record exception in span
        if span is not None:
            record_exception(span, e)
            add_span_attributes(span, {
                TOOL_SUCCESS: False
            })

        observation = f"Tool '{tool_name}' error: {str(e)}"
        observations.append(observation)

        new_messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": json.dumps({"success": False, "error": str(e)})
        })
