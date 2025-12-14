#!/usr/bin/env python3
"""Demo with multiple test queries"""
import argparse

# Load .env FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from src.utils.logger import set_log_level
from config.policies import APPROVED_LIBRARIES
from src.llm.nvidia_client import NVIDIAClient
from src.tools.registry import ToolRegistry
from src.tools.security_checker import SecurityPolicyChecker
from src.tools.cost_estimator import CostEstimator
from src.tools.docs_search import InternalDocsSearch
from src.rag.embeddings import EmbeddingModel
from src.rag.vectorstore import VectorStore
from src.orchestrator.agent import GenAIOpsAgent
from src.guardrails.nemo_guardrails import NemoGuardrailsWrapper

# Parse arguments
parser = argparse.ArgumentParser(description="Demo with multiple queries")
parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
parser.add_argument('--vv', action='store_true', help='Enable very verbose logging')
parser.add_argument('--quiet', '-q', action='store_true', help='Show errors only')
args = parser.parse_args()

# Set log level
if args.quiet:
    set_log_level(0)
elif args.vv:
    set_log_level(3)
elif args.verbose:
    set_log_level(2)
else:
    set_log_level(1)

print("=" * 70)
print("GenAIOps Agent - Demo Queries")
print("=" * 70)
print("\nInitializing...", end="")

llm_client = NVIDIAClient(settings.nvidia_api_key, settings.nvidia_base_url, settings.nvidia_model)
embedding_model = EmbeddingModel()
vectorstore = VectorStore(persist_directory=settings.chroma_persist_dir)
tool_registry = ToolRegistry()
tool_registry.register(SecurityPolicyChecker(approved_list=APPROVED_LIBRARIES))
tool_registry.register(CostEstimator())
tool_registry.register(InternalDocsSearch(vectorstore=vectorstore, embedding_function=embedding_model))
agent = GenAIOpsAgent(llm_client=llm_client, tool_registry=tool_registry)
guardrails = NemoGuardrailsWrapper()

print(" ✓\n")

# Show guardrails status
status = guardrails.get_status()
print("🛡️  Guardrails Status:")
print(f"   • NeMo Guardrails: {'✅ ENABLED' if status['nemo_enabled'] else '❌ Using Fallback'}")
print(f"   • Fallback: {status['fallback_type']}")
print()

queries = [
    "Is NeMo Retriever approved for production?",
    "What is the cost for running a medium model with 5 million tokens per month?",
    "What are the GPU requirements for NeMo Retriever?",
]

for i, query in enumerate(queries, 1):
    print("\n" + "=" * 70)
    print(f"Query {i}: {query}")
    print("=" * 70)

    result = agent.run(query)

    if result["success"]:
        # Check output with NeMo Guardrails
        passed, reason = guardrails.check_output(result["answer"])
        guardrails_icon = "🛡️✅" if passed else "🛡️⚠️"
        guardrails_type = "NeMo" if guardrails.is_enabled() else "Fallback"

        print(f"\n🤖 {result['answer']}")
        print(f"\n📊 {result['tool_calls']} tool calls | {result['iterations']} iterations | {guardrails_icon} {guardrails_type} guardrails")
        if not passed:
            print(f"   ⚠️  Guardrails concern: {reason}")
    else:
        print(f"\n❌ {result.get('error')}")

print("\n" + "=" * 70)
print("Demo complete!")
print("=" * 70)
