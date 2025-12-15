"""Metrics collection for agent observability

This module defines custom metrics for tracking agent performance
and behavior. Metrics complement traces by providing aggregated
statistics over time.

Note: For console export demos, metrics are less visible than traces.
Metrics are most useful when exported to a metrics backend like Prometheus.
"""

from typing import Optional
from opentelemetry.metrics import Meter

# Global meter instance
_meter: Optional[Meter] = None

# Metric instruments
_iterations_counter = None
_tool_calls_counter = None
_guardrails_blocks_counter = None
_iteration_duration_histogram = None
_tool_duration_histogram = None
_llm_duration_histogram = None
_rag_duration_histogram = None
_active_iterations_counter = None


def initialize_metrics(meter: Meter) -> None:
    """Initialize custom metrics instruments

    Args:
        meter: OpenTelemetry meter instance
    """
    global _meter
    global _iterations_counter
    global _tool_calls_counter
    global _guardrails_blocks_counter
    global _iteration_duration_histogram
    global _tool_duration_histogram
    global _llm_duration_histogram
    global _rag_duration_histogram
    global _active_iterations_counter

    _meter = meter

    # Counters
    _iterations_counter = meter.create_counter(
        name="agent.iterations",
        description="Number of agent reasoning iterations",
        unit="iteration"
    )

    _tool_calls_counter = meter.create_counter(
        name="agent.tool_calls",
        description="Number of tool calls made by the agent",
        unit="call"
    )

    _guardrails_blocks_counter = meter.create_counter(
        name="guardrails.blocks",
        description="Number of requests blocked by guardrails",
        unit="block"
    )

    # Histograms for duration tracking
    _iteration_duration_histogram = meter.create_histogram(
        name="agent.iteration.duration",
        description="Duration of agent reasoning iterations",
        unit="ms"
    )

    _tool_duration_histogram = meter.create_histogram(
        name="tool.execution.duration",
        description="Duration of tool executions",
        unit="ms"
    )

    _llm_duration_histogram = meter.create_histogram(
        name="llm.call.duration",
        description="Duration of LLM API calls",
        unit="ms"
    )

    _rag_duration_histogram = meter.create_histogram(
        name="rag.search.duration",
        description="Duration of RAG search operations",
        unit="ms"
    )

    # UpDownCounter for active iterations
    _active_iterations_counter = meter.create_up_down_counter(
        name="agent.active_iterations",
        description="Number of currently active agent iterations",
        unit="iteration"
    )


def record_iteration(attributes: dict = None) -> None:
    """Record an agent iteration"""
    if _iterations_counter:
        _iterations_counter.add(1, attributes or {})


def record_tool_call(attributes: dict = None) -> None:
    """Record a tool call"""
    if _tool_calls_counter:
        _tool_calls_counter.add(1, attributes or {})


def record_guardrails_block(attributes: dict = None) -> None:
    """Record a guardrails block"""
    if _guardrails_blocks_counter:
        _guardrails_blocks_counter.add(1, attributes or {})


def record_iteration_duration(duration_ms: float, attributes: dict = None) -> None:
    """Record iteration duration"""
    if _iteration_duration_histogram:
        _iteration_duration_histogram.record(duration_ms, attributes or {})


def record_tool_duration(duration_ms: float, attributes: dict = None) -> None:
    """Record tool execution duration"""
    if _tool_duration_histogram:
        _tool_duration_histogram.record(duration_ms, attributes or {})


def record_llm_duration(duration_ms: float, attributes: dict = None) -> None:
    """Record LLM call duration"""
    if _llm_duration_histogram:
        _llm_duration_histogram.record(duration_ms, attributes or {})


def record_rag_duration(duration_ms: float, attributes: dict = None) -> None:
    """Record RAG search duration"""
    if _rag_duration_histogram:
        _rag_duration_histogram.record(duration_ms, attributes or {})


def increment_active_iterations(delta: int = 1, attributes: dict = None) -> None:
    """Increment active iterations counter"""
    if _active_iterations_counter:
        _active_iterations_counter.add(delta, attributes or {})


def decrement_active_iterations(delta: int = 1, attributes: dict = None) -> None:
    """Decrement active iterations counter"""
    if _active_iterations_counter:
        _active_iterations_counter.add(-delta, attributes or {})
