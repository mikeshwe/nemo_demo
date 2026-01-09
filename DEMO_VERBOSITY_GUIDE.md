# Data Quality Demo - Verbosity Guide

## Overview

The data quality governance demo now supports three verbosity levels to show different levels of detail about OpenLineage integration, Trust Plane decisions, and LLM Judge validation.

## Verbosity Levels

### Normal Mode (default)
Shows essential information only:
- Component initialization
- Data quality metrics summary
- Trust Plane decisions (ALLOW/DENY)
- LLM Judge verdicts
- Final results

```bash
python3 demo_data_quality.py --mode both
```

### Verbose Mode (`--verbose` or `-v`)
Adds detailed information about:
- **OpenLineage**: Run IDs, job names, events emitted
- **Trust Plane**: Query details, policy evaluation, metadata source
- **LLM Judge**: Ground truth summary, model details, lineage trace
- **Ingestion**: Lineage tracking details

```bash
python3 demo_data_quality.py --mode both --verbose
```

Example verbose output:
```
[VERBOSE] Lineage Run ID: 90115eb7-a4df-4e3e-ad54-809b030547e4
[VERBOSE] Job Name: demo_stale_ingestion

[VERBOSE] OpenLineage Events Emitted:
  • START event with input datasets
  • COMPLETE event with output dataset: chromadb/stale_docs.chunks
  • Data quality facets attached to output dataset

[VERBOSE] Trust Plane Query:
  • Namespace: chromadb
  • Dataset: stale_docs.chunks
  • Tool: internal_docs_search

[VERBOSE] Policy Evaluation:
  • Policies matched: 2
  • Decision: DENY (not allowed)

[VERBOSE] Ground Truth Entry:
  • Expected answer: Yes, NeMo Retriever is approved for production...
  • Key facts: 6 facts to check
  • Known errors: 3 common errors

[VERBOSE] LLM Judge Call:
  • Model: meta/llama-3.1-70b-instruct
  • Temperature: 0.1 (low for consistency)
  • Prompt type: Structured JSON verdict

[VERBOSE] Lineage Trace:
  • Dataset: chromadb/stale_docs.chunks
  • Max freshness: 45.0 days
  • Avg freshness: 45.0 days
  • Source files: 1 files
```

### Very Verbose Mode (`--vv`)
Shows complete JSON dumps and all metadata:
- **Full metrics**: Complete data quality metrics JSON
- **Metadata retrieval**: Cache source, timestamp, full metrics object
- **Ground truth**: Complete expected answer, all key facts, all common errors
- **Source files**: Individual file details (path, age, size)
- **OTel-OpenLineage correlation**: Step-by-step trace showing how OTel span attributes link to OpenLineage dataset facets and the violating metric

```bash
python3 demo_data_quality.py --mode both --vv
```

Example very verbose output:
```
[VV] Detailed Metrics:
{
  "avg_freshness_days": 45.0,
  "max_freshness_days": 45.0,
  "min_freshness_days": 45.0,
  "row_count": 1,
  "file_count": 1,
  "total_size_bytes": 398,
  "files": [
    {
      "path": "/var/folders/.../nemo_retriever_deployment.md",
      "freshness_days": 45.0,
      "size_bytes": 398
    }
  ]
}

[VV] Metadata Retrieval:
  • Source: Local cache
  • Cached at: 2026-01-08T19:45:31.673Z
  • Metrics: {
    "avg_freshness_days": 45.0,
    "max_freshness_days": 45.0,
    "row_count": 1,
    "file_count": 1,
    "files": [...]
}

[VV] Complete Ground Truth:
{
  "expected_answer": "Yes, NeMo Retriever is approved for production use. It requires Python 3.10+ and CUDA 12.0+...",
  "key_facts": [
    "NeMo Retriever is approved for production",
    "Requires Python 3.10+",
    "Requires CUDA 12.0+",
    "Recommended GPU: NVIDIA A100 or H100",
    "Minimum 40GB VRAM",
    "Supports ChromaDB, Milvus, and Pinecone"
  ],
  "common_errors": [
    {
      "type": "outdated_version",
      "description": "Stating Python 3.8 instead of 3.10+",
      "source": "Stale documentation from 2023"
    },
    ...
  ]
}

[VV] OpenTelemetry → OpenLineage Correlation:

Step 1: OTel Span Attributes (if agent was instrumented):
  {
    'span.name': 'agent.run',
    'agent.query': 'Is NeMo Retriever approved...',
    'lineage.run_id': '<ingestion_run_id>',
    'lineage.job_name': 'demo_stale_ingestion',
    'lineage.namespace': 'demo-data-quality'
  }

Step 2: Query OpenLineage via run_id:
  GET /api/v1/lineage?nodeId=run:<run_id>
  Returns:
    - Job: demo_stale_ingestion
    - Output datasets: chromadb/stale_docs.chunks

Step 3: Query Dataset Facets:
  GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks
  Returns dataQualityMetrics facet:
  {
    '_producer': 'genaiops-agent/1.0',
    'rowCount': 1,
    'columnMetrics': {
      'freshness': {
        'min': 45.0,
        'max': 45.0,  ← VIOLATION!
        'quantiles': {'0.5': 45.0}
      }
    }
  }

Step 4: Root Cause Analysis:
  max_freshness_days = 45.0 days
  Policy threshold = 30 days
  Violation: 45.0 > 30 ✗

[VV] Source File Details:
  • nemo_retriever_deployment.md:
    - Age: 45.0 days ← Root cause
    - Size: 398 bytes
    - Path: /var/folders/.../nemo_retriever_deployment.md
```

## Usage Examples

### Test Proactive Mode Only
```bash
# Normal
python3 demo_data_quality.py --mode proactive

# Verbose - see Trust Plane internals
python3 demo_data_quality.py --mode proactive --verbose

# Very Verbose - see full metadata JSON
python3 demo_data_quality.py --mode proactive --vv
```

### Test Reactive Mode Only
```bash
# Normal
python3 demo_data_quality.py --mode reactive

# Verbose - see LLM Judge details and lineage trace
python3 demo_data_quality.py --mode reactive --verbose

# Very Verbose - see full ground truth and source files
python3 demo_data_quality.py --mode reactive --vv
```

### Test Both Modes (Side-by-Side)
```bash
# Normal - see comparison table only
python3 demo_data_quality.py --mode both

# Verbose - full details for both modes
python3 demo_data_quality.py --mode both --verbose

# Very Verbose - complete JSON dumps for everything
python3 demo_data_quality.py --mode both --vv
```

## What Each Mode Shows

### Proactive Mode Verbosity

| Level | Information Shown |
|-------|------------------|
| Normal | Trust Plane decision, policy violations, final result |
| Verbose | + Query details, policy evaluation, metadata source |
| Very Verbose | + Full metadata JSON with all metrics |

### Reactive Mode Verbosity

| Level | Information Shown |
|-------|------------------|
| Normal | Agent answer, judge verdict, detected errors |
| Verbose | + Ground truth summary, LLM call details, lineage trace |
| Very Verbose | + Complete ground truth JSON, source file details |

### Ingestion Verbosity

| Level | Information Shown |
|-------|------------------|
| Normal | Metrics summary, lineage status |
| Verbose | + Run ID, job name, events emitted |
| Very Verbose | + Complete metrics JSON with file details |

## OpenLineage Integration Details

### In Verbose Mode
Shows how OpenLineage tracks data flow:
- Run IDs for correlation across systems
- Job names for identifying ingestion/query operations
- Events emitted (START, COMPLETE) with dataset references
- Output datasets with quality facets attached

### In Very Verbose Mode
Shows complete metadata structure:
- Full metrics JSON as stored in OpenLineage facets
- Metadata cache details (source, timestamp)
- Source file paths, ages, and sizes
- Correlation between OTel spans and lineage runs

## OpenTelemetry → OpenLineage Correlation (VV Mode)

The very verbose mode shows a **4-step trace** from OpenTelemetry spans to the root cause in OpenLineage dataset facets:

### Step 1: OTel Span Attributes
When an agent is instrumented with OpenTelemetry, spans include lineage correlation attributes:
```python
{
  'span.name': 'agent.run',
  'agent.query': 'Is NeMo Retriever approved for production use?',
  'lineage.run_id': '<ingestion_run_id>',      # Links to OpenLineage
  'lineage.job_name': 'demo_stale_ingestion',  # Job that created data
  'lineage.namespace': 'demo-data-quality'     # OpenLineage namespace
}
```

### Step 2: Query OpenLineage API
Using the `lineage.run_id` from the OTel span, query the Marquez API:
```bash
GET /api/v1/lineage?nodeId=run:<run_id>
```

This returns the lineage graph showing:
- Job: `demo_stale_ingestion`
- Output datasets: `chromadb/stale_docs.chunks`

### Step 3: Query Dataset Facets
Fetch the dataset's data quality metrics:
```bash
GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks
```

Returns the `dataQualityMetrics` facet:
```json
{
  "_producer": "genaiops-agent/1.0",
  "rowCount": 1,
  "columnMetrics": {
    "freshness": {
      "min": 45.0,
      "max": 45.0,  ← VIOLATION!
      "quantiles": {"0.5": 45.0}
    }
  }
}
```

### Step 4: Root Cause Analysis
Compare metrics against policies:
```
max_freshness_days = 45.0 days
Policy threshold = 30 days
Violation: 45.0 > 30 ✗
```

Trace back to source files:
```
Source: nemo_retriever_deployment.md
Age: 45.0 days ← Root cause
Last modified: 45 days ago
```

### Complete Trace Path

```
OpenTelemetry Span (agent.run)
  └─ lineage.run_id attribute
      └─ OpenLineage Run Event
          └─ Output Dataset: chromadb/stale_docs.chunks
              └─ dataQualityMetrics Facet
                  └─ freshness.max = 45.0 days
                      └─ Policy Violation (> 30 days)
                          └─ Source File: nemo_retriever_deployment.md
```

This correlation enables **end-to-end tracing** from LLM errors back to specific source files that caused the problem.

## Use Cases

### For Demos
- **Normal mode**: Clean output for presentations
- **Verbose mode**: Show technical details without overwhelming
- **Very verbose mode**: Deep dive for technical audiences

### For Debugging
- **Normal mode**: Verify basic functionality
- **Verbose mode**: Trace policy decisions and lineage flow
- **Very verbose mode**: Inspect exact metadata and JSON structures

### For Development
- **Verbose mode**: Understand system behavior
- **Very verbose mode**: Validate data structures and transformations

## Performance Impact

- **Normal mode**: Minimal overhead (default behavior)
- **Verbose mode**: Negligible overhead (just string formatting)
- **Very verbose mode**: Small overhead (JSON serialization for display only)

All modes execute the same underlying logic - verbosity only affects console output.
