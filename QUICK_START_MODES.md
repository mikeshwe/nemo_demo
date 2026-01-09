# Quick Start: Full Traceability Demo Modes

## TL;DR

```bash
# Start Marquez
docker-compose -f docker-compose-marquez.yml up -d

# Run demo (default: both modes)
python3 demo_full_traceability.py
```

## Three Modes

### 1. Proactive Mode (Trust Plane)
**Prevents errors BEFORE they happen**

```bash
python3 demo_full_traceability.py --mode proactive
```

**What happens:**
- ✅ Trust Plane checks data quality BEFORE query
- ✅ Blocks query if data is stale (> 30 days)
- ✅ Agent never sees outdated information
- ✅ Shows root cause immediately

**Output:**
```
✗ BLOCKED: Data quality violation: max_freshness_days (45.0) > threshold (30)
✓ PROACTIVE PREVENTION: Stale data detected BEFORE query execution
```

---

### 2. Reactive Mode (LLM Judge)
**Detects errors AFTER they happen**

```bash
python3 demo_full_traceability.py --mode reactive
```

**What happens:**
- ❌ No pre-query checks
- ❌ Agent retrieves stale data
- ❌ Agent generates answer with outdated info
- ✅ LLM Judge detects error AFTER response

**Output:**
```
Agent Answer: [Contains Python 3.8, CUDA 11.0, V100...]
✗ REACTIVE DETECTION: Outdated info found AFTER agent response
```

---

### 3. Both Mode (Comparison)
**Shows proactive vs reactive side-by-side**

```bash
python3 demo_full_traceability.py --mode both  # or just: python3 demo_full_traceability.py
```

**What happens:**
- Runs proactive mode first
- Runs reactive mode second
- Shows comparison

**Output:**
```
COMPARISON: PROACTIVE VS REACTIVE

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
```

## Verbose Modes

```bash
# Verbose: Shows tracking details, Trust Plane checks
python3 demo_full_traceability.py --mode both -v

# Very verbose: Shows all metadata for all chunks
python3 demo_full_traceability.py --mode both -vv
```

## What Makes This Demo Special?

### Real ChromaDB Integration ✅
- Not simulated - actually ingests documents
- Real embeddings with sentence-transformers
- Real vector search during queries
- producer_run_id in actual document metadata

### Full Bidirectional Traceability ✅
- Ingestion job → OpenLineage → Marquez
- ChromaDB metadata → producer_run_id
- Agent query → OTel span → lineage.input_run_ids
- Query Marquez API → Full lineage graph

### Both Patterns ✅
- **Proactive (Trust Plane)**: Authorization layer
- **Reactive (LLM Judge)**: Validation layer
- Side-by-side comparison shows why proactive is better

## Viewing Results

### Marquez UI
```bash
open http://localhost:3001
```

Navigate to: Jobs → `stale_doc_ingestion` → Latest Run → Outputs

### Marquez API
```bash
# List jobs
curl http://localhost:5001/api/v1/namespaces/demo/jobs | python3 -m json.tool

# Get dataset with data quality facets
curl http://localhost:5001/api/v1/namespaces/chromadb/datasets/internal_docs.chunks | python3 -m json.tool
```

## Understanding the Output

### Step 1: Ingestion
```
Lineage Run ID: 38a200cc...
Data Quality Metrics:
  • Max freshness: 45.0 days ← STALE!

✓ OpenLineage Events Emitted
  • Metadata cached for Trust Plane
```

### Step 2: Proactive Mode
```
Trust Plane Authorization:
  ✗ BLOCKED

Root Cause Analysis:
  • Producer run ID: 38a200cc...
  • Max freshness: 45.0 days > 30 days threshold
```

### Step 2: Reactive Mode
```
Agent Answer: [outdated info]

LLM Judge Validation:
  • Verdict: FAIL
  • Outdated info found: Python 3.8, CUDA 11.0, V100
```

### Step 3: Traceability
```
1. Agent Span → lineage.input_run_ids: 38a200cc...
2. ChromaDB Metadata → producer_run_id: 38a200cc...
3. OpenLineage Event → producerRunId: 38a200cc...
4. Marquez Query → dataQualityMetrics: max_freshness_days: 45.0
5. Root Cause: stale_nemo_guide.md (45 days old)
```

## Common Use Cases

### Demo to stakeholders
```bash
python3 demo_full_traceability.py --mode both
```
Shows both approaches side-by-side

### Focus on prevention
```bash
python3 demo_full_traceability.py --mode proactive -v
```
Shows how Trust Plane blocks bad queries

### Debug lineage flow
```bash
python3 demo_full_traceability.py --mode both -vv
```
Shows all metadata propagation

## Troubleshooting

### Marquez not running
```bash
docker-compose -f docker-compose-marquez.yml up -d
docker ps | grep marquez  # Should show 3 containers
```

### OpenLineage not enabled
Check `.env`:
```bash
OPENLINEAGE_ENABLED=true
OPENLINEAGE_URL=http://localhost:5001
```

### Port conflict (5000)
macOS ControlCenter uses port 5000. We use port 5001 instead:
```bash
OPENLINEAGE_URL=http://localhost:5001  # Note: 5001, not 5000
```

## Key Takeaways

1. **Proactive (Trust Plane) PREVENTS errors** by checking data quality before query execution
2. **Reactive (LLM Judge) DETECTS errors** after agent has already generated incorrect answer
3. **Bidirectional traceability** enables automated root cause analysis from agent error → stale data file
4. **Real ChromaDB integration** shows production-ready patterns, not simulations
5. **OpenLineage + OTel** correlation provides complete observability

## Related Docs

- [README_FULL_TRACEABILITY.md](README_FULL_TRACEABILITY.md) - Detailed guide
- [DEMO_MODES_IMPLEMENTATION.md](DEMO_MODES_IMPLEMENTATION.md) - Implementation details
- [BIDIRECTIONAL_TRACEABILITY.md](BIDIRECTIONAL_TRACEABILITY.md) - Architecture
- [DATA_QUALITY_SUMMARY.md](DATA_QUALITY_SUMMARY.md) - Trust Plane overview
