#!/usr/bin/env python3
"""
Unified Data Quality Demo: Proactive vs Reactive

This demo shows two approaches to handling stale data:
1. PROACTIVE: Trust Plane blocks access to stale data BEFORE agent uses it
2. REACTIVE: LLM Judge detects errors AFTER agent uses stale data

The demo uses a "Stale Documentation Error" scenario where 45-day-old
docs contain outdated information (Python 3.8, CUDA 11.0) that leads
to wrong answers.
"""
import os
import sys
import argparse
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import components
from openai import OpenAI
from src.observability.lineage import initialize_lineage, shutdown_lineage, get_lineage_client
from src.trust_plane import initialize_trust_plane, shutdown_trust_plane, authorize_dataset_access
from src.ingestion.lineage_tracker import track_ingestion
from src.validation import validate_answer, load_ground_truth

# Global verbosity level
VERBOSITY = 0  # 0=normal, 1=verbose, 2=very_verbose


def log_verbose(message, level=1):
    """Print verbose logging message

    Args:
        message: Message to print
        level: 1=verbose, 2=very_verbose
    """
    if VERBOSITY >= level:
        print(message)


def print_banner():
    """Print demo banner"""
    print("\n" + "="*80)
    print(" "*20 + "Data Quality Governance Demo")
    print(" "*15 + "Proactive (Trust Plane) vs Reactive (LLM Judge)")
    print("="*80 + "\n")


def create_stale_docs():
    """Create test documents with stale data (45 days old)

    Returns:
        tuple: (temp_dir, file_paths)
    """
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Creating stale documentation dataset in: {temp_dir}\n")

    # Create stale doc with outdated info
    stale_doc = temp_dir / "nemo_retriever_deployment.md"
    stale_content = """# NeMo Retriever Deployment Guide

## System Requirements

NeMo Retriever is approved for production use with the following requirements:

### Software
- Python 3.8 or higher
- CUDA 11.0 or higher

### Hardware
- NVIDIA V100 GPU
- Minimum 16GB VRAM
- 64GB system RAM

### Vector Databases
- ChromaDB (recommended)

## Installation

```bash
pip install nemo-retriever
```

Last updated: 45 days ago
"""
    stale_doc.write_text(stale_content)

    # Set mtime to 45 days ago
    forty_five_days_ago = (datetime.now() - timedelta(days=45)).timestamp()
    os.utime(stale_doc, (forty_five_days_ago, forty_five_days_ago))

    print(f"✓ Created: {stale_doc.name}")
    print(f"  Age: 45 days old")
    print(f"  Contains STALE info: Python 3.8, CUDA 11.0, V100, 16GB VRAM\n")

    return temp_dir, [stale_doc]


def ingest_stale_docs(file_paths):
    """Ingest stale docs with lineage tracking

    Args:
        file_paths: List of file paths to ingest

    Returns:
        dict: Metrics from ingestion
    """
    print("="*80)
    print("INGESTION: Tracking Data Lineage")
    print("="*80 + "\n")

    print("Ingesting stale documentation with OpenLineage tracking...\n")

    with track_ingestion(job_name="demo_stale_ingestion") as tracker:
        log_verbose(f"\n[VERBOSE] Lineage Run ID: {tracker.run_id}")
        log_verbose(f"[VERBOSE] Job Name: {tracker.job_name}\n")

        tracker.start(file_paths)

        metrics = tracker.metrics
        print(f"Data Quality Metrics:")
        print(f"  • Files ingested: {metrics['file_count']}")
        print(f"  • Avg freshness: {metrics['avg_freshness_days']:.1f} days")
        print(f"  • Max freshness: {metrics['max_freshness_days']:.1f} days")
        print(f"  • Total size: {metrics['total_size_bytes']} bytes\n")

        if VERBOSITY >= 2:
            log_verbose("\n[VV] Detailed Metrics:", 2)
            log_verbose(json.dumps(metrics, indent=2), 2)
            log_verbose("", 2)

        # Simulate chunking and embedding (we'll skip actual vector store)
        num_chunks = len(file_paths) * 3  # Simulate 3 chunks per file

        tracker.complete(collection_name="stale_docs", num_chunks=num_chunks)
        print(f"✓ Lineage tracked: START → COMPLETE")
        print(f"✓ Metadata cached for Trust Plane\n")

        log_verbose(f"[VERBOSE] OpenLineage Events Emitted:", 1)
        log_verbose(f"  • START event with input datasets", 1)
        log_verbose(f"  • COMPLETE event with output dataset: chromadb/stale_docs.chunks", 1)
        log_verbose(f"  • Data quality facets attached to output dataset\n", 1)

    return metrics


def run_proactive_mode(llm_client):
    """Run proactive mode: Trust Plane blocks stale data

    Args:
        llm_client: OpenAI client

    Returns:
        dict: Results from proactive mode
    """
    print("\n" + "="*80)
    print("MODE 1: PROACTIVE (Trust Plane)")
    print("="*80 + "\n")

    print("Scenario: Agent tries to access stale documentation\n")

    query = "Is NeMo Retriever approved for production use?"
    print(f"User Query: \"{query}\"\n")

    # Check Trust Plane authorization
    print("Trust Plane: Checking data quality before allowing access...\n")

    log_verbose("[VERBOSE] Trust Plane Query:", 1)
    log_verbose(f"  • Namespace: chromadb", 1)
    log_verbose(f"  • Dataset: stale_docs.chunks", 1)
    log_verbose(f"  • Tool: internal_docs_search\n", 1)

    decision = authorize_dataset_access(
        namespace="chromadb",
        dataset_name="stale_docs.chunks",
        tool_name="internal_docs_search"
    )

    if VERBOSITY >= 2:
        log_verbose("\n[VV] Metadata Retrieval:", 2)
        client = get_lineage_client()
        if client:
            metadata = client.get_dataset_metadata("chromadb", "stale_docs.chunks")
            if metadata:
                log_verbose(f"  • Source: Local cache", 2)
                log_verbose(f"  • Cached at: {metadata.get('cached_at', 'N/A')}", 2)
                log_verbose(f"  • Metrics: {json.dumps(metadata.get('metrics', {}), indent=4)}\n", 2)
            else:
                log_verbose(f"  • Source: No metadata available\n", 2)

    print(f"Trust Plane Decision:")
    print(f"  • Action: {decision.action}")
    print(f"  • Allowed: {decision.allowed}")
    print(f"  • Reason: {decision.reason}\n")

    if decision.violations:
        print(f"Policy Violations ({len(decision.violations)}):")
        for v in decision.violations:
            print(f"  ✗ {v['metric']}: {v['actual']} (threshold: {v['operator']} {v['threshold']})")
            print(f"    {v['reason']}")
        print()

        if VERBOSITY >= 1:
            log_verbose("[VERBOSE] Policy Evaluation:", 1)
            log_verbose(f"  • Policies matched: {len(decision.violations)}", 1)
            log_verbose(f"  • Decision: {decision.action} (not allowed)\n", 1)

    if not decision.allowed:
        print("❌ ACCESS DENIED\n")
        print("Agent Response:")
        print(f"  \"I cannot answer this question because the documentation")
        print(f"   data is stale (45 days old, exceeds 30-day policy).")
        print(f"   Please refresh the documentation dataset first.\"\n")

        print("✅ RESULT: Error prevented BEFORE wrong answer was generated!\n")

        return {
            "mode": "proactive",
            "prevented_error": True,
            "decision": decision,
            "answer": None,
            "cost": "0 LLM calls (agent blocked before using data)"
        }
    else:
        print("✓ Access allowed (data meets quality standards)\n")
        return {
            "mode": "proactive",
            "prevented_error": False,
            "decision": decision,
            "answer": "Would proceed with agent query",
            "cost": "2-3 LLM calls"
        }


def run_reactive_mode(llm_client, ground_truth):
    """Run reactive mode: LLM Judge detects error after it happens

    Args:
        llm_client: OpenAI client
        ground_truth: Ground truth dataset

    Returns:
        dict: Results from reactive mode
    """
    print("\n" + "="*80)
    print("MODE 2: REACTIVE (LLM Judge)")
    print("="*80 + "\n")

    print("Scenario: Agent uses stale data and gives wrong answer\n")

    query = "Is NeMo Retriever approved for production use?"
    print(f"User Query: \"{query}\"\n")

    # Simulate agent answer with stale data
    agent_answer = (
        "Yes, NeMo Retriever is approved for production use. "
        "It requires Python 3.8 and CUDA 11.0. "
        "The recommended GPU is NVIDIA V100 with at least 16GB VRAM. "
        "It supports ChromaDB for vector storage."
    )

    print("Agent Answer (using stale data):")
    print(f"  \"{agent_answer}\"\n")

    # Get ground truth
    gt_entry = ground_truth.get(query)
    if not gt_entry:
        print("✗ No ground truth found for validation\n")
        return {"mode": "reactive", "error_detected": False}

    if VERBOSITY >= 1:
        log_verbose("[VERBOSE] Ground Truth Entry:", 1)
        log_verbose(f"  • Expected answer: {gt_entry.expected_answer[:100]}...", 1)
        log_verbose(f"  • Key facts: {len(gt_entry.key_facts)} facts to check", 1)
        log_verbose(f"  • Known errors: {len(gt_entry.common_errors)} common errors\n", 1)

    if VERBOSITY >= 2:
        log_verbose("[VV] Complete Ground Truth:", 2)
        log_verbose(json.dumps({
            "expected_answer": gt_entry.expected_answer,
            "key_facts": gt_entry.key_facts,
            "common_errors": gt_entry.common_errors
        }, indent=2), 2)
        log_verbose("", 2)

    # Run LLM Judge
    print("LLM Judge: Validating answer against ground truth...\n")

    log_verbose("[VERBOSE] LLM Judge Call:", 1)
    log_verbose(f"  • Model: meta/llama-3.1-70b-instruct", 1)
    log_verbose(f"  • Temperature: 0.1 (low for consistency)", 1)
    log_verbose(f"  • Prompt type: Structured JSON verdict\n", 1)

    verdict = validate_answer(
        query=query,
        agent_answer=agent_answer,
        ground_truth=gt_entry,
        llm_client=llm_client
    )

    print(f"Judge Verdict:")
    print(f"  • Verdict: {verdict.verdict.value}")
    print(f"  • Confidence: {verdict.confidence:.2f}")
    print(f"  • Correct: {verdict.is_correct}\n")

    print(f"Reasoning:")
    print(f"  {verdict.reasoning}\n")

    if verdict.errors:
        print(f"Detected Errors ({len(verdict.errors)}):")
        for i, error in enumerate(verdict.errors, 1):
            print(f"  {i}. {error}")
        print()

    if verdict.key_facts_incorrect:
        print(f"Incorrect Facts:")
        for fact in verdict.key_facts_incorrect:
            print(f"  ✗ {fact}")
        print()

    if not verdict.is_correct:
        print("❌ ERROR DETECTED\n")

        if VERBOSITY >= 1:
            log_verbose("[VERBOSE] Lineage Trace:", 1)
            client = get_lineage_client()
            if client:
                metadata = client.get_dataset_metadata("chromadb", "stale_docs.chunks")
                if metadata:
                    log_verbose(f"  • Dataset: chromadb/stale_docs.chunks", 1)
                    log_verbose(f"  • Max freshness: {metadata['metrics']['max_freshness_days']} days", 1)
                    log_verbose(f"  • Avg freshness: {metadata['metrics']['avg_freshness_days']} days", 1)
                    log_verbose(f"  • Source files: {metadata['metrics']['file_count']} files", 1)

                    if VERBOSITY >= 2:
                        # Extract producer_run_id from cached metadata
                        producer_run_id = metadata.get('producer_run_id', '<unknown>')
                        producer_job = metadata.get('producer_job', 'demo_stale_ingestion')

                        log_verbose("\n[VV] OpenTelemetry → OpenLineage Correlation:", 2)
                        log_verbose("", 2)
                        log_verbose("Step 1: OTel Span Attributes (if agent was instrumented):", 2)
                        log_verbose("  {", 2)
                        log_verbose("    'span.name': 'agent.run',", 2)
                        log_verbose("    'agent.query': 'Is NeMo Retriever approved...',", 2)
                        log_verbose(f"    'lineage.input_run_ids': '{producer_run_id[:8]}...',  ← From RAG query!", 2)
                        log_verbose(f"    'lineage.job_name': 'agent_query'", 2)
                        log_verbose("  }", 2)
                        log_verbose("", 2)
                        log_verbose("Step 2: Query OpenLineage via input_run_id:", 2)
                        log_verbose(f"  GET /api/v1/lineage?nodeId=run:{producer_run_id[:8]}...", 2)
                        log_verbose("  Returns:", 2)
                        log_verbose(f"    - Job: {producer_job}", 2)
                        log_verbose("    - Output datasets: chromadb/stale_docs.chunks", 2)
                        log_verbose("", 2)
                        log_verbose("Step 3: Query Dataset Facets:", 2)
                        log_verbose(f"  GET /api/v1/namespaces/chromadb/datasets/stale_docs.chunks", 2)
                        log_verbose("  Returns dataQualityMetrics facet:", 2)
                        log_verbose("  {", 2)
                        log_verbose("    '_producer': 'genaiops-agent/1.0',", 2)
                        log_verbose("    'rowCount': 1,", 2)
                        log_verbose("    'columnMetrics': {", 2)
                        log_verbose("      'freshness': {", 2)
                        log_verbose(f"        'min': {metadata['metrics'].get('min_freshness_days', 45.0)},", 2)
                        log_verbose(f"        'max': {metadata['metrics']['max_freshness_days']},  ← VIOLATION!", 2)
                        log_verbose(f"        'quantiles': {{'0.5': {metadata['metrics']['avg_freshness_days']}}}", 2)
                        log_verbose("      }", 2)
                        log_verbose("    }", 2)
                        log_verbose("  }", 2)
                        log_verbose("", 2)
                        log_verbose("Step 4: Bidirectional Traceability:", 2)
                        log_verbose(f"  Producer Run ID: {producer_run_id}", 2)
                        log_verbose(f"  Producer Job: {producer_job}", 2)
                        log_verbose(f"  Data Quality: max_freshness = {metadata['metrics']['max_freshness_days']} days", 2)
                        log_verbose("  Policy Threshold: 30 days", 2)
                        log_verbose(f"  Violation: {metadata['metrics']['max_freshness_days']} > 30 ✗", 2)
                        log_verbose("", 2)

                        log_verbose("[VV] Source File Details:", 2)
                        for file_info in metadata['metrics'].get('files', []):
                            file_path = file_info.get('path', file_info.get('name', 'unknown'))
                            file_name = file_path.split('/')[-1] if '/' in file_path else file_path
                            log_verbose(f"  • {file_name}:", 2)
                            log_verbose(f"    - Age: {file_info['freshness_days']} days ← Root cause", 2)
                            log_verbose(f"    - Size: {file_info['size_bytes']} bytes", 2)
                            log_verbose(f"    - Path: {file_path}", 2)
                    log_verbose("", 1)

        print("Next Step: Trace error back to source via lineage")
        print("  → lineage.run_id → OpenLineage → Dataset facets")
        print("  → max_freshness_days: 45.0 (exceeds threshold)")
        print("  → Root cause: 45-day-old source files\n")

        print("✅ RESULT: Error detected AFTER wrong answer, traced to stale data!\n")

        return {
            "mode": "reactive",
            "error_detected": True,
            "verdict": verdict,
            "answer": agent_answer,
            "cost": "3 LLM calls (2 for agent + 1 for judge)"
        }
    else:
        print("✓ Answer validated as correct\n")
        return {
            "mode": "reactive",
            "error_detected": False,
            "verdict": verdict,
            "answer": agent_answer,
            "cost": "3 LLM calls"
        }


def print_comparison(proactive_result, reactive_result):
    """Print side-by-side comparison of both modes

    Args:
        proactive_result: Results from proactive mode
        reactive_result: Results from reactive mode
    """
    print("\n" + "="*80)
    print("COMPARISON: Proactive vs Reactive")
    print("="*80 + "\n")

    print("┌" + "─"*38 + "┬" + "─"*39 + "┐")
    print("│ " + "PROACTIVE (Trust Plane)".center(36) + " │ " + "REACTIVE (LLM Judge)".center(37) + " │")
    print("├" + "─"*38 + "┼" + "─"*39 + "┤")

    print("│ " + "Prevents errors BEFORE they happen".ljust(36) + " │ " + "Detects errors AFTER they happen".ljust(37) + " │")
    print("│ " + "Blocks data access proactively".ljust(36) + " │ " + "Validates answers reactively".ljust(37) + " │")
    print("│ " + f"{proactive_result['cost']}".ljust(36) + " │ " + f"{reactive_result['cost']}".ljust(37) + " │")

    proactive_outcome = "✓ Error prevented" if proactive_result.get('prevented_error') else "✗ Would allow"
    reactive_outcome = "✓ Error detected" if reactive_result.get('error_detected') else "✗ Missed error"

    print("│ " + proactive_outcome.ljust(36) + " │ " + reactive_outcome.ljust(37) + " │")
    print("└" + "─"*38 + "┴" + "─"*39 + "┘\n")

    print("RECOMMENDATION:")
    print("  • Use BOTH for defense in depth")
    print("  • Trust Plane: First line of defense (proactive)")
    print("  • LLM Judge: Safety net for validation (reactive)")
    print("  • Together: Complete data quality governance\n")


def main():
    """Main demo flow"""
    global VERBOSITY

    parser = argparse.ArgumentParser(
        description="Data Quality Governance Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Verbosity Levels:
  --verbose, -v   : Show detailed lineage and Trust Plane info
  --vv            : Show very verbose output with full JSON metadata
  (default)       : Normal output only

Examples:
  python3 demo_data_quality.py --mode proactive
  python3 demo_data_quality.py --mode reactive --verbose
  python3 demo_data_quality.py --mode both --vv
        """
    )
    parser.add_argument(
        "--mode",
        choices=["proactive", "reactive", "both"],
        default="both",
        help="Demo mode (default: both)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--vv",
        action="store_true",
        help="Enable very verbose logging"
    )
    args = parser.parse_args()

    # Set verbosity level
    if args.vv:
        VERBOSITY = 2
    elif args.verbose:
        VERBOSITY = 1
    else:
        VERBOSITY = 0

    print_banner()

    if VERBOSITY >= 1:
        log_verbose(f"[VERBOSE] Verbosity Level: {VERBOSITY} ({'very verbose' if VERBOSITY == 2 else 'verbose'})\n", 1)

    # Check for API key
    if not os.getenv("NVIDIA_API_KEY"):
        print("✗ ERROR: NVIDIA_API_KEY not found")
        print("Please set NVIDIA_API_KEY in .env file\n")
        return 1

    # Initialize LLM client
    print("Initializing components...")
    llm_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY")
    )
    print("✓ NVIDIA LLM client initialized\n")

    # Initialize OpenLineage
    lineage_url = os.getenv("OPENLINEAGE_URL", "http://localhost:5001")
    lineage_success = initialize_lineage(
        enabled=True,
        url=lineage_url,
        namespace="demo-data-quality"
    )
    print(f"✓ OpenLineage initialized\n")

    # Initialize Trust Plane
    trust_plane_success = initialize_trust_plane(
        enabled=True,
        policy_file="src/trust_plane/policies.yaml"
    )
    print(f"✓ Trust Plane initialized\n")

    # Load ground truth
    ground_truth = load_ground_truth()
    print(f"✓ Ground truth loaded ({len(ground_truth)} entries)\n")

    try:
        # Create and ingest stale docs
        temp_dir, file_paths = create_stale_docs()
        metrics = ingest_stale_docs(file_paths)

        # Run demos based on mode
        if args.mode in ["proactive", "both"]:
            proactive_result = run_proactive_mode(llm_client)
        else:
            proactive_result = None

        if args.mode in ["reactive", "both"]:
            reactive_result = run_reactive_mode(llm_client, ground_truth)
        else:
            reactive_result = None

        # Show comparison if both modes run
        if args.mode == "both":
            print_comparison(proactive_result, reactive_result)

        # Cleanup
        for f in file_paths:
            f.unlink()
        temp_dir.rmdir()

        print("="*80)
        print("Demo Complete!")
        print("="*80 + "\n")

        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        shutdown_trust_plane()
        shutdown_lineage()


if __name__ == "__main__":
    sys.exit(main())
