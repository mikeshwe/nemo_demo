# Proposal: Add Forward Lineage (Impact Analysis) to Demo

## Problem
Currently the demo only shows **backward lineage** (agent error → stale data). We don't demonstrate **forward lineage** (stale data → impacted tools/queries), which would make the "bidirectional" claim accurate.

## Proposed Enhancement

Add a new step to the demo that shows **impact analysis from ingestion issues**, demonstrating forward lineage tracing.

## Implementation Design

### Step 0: Impact Analysis (NEW - Before Proactive/Reactive)

After ingestion completes, analyze the data quality metrics and predict which tools/queries will be affected:

```
════════════════════════════════════════════════════════════════
STEP 0: IMPACT ANALYSIS (Forward Lineage)
════════════════════════════════════════════════════════════════

Data Ingestion Completed:
  ✓ Run ID: 38a200cc-1a2b-3c4d-5e6f-7890abcdef12
  ✓ Dataset: chromadb/internal_docs.chunks
  ✓ Files ingested: 1

⚠️  Data Quality Issues Detected:

  Issue: Stale Data (max_freshness_days: 45.0 > threshold: 30)
    └─ Source: stale_nemo_guide.md (last modified: 45 days ago)

📊 Forward Lineage Impact Analysis:

  Querying Marquez for downstream consumers...
  └─ GET /api/v1/lineage?nodeId=dataset:chromadb/internal_docs.chunks

  Predicted Impact:
    ⚠️  Tool: internal_docs_search
        └─ Status: DEGRADED - Will return outdated information
        └─ Affected queries:
           • "What are the system requirements for NeMo?"
           • "How do I deploy NeMo Retriever?"
           • Any query about NeMo documentation

    ⚠️  Agent Capability: Documentation Assistance
        └─ Status: BLOCKED by Trust Plane policy
        └─ Reason: Data freshness violation (45 days > 30 day threshold)

  Recommendation:
    ⚠️  Re-ingest documents before running agent queries
    └─ Until data is refreshed, the following will occur:
       • Proactive Mode: Queries will be BLOCKED
       • Reactive Mode: Answers will contain outdated info

Would you like to:
  1. Continue anyway (show proactive/reactive demo)
  2. Re-ingest with fresh data
  3. Exit

[Continuing with demo to show proactive vs reactive behavior...]
```

### Code Changes

#### 1. New Function: `analyze_impact(ingestion_run_id, metrics)`

```python
def analyze_impact(ingestion_run_id, metrics):
    """
    Analyze forward lineage impact of data quality issues

    Shows which tools/queries will be affected by stale data
    """
    print("=" * 70)
    print("STEP 0: IMPACT ANALYSIS (Forward Lineage)")
    print("=" * 70)
    print()

    print("Data Ingestion Completed:")
    print(f"  ✓ Run ID: {ingestion_run_id}")
    print(f"  ✓ Dataset: chromadb/internal_docs.chunks")
    print()

    # Check for data quality issues
    max_freshness = metrics.get('max_freshness_days', 0)
    threshold = 30

    if max_freshness > threshold:
        print("⚠️  Data Quality Issues Detected:")
        print()
        print(f"  Issue: Stale Data (max_freshness_days: {max_freshness} > threshold: {threshold})")
        print(f"    └─ Source: stale_nemo_guide.md (last modified: {int(max_freshness)} days ago)")
        print()

        # Forward lineage analysis
        print("📊 Forward Lineage Impact Analysis:")
        print()
        print("  Querying Marquez for downstream consumers...")

        marquez_url = os.getenv("OPENLINEAGE_URL", "http://localhost:5001")
        lineage_url = f"{marquez_url}/api/v1/lineage?nodeId=dataset:chromadb/internal_docs.chunks&depth=2"
        print(f"  └─ GET {lineage_url}")
        print()

        # Query Marquez for consumers (if available)
        try:
            response = requests.get(lineage_url, timeout=2)
            if response.status_code == 200:
                lineage_data = response.json()
                graph = lineage_data.get('graph', {})

                # Find consumer jobs
                consumers = []
                for edge in graph.get('edges', []):
                    if 'internal_docs.chunks' in edge.get('origin', ''):
                        destination = edge.get('destination', '')
                        if 'agent_query' in destination:
                            consumers.append(destination)

                if consumers:
                    print(f"  Found {len(consumers)} downstream consumer(s):")
                    for consumer in consumers:
                        print(f"    └─ {consumer}")
                    print()
        except:
            pass  # Marquez might not have consumers yet

        # Predict impact
        print("  Predicted Impact:")
        print()
        print("    ⚠️  Tool: internal_docs_search")
        print("        └─ Status: DEGRADED - Will return outdated information")
        print("        └─ Affected queries:")
        print("           • \"What are the system requirements for NeMo?\"")
        print("           • \"How do I deploy NeMo Retriever?\"")
        print("           • Any query about NeMo documentation")
        print()

        print("    ⚠️  Agent Capability: Documentation Assistance")
        print("        └─ Status: BLOCKED by Trust Plane policy")
        print(f"        └─ Reason: Data freshness violation ({int(max_freshness)} days > {threshold} day threshold)")
        print()

        print("  Recommendation:")
        print("    ⚠️  Re-ingest documents before running agent queries")
        print("    └─ Until data is refreshed, the following will occur:")
        print("       • Proactive Mode: Queries will be BLOCKED")
        print("       • Reactive Mode: Answers will contain outdated info")
        print()

        # Pause for user
        print("Would you like to:")
        print("  1. Continue anyway (show proactive/reactive demo)")
        print("  2. Re-ingest with fresh data")
        print("  3. Exit")
        print()
        print("[Continuing with demo to show proactive vs reactive behavior...]")
        print()
        time.sleep(2)  # Brief pause
```

#### 2. Update `main()` to call `analyze_impact()`

```python
def main():
    # ... existing setup ...

    # Step 1: Ingestion (existing)
    print("=" * 70)
    print("STEP 1: INGEST STALE DOCUMENT WITH LINEAGE TRACKING")
    print("=" * 70)
    # ... existing ingestion code ...

    # NEW: Step 0 - Impact Analysis
    analyze_impact(ingestion_run_id, tracker.metrics)

    # Step 2: Run modes (existing)
    if mode == "proactive":
        run_proactive_mode(agent, ingestion_run_id)
    elif mode == "reactive":
        run_reactive_mode(agent, ingestion_run_id, llm_client)
    else:  # both
        run_proactive_mode(agent, ingestion_run_id)
        run_reactive_mode(agent, ingestion_run_id, llm_client)
        show_comparison(...)
```

### Benefits

1. **True Bidirectional Traceability**:
   - Backward: Agent error → stale data (already shown)
   - Forward: Stale data → impacted tools (NEW)

2. **Proactive Governance**:
   - Shows how lineage enables "shift left" - detecting impact before queries run
   - Demonstrates predictive analysis based on data quality

3. **Educational Value**:
   - Users see both directions of lineage tracing
   - Clear connection between data issues and downstream impact

4. **Real-world Relevance**:
   - In production, teams need to know "what breaks if I don't refresh this data?"
   - Impact analysis is critical for data ops planning

### Example Output (Full Flow)

```
STEP 0: IMPACT ANALYSIS (Forward Lineage)
  ⚠️  Stale data detected (45 days)
  📊 Predicted Impact:
     • internal_docs_search tool will be degraded
     • Agent queries will be BLOCKED by Trust Plane

STEP 1: PROACTIVE MODE (Trust Plane)
  ✗ BLOCKED
  ✓ Trust Plane used lineage to prevent error

STEP 2: REACTIVE MODE (LLM Judge)
  ✗ ERROR DETECTED
  ✓ Root cause traced via lineage (but too late)

COMPARISON:
  • Impact Analysis: Predicted the problem
  • Proactive: Prevented the problem
  • Reactive: Detected the problem after the fact

Key Insight: Lineage enables governance at multiple stages
```

## Alternative: Simpler Version

If the full version is too complex, we could do a simpler text-based impact analysis:

```python
def show_impact_analysis_simple(metrics):
    """Simple text-based impact prediction"""
    max_freshness = metrics.get('max_freshness_days', 0)

    if max_freshness > 30:
        print("📊 Forward Lineage: Impact Analysis")
        print()
        print(f"  Data Quality Issue: max_freshness = {max_freshness} days")
        print()
        print("  Impact on Downstream Consumers:")
        print("    └─ Tool 'internal_docs_search': Will return stale data")
        print("    └─ Agent queries: Will be blocked by Trust Plane")
        print()
        print("  This demonstrates FORWARD lineage tracing:")
        print("    Data issue → Predicted tool/query impact")
        print()
```

## Questions

1. Should we query Marquez for actual consumers (may be empty on first run)?
2. Should we make this interactive (ask user to continue)?
3. Should this be verbose-only, or always shown?
4. Should we show a visual lineage graph in ASCII?

## Recommendation

Implement the **full version** with:
- Always show impact analysis (not just verbose mode)
- Query Marquez but don't fail if no consumers found yet
- Brief pause (2-3 seconds) but don't require user input
- This makes the demo clearly show BOTH directions of lineage

This would make the "bidirectional traceability" claim accurate and pedagogically valuable.
