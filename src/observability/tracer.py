"""OpenTelemetry tracer and meter management"""
from typing import Optional, Dict, Any
from opentelemetry import trace, metrics
from opentelemetry.trace import Tracer, Span
from opentelemetry.metrics import Meter

# Global tracer and meter instances
_tracer: Optional[Tracer] = None
_meter: Optional[Meter] = None


def initialize_tracer_and_meter(service_name: str = "genaiops-agent"):
    """Initialize global tracer and meter instances

    Args:
        service_name: Name of the service for instrumentation
    """
    global _tracer, _meter

    # Get tracer provider and create tracer
    tracer_provider = trace.get_tracer_provider()
    _tracer = tracer_provider.get_tracer(__name__, "1.0.0")

    # Get meter provider and create meter
    meter_provider = metrics.get_meter_provider()
    _meter = meter_provider.get_meter(__name__, "1.0.0")


def get_tracer() -> Tracer:
    """Get the global tracer instance

    Returns:
        OpenTelemetry Tracer instance

    Raises:
        RuntimeError: If tracer has not been initialized
    """
    if _tracer is None:
        raise RuntimeError(
            "Tracer not initialized. Call initialize_observability() first."
        )
    return _tracer


def get_meter() -> Meter:
    """Get the global meter instance

    Returns:
        OpenTelemetry Meter instance

    Raises:
        RuntimeError: If meter has not been initialized
    """
    if _meter is None:
        raise RuntimeError(
            "Meter not initialized. Call initialize_observability() first."
        )
    return _meter


def add_span_attributes(span: Span, attributes: Dict[str, Any]) -> None:
    """Add multiple attributes to a span

    Args:
        span: OpenTelemetry Span instance
        attributes: Dictionary of attributes to add
    """
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def record_exception(span: Span, exception: Exception) -> None:
    """Record an exception in a span

    Args:
        span: OpenTelemetry Span instance
        exception: Exception to record
    """
    span.record_exception(exception)
    span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
