#!/usr/bin/env python3
"""
Langfuse Observability Demo

This script demonstrates Langfuse LLM observability features:
- Interactive trace visualization
- Automatic cost tracking
- Quality and efficiency scoring
- Tool execution logging
- Multi-step agent reasoning

Run this demo, then open http://localhost:3000 to explore traces!
"""
import sys
import time
from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from src.utils.logger import set_log_level, log_info
from config.policies import APPROVED_LIBRARIES
from src.llm.nvidia_client import NVIDIAClient
from src.tools.registry import ToolRegistry
from src.tools.security_checker import SecurityPolicyChecker
from src.tools.cost_estimator import CostEstimator
from src.tools.docs_search import InternalDocsSearch
from src.rag.embeddings import EmbeddingModel
from src.rag.vectorstore import VectorStore
from src.orchestrator.agent import GenAIOpsAgent

# Langfuse observability
from src.observability.langfuse_integration import initialize_langfuse, shutdown_langfuse

def print_banner():
    """Print demo banner"""
    print("\n" + "=" * 80)
    print(" " * 25 + "🔍 LANGFUSE OBSERVABILITY DEMO")
    print(" " * 20 + "LLM Analytics & Cost Tracking")
    print("=" * 80)
    print("\nThis demo will:")
    print("  1. Run multiple agent queries with different complexity levels")
    print("  2. Log all LLM calls, tool executions, and costs to Langfuse")
    print("  3. Track quality scores (success rate, efficiency)")
    print("  4. Generate interactive traces for exploration")
    print("\n" + "-" * 80)

def print_langfuse_instructions():
    """Print instructions for viewing Langfuse dashboard"""
    print("\n" + "=" * 80)
    print("📊 VIEW RESULTS IN LANGFUSE DASHBOARD")
    print("=" * 80)
    print("\n1. Ensure Langfuse is running:")
    print("   docker-compose -f docker-compose.langfuse.yml up -d")
    print("\n2. Open the dashboard:")
    print("   → http://localhost:3000")
    print("\n3. Click 'Traces' in the sidebar to see:")
    print("   • All agent runs from this demo")
    print("   • Execution timeline for each query")
    print("   • LLM calls with full input/output")
    print("   • Tool executions with arguments")
    print("   • Cost per query in USD")
    print("   • Success and efficiency scores")
    print("\n4. Click any trace to drill down into:")
    print("   • Individual LLM generations")
    print("   • Token usage breakdown")
    print("   • Tool execution details")
    print("   • Timing information")
    print("\n" + "=" * 80 + "\n")

def check_langfuse_server():
    """Check if Langfuse server is running"""
    import requests
    try:
        response = requests.get("http://localhost:3000/api/public/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def run_demo():
    """Run Langfuse demo with multiple queries"""

    # Set to info level for clean output
    set_log_level(1)

    print_banner()

    # Check if Langfuse server is running
    print("\n🔍 Checking Langfuse server...")
    if check_langfuse_server():
        print("   ✅ Langfuse is running at http://localhost:3000")
    else:
        print("   ⚠️  Langfuse server not detected!")
        print("\n   Please start Langfuse first:")
        print("   docker-compose -f docker-compose.langfuse.yml up -d")
        print("\n   Then run this demo again.")
        print("\n   (Demo will continue anyway, but traces won't be visible)")
        time.sleep(2)

    # Initialize Langfuse
    print("\n📡 Initializing Langfuse integration...")
    langfuse_success = initialize_langfuse(enabled=True)
    if langfuse_success:
        print("   ✅ Langfuse initialized successfully!")
    else:
        print("   ⚠️  Langfuse initialization failed, continuing without it")
        print("   (This is expected if Langfuse server is not running)")

    # Initialize agent components
    print("\n🤖 Initializing agent components...")
    try:
        llm_client = NVIDIAClient(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model_name=settings.nvidia_model
        )

        embedding_model = EmbeddingModel()
        vectorstore = VectorStore(persist_directory=settings.chroma_persist_dir)

        tool_registry = ToolRegistry()
        tool_registry.register(SecurityPolicyChecker(approved_list=APPROVED_LIBRARIES))
        tool_registry.register(CostEstimator())
        tool_registry.register(InternalDocsSearch(
            vectorstore=vectorstore,
            embedding_function=embedding_model
        ))

        agent = GenAIOpsAgent(
            llm_client=llm_client,
            tool_registry=tool_registry,
            max_iterations=10
        )

        print("   ✅ Agent ready!\n")

    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        return 1

    # Demo queries with different characteristics
    demo_queries = [
        {
            "query": "Is NeMo Retriever approved for production?",
            "description": "Simple policy check (1 tool call expected)",
            "category": "security_policy"
        },
        {
            "query": "What is the cost for running a medium model with 5 million tokens per month?",
            "description": "Cost estimation (1 tool call expected)",
            "category": "cost_estimation"
        },
        {
            "query": "What are the GPU requirements for NeMo Retriever?",
            "description": "Documentation search with RAG (1 tool call expected)",
            "category": "documentation"
        },
        {
            "query": "Is TensorRT approved and what would it cost to run at 10M tokens monthly?",
            "description": "Multi-step reasoning (2 tool calls expected)",
            "category": "multi_step"
        },
    ]

    print("\n" + "=" * 80)
    print(f"RUNNING {len(demo_queries)} DEMO QUERIES")
    print("=" * 80)
    print("\nEach query will be logged to Langfuse with:")
    print("  • Full trace of agent execution")
    print("  • LLM generations with token usage")
    print("  • Tool executions with results")
    print("  • Cost in USD")
    print("  • Quality scores (success, efficiency)")
    print()

    results = []
    total_cost = 0.0

    for i, demo in enumerate(demo_queries, 1):
        print("\n" + "-" * 80)
        print(f"Query {i}/{len(demo_queries)}: {demo['description']}")
        print("-" * 80)
        print(f"\n❓ {demo['query']}\n")

        try:
            # Run agent (this will create a Langfuse trace automatically)
            result = agent.run(demo['query'])

            if result["success"]:
                print(f"✅ Success!")
                print(f"\n💬 Answer: {result['answer']}\n")
                print(f"📊 Metrics:")
                print(f"   • Tool Calls: {result['tool_calls']}")
                print(f"   • Iterations: {result['iterations']}")
                print(f"   • Efficiency: {((1 - result['iterations'] / 10) * 100):.0f}%")

                # Estimate cost (approximate based on typical usage)
                estimated_cost = result['iterations'] * 0.002  # ~$0.002 per iteration
                total_cost += estimated_cost
                print(f"   • Estimated Cost: ${estimated_cost:.4f} USD")

                results.append({
                    "query": demo['query'],
                    "success": True,
                    "tool_calls": result['tool_calls'],
                    "iterations": result['iterations'],
                    "cost": estimated_cost
                })
            else:
                print(f"❌ Failed: {result.get('error', 'Unknown error')}")
                results.append({
                    "query": demo['query'],
                    "success": False
                })

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "query": demo['query'],
                "success": False,
                "error": str(e)
            })

        # Small delay between queries for readability
        if i < len(demo_queries):
            time.sleep(1)

    # Summary
    print("\n" + "=" * 80)
    print("DEMO SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results if r.get("success", False))
    total_tool_calls = sum(r.get("tool_calls", 0) for r in results)
    total_iterations = sum(r.get("iterations", 0) for r in results)

    print(f"\n📊 Overall Statistics:")
    print(f"   • Total Queries: {len(results)}")
    print(f"   • Successful: {successful}/{len(results)}")
    print(f"   • Success Rate: {(successful/len(results)*100):.0f}%")
    print(f"   • Total Tool Calls: {total_tool_calls}")
    print(f"   • Total Iterations: {total_iterations}")
    print(f"   • Estimated Total Cost: ${total_cost:.4f} USD")
    print(f"   • Avg Cost per Query: ${(total_cost/len(results)):.4f} USD")

    print("\n💰 Cost Breakdown:")
    for i, r in enumerate(results, 1):
        if r.get("success"):
            print(f"   Query {i}: ${r['cost']:.4f}")

    print_langfuse_instructions()

    return 0

def main():
    """Main entry point"""
    try:
        return run_demo()
    finally:
        # Always shutdown Langfuse to flush data
        print("📡 Flushing Langfuse data...")
        shutdown_langfuse()
        print("   ✅ Done!\n")

if __name__ == "__main__":
    sys.exit(main())
