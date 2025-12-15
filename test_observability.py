#!/usr/bin/env python3
"""Test OpenTelemetry observability integration"""
import sys

# Initialize OpenTelemetry first
from src.observability import initialize_observability, shutdown_observability

print("=" * 70)
print("Testing OpenTelemetry Integration")
print("=" * 70)

# Initialize observability with console export
print("\n[1/4] Initializing OpenTelemetry...")
try:
    initialize_observability(
        service_name="genaiops-agent-test",
        service_version="1.0.0-test",
        environment="testing",
        enable_console=True
    )
    print("✓ OpenTelemetry initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize OpenTelemetry: {e}")
    sys.exit(1)

# Now import agent components
print("\n[2/4] Importing agent components...")
try:
    from src.llm.nvidia_client import NVIDIAClient
    from src.tools.registry import ToolRegistry
    from src.tools.security_checker import SecurityPolicyChecker
    from src.tools.cost_estimator import CostEstimator
    from src.orchestrator.agent import GenAIOpsAgent
    from config.settings import settings
    from config.policies import APPROVED_LIBRARIES
    print("✓ Components imported successfully")
except Exception as e:
    print(f"✗ Failed to import components: {e}")
    shutdown_observability()
    sys.exit(1)

# Initialize components
print("\n[3/4] Initializing agent components...")
try:
    # LLM client
    llm_client = NVIDIAClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model_name=settings.nvidia_model
    )

    # Tool registry
    tool_registry = ToolRegistry()

    # Add security checker (no RAG needed for this test)
    security_tool = SecurityPolicyChecker(APPROVED_LIBRARIES)
    tool_registry.register(security_tool)

    # Add cost estimator
    cost_tool = CostEstimator()
    tool_registry.register(cost_tool)

    # Create agent
    agent = GenAIOpsAgent(llm_client, tool_registry, max_iterations=5)

    print("✓ Agent initialized successfully")
    print(f"  - Registered tools: {tool_registry.list_tools()}")
except Exception as e:
    print(f"✗ Failed to initialize agent: {e}")
    import traceback
    traceback.print_exc()
    shutdown_observability()
    sys.exit(1)

# Run a simple test query
print("\n[4/4] Running test query with OpenTelemetry tracing...")
print("-" * 70)

test_query = "Is NeMo Retriever approved for production?"
print(f"\nQuery: {test_query}\n")

try:
    result = agent.run(test_query)

    print("\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Answer: {result['answer'][:200]}...")
    print(f"  Tool calls: {result['tool_calls']}")
    print(f"  Iterations: {result['iterations']}")

    print("\n✓ Test completed successfully!")
    print("\n" + "=" * 70)
    print("OpenTelemetry traces should appear above ☝️")
    print("=" * 70)

except Exception as e:
    print(f"\n✗ Test query failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Shutdown and flush telemetry
    print("\nShutting down OpenTelemetry...")
    shutdown_observability()
    print("✓ OpenTelemetry shutdown complete")
