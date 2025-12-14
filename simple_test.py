#!/usr/bin/env python3
"""Simple single query test"""
import argparse
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

# Parse arguments
parser = argparse.ArgumentParser(description="Simple test query")
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

print("Initializing components...")

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
tool_registry.register(InternalDocsSearch(vectorstore=vectorstore, embedding_function=embedding_model))

agent = GenAIOpsAgent(llm_client=llm_client, tool_registry=tool_registry, max_iterations=10)

print("✓ Ready!\n")

# Simple query
query = "Is NeMo Retriever approved for production?"
print(f"Query: {query}\n")

result = agent.run(query)

if result["success"]:
    print(f"Answer: {result['answer']}\n")
    print(f"Tool calls: {result['tool_calls']}, Iterations: {result['iterations']}")
else:
    print(f"Error: {result.get('error')}")
