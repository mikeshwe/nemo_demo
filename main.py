#!/usr/bin/env python3
"""GenAIOps Documentation Assistant Agent - Main CLI"""
import sys
import os
import argparse
from pathlib import Path

# Load .env FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

# Initialize OpenTelemetry observability
from src.observability import initialize_observability, shutdown_observability

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
from src.guardrails.nemo_guardrails import NemoGuardrailsWrapper

# Utils
from src.utils.logger import log_info, log_error, log_warning, set_log_level

def print_banner():
    """Print welcome banner"""
    print("\n" + "=" * 70)
    print(" " * 15 + "GenAIOps Documentation Assistant Agent")
    print(" " * 20 + "Powered by NVIDIA Nemotron")
    print("=" * 70)
    print()

def initialize_components():
    """Initialize all agent components

    Returns:
        tuple: (agent, guardrails_checker) or (None, None) on failure
    """
    try:
        # Validate configuration
        if not settings.validate():
            log_error("Configuration validation failed")
            print("\n❌ Configuration Error!")
            print("\nPlease ensure you have:")
            print("1. Copied .env.example to .env")
            print("2. Added your NVIDIA API key from https://build.nvidia.com")
            print("3. Saved the .env file")
            print("\nThen run this script again.")
            return None, None

        print("Initializing components...")

        # 1. Initialize LLM client
        print("  [1/6] Connecting to NVIDIA API...")
        llm_client = NVIDIAClient(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model_name=settings.nvidia_model
        )

        if not llm_client.validate_connection():
            log_error("Failed to connect to NVIDIA API")
            print("\n❌ Cannot connect to NVIDIA API")
            print("Please check:")
            print("- Your API key is correct")
            print("- You have internet connection")
            print("- The API endpoint is accessible")
            return None, None

        # 2. Initialize RAG components
        print("  [2/6] Loading embedding model...")
        embedding_model = EmbeddingModel()

        print("  [3/6] Connecting to vector store...")
        if not os.path.exists(settings.chroma_persist_dir):
            log_warning("Vector store not found. Run 'python scripts/setup_vectorstore.py' first.")
            print("\n⚠️  Vector store not initialized!")
            print("Please run: python scripts/setup_vectorstore.py")
            print("\nContinuing without document search capability...")
            vectorstore = None
        else:
            vectorstore = VectorStore(persist_directory=settings.chroma_persist_dir)

        # 3. Initialize tools
        print("  [4/6] Registering agent tools...")
        tool_registry = ToolRegistry()

        # Register tools
        tool_registry.register(SecurityPolicyChecker(approved_list=APPROVED_LIBRARIES))
        tool_registry.register(CostEstimator())

        if vectorstore:
            tool_registry.register(InternalDocsSearch(
                vectorstore=vectorstore,
                embedding_function=embedding_model
            ))
        else:
            log_warning("Skipping InternalDocsSearch tool (no vector store)")

        # 4. Initialize guardrails
        print("  [5/6] Setting up guardrails...")
        guardrails_checker = NemoGuardrailsWrapper()

        # 5. Create agent
        print("  [6/6] Building LangGraph agent...")
        agent = GenAIOpsAgent(
            llm_client=llm_client,
            tool_registry=tool_registry,
            max_iterations=settings.max_iterations
        )

        print("\n✅ All components initialized successfully!\n")

        return agent, guardrails_checker

    except Exception as e:
        log_error(f"Initialization failed: {e}")
        print(f"\n❌ Initialization failed: {e}")
        return None, None

def run_interactive_mode(agent, guardrails_checker):
    """Run interactive CLI chat mode

    Args:
        agent: GenAIOpsAgent instance
        guardrails_checker: NemoGuardrailsWrapper instance
    """
    # Show guardrails status
    status = guardrails_checker.get_status()
    print("🛡️  Guardrails Status:")
    print(f"   • NeMo Guardrails: {'✅ ENABLED' if status['nemo_enabled'] else '❌ Using Fallback'}")
    print(f"   • Fallback: {status['fallback_type']}")
    print()

    print("Available tools:")
    for tool_name in agent.list_available_tools():
        print(f"  • {tool_name}")

    print("\nType your questions or 'exit' to quit")
    print("-" * 70)

    while True:
        try:
            # Get user input
            user_input = input("\n🧑 You: ").strip()

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n👋 Goodbye!\n")
                break

            if not user_input:
                continue

            # Run agent
            print("\n🤖 Agent: [Processing...]")

            result = agent.run(user_input)

            if not result["success"]:
                print(f"\n❌ Error: {result.get('error', 'Unknown error')}")
                continue

            # Check guardrails on output
            passed, reason = guardrails_checker.check_output(result["answer"])

            if not passed:
                print("\n⚠️  Guardrails Warning:")
                print(f"  • {reason}")
                print()

            # Display answer
            print(f"\n🤖 Agent: {result['answer']}")

            # Display metadata
            guardrails_icon = "🛡️✅" if passed else "🛡️⚠️"
            guardrails_type = "NeMo" if guardrails_checker.is_enabled() else "Fallback"

            print(f"\n📊 Metadata:")
            print(f"  • Tool Calls: {result['tool_calls']}")
            print(f"  • Iterations: {result['iterations']}")
            print(f"  • Guardrails: {guardrails_icon} {guardrails_type} {'PASSED' if passed else 'WARNINGS'}")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break

        except Exception as e:
            log_error(f"Error during interaction: {e}")
            print(f"\n❌ Error: {e}")

def main():
    """Main entry point"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="GenAIOps Documentation Assistant Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Verbosity Levels:
  --quiet    : Errors only
  --verbose  : Show debug messages
  --vv       : Show very verbose messages (all details)
  (default)  : Show info and warnings

Examples:
  python main.py              # Normal output
  python main.py --verbose    # Debug output
  python main.py --vv         # Very verbose output
  python main.py --quiet      # Errors only
        """
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable debug logging')
    parser.add_argument('--vv', action='store_true', help='Enable very verbose logging (all details)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Show errors only')
    parser.add_argument('--save-telemetry', type=str, metavar='PATH',
                        help='Save telemetry to file (default: telemetry_report.txt)')

    args = parser.parse_args()

    # Set log level based on arguments
    if args.quiet:
        set_log_level(0)  # Errors only
    elif args.vv:
        set_log_level(3)  # Verbose
    elif args.verbose:
        set_log_level(2)  # Debug
    else:
        set_log_level(1)  # Info (default)

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
        environment="production",
        enable_console=(not args.save_telemetry),  # Disable console if saving to file
        file_path=telemetry_json
    )

    try:
        print_banner()

        # Initialize components
        agent, guardrails_checker = initialize_components()

        if not agent:
            return 1

        # Run interactive mode
        try:
            run_interactive_mode(agent, guardrails_checker)
            return 0

        except Exception as e:
            log_error(f"Fatal error: {e}")
            print(f"\n❌ Fatal error: {e}")
            return 1

    finally:
        # Shutdown and flush OpenTelemetry
        shutdown_observability()

        # Generate telemetry report if requested
        if telemetry_json and telemetry_report:
            from src.observability.file_exporter import save_telemetry_report
            save_telemetry_report(telemetry_json, telemetry_report)

if __name__ == "__main__":
    sys.exit(main())
