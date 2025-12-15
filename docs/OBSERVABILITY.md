# OpenTelemetry AI Observability Guide

This document provides comprehensive guidance on the OpenTelemetry instrumentation in the GenAIOps Documentation Assistant Agent.

## Overview

This demo includes production-grade OpenTelemetry instrumentation for AI observability, demonstrating best practices for monitoring and debugging agentic AI systems. All major components are instrumented to provide deep visibility into agent behavior, performance, and decision-making.

## Architecture

### Instrumentation Layers

The observability stack consists of several layers:

1. **Auto-Instrumentation**: OpenAI SDK automatically captures all LLM API calls
2. **Agent Orchestration**: Custom spans for agent execution flow and iterations
3. **Tool Execution**: Detailed tracing of tool calls with arguments and results
4. **Guardrails**: Safety validation tracking (NeMo Guardrails + fallback)
5. **RAG System**: Embedding generation and vector search operations

### Trace Hierarchy

```
agent.run (root)                              # Complete agent execution
├── agent.iteration (iteration #1)            # First reasoning step
│   ├── guardrails.input_check                # Input safety validation
│   │   └── attributes: type=nemo, passed=true
│   ├── openai.chat                           # LLM API call (auto-instrumented)
│   │   └── attributes: model, temperature, tokens, prompts
│   ├── agent.tool_execution                  # Tool execution wrapper
│   │   └── tool.security_policy_checker      # Individual tool span
│   │       └── tool.execute.security_policy_checker  # Tool registry execution
│   │           └── attributes: name, args, success, result_size
│   └── guardrails.output_check               # Output safety validation (optional)
└── agent.iteration (iteration #2)            # Final answer iteration
    ├── openai.chat                           # Final LLM call
    └── guardrails.output_check               # Output validation
        └── attributes: type=nemo, passed=true
```

## Instrumented Components

### 1. Agent Execution (`src/orchestrator/agent.py`)

**Span**: `agent.run`

**Attributes**:
- `agent.query`: User's query (truncated to 200 chars)
- `agent.max_iterations`: Maximum allowed iterations
- `agent.final_iterations`: Actual iterations completed
- `agent.tool_calls`: Total number of tool calls
- `agent.success`: Whether execution succeeded

**Events**:
- `agent_start`: Agent execution begins
- `agent_complete`: Agent execution completes successfully
- `agent_error`: Agent execution failed

### 2. Reasoning Iterations (`src/orchestrator/nodes.py`)

**Span**: `agent.iteration`

**Attributes**:
- `iteration.number`: Current iteration number
- `iteration.type`: "reasoning" or "final"
- `llm.tool_calls_count`: Number of tool calls requested by LLM
- `llm.has_final_answer`: Whether LLM provided final answer
- `llm.message_count`: Number of messages in conversation

### 3. LLM API Calls (Auto-instrumented)

**Span**: `openai.chat`

**Attributes** (provided by auto-instrumentation):
- `gen_ai.system`: "openai"
- `gen_ai.request.model`: Model name (e.g., "meta/llama-3.1-70b-instruct")
- `gen_ai.request.temperature`: Temperature setting
- `gen_ai.request.max_tokens`: Max tokens limit
- `llm.usage.total_tokens`: Total tokens used
- `gen_ai.usage.input_tokens`: Input token count
- `gen_ai.usage.output_tokens`: Output token count
- `gen_ai.prompt.{N}.role`: Message role
- `gen_ai.prompt.{N}.content`: Message content
- `gen_ai.completion.0.role`: Completion role
- `gen_ai.completion.0.content`: Completion content
- `gen_ai.completion.0.tool_calls.*`: Tool call details

### 4. Tool Execution (`src/orchestrator/nodes.py`, `src/tools/registry.py`)

**Span**: `tool.{tool_name}` (orchestration)
**Span**: `tool.execute.{tool_name}` (registry)

**Attributes**:
- `tool.name`: Name of the tool
- `tool.arguments`: JSON-encoded tool arguments
- `tool.success`: Whether execution succeeded
- `tool.result_size`: Size of result in bytes

### 5. Guardrails Validation (`src/guardrails/nemo_guardrails.py`)

**Span**: `guardrails.input_check`
**Span**: `guardrails.output_check`

**Attributes**:
- `guardrails.check_type`: "input" or "output"
- `guardrails.type`: "nemo" or "fallback"
- `guardrails.input_length`: Length of input text
- `guardrails.output_length`: Length of output text
- `guardrails.passed`: Whether validation passed
- `guardrails.rejection_reason`: Reason for rejection (if blocked)

**Events**:
- `input_blocked`: Input was blocked by guardrails
- `output_blocked`: Output was blocked by guardrails

### 6. RAG Operations

#### Embedding Generation (`src/rag/embeddings.py`)

**Span**: `rag.embedding.query`

**Attributes**:
- `embedding.model`: Model name (e.g., "all-MiniLM-L6-v2")
- `embedding.text_length`: Length of input text
- `embedding.dimension`: Embedding vector dimension

#### Vector Search (`src/rag/vectorstore.py`)

**Span**: `rag.vector_search`
**Span**: `rag.chromadb_query` (nested)

**Attributes**:
- `rag.query`: Query text (truncated to 200 chars)
- `rag.query_length`: Length of query
- `rag.top_k`: Number of results requested
- `rag.results_count`: Number of results returned
- `rag.top_score`: Highest similarity score

## Configuration

### Console Export (Default)

The demo uses console export by default for easy visibility. Traces are printed to stdout in JSON format.

```python
from src.observability import initialize_observability, shutdown_observability

initialize_observability(
    service_name="genaiops-agent",
    service_version="1.0.0",
    environment="development",  # or "production", "staging"
    enable_console=True  # Enable console export
)

try:
    # Your agent code here
    pass
finally:
    shutdown_observability()  # Flush remaining spans
```

### File Export with Visualizations

Export telemetry to files with human-readable reports and ASCII visualizations:

```python
from src.observability import initialize_observability, shutdown_observability
from src.observability.file_exporter import save_telemetry_report

# Initialize with file export
initialize_observability(
    service_name="genaiops-agent",
    service_version="1.0.0",
    environment="development",
    enable_console=True,  # Optional: also show console output
    file_path="telemetry.json"  # Export spans to JSON
)

try:
    # Your agent code here
    pass
finally:
    shutdown_observability()

    # Generate human-readable report with visualizations
    save_telemetry_report("telemetry.json", "telemetry_report.txt")
```

**Command-line usage:**

```bash
# Save telemetry with visualizations
python simple_test.py --save-telemetry my_report.txt

# Quiet mode (no console output, only file)
python simple_test.py --quiet --save-telemetry my_report.txt

# Works with main.py too
python main.py --save-telemetry session_telemetry.txt
```

**Generated files:**
- `my_report.json` - Raw telemetry data (spans in JSON format)
- `my_report.txt` - Human-readable report with ASCII visualizations

**Report contents:**
1. **Summary Statistics**: Overall metrics (spans, iterations, tool calls, tokens)
2. **Execution Timeline**: ASCII visualization of span hierarchy with timing bars
3. **Token Usage Chart**: Bar chart showing token consumption per LLM call
4. **Tool Timing**: Performance breakdown for each tool execution

### OTLP Export (Production)

To export to Jaeger, Prometheus, or other OTLP-compatible backends:

1. **Update `src/observability/__init__.py`**:

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

def _initialize_tracing(resource: Resource, enable_console: bool) -> None:
    tracer_provider = TracerProvider(resource=resource)

    # Add OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4317",  # Jaeger endpoint
        insecure=True
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Optional: Also keep console exporter for local debugging
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    trace.set_tracer_provider(tracer_provider)
```

2. **Set environment variables** (optional):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=genaiops-agent
export OTEL_SERVICE_VERSION=1.0.0
export OTEL_ENVIRONMENT=production
```

### Running Jaeger Locally

```bash
# Start Jaeger all-in-one
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HTTP_PORT=9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14268:14268 \
  -p 14250:14250 \
  -p 9411:9411 \
  jaegertracing/all-in-one:latest

# Access Jaeger UI
open http://localhost:16686
```

## Metrics Collection

Custom metrics are defined in `src/observability/metrics.py` but not actively recorded in the current implementation. The focus is on tracing for this demo.

Available metric instruments:
- **Counters**: `agent.iterations`, `agent.tool_calls`, `guardrails.blocks`
- **Histograms**: `agent.iteration.duration`, `tool.execution.duration`, `llm.call.duration`, `rag.search.duration`
- **UpDownCounters**: `agent.active_iterations`

Auto-instrumentation provides token usage metrics:
- `gen_ai.client.token.usage`: Token counts by type (input/output)

## Example Traces

### Simple Query

```json
{
  "name": "agent.run",
  "attributes": {
    "agent.query": "Is NeMo Retriever approved for production?",
    "agent.max_iterations": 10,
    "agent.final_iterations": 2,
    "agent.tool_calls": 1,
    "agent.success": true
  },
  "events": [
    {"name": "agent_start", "timestamp": "..."},
    {"name": "agent_complete", "timestamp": "..."}
  ]
}
```

### Tool Execution

```json
{
  "name": "tool.security_policy_checker",
  "attributes": {
    "tool.name": "security_policy_checker",
    "tool.arguments": "{\"library_name\": \"NeMo Retriever\"}",
    "tool.success": true,
    "tool.result_size": 263
  }
}
```

### Guardrails Check

```json
{
  "name": "guardrails.input_check",
  "attributes": {
    "guardrails.check_type": "input",
    "guardrails.type": "nemo",
    "guardrails.input_length": 45,
    "guardrails.passed": true
  }
}
```

## Best Practices

### 1. Service Identification

Always provide clear service metadata:

```python
initialize_observability(
    service_name="genaiops-agent",
    service_version="1.0.0",  # Use semantic versioning
    environment="production",  # Or "staging", "development"
)
```

### 2. Span Attributes

Follow OpenTelemetry semantic conventions:
- Use dot notation (e.g., `agent.query`, `tool.name`)
- Truncate long strings (e.g., queries, prompts) to avoid overhead
- Include success/failure status on all operations

### 3. Error Handling

Always record exceptions in spans:

```python
try:
    result = tool.execute(**kwargs)
except Exception as e:
    record_exception(span, e)
    raise
```

### 4. Resource Cleanup

Always shutdown to flush remaining spans:

```python
try:
    # Your code
    pass
finally:
    shutdown_observability()  # Critical for ensuring all spans are exported
```

## Troubleshooting

### Traces Not Appearing

1. **Check initialization**: Ensure `initialize_observability()` is called before agent execution
2. **Check shutdown**: Ensure `shutdown_observability()` is called to flush remaining spans
3. **Check console output**: Traces are printed to stdout, verify they're not filtered

### Missing Spans

1. **Check imports**: Verify OpenTelemetry imports don't fail silently
2. **Check OTEL_AVAILABLE flag**: Components gracefully degrade if imports fail
3. **Check span nesting**: Child spans require parent context

### High Overhead

1. **Disable console export** in production (slow for high throughput)
2. **Use sampling** for high-volume production systems
3. **Reduce attribute verbosity** (truncate long strings)

## Production Deployment

For production deployments:

1. **Use OTLP export** instead of console
2. **Configure sampling** to reduce overhead
3. **Set up proper backends** (Jaeger, Datadog, etc.)
4. **Monitor resource usage** of observability overhead
5. **Implement alerting** on key metrics (errors, latency, token usage)
6. **Set up dashboards** for visualization

## Further Reading

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [OpenAI Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/openai/openai.html)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Semantic Conventions for AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
