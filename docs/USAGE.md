# Usage Guide - Verbosity Levels

## Command-Line Options

All scripts support verbosity control via command-line flags:

| Flag | Level | What You See |
|------|-------|--------------|
| (none) | **Info** (default) | Info messages, warnings, errors, and results |
| `--quiet` or `-q` | **Errors Only** | Only error messages - cleanest output |
| `--verbose` or `-v` | **Debug** | Info + debug messages (API calls, tool execution) |
| `--vv` | **Very Verbose** | All messages including detailed execution traces |

## Examples

### Simple Test

```bash
# Normal output (recommended for demos)
python3 simple_test.py

# Clean output only
python3 simple_test.py --quiet

# Debug output (see what the agent is doing)
python3 simple_test.py --verbose

# Very verbose (see all internal details)
python3 simple_test.py --vv
```

### Demo Queries

```bash
# Normal output
python3 demo_queries.py

# Clean output for presentations
python3 demo_queries.py --quiet

# Debug to see tool calls
python3 demo_queries.py --verbose

# Full trace
python3 demo_queries.py --vv
```

### Interactive Mode

```bash
# Normal interactive mode
python3 main.py

# Quiet mode (minimal logs)
python3 main.py --quiet

# Debug mode (see agent reasoning)
python3 main.py --verbose

# Very verbose (see everything)
python3 main.py --vv
```

## What Each Level Shows

### Default (Info Level)
```
[INFO] Initialized NVIDIA client with model: meta/llama-3.1-70b-instruct
[INFO] Running agent on query: Is NeMo Retriever approved?...
[INFO] Reasoning iteration 1
[INFO] LLM requested 1 tool call(s)
[INFO] Executing tool: security_policy_checker
[INFO] ✓ security_policy_checker succeeded
[INFO] ✓ Agent completed: 2 iterations, 4 tool calls
```

### Quiet Mode
```
Initializing components...
✓ Ready!

Query: Is NeMo Retriever approved for production?

Answer: Yes, NeMo Retriever is approved for production deployment.

Tool calls: 4, Iterations: 2
```

### Verbose Mode (--verbose)
Adds `[DEBUG]` messages:
```
[DEBUG] Calling NVIDIA API with 2 messages
[DEBUG] Including 3 tools in request
[DEBUG] Received response with 1 choices
[DEBUG] Executing tool: security_policy_checker with args: ['library_name']
[DEBUG] Tool security_policy_checker returned: success=True
```

### Very Verbose Mode (--vv)
Adds `[VERBOSE]` messages with internal details and **verbatim LLM responses**:
```
[VERBOSE] Preparing LLM call with 2 messages
[VERBOSE] Available tools: ['security_policy_checker', 'cost_estimator', 'internal_docs_search']
[VERBOSE]   Message 1 [system]: You are a GenAIOps Documentation Assistant Agent...
[VERBOSE]   Message 2 [user]: Is NeMo Retriever approved for production?
[VERBOSE] ============================================================
[VERBOSE] VERBATIM LLM RESPONSE:
[VERBOSE] ------------------------------------------------------------
[VERBOSE] Content: (empty)
[VERBOSE]
Tool Calls (1):
[VERBOSE]   [1] ID: chatcmpl-tool-773a3b6908b84622bede0f1b52522083
[VERBOSE]       Type: function
[VERBOSE]       Function Name: security_policy_checker
[VERBOSE]       Function Arguments: {"library_name": "NeMo Retriever"}
[VERBOSE] ============================================================
[VERBOSE] Tool arguments: {'library_name': 'NeMo Retriever'}
[VERBOSE] Tool result success: True
```

**Features in Very Verbose Mode**:
- Shows actual message content being sent to NVIDIA API
- **Displays verbatim LLM response** including formatted tool calls
- Shows tool call IDs, types, and exact JSON arguments
- Reveals whether response has content, tool calls, or both

## Recommendations

### For Demonstrations
Use **quiet mode** for clean output:
```bash
python3 demo_queries.py --quiet
```

### For Development/Debugging
Use **verbose mode** to see what's happening:
```bash
python3 simple_test.py --verbose
```

### For Deep Debugging
Use **very verbose mode** to trace every step:
```bash
python3 simple_test.py --vv
```

### For Interactive Use
Use **default mode** (info level) - good balance:
```bash
python3 main.py
```

## Filtering Output

You can also pipe output to grep to filter specific messages:

```bash
# Only show tool-related messages
python3 demo_queries.py --vv 2>&1 | grep -i tool

# Only show errors
python3 demo_queries.py 2>&1 | grep ERROR

# Only show the final answers
python3 demo_queries.py --quiet
```

## Getting Help

```bash
python3 main.py --help
python3 simple_test.py --help
python3 demo_queries.py --help
```
