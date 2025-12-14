#!/usr/bin/env python3
"""Debug script to check NeMo Guardrails initialization"""
import os
import sys

print("=" * 70)
print("NeMo Guardrails Diagnostic")
print("=" * 70)
print()

# Step 1: Check .env loading
print("Step 1: Loading .env file...")
from dotenv import load_dotenv
load_dotenv()

nvidia_api_key = os.getenv("NVIDIA_API_KEY")
print(f"  NVIDIA_API_KEY present: {'✓ YES' if nvidia_api_key else '✗ NO'}")
if nvidia_api_key:
    print(f"  NVIDIA_API_KEY length: {len(nvidia_api_key)} chars")
print()

# Step 2: Check NeMo package
print("Step 2: Checking NeMo Guardrails package...")
try:
    from nemoguardrails import RailsConfig, LLMRails
    import nemoguardrails
    print(f"  ✓ NeMo Guardrails installed: v{nemoguardrails.__version__}")
except ImportError as e:
    print(f"  ✗ NeMo Guardrails import failed: {e}")
    sys.exit(1)
print()

# Step 3: Check langchain-openai
print("Step 3: Checking langchain-openai...")
try:
    import langchain_openai
    print(f"  ✓ langchain-openai installed")
except ImportError as e:
    print(f"  ✗ langchain-openai import failed: {e}")
print()

# Step 4: Initialize wrapper
print("Step 4: Initializing NemoGuardrailsWrapper...")
sys.path.insert(0, 'src')

from src.guardrails.nemo_guardrails import NemoGuardrailsWrapper, NEMO_AVAILABLE

print(f"  NEMO_AVAILABLE: {NEMO_AVAILABLE}")

wrapper = NemoGuardrailsWrapper()

status = wrapper.get_status()
print(f"  NeMo Available: {status['nemo_available']}")
print(f"  NeMo Enabled: {status['nemo_enabled']}")
print(f"  Using Fallback: {status['using_fallback']}")
print()

# Step 5: Show environment variables that NeMo needs
print("Step 5: Environment variables after wrapper init...")
print(f"  NVIDIA_API_KEY: {'✓ SET' if os.getenv('NVIDIA_API_KEY') else '✗ NOT SET'}")
print(f"  OPENAI_API_KEY: {'✓ SET' if os.getenv('OPENAI_API_KEY') else '✗ NOT SET'}")
print(f"  OPENAI_API_BASE: {os.getenv('OPENAI_API_BASE', 'NOT SET')}")
print()

# Step 6: Test input check
print("Step 6: Testing input check...")
passed, reason = wrapper.check_input("Is NeMo Retriever approved?")
print(f"  Test query passed: {passed}")
if not passed:
    print(f"  Reason: {reason}")
print()

print("=" * 70)
if status['nemo_enabled']:
    print("✅ NeMo Guardrails is ENABLED and working!")
else:
    print("❌ NeMo Guardrails is NOT enabled - using fallback")
    print("\nPlease check:")
    print("  1. NVIDIA_API_KEY is set in .env file")
    print("  2. Python cache is cleared: rm -rf **/__pycache__")
    print("  3. You're using the correct Python environment")
print("=" * 70)
