# Data Quality Governance Implementation Summary

## Overview

Successfully implemented a complete data quality governance system for the GenAIOps agent, demonstrating both **proactive** (Trust Plane) and **reactive** (LLM Judge) approaches to detecting and preventing data quality issues.

## What Was Built

### Phase 1: OpenLineage Core Infrastructure
✅ **Data Lineage Tracking**
- OpenLineage client with HTTP transport to Marquez backend
- Graceful fallback to console transport when Marquez unavailable
- Thread-local context management for lineage run correlation
- Event emission for START, COMPLETE, FAIL states

**Files Created:**
- `src/observability/lineage/__init__.py` - Public API
- `src/observability/lineage/client.py` - Client with Marquez API integration
- `src/observability/lineage/emitter.py` - Event emission helpers
- `src/observability/lineage/context.py` - Thread-local context management

### Phase 2: Data Quality Metrics
✅ **Freshness Metrics from File Metadata**
- Calculate file age from mtime (modification time)
- Aggregate metrics: avg_freshness_days, max_freshness_days, min_freshness_days
- OpenLineage dataQualityMetrics facet generation
- Metadata caching for Trust Plane queries

**Files Created:**
- `src/observability/lineage/metrics.py` - Metrics calculation
- `src/ingestion/lineage_tracker.py` - Ingestion tracking context manager

**Integration:**
- Modified `scripts/setup_vectorstore.py` to track ingestion jobs

### Phase 3: Agent Trust Plane
✅ **Proactive Data Quality Enforcement**
- Policy engine with YAML configuration
- Wildcard pattern matching (e.g., `*.chunks`)
- Three-tier metadata access: Cache → Marquez API → None
- Authorization decisions: ALLOW, DENY, WARN
- Fail-open policy (allow if no metadata available)

**Files Created:**
- `src/trust_plane/__init__.py` - Public API
- `src/trust_plane/policy.py` - Policy engine and rules
- `src/trust_plane/enforcer.py` - Authorization decision logic
- `src/trust_plane/policies.yaml` - Default policies

**Policy Example:**
```yaml
policies:
  - name: chromadb_freshness_policy
    namespace: chromadb
    dataset_pattern: "*.chunks"
    rules:
      - metric: max_freshness_days
        operator: lte
        threshold: 30
        action: DENY
        reason: "Dataset contains stale documents (>30 days old)"
```

**Integration:**
- Modified `src/tools/docs_search.py` to check Trust Plane before data access

### Phase 4: LLM Judge
✅ **Reactive Answer Validation**
- Second LLM call for validation (low temperature 0.1)
- Structured JSON verdicts with confidence scores
- Specific error detection and categorization
- Ground truth dataset with expected answers and key facts

**Files Created:**
- `src/validation/__init__.py` - Public API
- `src/validation/verdict.py` - Verdict data structures
- `src/validation/judge.py` - LLM-as-a-Judge implementation
- `src/validation/ground_truth.py` - Ground truth loading
- `data/ground_truth.json` - Test dataset (4 entries)

**Verdict Structure:**
```python
{
  "verdict": "CORRECT" | "INCORRECT" | "PARTIAL" | "UNCLEAR",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed explanation",
  "errors": ["specific error 1", "specific error 2"],
  "key_facts_missing": ["missing fact 1"],
  "key_facts_incorrect": ["incorrect fact 1"]
}
```

### Phase 5: Agent Integration
✅ **Full System Integration**
- Lineage context in agent runs
- OTel spans tagged with lineage.run_id for correlation
- Trust Plane initialization in main.py
- Configuration via environment variables

**Modified Files:**
- `config/settings.py` - Trust Plane settings
- `.env.example` - Configuration examples
- `main.py` - Initialize/shutdown Trust Plane and lineage
- `src/orchestrator/agent.py` - Lineage context and OTel correlation

### Phase 6: Unified Demo
✅ **End-to-End Demonstration**
- Stale documentation scenario (45-day-old files)
- Outdated information: Python 3.8, CUDA 11.0, V100, 16GB VRAM
- Proactive mode: Trust Plane blocks access
- Reactive mode: LLM Judge detects errors
- Side-by-side comparison

**File Created:**
- `demo_data_quality.py` - Complete unified demo

## Demo Results

### Proactive Mode (Trust Plane)
```
Trust Plane Decision: DENY
Policy Violations (2):
  ✗ max_freshness_days: 45.0 (threshold: lte 30)
  ✗ avg_freshness_days: 45.0 (threshold: lte 14)

Result: Error prevented BEFORE wrong answer
Cost: 0 LLM calls (blocked before using data)
```

### Reactive Mode (LLM Judge)
```
Judge Verdict: INCORRECT (confidence: 0.60)
Detected Errors (5):
  1. Incorrect Python version (3.8 instead of 3.10+)
  2. Incorrect CUDA version (11.0 instead of 12.0+)
  3. Recommended GPU is outdated (V100 instead of A100 or H100)
  4. Insufficient VRAM (16GB instead of 40GB)
  5. Missing supported vector databases (Milvus and Pinecone)

Result: Error detected AFTER wrong answer, traced to stale data
Cost: 3 LLM calls (2 for agent + 1 for judge)
```

## Running the Demo

### All Modes (Side-by-Side Comparison)
```bash
python3 demo_data_quality.py --mode both
```

### Proactive Mode Only
```bash
python3 demo_data_quality.py --mode proactive
```

### Reactive Mode Only
```bash
python3 demo_data_quality.py --mode reactive
```

## Key Features

### 1. OpenLineage Integration
- ✅ Data lineage tracking from source → ingestion → vector DB → agent
- ✅ HTTP transport to Marquez backend (port 5000)
- ✅ Console fallback when Marquez unavailable
- ✅ Dataset facets with data quality metrics
- ✅ Run events (START, COMPLETE, FAIL)

### 2. Trust Plane
- ✅ Proactive authorization before data access
- ✅ Policy-driven decision making (YAML configuration)
- ✅ Three-tier metadata access (Cache → API → None)
- ✅ Wildcard pattern matching for datasets
- ✅ Fail-open policy for resilience

### 3. LLM Judge
- ✅ Reactive validation against ground truth
- ✅ Structured JSON verdicts with confidence
- ✅ Specific error detection and categorization
- ✅ Root cause tracing via lineage metadata

### 4. Observability Correlation
- ✅ OTel spans tagged with lineage.run_id
- ✅ End-to-end tracing: OTel → OpenLineage → Source
- ✅ Consistent run_id across all systems
- ✅ Thread-local context management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Query Flow                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PROACTIVE: Trust Plane (Before Data Access)                │
│  • Check data quality policies                               │
│  • Query OpenLineage metadata (Cache → API → None)          │
│  • DENY if freshness exceeds threshold                       │
│  • Prevent error BEFORE it happens                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ (if allowed)
┌─────────────────────────────────────────────────────────────┐
│  Agent Execution                                             │
│  • Retrieve data from vector DB                              │
│  • Generate answer using LLM                                 │
│  • Return answer to user                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  REACTIVE: LLM Judge (After Answer Generated)               │
│  • Validate answer against ground truth                      │
│  • Second LLM call for judgment                              │
│  • INCORRECT if errors detected                              │
│  • Trace root cause via lineage metadata                     │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Enable Trust Plane
```bash
# .env
OPENLINEAGE_ENABLED=true
OPENLINEAGE_URL=http://localhost:5000
OPENLINEAGE_NAMESPACE=genaiops-demo

TRUST_PLANE_ENABLED=true
TRUST_PLANE_POLICY_FILE=src/trust_plane/policies.yaml
```

### Start Marquez (Optional)
```bash
docker run -p 3000:3000 -p 5000:5000 marquezproject/marquez
```

Note: Marquez is optional. The system works with graceful degradation:
- With Marquez: Full lineage visualization + persistent metadata
- Without Marquez: Console logging + local cache only

## Testing

All components tested and working:
- ✅ OpenLineage event emission (START/COMPLETE)
- ✅ Data quality metrics calculation (freshness from mtime)
- ✅ Trust Plane policy evaluation (DENY on stale data)
- ✅ LLM Judge error detection (5 errors found)
- ✅ Metadata caching and Marquez API fallback
- ✅ OTel-Lineage correlation (lineage.run_id attributes)
- ✅ End-to-end demo (both proactive and reactive modes)

## Benefits

### Proactive Approach (Trust Plane)
- **Prevention**: Blocks bad data before agent uses it
- **Efficiency**: No wasted LLM calls on bad data
- **Transparency**: Clear policy violations shown to user
- **Cost**: 0 LLM calls when data blocked

### Reactive Approach (LLM Judge)
- **Detection**: Catches errors after they occur
- **Analysis**: Detailed error categorization
- **Tracing**: Root cause via lineage metadata
- **Cost**: 1 extra LLM call per answer

### Defense in Depth
Using BOTH approaches provides:
- First line of defense: Trust Plane (proactive)
- Safety net: LLM Judge (reactive)
- Complete coverage: Prevention + Detection
- Error tracing: Full lineage visibility

## Next Steps (Optional)

1. **Start Marquez Backend**
   ```bash
   docker run -p 3000:3000 -p 5000:5000 marquezproject/marquez
   ```
   Access UI at http://localhost:3000

2. **Add More Ground Truth**
   Expand `data/ground_truth.json` with additional test cases

3. **Integrate with Real Agent**
   Enable Trust Plane in `main.py` interactive mode

4. **Add More Policies**
   Create additional rules in `src/trust_plane/policies.yaml`

5. **Dashboard Integration**
   Connect to Langfuse for LLM Judge analytics

## File Summary

### New Files (19)
1. `src/observability/lineage/__init__.py`
2. `src/observability/lineage/client.py`
3. `src/observability/lineage/emitter.py`
4. `src/observability/lineage/context.py`
5. `src/observability/lineage/metrics.py`
6. `src/ingestion/__init__.py`
7. `src/ingestion/lineage_tracker.py`
8. `src/trust_plane/__init__.py`
9. `src/trust_plane/policy.py`
10. `src/trust_plane/enforcer.py`
11. `src/trust_plane/policies.yaml`
12. `src/validation/__init__.py`
13. `src/validation/verdict.py`
14. `src/validation/judge.py`
15. `src/validation/ground_truth.py`
16. `data/ground_truth.json`
17. `demo_data_quality.py`
18. `test_trust_plane.py`
19. `DATA_QUALITY_SUMMARY.md`

### Modified Files (7)
1. `requirements.txt` - OpenLineage dependencies
2. `.env.example` - Lineage and Trust Plane configuration
3. `config/settings.py` - Load new settings
4. `main.py` - Initialize/shutdown lineage and Trust Plane
5. `src/orchestrator/agent.py` - Lineage context and OTel correlation
6. `src/tools/docs_search.py` - Trust Plane authorization check
7. `scripts/setup_vectorstore.py` - Lineage tracking during ingestion

## Success Metrics

All Phase 6 objectives achieved:
- ✅ Complete OpenLineage integration
- ✅ Data quality metrics from file freshness
- ✅ Proactive Trust Plane blocking stale data
- ✅ Reactive LLM Judge detecting errors
- ✅ Full observability correlation
- ✅ Working end-to-end demo
- ✅ Both modes tested and validated

## Conclusion

This implementation demonstrates enterprise-grade data quality governance for LLM agents using industry-standard tools (OpenLineage, OpenTelemetry) and novel techniques (Trust Plane, LLM-as-a-Judge). The system provides both proactive prevention and reactive detection, creating a comprehensive defense-in-depth strategy for data quality issues.
