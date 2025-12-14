#!/usr/bin/env python3
"""Test the agent with a sample query (non-interactive)"""
import sys

# Configuration
from config.settings import settings
from config.policies import APPROVED_LIBRARIES

# LLM Client
from src.llm.nvidia_client import NVIDIAClient

# Tools
from src.tools.registry import ToolRegistry
from src.tools.security_checker import SecurityPolicyChecker
from src.tools.cost_estimator import CostEstimator
from src.tools.docs_search import InternalDocsSearch

# RAG
from src.rag.embeddings import EmbeddingModel
from src.rag.vectorstore import VectorStore

# Agent
from src.orchestrator.agent import GenAIOpsAgent

# Guardrails
from src.guardrails.policy_checker import SimplePolicyChecker

def main():
    print("=" * 70)
    print("GenAIOps Agent - Test Query")
    print("=" * 70)

    # Initialize components
    print("\nInitializing...")

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

    guardrails_checker = SimplePolicyChecker()

    agent = GenAIOpsAgent(
        llm_client=llm_client,
        tool_registry=tool_registry,
        max_iterations=settings.max_iterations
    )

    print("✓ Initialized!\n")

    # Test queries
    test_queries = [
        "Is NeMo Retriever approved for production use?",
        "What is the cost of running a medium model with 5 million tokens per month?",
        "I need to deploy NeMo Retriever. Check if it's approved and estimate the cost for 10M tokens monthly.",
    ]

    for i, query in enumerate(test_queries, 1):
        print("\n" + "=" * 70)
        print(f"TEST {i}: {query}")
        print("=" * 70)

        result = agent.run(query)

        if result["success"]:
            # Check guardrails
            passed, violations = guardrails_checker.check(result["answer"])

            print(f"\n🤖 Answer:\n{result['answer']}\n")
            print(f"📊 Metadata:")
            print(f"  • Tool Calls: {result['tool_calls']}")
            print(f"  • Iterations: {result['iterations']}")
            print(f"  • Guardrails: {'✅ PASSED' if passed else '⚠️  WARNINGS'}")

            if not passed:
                print(f"\n⚠️  Violations:")
                for v in violations:
                    print(f"  • {v}")
        else:
            print(f"\n❌ Error: {result.get('error', 'Unknown error')}")

        if i < len(test_queries):
            print("\n" + "-" * 70)

    print("\n" + "=" * 70)
    print("✓ All tests complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
