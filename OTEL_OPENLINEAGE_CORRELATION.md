# OpenTelemetry ↔ OpenLineage Correlation Guide

## Overview

This document explains how OpenTelemetry (OTel) spans are correlated with OpenLineage (OL) data lineage to enable end-to-end tracing from LLM agent errors back to specific source files.

## Architecture

### The Problem
When an LLM agent gives a wrong answer due to stale data, we need to:
1. **Detect** the error (LLM Judge validates the answer)
2. **Trace** it back to the dataset that caused it
3. **Identify** the specific source files and their quality metrics
4. **Understand** why the data failed policy checks

### The Solution
Use **dual observability** with correlation attributes:
- **OpenTelemetry**: Tracks agent execution (spans, traces)
- **OpenLineage**: Tracks data lineage (datasets, facets, metrics)
- **Correlation**: OTel spans include `lineage.run_id` to link to OL events

## 4-Step Correlation Flow

### Step 1: OpenTelemetry Span Attributes

When an agent runs, it creates an OTel span with lineage correlation:

```python
# In src/orchestrator/agent.py
def run(self, query):
    # Set lineage context
    if is_lineage_enabled():
        run_id = str(uuid.uuid4())
        set_lineage_context(run_id, "agent_query")

    # Create OTel span
    with tracer.start_as_current_span("agent.run") as span:
        # Add lineage correlation attributes
        if is_lineage_enabled():
            run_id = get_current_run_id()
            span.set_attribute("lineage.run_id", run_id)
            span.set_attribute("lineage.job_name", "agent_query")
            span.set_attribute("lineage.namespace", "demo-data-quality")
```

**Resulting OTel Span:**
```json
{
  "span_id": "abc123",
  "trace_id": "xyz789",
  "name": "agent.run",
  "attributes": {
    "agent.query": "Is NeMo Retriever approved for production use?",
    "lineage.run_id": "90115eb7-a4df-4e3e-ad54-809b030547e4",
    "lineage.job_name": "demo_stale_ingestion",
    "lineage.namespace": "demo-data-quality"
  }
}
```

### Step 2: Query OpenLineage via Run ID

Use the `lineage.run_id` attribute to query the Marquez API:

```bash
GET http://localhost:5000/api/v1/lineage?nodeId=run:90115eb7-a4df-4e3e-ad54-809b030547e4
```

**Response:**
```json
{
  "graph": {
    "nodes": [
      {
        "id": "run:90115eb7-a4df-4e3e-ad54-809b030547e4",
        "type": "RUN",
        "data": {
          "job": {
            "name": "demo_stale_ingestion",
            "namespace": "demo-data-quality"
          }
        }
      },
      {
        "id": "dataset:chromadb:stale_docs.chunks",
        "type": "DATASET",
        "data": {
          "name": "stale_docs.chunks",
          "namespace": "chromadb"
        }
      }
    ],
    "edges": [
      {
        "origin": "run:90115eb7...",
        "destination": "dataset:chromadb:stale_docs.chunks",
        "type": "OUTPUT"
      }
    ]
  }
}
```

This shows:
- The job `demo_stale_ingestion` produced the dataset
- Output dataset: `chromadb/stale_docs.chunks`

### Step 3: Query Dataset Facets

Fetch the dataset's data quality metrics:

```bash
GET http://localhost:5000/api/v1/namespaces/chromadb/datasets/stale_docs.chunks
```

**Response:**
```json
{
  "name": "stale_docs.chunks",
  "namespace": "chromadb",
  "facets": {
    "dataQualityMetrics": {
      "_producer": "genaiops-agent/1.0",
      "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
      "rowCount": 1,
      "columnMetrics": {
        "freshness": {
          "min": 45.0,
          "max": 45.0,
          "quantiles": {
            "0.5": 45.0
          }
        }
      }
    }
  }
}
```

**Key Finding:** `freshness.max = 45.0` days

### Step 4: Root Cause Analysis

Compare the metric against the policy:

```yaml
# From src/trust_plane/policies.yaml
policies:
  - name: chromadb_freshness_policy
    namespace: chromadb
    dataset_pattern: "*.chunks"
    rules:
      - metric: max_freshness_days
        operator: lte
        threshold: 30
        action: DENY
```

**Analysis:**
```
max_freshness_days = 45.0 days  (from OpenLineage facet)
Policy threshold = 30 days      (from Trust Plane policy)
Violation: 45.0 > 30 ✗         (DENY access)
```

**Trace to Source:**
From the cached metadata (populated during ingestion):
```json
{
  "metrics": {
    "max_freshness_days": 45.0,
    "files": [
      {
        "path": "/path/to/nemo_retriever_deployment.md",
        "freshness_days": 45.0,
        "size_bytes": 398
      }
    ]
  }
}
```

**Root Cause:** The file `nemo_retriever_deployment.md` is 45 days old, exceeding the 30-day policy threshold.

## Complete Trace Path

```
┌─────────────────────────────────────────────────────────────┐
│ 1. LLM Agent Error Detected                                 │
│    "Wrong answer: Python 3.8 instead of 3.10+"             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. OpenTelemetry Span                                       │
│    span.name: agent.run                                     │
│    lineage.run_id: 90115eb7-a4df-4e3e-ad54-809b030547e4   │
│    lineage.job_name: demo_stale_ingestion                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. OpenLineage Run Event                                    │
│    GET /api/v1/lineage?nodeId=run:<run_id>                 │
│    Returns: Job → Output Dataset                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. OpenLineage Dataset                                       │
│    chromadb/stale_docs.chunks                               │
│    GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks│
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Data Quality Facet                                       │
│    dataQualityMetrics.columnMetrics.freshness.max = 45.0   │
│    ← VIOLATION (exceeds 30-day threshold)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Source File                                              │
│    nemo_retriever_deployment.md                             │
│    Age: 45 days ← ROOT CAUSE                                │
│    Contains: Outdated Python 3.8, CUDA 11.0 info           │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### Setting Lineage Context

```python
# src/observability/lineage/context.py
import contextvars

_current_run_id: contextvars.ContextVar[Optional[str]] = \
    contextvars.ContextVar('lineage_run_id', default=None)

def set_lineage_context(run_id: str, job_name: str):
    """Set lineage context for current execution"""
    _current_run_id.set(run_id)
    _current_job_name.set(job_name)

def get_current_run_id() -> Optional[str]:
    """Get current lineage run ID"""
    return _current_run_id.get()
```

### Adding OTel Span Attributes

```python
# src/orchestrator/agent.py
from src.observability.lineage import get_current_run_id, is_lineage_enabled

def _execute_agent(self, initial_state, query):
    with tracer.start_as_current_span("agent.run") as span:
        # Add lineage correlation
        if is_lineage_enabled():
            run_id = get_current_run_id()
            if run_id:
                span.set_attribute("lineage.run_id", run_id)
                span.set_attribute("lineage.job_name", "agent_query")
```

### Emitting OpenLineage Events

```python
# src/ingestion/lineage_tracker.py
from src.observability.lineage import emit_job_event

def complete(self, collection_name: str, num_chunks: int):
    """Emit COMPLETE event with data quality facets"""
    quality_facet = build_data_quality_facet(self.metrics)

    outputs = [{
        "namespace": "chromadb",
        "name": f"{collection_name}.chunks",
        "facets": {
            "dataQualityMetrics": quality_facet
        }
    }]

    emit_job_event(
        job_name=self.job_name,
        run_id=self.run_id,
        event_type="COMPLETE",
        outputs=outputs
    )
```

### Querying Metadata

```python
# src/trust_plane/enforcer.py
from src.observability.lineage import get_lineage_client

def authorize_dataset_access(namespace: str, dataset_name: str):
    """Check data quality before allowing access"""
    client = get_lineage_client()

    # Get metadata from cache or Marquez API
    metadata = client.get_dataset_metadata(namespace, dataset_name)

    if metadata:
        metrics = metadata['metrics']
        # Evaluate against policies
        max_freshness = metrics['max_freshness_days']
        if max_freshness > 30:
            return DENY
```

## Benefits

### End-to-End Traceability
- From LLM error → OTel span → OL run → Dataset → Source file
- Complete audit trail for debugging

### Reactive Error Detection
- LLM Judge detects wrong answer
- Trace back through lineage to find stale data
- Identify specific files that need updating

### Proactive Prevention
- Trust Plane queries metadata before data access
- Blocks stale data before agent uses it
- Prevents errors from happening

### Cross-System Correlation
- OTel: Agent execution tracing
- OpenLineage: Data lineage tracking
- Single `run_id` links both systems

## Viewing in Demo

Run the demo with very verbose mode:

```bash
python3 demo_data_quality.py --mode reactive --vv
```

Look for the section:
```
[VV] OpenTelemetry → OpenLineage Correlation:

Step 1: OTel Span Attributes (if agent was instrumented):
  {
    'span.name': 'agent.run',
    'lineage.run_id': '<ingestion_run_id>',
    ...
  }

Step 2: Query OpenLineage via run_id:
  GET /api/v1/lineage?nodeId=run:<run_id>
  ...

Step 3: Query Dataset Facets:
  GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks
  Returns dataQualityMetrics facet:
  {
    'columnMetrics': {
      'freshness': {
        'max': 45.0,  ← VIOLATION!
      }
    }
  }

Step 4: Root Cause Analysis:
  max_freshness_days = 45.0 days
  Violation: 45.0 > 30 ✗
```

## References

- **OpenTelemetry Semantic Conventions**: https://opentelemetry.io/docs/specs/semconv/
- **OpenLineage Spec**: https://openlineage.io/spec/
- **Marquez API**: https://marquezproject.github.io/marquez/openapi.html
- **Data Quality Facets**: https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json
