# Data Quality Metadata Flow: Trust Plane vs OTel

## Overview

Understanding how data quality metrics flow through the system in both modes.

## Trust Plane (Proactive Mode)

### How Trust Plane Determines Data Quality

The Trust Plane **exclusively uses OpenLineage metadata** to make authorization decisions.

### Data Flow

```
1. INGESTION TIME (writes metadata)
   ↓
   scripts/setup_vectorstore.py
   ├─> Calculates metrics from source files:
   │   - avg_freshness_days = 42
   │   - max_freshness_days = 45
   │   - row_count = 156
   │   - source_file_count = 2
   │
   ├─> Emits OpenLineage COMPLETE event:
   │   {
   │     "outputs": [{
   │       "namespace": "chromadb",
   │       "name": "internal_docs.chunks",
   │       "facets": {
   │         "dataQualityMetrics": {
   │           "columnMetrics": {
   │             "avg_freshness_days": 42,
   │             "max_freshness_days": 45
   │           }
   │         }
   │       }
   │     }]
   │   }
   │
   └─> Caches metadata locally:
       lineage_client.cache_dataset_metadata(
           "chromadb", "internal_docs.chunks",
           metadata={"metrics": {...}}
       )

2. QUERY TIME (reads metadata)
   ↓
   Agent wants to call RAG tool
   ↓
   Trust Plane intercepts
   ├─> Looks up dataset metadata:
   │   metadata = lineage_client.get_dataset_metadata(
   │       "chromadb", "internal_docs.chunks"
   │   )
   │   # Returns: {"metrics": {"avg_freshness_days": 42, ...}}
   │
   ├─> Applies policies:
   │   policy: avg_freshness_days <= 7 (threshold)
   │   actual: 42
   │   result: 42 > 7 → VIOLATION
   │
   └─> Makes decision:
       if violation: return DENY
```

### Key Implementation

**Step 1: Ingestion captures and stores metrics**

`scripts/setup_vectorstore.py`:
```python
def index_documents_with_lineage(...):
    # Calculate data quality metrics
    freshness_days = {}
    for file_path in markdown_files:
        modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        age_days = (datetime.now() - modified_time).days
        freshness_days[file_path.name] = age_days

    avg_freshness = sum(freshness_days.values()) / len(freshness_days)
    max_freshness = max(freshness_days.values())

    metrics = {
        "row_count": len(all_documents),
        "avg_freshness_days": avg_freshness,
        "max_freshness_days": max_freshness,
        "source_file_count": len(markdown_files)
    }

    # Method 1: Emit to OpenLineage backend (Marquez)
    emit_job_event(
        job_name="document_ingestion",
        event_type="COMPLETE",
        outputs=[{
            "namespace": "chromadb",
            "name": "internal_docs.chunks",
            "facets": {
                "dataQualityMetrics": {
                    "columnMetrics": metrics
                }
            }
        }]
    )

    # Method 2: Cache locally for fast access
    lineage_client = get_lineage_client()
    lineage_client.cache_dataset_metadata(
        namespace="chromadb",
        name="internal_docs.chunks",
        metadata={"metrics": metrics}
    )
```

**Step 2: Trust Plane queries metadata**

`src/trust_plane/engine.py`:
```python
def _get_dataset_metadata(self, namespace: str, name: str) -> Optional[Dict]:
    """Get dataset metadata from OpenLineage

    This queries the lineage system for the latest data quality metrics.

    Options:
    1. Local cache (fast, but may be stale)
    2. Marquez API (authoritative, but requires HTTP call)
    3. Hybrid: Check cache first, fallback to API
    """

    # Option 1: Check local cache (RECOMMENDED for demo)
    lineage_client = get_lineage_client()
    if lineage_client:
        metadata = lineage_client.get_dataset_metadata(namespace, name)
        if metadata:
            return metadata

    # Option 2: Query Marquez API (if running)
    if self._marquez_available():
        metadata = self._query_marquez_api(namespace, name)
        if metadata:
            return metadata

    # No metadata available
    return None

def _query_marquez_api(self, namespace: str, name: str) -> Optional[Dict]:
    """Query Marquez for dataset metadata

    Example API call:
    GET http://localhost:5000/api/v1/namespaces/{namespace}/datasets/{name}

    Returns latest facets including dataQualityMetrics
    """
    import requests

    url = f"{self.marquez_url}/api/v1/namespaces/{namespace}/datasets/{name}"

    try:
        response = requests.get(url, timeout=1.0)
        if response.status_code == 200:
            dataset = response.json()

            # Extract data quality facets
            facets = dataset.get("facets", {})
            quality_facets = facets.get("dataQualityMetrics", {})

            metrics = quality_facets.get("columnMetrics", {})

            return {"metrics": metrics}
    except Exception as e:
        logger.warning(f"Failed to query Marquez: {e}")
        return None
```

**Step 3: Trust Plane evaluates policies**

`src/trust_plane/policies.py`:
```python
def evaluate(self, dataset_metadata: Dict) -> List[Dict]:
    """Evaluate dataset against policy rules

    Args:
        dataset_metadata: {
            "metrics": {
                "avg_freshness_days": 42,
                "max_freshness_days": 45,
                "row_count": 156
            }
        }

    Returns:
        List of violations
    """
    violations = []

    metrics = dataset_metadata.get("metrics", {})

    for rule in self.rules:
        # rule.metric = "avg_freshness_days"
        # rule.threshold = 7
        # rule.operator = "<="

        metric_value = metrics.get(rule.metric)  # Gets 42

        if metric_value is None:
            continue

        if rule.evaluate(metric_value):  # 42 > 7 = True (violation)
            violations.append({
                "rule": rule.metric,
                "threshold": rule.threshold,
                "actual_value": metric_value,  # 42
                "action": rule.action,  # "deny"
                "message": rule.message  # "Data is too stale"
            })

    return violations
```

### Where Metrics Come From

```
Source Files on Disk
  ├─> nemo_retriever_setup.md (modified: 2023-11-23)
  └─> deployment_guide.md (modified: 2023-12-01)
       ↓
Python os.path.getmtime() / stat()
  ├─> File 1: 45 days old
  └─> File 2: 38 days old
       ↓
Calculate aggregates
  ├─> avg_freshness_days = (45 + 38) / 2 = 41.5
  └─> max_freshness_days = 45
       ↓
Store in OpenLineage
  └─> Dataset facet: dataQualityMetrics
       ↓
Trust Plane queries
  └─> Gets metrics from lineage
       ↓
Compare to policy
  └─> 41.5 > 7 → DENY
```

### Trust Plane Does NOT Use:

- ❌ OTel traces/spans
- ❌ Langfuse metadata
- ❌ Runtime inspection of data
- ❌ LLM calls

It **only** uses:
- ✅ OpenLineage dataset facets
- ✅ Pre-calculated data quality metrics
- ✅ Policy definitions (YAML)

---

## OpenTelemetry (Both Modes)

### What OTel Captures

OTel **does NOT determine data quality**. Instead, it:
1. **Traces execution flow**
2. **Links to lineage context**
3. **Records decisions made by Trust Plane or Judge**

### Reactive Mode: OTel Metadata Flow

```
1. Agent Run
   ↓
   OTel Span: agent.run
   ├─> Attributes:
   │   - agent.query = "What are requirements?"
   │   - agent.max_iterations = 10
   │
   └─> Child Span: rag.vector_search
       ├─> Attributes:
       │   - rag.query = "requirements"
       │   - rag.top_k = 3
       │   - rag.results_count = 3
       │   - rag.top_score = 0.87
       │
       ├─> LINK TO LINEAGE (added by vectorstore.py):
       │   - lineage.dataset.namespace = "chromadb"
       │   - lineage.dataset.name = "internal_docs.chunks"
       │   - lineage.run_id = "abc-123"
       │   - lineage.data_quality.freshness_days = 42  ← From lineage!
       │
       └─> Child Span: llm.chat_completion
           ├─> Attributes:
           │   - llm.model = "llama-3.1-70b"
           │   - llm.prompt_tokens = 523
           │   - llm.completion_tokens = 87
           │
           └─> Child Span: llm_judge.validate
               ├─> Attributes:
               │   - validation.verdict = "incorrect"
               │   - validation.confidence = 0.95
               │   - validation.method = "llm_judge"
               │
               └─> Events:
                   - validation_error_outdated_info
                     {description: "Python 3.8 is outdated"}
```

### How OTel Links to Lineage

**In `src/rag/vectorstore.py`**:
```python
def similarity_search(self, query_text, embedding_function, k=3):
    """Search with lineage context added to OTel span"""

    if OTEL_AVAILABLE and is_initialized():
        tracer = get_tracer()
        with tracer.start_as_current_span("rag.vector_search") as span:
            # Regular RAG attributes
            span.set_attribute("rag.query", query_text)
            span.set_attribute("rag.top_k", k)

            # Execute search
            results = self.collection.query(...)

            span.set_attribute("rag.results_count", len(results))

            # LINK TO LINEAGE METADATA
            if LINEAGE_AVAILABLE and is_lineage_enabled():
                lineage_client = get_lineage_client()
                metadata = lineage_client.get_dataset_metadata(
                    "chromadb", "internal_docs.chunks"
                )

                if metadata:
                    # Add lineage context to OTel span
                    span.set_attribute(
                        "lineage.dataset.namespace", "chromadb"
                    )
                    span.set_attribute(
                        "lineage.dataset.name", "internal_docs.chunks"
                    )
                    span.set_attribute(
                        "lineage.run_id", get_current_run_id()
                    )

                    # Add data quality metrics from lineage
                    metrics = metadata.get("metrics", {})
                    if "avg_freshness_days" in metrics:
                        span.set_attribute(
                            "lineage.data_quality.freshness_days",
                            metrics["avg_freshness_days"]
                        )
                    if "row_count" in metrics:
                        span.set_attribute(
                            "lineage.data_quality.row_count",
                            metrics["row_count"]
                        )

            return results
```

### Using OTel Metadata in Reactive Mode

**For root cause analysis**:
```python
# In LLM Judge or post-mortem analysis

def analyze_failed_validation(trace_id: str):
    """Analyze why validation failed using OTel trace"""

    # 1. Get OTel trace
    trace = get_trace(trace_id)

    # 2. Find RAG span
    rag_span = trace.find_span("rag.vector_search")

    # 3. Check lineage attributes
    freshness = rag_span.attributes.get("lineage.data_quality.freshness_days")
    dataset = rag_span.attributes.get("lineage.dataset.name")

    if freshness and freshness > 7:
        print(f"""
        Root Cause Found:
        - Dataset: {dataset}
        - Freshness: {freshness} days (stale!)
        - This explains why LLM gave outdated answer
        """)

    # 4. Get full lineage graph from OpenLineage
    lineage_run_id = rag_span.attributes.get("lineage.run_id")
    lineage_graph = query_lineage_graph(lineage_run_id)

    print("Upstream data sources:", lineage_graph)
```

### Proactive Mode: OTel Metadata Flow

```
1. Agent Run
   ↓
   OTel Span: agent.run
   └─> Child Span: trust_plane.authorize
       ├─> Attributes:
       │   - trust_plane.dataset = "chromadb://internal_docs.chunks"
       │   - trust_plane.operation = "read"
       │   - trust_plane.decision = "deny"
       │   - trust_plane.policy = "rag_data_freshness"
       │
       ├─> LINK TO LINEAGE:
       │   - lineage.dataset.namespace = "chromadb"
       │   - lineage.dataset.name = "internal_docs.chunks"
       │   - lineage.data_quality.freshness_days = 42  ← From lineage!
       │   - lineage.data_quality.threshold = 7         ← From policy!
       │
       └─> Events:
           - trust_plane_denial
             {
               reason: "Data too stale (42 > 7)",
               policy: "rag_data_freshness"
             }

       NO child spans (RAG blocked)
       NO LLM span (prevented)
```

---

## Complete Data Flow Comparison

### Proactive Mode (Trust Plane)

```
┌─────────────────────────────────────────────────────────────┐
│ INGESTION TIME                                              │
├─────────────────────────────────────────────────────────────┤
│ 1. Source files have timestamps                            │
│ 2. Python calculates freshness metrics                     │
│ 3. OpenLineage COMPLETE event emitted                      │
│    └─> dataQualityMetrics facet                            │
│ 4. Metadata cached locally                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ QUERY TIME                                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Agent wants RAG data                                     │
│ 2. Trust Plane intercepts                                   │
│ 3. Query OpenLineage metadata (local cache or API)         │
│    └─> Gets: avg_freshness_days = 42                       │
│ 4. Apply policy: 42 > 7 = DENY                             │
│ 5. Block RAG tool                                           │
│ 6. Log decision to OTel                                     │
│    └─> Span attributes include lineage context             │
└─────────────────────────────────────────────────────────────┘

DATA SOURCES:
  ✅ OpenLineage: Source of truth for metrics
  ✅ OTel: Records decisions, links to lineage
  ❌ Langfuse: Not used for decisions
```

### Reactive Mode (LLM Judge)

```
┌─────────────────────────────────────────────────────────────┐
│ INGESTION TIME (same as proactive)                         │
├─────────────────────────────────────────────────────────────┤
│ 1-4. Same OpenLineage metadata created                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ QUERY TIME                                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Agent calls RAG (no blocking)                            │
│ 2. RAG executes, adds lineage context to OTel span         │
│    └─> Span attribute: freshness_days = 42                 │
│ 3. LLM generates answer (wrong, uses stale data)           │
│ 4. LLM Judge validates                                      │
│    └─> Verdict: incorrect                                  │
│ 5. Post-mortem analysis                                     │
│    a. Check OTel span for lineage attributes               │
│    b. See freshness_days = 42 (stale!)                     │
│    c. Query full lineage graph via OpenLineage             │
│    d. Trace to source files (45 days old)                  │
└─────────────────────────────────────────────────────────────┘

DATA SOURCES:
  ✅ Ground truth: Source for validation
  ✅ OTel: Contains lineage pointers
  ✅ OpenLineage: Root cause analysis
  ❌ Used reactively, after error occurs
```

---

## Key Differences

### Trust Plane (Proactive)

**Decision Logic**:
```python
# Trust Plane queries OpenLineage DIRECTLY
metadata = lineage_client.get_dataset_metadata("chromadb", "internal_docs.chunks")
# Returns: {"metrics": {"avg_freshness_days": 42}}

# Apply policy
if metadata["metrics"]["avg_freshness_days"] > 7:
    return DENY
```

**Data source**: OpenLineage dataset facets

**Timing**: Before tool execution

**OTel role**: Records the decision, doesn't make it

### LLM Judge (Reactive)

**Decision Logic**:
```python
# Judge compares LLM answer to ground truth
verdict = judge_llm(agent_answer, ground_truth)
# Returns: {"verdict": "incorrect", "errors": [...]}

# Root cause analysis uses OTel + OpenLineage
if verdict == "incorrect":
    # 1. Find OTel span for RAG call
    span = trace.find_span("rag.vector_search")

    # 2. Get lineage context from span attributes
    freshness = span.get_attribute("lineage.data_quality.freshness_days")

    # 3. Query full lineage graph
    lineage_graph = query_openlineage(dataset_name)
```

**Data source**: Ground truth (for validation) + OTel (for correlation) + OpenLineage (for lineage)

**Timing**: After LLM generation

**OTel role**: Correlation layer linking validation to lineage

---

## Summary Table

| Aspect | Trust Plane | OTel | OpenLineage |
|--------|-------------|------|-------------|
| **Purpose** | Authorization | Tracing | Lineage |
| **When runs** | Before tool call | During execution | Ingestion + query |
| **Data source** | OpenLineage facets | Execution context | Source files |
| **Determines quality** | ✅ Yes (policies) | ❌ No (traces only) | ✅ Yes (metrics) |
| **Makes decisions** | ✅ Yes (DENY/ALLOW) | ❌ No (observes) | ❌ No (provides data) |
| **Links systems** | Queries lineage | Links to lineage | Source of metrics |

**Flow**:
1. **OpenLineage** = Calculates and stores metrics
2. **Trust Plane** = Queries OpenLineage, makes decisions
3. **OTel** = Records decisions, links execution to lineage
4. **Langfuse** = Logs high-level outcomes

All systems are **complementary**!
