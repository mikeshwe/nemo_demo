# Full Bidirectional Traceability Demo

## Overview

This demo shows **complete end-to-end data lineage** with actual ChromaDB usage, demonstrating how OpenTelemetry traces correlate with OpenLineage data lineage for automated root cause analysis.

## What's Different from `demo_data_quality.py`?

| Feature | demo_data_quality.py | demo_full_traceability.py |
|---------|---------------------|---------------------------|
| ChromaDB | ❌ Simulated | ✅ **Actually uses ChromaDB** |
| Document Ingestion | ❌ Fake | ✅ **Real ingestion with embeddings** |
| Agent RAG | ❌ Simulated | ✅ **Real vector search** |
| producer_run_id | ✅ In cache only | ✅ **In ChromaDB document metadata** |
| OTel Spans | ✅ Yes | ✅ **With lineage.input_run_ids from RAG** |
| OpenLineage Events | ✅ Emitted | ✅ **Agent emits events with input datasets** |

## Prerequisites

1. **Start Marquez** (optional, but recommended):
   ```bash
   docker-compose -f docker-compose-marquez.yml up -d
   ```

2. **Enable OpenLineage** in `.env`:
   ```bash
   OPENLINEAGE_ENABLED=true
   OPENLINEAGE_URL=http://localhost:5001
   ```

## Running the Demo

The demo now supports three modes:

```bash
# Proactive mode: Trust Plane blocks stale data BEFORE query
python3 demo_full_traceability.py --mode proactive

# Reactive mode: LLM Judge detects error AFTER agent answers
python3 demo_full_traceability.py --mode reactive

# Both modes: Side-by-side comparison (default)
python3 demo_full_traceability.py --mode both

# With verbose logging
python3 demo_full_traceability.py --mode both -v
python3 demo_full_traceability.py --mode both -vv  # Very verbose
```

## Demo Modes

### Proactive Mode (Trust Plane)

**PREVENTS** errors before they happen:

1. Trust Plane checks data quality policies BEFORE query execution
2. If data is stale (>30 days), query is **BLOCKED**
3. Agent never receives outdated information
4. User is alerted to data quality issue with root cause (producer run ID)

**Output:**
```
✗ BLOCKED: Data quality violation: max_freshness_days (45.0) > threshold (30)

✓ PROACTIVE PREVENTION:
  • Stale data detected BEFORE query execution
  • Agent never received outdated information
  • No hallucination risk
```

### Reactive Mode (LLM Judge)

**DETECTS** errors after they happen:

1. No pre-query checks - agent executes query immediately
2. Agent retrieves stale data from ChromaDB and generates answer
3. LLM Judge validates answer quality AFTER response
4. Detects outdated information in agent's answer

**Output:**
```
Agent Answer: [Contains outdated info like "Python 3.8, CUDA 11.0, V100"]

✗ REACTIVE DETECTION:
  • Outdated info found: Python 3.8, CUDA 11.0, V100, 16GB VRAM
  • Error detected AFTER agent response
  • User already saw incorrect answer
```

### Both Mode (Comparison)

Runs both modes side-by-side and shows the key difference:

```
Proactive (Trust Plane):
  • Status: BLOCKED
  • Timing: Pre-query authorization
  • Result: Prevented bad answer

Reactive (LLM Judge):
  • Status: FAIL
  • Timing: Post-query validation
  • Result: Error detected after response

Key Difference:
  • Proactive PREVENTED the error before it happened
  • Reactive DETECTED the error after user saw it
  • Proactive is superior for data quality issues
```

## What It Does

### Step 1: Ingestion with Producer Run ID

1. Creates a 45-day-old stale document
2. Chunks and embeds the document
3. Adds to ChromaDB with **lineage metadata**:
   ```python
   metadata = {
       "title": "NeMo Retriever Guide",
       "source": "stale_nemo_guide.md",
       "lineage.producer_run_id": "fd5420d4-...",  ← Links to ingestion job
       "lineage.producer_job": "stale_doc_ingestion"
   }
   ```
4. Emits OpenLineage events with data quality facets

### Step 2: Agent Query with RAG

1. User asks: "What are the system requirements for deploying NeMo Retriever?"
2. Agent calls `internal_docs_search` tool
3. Tool queries ChromaDB vector store
4. **Extracts `producer_run_id` from retrieved documents**
5. **Adds to OTel span**: `lineage.input_run_ids = "fd5420d4-..."`
6. Agent answers the question (with stale data!)
7. **Emits OpenLineage event** linking to input datasets

### Step 3: Bidirectional Traceability

Shows the complete correlation flow:

```
Agent Span (OTel)
  ├─ lineage.run_id: <agent-run-id>
  └─ lineage.input_run_ids: "fd5420d4-..."  ← From ChromaDB metadata!

      ↓ Query Marquez API

Ingestion Job (OpenLineage)
  ├─ run_id: fd5420d4-...
  ├─ job: stale_doc_ingestion
  └─ output: chromadb/internal_docs.chunks
      └─ facets:
          └─ dataQualityMetrics:
              └─ max_freshness_days: 45.0  ← ROOT CAUSE!
```

## Example Output

```
================================================================================
STEP 1: INGESTION WITH LINEAGE TRACKING
================================================================================

Lineage Run ID: fd5420d4-c1c5-4d8c-9ee1-0956e76d51a4

Data Quality Metrics:
  • Files: 1
  • Max freshness: 45.0 days ← STALE!
  • Avg freshness: 45.0 days

Document Processing:
  • Chunks created: 3
  • Embedding chunks...
  • Added to ChromaDB: 3 chunks
  • Each chunk tagged with producer_run_id: fd5420d4...

✓ OpenLineage Events Emitted:
  • START event
  • COMPLETE event with dataQualityMetrics facet
  • Metadata cached for Trust Plane

================================================================================
STEP 2: AGENT QUERY WITH RAG
================================================================================

User Query: "What are the system requirements for deploying NeMo Retriever?"

Agent Processing:
  • Creating agent execution span...
  • Tool: internal_docs_search
  • Querying ChromaDB vector store...

Agent Answer:
  Based on the documentation, here are the system requirements...
  [Answer contains outdated info from stale document]

Execution Stats:
  • Iterations: 2
  • Tool calls: 1
  • Success: True

================================================================================
STEP 3: BIDIRECTIONAL TRACEABILITY
================================================================================

Correlation Flow:

1. AGENT SPAN (OTel)
   ├─ span.name: 'agent.run'
   ├─ lineage.run_id: '<agent-run-id>'
   └─ Tool: internal_docs_search
      ├─ Queries: ChromaDB
      └─ Extracts: producer_run_id from document metadata

2. DOCUMENT METADATA (ChromaDB)
   ├─ title: 'NeMo Retriever Guide'
   ├─ source: 'stale_nemo_guide.md'
   ├─ lineage.producer_run_id: 'fd5420d4...' ← KEY!
   └─ lineage.producer_job: 'stale_doc_ingestion'

3. SPAN ATTRIBUTE ADDED (OTel)
   └─ lineage.input_run_ids: 'fd5420d4...'

4. OPENLINEAGE EVENT EMITTED
   ├─ eventType: COMPLETE
   ├─ job: agent_query
   └─ inputs: [
        {
          namespace: 'chromadb',
          name: 'internal_docs.chunks',
          facets: {
            producerRunId: 'fd5420d4...'
          }
        }
      ]

5. QUERY MARQUEZ (Root Cause Analysis)
   GET /api/v1/lineage?nodeId=run:fd5420d4...
   Returns:
     • Job: stale_doc_ingestion
     • Output: chromadb/internal_docs.chunks
     • Facets:
       - dataQualityMetrics:
         • max_freshness_days: 45.0 ← VIOLATION!
         • file: stale_nemo_guide.md

✓ FULL BIDIRECTIONAL TRACEABILITY ACHIEVED!
```

## Verification in Marquez UI

1. Open http://localhost:3001
2. Navigate to **Jobs → agent_query**
3. Click on the latest run
4. View **Inputs** tab:
   - You'll see `chromadb/internal_docs.chunks`
   - With `producerRunId` facet linking back to ingestion
5. Click on the input dataset
6. View the **producerRunId** to trace back to ingestion job
7. See the full lineage graph:
   ```
   stale_doc_ingestion → chromadb/internal_docs.chunks → agent_query
   ```

## Query Examples

### Get Agent Run Details
```bash
curl -s http://localhost:5001/api/v1/namespaces/agent/jobs/agent_query/runs/<agent-run-id> \
  | jq '.inputs'
```

### Get Dataset Producer
```bash
curl -s http://localhost:5001/api/v1/namespaces/chromadb/datasets/internal_docs.chunks \
  | jq '.facets.dataQualityMetrics'
```

### Get Full Lineage Graph
```bash
curl -s "http://localhost:5001/api/v1/lineage?nodeId=run:<ingestion-run-id>&depth=2" \
  | jq '.graph'
```

## Cleanup

```bash
# Remove ChromaDB data
rm -rf ./data/chroma_demo

# Stop Marquez
docker-compose -f docker-compose-marquez.yml down
```

## Key Takeaways

1. **Real ChromaDB Integration**: Unlike the conceptual demo, this actually stores and retrieves documents
2. **Metadata Propagation**: `producer_run_id` flows from ingestion → ChromaDB → RAG → Agent span
3. **OpenLineage Events**: Agent emits events with explicit input dataset links
4. **Automated Root Cause**: From agent error to data quality issue in 5 API calls
5. **Production-Ready Pattern**: This is how you'd implement it in a real system

## Comparison to demo_data_quality.py

**demo_data_quality.py**:
- ✅ Great for understanding Trust Plane and LLM Judge concepts
- ✅ No ChromaDB setup required
- ✅ Shows proactive vs reactive patterns
- ❌ Doesn't actually use ChromaDB
- ❌ producer_run_id only in cache, not in documents

**demo_full_traceability.py**:
- ✅ **Real ChromaDB integration**
- ✅ **Full bidirectional traceability implementation**
- ✅ **Agent actually queries vector store**
- ✅ **producer_run_id in document metadata**
- ✅ **OpenLineage events from agent with input datasets**
- ❌ Requires Chrom aDB setup
- ❌ Takes longer to run

## Related Documentation

- [BIDIRECTIONAL_TRACEABILITY.md](BIDIRECTIONAL_TRACEABILITY.md) - Architecture guide
- [MARQUEZ_SETUP.md](MARQUEZ_SETUP.md) - Marquez backend setup
- [DEMO_VERBOSITY_GUIDE.md](DEMO_VERBOSITY_GUIDE.md) - Verbosity levels
- [DATA_QUALITY_SUMMARY.md](DATA_QUALITY_SUMMARY.md) - Trust Plane overview
