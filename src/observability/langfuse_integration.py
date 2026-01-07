"""Langfuse LLM Observability Integration

This module provides Langfuse observability for the GenAIOps agent, compatible with Langfuse SDK v3.x.
Tracks LLM generations, tool executions, costs, and quality scores.
"""
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from config.settings import settings

# Global state
_langfuse_client = None
_langfuse_enabled = False

def initialize_langfuse(
    public_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    host: Optional[str] = None,
    enabled: bool = True
) -> bool:
    """Initialize Langfuse client

    Args:
        public_key: Langfuse public key (or from settings)
        secret_key: Langfuse secret key (or from settings)
        host: Langfuse host URL (or from settings)
        enabled: Whether to enable Langfuse

    Returns:
        True if initialized successfully, False otherwise
    """
    global _langfuse_client, _langfuse_enabled

    if not enabled:
        _langfuse_enabled = False
        return False

    try:
        from langfuse import Langfuse

        # Use provided keys or fallback to settings
        pub_key = public_key or settings.langfuse_public_key
        sec_key = secret_key or settings.langfuse_secret_key
        langfuse_host = host or settings.langfuse_host

        # Initialize client
        _langfuse_client = Langfuse(
            public_key=pub_key,
            secret_key=sec_key,
            host=langfuse_host
        )

        _langfuse_enabled = True

        print(f"[INFO] ✓ Langfuse initialized (host: {langfuse_host})")
        print(f"[INFO]   Dashboard: {langfuse_host}")

        return True

    except ImportError:
        print("[WARNING] Langfuse not installed. Install with: pip install langfuse")
        _langfuse_enabled = False
        return False
    except Exception as e:
        print(f"[WARNING] Langfuse initialization failed: {e}")
        _langfuse_enabled = False
        return False


def shutdown_langfuse():
    """Shutdown and flush Langfuse client"""
    global _langfuse_client, _langfuse_enabled

    if _langfuse_client and _langfuse_enabled:
        try:
            _langfuse_client.flush()
            print("[INFO] ✓ Langfuse flushed successfully")
        except Exception as e:
            print(f"[WARNING] Langfuse flush failed: {e}")

    _langfuse_client = None
    _langfuse_enabled = False


def is_langfuse_enabled() -> bool:
    """Check if Langfuse is enabled"""
    return _langfuse_enabled and _langfuse_client is not None


def get_langfuse_client():
    """Get Langfuse client instance"""
    return _langfuse_client if _langfuse_enabled else None


@contextmanager
def trace_agent_run(query: str, metadata: Optional[Dict[str, Any]] = None):
    """Create Langfuse trace for agent run using v3.x context manager API

    Args:
        query: User query
        metadata: Additional metadata

    Yields:
        Trace ID (or None if Langfuse disabled)
    """
    if not _langfuse_enabled or not _langfuse_client:
        yield None
        return

    try:
        # Use start_as_current_observation to create a trace
        # In v3.x, this starts a trace that becomes the current context
        with _langfuse_client.start_as_current_observation(
            name="agent_run",
            input={"query": query},
            metadata=metadata or {}
        ):
            trace_id = _langfuse_client.get_current_trace_id()
            yield trace_id
    except Exception as e:
        # Graceful degradation
        print(f"[WARNING] Langfuse trace creation failed: {e}")
        yield None


def set_trace_output(output: Any):
    """Set the output for the current trace

    Args:
        output: Output data
    """
    if not _langfuse_enabled or not _langfuse_client:
        return

    try:
        _langfuse_client.update_current_trace(output=output)
    except Exception as e:
        print(f"[WARNING] Failed to set trace output: {e}")


def log_llm_generation(
    name: str,
    model: str,
    input_messages: List[Dict[str, str]],
    output: str,
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None
):
    """Log LLM generation to Langfuse using v3.x API

    Args:
        name: Generation name
        model: Model name
        input_messages: Input messages
        output: Output text
        metadata: Additional metadata
        usage: Token usage dict (prompt_tokens, completion_tokens, total_tokens)
    """
    if not _langfuse_enabled or not _langfuse_client:
        return

    try:
        # Use start_generation (not as current, to not affect trace hierarchy)
        # Note: In v3.x, usage is passed via metadata
        gen_metadata = metadata or {}
        if usage:
            gen_metadata["usage"] = usage

        _langfuse_client.start_generation(
            name=name,
            model=model,
            input=input_messages,
            output=output,
            metadata=gen_metadata
        )
    except Exception as e:
        print(f"[WARNING] Failed to log LLM generation: {e}")


def log_tool_execution(
    name: str,
    input_args: Dict[str, Any],
    output: Any,
    metadata: Optional[Dict[str, Any]] = None
):
    """Log tool execution to Langfuse using v3.x API

    Args:
        name: Tool name
        input_args: Tool input arguments
        output: Tool output
        metadata: Additional metadata
    """
    if not _langfuse_enabled or not _langfuse_client:
        return

    try:
        # Use start_span (not as current, to not affect trace hierarchy)
        _langfuse_client.start_span(
            name=name,
            input=input_args,
            output=output,
            metadata=metadata or {}
        )
    except Exception as e:
        print(f"[WARNING] Failed to log tool execution: {e}")


def score_generation(
    name: str,
    value: float,
    comment: Optional[str] = None
):
    """Add a score to the current trace using v3.x API

    Args:
        name: Score name (e.g., "cost", "quality", "efficiency")
        value: Score value
        comment: Optional comment
    """
    if not _langfuse_enabled or not _langfuse_client:
        return

    try:
        # Use score_current_trace to add score to the current trace context
        _langfuse_client.score_current_trace(
            name=name,
            value=value,
            comment=comment
        )
    except Exception as e:
        print(f"[WARNING] Failed to add score: {e}")
