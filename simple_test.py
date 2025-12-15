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

# OpenTelemetry observability
from src.observability import initialize_observability, shutdown_observability

# Parse arguments
parser = argparse.ArgumentParser(description="Simple test query")
parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
parser.add_argument('--vv', action='store_true', help='Enable very verbose logging')
parser.add_argument('--quiet', '-q', action='store_true', help='Show errors only')
parser.add_argument('--save-telemetry', type=str, metavar='PATH',
                    help='Save telemetry to file (default: telemetry_report.txt)')
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

# Determine file paths for telemetry
telemetry_json = None
telemetry_report = None
if args.save_telemetry:
    # If user provided a path, use it; otherwise use default
    if args.save_telemetry == 'True':  # argparse quirk when used as flag
        telemetry_report = "telemetry_report.txt"
    else:
        telemetry_report = args.save_telemetry

    # JSON file will be .json version
    telemetry_json = telemetry_report.replace('.txt', '.json') if telemetry_report.endswith('.txt') else telemetry_report + '.json'

# Initialize OpenTelemetry observability
initialize_observability(
    service_name="genaiops-agent",
    service_version="1.0.0",
    environment="development",
    enable_console=(not args.quiet),  # Disable console if quiet mode
    file_path=telemetry_json
)

try:
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

finally:
    # Shutdown and flush OpenTelemetry
    shutdown_observability()

    # Generate telemetry report if requested
    if telemetry_json and telemetry_report:
        from src.observability.file_exporter import save_telemetry_report
        save_telemetry_report(telemetry_json, telemetry_report)
