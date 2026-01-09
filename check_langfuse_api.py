#!/usr/bin/env python3
"""Check Langfuse SDK API"""

from langfuse import Langfuse

# Create client
client = Langfuse()

# List all public methods
methods = [m for m in dir(client) if not m.startswith('_')]

print("Langfuse SDK methods and attributes:")
print("-" * 50)
for method in sorted(methods):
    obj = getattr(client, method)
    if callable(obj):
        print(f"  ✓ {method}() - method")
    else:
        print(f"  - {method} - attribute")
