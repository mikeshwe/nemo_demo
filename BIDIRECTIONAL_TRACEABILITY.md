# Bidirectional Lineage Traceability

## Overview

This document explains the **full bidirectional traceability** implementation that links OpenTelemetry traces with OpenLineage data lineage, enabling automated root cause analysis of data quality issues.

## Architecture

```
INGESTION JOB                        AGENT QUERY
┌──────────────────┐                ┌──────────────────┐
│ Document Ingestion│               │ Agent Run        │
│ run_id: abc-123   │               │ run_id: xyz-789  │
└────────┬──────────┘                └────────┬─────────┘
         │                                     │
         │ Produces                            │ Consumes
         ▼                                     ▼
┌──────────────────────────────────────────────────────┐
│ ChromaDB: internal_docs.chunks                        │
│ ┌────────────────────────────────────────────────┐  │
│ │ Document Metadata:                              │  │
│ │ - title: "NeMo Setup Guide"                     │  │
│ │ - source: "nemo_setup.md"                       │  │
│ │ - lineage.producer_run_id: "abc-123"  ◄─────────┼──┼─ KEY!
│ │ - lineage.producer_job: "document_ingestion"    │  │
│ └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
         │
         │ Metadata stored in
         ▼
┌──────────────────────────────────────────────────────┐
│ Marquez (OpenLineage Backend)                         │
│ ┌────────────────────────────────────────────────┐  │
│ │ Run: abc-123                                    │  │
│ │ Job: document_ingestion                         │  │
│ │ Output: chromadb/internal_docs.chunks           │  │
│ │ Facets:                                         │  │
│ │   - dataQualityMetrics:                         │  │
│ │     • max_freshness_days: 45.0 ◄─────────────────┼─ VIOLATION!
│ │     • row_count: 150                            │  │
│ └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. Ingestion: Store producer_run_id in ChromaDB

**File: `scripts/setup_vectorstore.py`**

```python
# Add lineage correlation to document metadata
for chunk_idx, chunk in enumerate(chunks):
    metadata = {
        "title": title,
        "source": file_path.name,
        "chunk_index": chunk_idx,
        "total_chunks": len(chunks),
        # Bidirectional traceability
        "lineage.producer_run_id": lineage_tracker.run_id,  # Links to ingestion job!
        "lineage.producer_job": lineage_tracker.job_name
    }
    all_metadatas.append(metadata)
```

**Why**: This embeds the ingestion job's run_id into every document chunk, creating a permanent link from data → producer.

### 2. RAG Query: Retrieve producer_run_id

**File: `src/rag/vectorstore.py`**

```python
def similarity_search(self, query_text, embedding_function, k=3):
    # ... query ChromaDB ...

    producer_run_ids = set()
    for i in range(len(results["documents"][0])):
        metadata = results["metadatas"][0][i]
        doc = {
            "content": results["documents"][0][i],
            "metadata": metadata,
            "score": 1.0 - results["distances"][0][i]
        }
        documents.append(doc)

        # Collect producer_run_id for lineage correlation
        if "lineage.producer_run_id" in metadata:
            producer_run_ids.add(metadata["lineage.producer_run_id"])

    # Add to OTel span for correlation
    if producer_run_ids:
        span.set_attribute("lineage.input_run_ids", ",".join(list(producer_run_ids)))
```

**Why**: When the agent queries the vector store, we extract the `producer_run_id` and propagate it to the OpenTelemetry span.

### 3. Tool Execution: Propagate to Agent Span

**File: `src/tools/docs_search.py`**

```python
def execute(self, query, top_k=3):
    # ... query vector store ...

    producer_run_ids = set()
    for doc in results:
        if "lineage.producer_run_id" in doc["metadata"]:
            producer_run_ids.add(doc["metadata"]["lineage.producer_run_id"])

    # Add lineage correlation to current OTel span
    if OTEL_AVAILABLE and producer_run_ids:
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(
                "lineage.input_run_ids",
                ",".join(list(producer_run_ids))
            )
```

**Why**: The tool adds `lineage.input_run_ids` to its span, which bubbles up to the parent agent span.

### 4. Agent Execution: Emit OpenLineage Event

**File: `src/orchestrator/agent.py`**

```python
def _emit_agent_lineage_event(self, span, final_state):
    """Emit OpenLineage event for agent run with input datasets"""

    # Extract input run IDs from span attributes
    input_run_ids_str = span.attributes.get("lineage.input_run_ids", "")
    input_run_ids = input_run_ids_str.split(",")

    # Build input datasets with producerRunId facet
    inputs = []
    for producer_run_id in input_run_ids:
        inputs.append({
            "namespace": "chromadb",
            "name": "internal_docs.chunks",
            "facets": {
                "producerRunId": {
                    "producerRunId": producer_run_id.strip()
                }
            }
        })

    # Emit COMPLETE event
    emit_job_event(
        job_name="agent_query",
        run_id=get_current_run_id(),
        event_type="COMPLETE",
        inputs=inputs,  # Links agent to ingestion jobs!
        metadata={
            "iterations": final_state.get("iteration_count", 0),
            "tool_calls": final_state.get("tool_call_count", 0)
        }
    )
```

**Why**: This creates an OpenLineage event that explicitly links the agent run to the ingestion jobs that produced its input data.

## Bidirectional Query Patterns

### Forward: Data Lineage (Ingestion → Agent)

```bash
# 1. Start with ingestion job
GET /api/v1/namespaces/document_ingestion/jobs/daily_ingest/runs/abc-123

# 2. Find output datasets
{
  "outputs": [
    {
      "namespace": "chromadb",
      "name": "internal_docs.chunks",
      "facets": {
        "dataQualityMetrics": {
          "max_freshness_days": 45.0  # VIOLATION!
        }
      }
    }
  ]
}

# 3. Query dataset consumers
GET /api/v1/lineage?nodeId=dataset:chromadb/internal_docs.chunks

# 4. Find agent runs that consumed this data
{
  "graph": {
    "nodes": [
      {"id": "run:abc-123", "type": "JOB", "data": {"job": "daily_ingest"}},
      {"id": "dataset:chromadb/internal_docs.chunks", "type": "DATASET"},
      {"id": "run:xyz-789", "type": "JOB", "data": {"job": "agent_query"}}  # ← Consumer!
    ]
  }
}
```

### Backward: Root Cause Analysis (Agent → Ingestion)

```bash
# 1. Start with agent error/OTel span
OTel Span Attributes:
{
  "span.name": "agent.run",
  "lineage.run_id": "xyz-789",
  "lineage.input_run_ids": "abc-123,def-456"  # ← From RAG query!
}

# 2. Query input datasets
GET /api/v1/lineage?nodeId=run:abc-123

# 3. Find ingestion job details
{
  "job": "daily_ingest",
  "outputs": [
    {
      "namespace": "chromadb",
      "name": "internal_docs.chunks",
      "facets": {
        "dataQualityMetrics": {
          "max_freshness_days": 45.0,  # ← ROOT CAUSE!
          "files": [
            {"path": "/docs/nemo_setup.md", "freshness_days": 45.0}
          ]
        }
      }
    }
  ]
}

# 4. Root cause identified: Stale source file!
```

## Example: End-to-End Trace

```
USER QUERY: "Is NeMo Retriever approved for production?"

1. AGENT EXECUTION (run_id: xyz-789)
   ├─ OTel Span: agent.run
   │  ├─ Attributes:
   │  │  ├─ lineage.run_id: xyz-789
   │  │  └─ agent.query: "Is NeMo Retriever approved..."
   │  │
   │  └─ Tool: internal_docs_search
   │     ├─ OTel Span: tool.internal_docs_search
   │     │  ├─ RAG Query: "NeMo Retriever approval"
   │     │  └─ Vector Store Search
   │     │
   │     └─ Results (3 documents):
   │        ├─ Doc 1: metadata["lineage.producer_run_id"] = "abc-123"
   │        ├─ Doc 2: metadata["lineage.producer_run_id"] = "abc-123"
   │        └─ Doc 3: metadata["lineage.producer_run_id"] = "def-456"
   │
   └─ OTel Span Attribute Added:
      lineage.input_run_ids: "abc-123,def-456"

2. OPENLINEAGE EVENT EMITTED
   {
     "eventType": "COMPLETE",
     "job": {"name": "agent_query"},
     "run": {"runId": "xyz-789"},
     "inputs": [
       {
         "namespace": "chromadb",
         "name": "internal_docs.chunks",
         "facets": {
           "producerRunId": {"producerRunId": "abc-123"}
         }
       }
     ]
   }

3. QUERY MARQUEZ FOR ROOT CAUSE
   GET /api/v1/lineage?nodeId=run:abc-123
   ↓
   Returns: Ingestion job "daily_ingest" produced chromadb/internal_docs.chunks
   ↓
   GET /api/v1/namespaces/chromadb/datasets/internal_docs.chunks
   ↓
   Returns: dataQualityMetrics.max_freshness_days = 45.0 days ← VIOLATION!

4. ROOT CAUSE IDENTIFIED
   ✓ Agent run xyz-789 used data from ingestion run abc-123
   ✓ Ingestion run abc-123 had max_freshness_days = 45.0
   ✓ Policy threshold = 30 days
   ✓ Violation: 45.0 > 30 → STALE DATA!
   ✓ Source file: /docs/nemo_setup.md (45 days old)
```

## Benefits

### 1. Automated Root Cause Analysis

When an agent gives a wrong answer:
1. Check OTel span for `lineage.input_run_ids`
2. Query Marquez for those run IDs
3. Inspect data quality facets
4. Identify exact source files/datasets causing the error

### 2. Impact Analysis

When a data quality issue is detected:
1. Find the ingestion run_id
2. Query Marquez for consumers
3. Identify all agent runs affected by the bad data
4. Proactively notify or rollback

### 3. Compliance & Auditing

Full traceability from:
- User query → Agent run → Data consumed → Ingestion job → Source files
- Enables "data provenance" auditing for regulated environments

### 4. Observability Integration

- **OTel**: Distributed tracing with lineage correlation
- **OpenLineage**: Data lineage with quality facets
- **Marquez**: Centralized lineage backend with UI
- **Trust Plane**: Proactive authorization using lineage metadata

## Configuration

Enable full bidirectional traceability:

```bash
# .env
OPENLINEAGE_ENABLED=true
OPENLINEAGE_URL=http://localhost:5001
TRUST_PLANE_ENABLED=true
```

## API Examples

### Query Agent's Input Datasets

```bash
# Get agent run details
curl -s http://localhost:5001/api/v1/namespaces/agent/jobs/agent_query/runs/xyz-789 \
  | jq '.inputs'

# Returns:
[
  {
    "namespace": "chromadb",
    "name": "internal_docs.chunks",
    "facets": {
      "producerRunId": {
        "producerRunId": "abc-123"
      }
    }
  }
]
```

### Query Dataset Producer

```bash
# Get dataset details
curl -s http://localhost:5001/api/v1/namespaces/chromadb/datasets/internal_docs.chunks \
  | jq '.facets.dataQualityMetrics'

# Returns:
{
  "_producer": "genaiops-agent/1.0",
  "rowCount": 150,
  "columnMetrics": {
    "freshness": {
      "max": 45.0,  # ← Violation!
      "min": 1.0,
      "quantiles": {"0.5": 15.0}
    }
  }
}
```

### Query Lineage Graph

```bash
# Get full lineage graph
curl -s "http://localhost:5001/api/v1/lineage?nodeId=run:abc-123&depth=2" \
  | jq '.graph'

# Returns:
{
  "nodes": [
    {"id": "dataset:filesystem/documents", "type": "DATASET"},
    {"id": "run:abc-123", "type": "RUN"},
    {"id": "dataset:chromadb/internal_docs.chunks", "type": "DATASET"},
    {"id": "run:xyz-789", "type": "RUN"}
  ],
  "edges": [
    {"source": "dataset:filesystem/documents", "destination": "run:abc-123"},
    {"source": "run:abc-123", "destination": "dataset:chromadb/internal_docs.chunks"},
    {"source": "dataset:chromadb/internal_docs.chunks", "destination": "run:xyz-789"}
  ]
}
```

## Testing

### 1. Run Fresh Ingestion

```bash
# Ingest fresh documents with lineage tracking
python3 scripts/setup_vectorstore.py --use-lineage
```

This creates:
- ChromaDB documents with `lineage.producer_run_id`
- OpenLineage events in Marquez
- Cached metadata for Trust Plane

### 2. Query with Agent

```bash
# Run agent with OTEL and OpenLineage enabled
python3 main.py --query "How to deploy NeMo?" --verbose
```

Agent execution:
- Queries ChromaDB
- Extracts `producer_run_id` from results
- Adds to OTel span attributes
- Emits OpenLineage event with input datasets

### 3. Verify in Marquez UI

1. Open http://localhost:3001
2. Navigate to Jobs → agent_query
3. Click on latest run
4. View "Inputs" tab → See producer run IDs
5. Click on input dataset
6. View lineage graph showing full flow

## Future Enhancements

1. **Multi-hop Lineage**: Track transformations through multiple processing stages
2. **Version Tracking**: Link to specific document versions/commits
3. **Schema Evolution**: Track schema changes in lineage graph
4. **ML Model Lineage**: Extend to track model training data lineage
5. **Automated Remediation**: Auto-refresh data when quality violations detected

## Related Documentation

- [OTEL_OPENLINEAGE_CORRELATION.md](OTEL_OPENLINEAGE_CORRELATION.md) - Conceptual overview
- [DEMO_VERBOSITY_GUIDE.md](DEMO_VERBOSITY_GUIDE.md) - Demo verbosity levels
- [MARQUEZ_SETUP.md](MARQUEZ_SETUP.md) - Marquez backend setup
- [DATA_QUALITY_SUMMARY.md](DATA_QUALITY_SUMMARY.md) - Trust Plane integration
