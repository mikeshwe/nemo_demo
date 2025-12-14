#!/usr/bin/env python3
"""Test script to verify NVIDIA API connectivity"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.llm.nvidia_client import NVIDIAClient

def main():
    print("=" * 60)
    print("NVIDIA API Connection Test")
    print("=" * 60)

    # Validate settings
    if not settings.validate():
        print("\n✗ Configuration invalid. Please check your .env file.")
        print("\nSteps to fix:")
        print("1. Copy .env.example to .env")
        print("2. Add your NVIDIA API key from https://build.nvidia.com")
        print("3. Run this script again")
        sys.exit(1)

    print(f"\nConfiguration:")
    print(f"  Base URL: {settings.nvidia_base_url}")
    print(f"  Model: {settings.nvidia_model}")
    print(f"  API Key: {settings.nvidia_api_key[:20]}...")

    # Create client
    client = NVIDIAClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model_name=settings.nvidia_model
    )

    # Test connection
    if client.validate_connection():
        print("\n" + "=" * 60)
        print("✓ SUCCESS! NVIDIA API is working correctly.")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("✗ FAILED! Could not connect to NVIDIA API.")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("- Verify your API key is correct")
        print("- Check your internet connection")
        print("- Visit https://build.nvidia.com to manage your API keys")
        return 1

if __name__ == "__main__":
    sys.exit(main())
