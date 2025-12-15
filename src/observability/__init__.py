"""OpenTelemetry observability initialization for GenAIOps agent"""
from typing import Optional
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

from .config import ObservabilityConfig
from .tracer import initialize_tracer_and_meter, get_tracer, get_meter
from .attributes import *

# Global configuration and instrumentation state
_config: Optional[ObservabilityConfig] = None
_initialized: bool = False


def initialize_observability(
    service_name: str = "genaiops-agent",
    service_version: str = "1.0.0",
    environment: str = "development",
    enable_console: bool = True,
    file_path: str = None
) -> None:
    """Initialize OpenTelemetry observability

    Sets up tracing and metrics with console exporters and
    auto-instruments the OpenAI SDK for LLM call tracking.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        environment: Deployment environment (dev/staging/prod)
        enable_console: Enable console exporter for traces/metrics
        file_path: Optional path to export telemetry to JSON file
    """
    global _config, _initialized

    if _initialized:
        return  # Already initialized

    # Create configuration
    _config = ObservabilityConfig(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        enable_console_exporter=enable_console
    )

    # Create resource with service information
    resource = Resource.create(_config.get_resource_attributes())

    # Initialize tracing
    if _config.enable_tracing:
        _initialize_tracing(resource, enable_console, file_path)

    # Initialize metrics
    if _config.enable_metrics:
        _initialize_metrics(resource, enable_console)

    # Initialize tracer and meter instances
    initialize_tracer_and_meter(service_name)

    # Auto-instrument OpenAI SDK
    _instrument_openai()

    _initialized = True


def _initialize_tracing(resource: Resource, enable_console: bool, file_path: str = None) -> None:
    """Initialize OpenTelemetry tracing

    Args:
        resource: Resource with service information
        enable_console: Enable console span exporter
        file_path: Optional path to export telemetry to JSON file
    """
    from src.observability.file_exporter import JSONFileSpanExporter

    # Create tracer provider with resource
    tracer_provider = TracerProvider(resource=resource)

    # Add console exporter if enabled
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        span_processor = BatchSpanProcessor(console_exporter)
        tracer_provider.add_span_processor(span_processor)

    # Add file exporter if path provided
    if file_path:
        file_exporter = JSONFileSpanExporter(file_path)
        file_processor = BatchSpanProcessor(file_exporter)
        tracer_provider.add_span_processor(file_processor)

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)


def _initialize_metrics(resource: Resource, enable_console: bool) -> None:
    """Initialize OpenTelemetry metrics

    Args:
        resource: Resource with service information
        enable_console: Enable console metric exporter
    """
    readers = []

    # Add console reader if enabled
    if enable_console:
        console_exporter = ConsoleMetricExporter()
        console_reader = PeriodicExportingMetricReader(
            console_exporter,
            export_interval_millis=60000  # Export every 60 seconds
        )
        readers.append(console_reader)

    # Create meter provider with resource and readers
    meter_provider = MeterProvider(resource=resource, metric_readers=readers)

    # Set global meter provider
    metrics.set_meter_provider(meter_provider)


def _instrument_openai() -> None:
    """Auto-instrument OpenAI SDK for LLM call tracking

    This automatically creates spans for all OpenAI API calls,
    including calls to NVIDIA's OpenAI-compatible API.
    """
    try:
        OpenAIInstrumentor().instrument()
    except Exception as e:
        # Don't fail initialization if instrumentation fails
        print(f"[WARN] Failed to instrument OpenAI SDK: {e}")


def shutdown_observability() -> None:
    """Shutdown OpenTelemetry and flush remaining telemetry

    Should be called before application exit to ensure all
    spans and metrics are exported.
    """
    global _initialized

    if not _initialized:
        return

    # Shutdown tracer provider
    tracer_provider = trace.get_tracer_provider()
    if hasattr(tracer_provider, 'shutdown'):
        tracer_provider.shutdown()

    # Shutdown meter provider
    meter_provider = metrics.get_meter_provider()
    if hasattr(meter_provider, 'shutdown'):
        meter_provider.shutdown()

    _initialized = False


def is_initialized() -> bool:
    """Check if observability has been initialized

    Returns:
        True if initialized, False otherwise
    """
    return _initialized


# Export key functions and attributes
__all__ = [
    "initialize_observability",
    "shutdown_observability",
    "is_initialized",
    "get_tracer",
    "get_meter",
    "ObservabilityConfig",
    # Attribute constants
    "AGENT_QUERY",
    "AGENT_MAX_ITERATIONS",
    "AGENT_FINAL_ITERATIONS",
    "AGENT_TOOL_CALLS",
    "AGENT_SUCCESS",
    "ITERATION_NUMBER",
    "ITERATION_TYPE",
    "LLM_TOOL_CALLS_COUNT",
    "LLM_HAS_FINAL_ANSWER",
    "LLM_MESSAGE_COUNT",
    "TOOL_NAME",
    "TOOL_ARGUMENTS",
    "TOOL_SUCCESS",
    "TOOL_RESULT_SIZE",
    "GUARDRAILS_TYPE",
    "GUARDRAILS_CHECK_TYPE",
    "GUARDRAILS_PASSED",
    "GUARDRAILS_REJECTION_REASON",
    "GUARDRAILS_INPUT_LENGTH",
    "GUARDRAILS_OUTPUT_LENGTH",
    "RAG_QUERY",
    "RAG_QUERY_LENGTH",
    "RAG_TOP_K",
    "RAG_RESULTS_COUNT",
    "RAG_TOP_SCORE",
    "EMBEDDING_MODEL",
    "EMBEDDING_TEXT_LENGTH",
    "EMBEDDING_DIMENSION",
    # Event names
    "EVENT_AGENT_START",
    "EVENT_AGENT_COMPLETE",
    "EVENT_AGENT_ERROR",
    "EVENT_INPUT_BLOCKED",
    "EVENT_OUTPUT_BLOCKED",
]
