# What Runs Where: NVIDIA vs Local

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR MacBook (Local)                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LangGraph Agent Orchestrator                               │ │
│  │ - State management                                         │ │
│  │ - Graph execution (ReAct loop)                             │ │
│  │ - Tool routing                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Agent Tools (Local Execution)                              │ │
│  │ - SecurityPolicyChecker   (checks Python dict)             │ │
│  │ - CostEstimator          (calculates with Python)          │ │
│  │ - InternalDocsSearch     (queries ChromaDB)                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ RAG Pipeline (Local)                                       │ │
│  │ - ChromaDB vector store   (local database)                 │ │
│  │ - SentenceTransformers    (local embeddings model)         │ │
│  │ - Document indexing       (local processing)               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Guardrails (Local)                                         │ │
│  │ - SimplePolicyChecker     (regex validation)               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│                            ↓ ↑                                   │
│                      HTTPS API Call                              │
│                (only for LLM reasoning)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ ↑
         ┌────────────────────────────────────────┐
         │   NVIDIA API Catalog (Remote Cloud)    │
         │                                        │
         │  ┌──────────────────────────────────┐ │
         │  │  Nemotron NIM                    │ │
         │  │  (LLM Inference)                 │ │
         │  │                                  │ │
         │  │  - Reasoning                     │ │
         │  │  - Decision making               │ │
         │  │  - Tool selection                │ │
         │  │  - Answer generation             │ │
         │  │                                  │ │
         │  │  Model: meta/llama-3.1-70b      │ │
         │  └──────────────────────────────────┘ │
         └────────────────────────────────────────┘
```

## What Runs on NVIDIA Nemotron NIM API ☁️

**ONLY the LLM reasoning and text generation:**

1. **Reasoning** - "What should I do next?"
   - Analyzing the user's query
   - Deciding which tool to call
   - Determining if more information is needed

2. **Tool Selection** - "Which tool should I use?"
   - Looking at available tools (security_policy_checker, cost_estimator, internal_docs_search)
   - Choosing the appropriate tool based on the query
   - Generating tool call with proper arguments

3. **Response Generation** - "How should I answer?"
   - Synthesizing information from tool results
   - Generating natural language responses
   - Formatting the final answer

### What Gets Sent to NVIDIA API:
```python
{
  "model": "meta/llama-3.1-70b-instruct",
  "messages": [
    {"role": "system", "content": "You are a GenAIOps Documentation Assistant..."},
    {"role": "user", "content": "Is NeMo Retriever approved for production?"},
    # ... conversation history
  ],
  "tools": [
    {"function": {"name": "security_policy_checker", ...}},
    {"function": {"name": "cost_estimator", ...}},
    {"function": {"name": "internal_docs_search", ...}}
  ],
  "temperature": 0.2,
  "max_tokens": 1024
}
```

### What Comes Back from NVIDIA API:
```python
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Calling tools...",
      "tool_calls": [{
        "function": {
          "name": "security_policy_checker",
          "arguments": '{"library_name": "NeMo Retriever"}'
        }
      }]
    }
  }]
}
```

## What Runs Locally on Your MacBook 💻

**Everything else:**

### 1. Agent Orchestration (LangGraph)
- **Location**: `src/orchestrator/`
- **What it does**:
  - Manages the ReAct loop (Reasoning → Acting → Observing)
  - Routes tool calls to local functions
  - Maintains conversation state
  - Decides when to call the NVIDIA API
  - Handles iterations and termination

### 2. Tool Execution
- **Location**: `src/tools/`
- **What it does**:

  **SecurityPolicyChecker**:
  ```python
  # This runs on YOUR computer, not NVIDIA's
  def execute(library_name):
      is_approved = library_name in APPROVED_LIBRARIES  # Python dict lookup
      return {"is_approved": is_approved}
  ```

  **CostEstimator**:
  ```python
  # This runs on YOUR computer, not NVIDIA's
  def execute(model_size, tokens_per_month):
      cost = (tokens_per_month / 1_000_000) * PRICING_TABLE[model_size]  # Math
      return {"monthly_cost_usd": cost}
  ```

  **InternalDocsSearch** (RAG):
  ```python
  # This runs on YOUR computer, not NVIDIA's
  def execute(query):
      results = vectorstore.similarity_search(query)  # ChromaDB query
      return {"documents": results}
  ```

### 3. RAG Pipeline (ChromaDB + Embeddings)
- **Location**: `src/rag/`
- **What it does**:
  - Stores 17 document chunks in local ChromaDB database
  - Uses local SentenceTransformers model for embeddings
  - Performs vector similarity search locally
  - No data leaves your machine

### 4. Guardrails
- **Location**: `src/guardrails/`
- **What it does**:
  - Validates responses with regex patterns
  - Checks for policy violations
  - All processing happens locally

### 5. Memory/State
- **Everything in memory** - conversation state, tool results, observations

## Data Flow Example

Let's trace a query: **"Is NeMo Retriever approved for production?"**

### Step 1: Local Processing
```
User Query (Local)
    ↓
LangGraph Agent (Local)
    ↓
Prepare messages + tool definitions (Local)
```

### Step 2: NVIDIA API Call #1 ☁️
```
Send to NVIDIA API:
  - System prompt
  - User query
  - 3 tool definitions

NVIDIA Nemotron Processes:
  - Reads the query
  - Thinks: "I need to check security policy"
  - Decides: "Call security_policy_checker tool"

Returns to Local:
  - Tool call: security_policy_checker("NeMo Retriever")
```

### Step 3: Local Tool Execution
```
LangGraph (Local) receives tool call
    ↓
Tool Execution Node (Local)
    ↓
SecurityPolicyChecker.execute(library_name="NeMo Retriever")  [LOCAL]
    ↓
Check: "NeMo Retriever" in APPROVED_LIBRARIES  [LOCAL PYTHON DICT]
    ↓
Result: {"is_approved": True}  [LOCAL]
```

### Step 4: NVIDIA API Call #2 ☁️
```
Send to NVIDIA API:
  - Previous conversation
  - Tool result: {"is_approved": True}

NVIDIA Nemotron Processes:
  - Reads tool result
  - Thinks: "The tool says it's approved"
  - Decides: "I can now answer the user"
  - Generates: "Yes, NeMo Retriever is approved for production deployment."

Returns to Local:
  - Final answer text
```

### Step 5: Local Post-Processing
```
Guardrails Check (Local)
    ↓
Response Formatting (Local)
    ↓
Display to User (Local)
```

## Cost & Performance Implications

### What Costs Money (NVIDIA API) 💰
- **LLM inference calls only** (typically 2 per query in ReAct loop)
- Charged per token (input + output)
- Example: ~1,000 tokens per typical query cycle

### What's Free (Local) 🆓
- Tool executions (instant, no API call)
- RAG search (ChromaDB query, ~50ms)
- Embedding generation (SentenceTransformers, ~100ms)
- Guardrails checking (regex, ~1ms)
- State management (in-memory, instant)

## Why This Hybrid Architecture?

### Advantages ✅

1. **Cost Efficiency**
   - Only pay for LLM reasoning, not tool execution
   - RAG search is free (local ChromaDB)
   - Embeddings are free (local model)

2. **Speed**
   - Tools execute instantly (no network latency)
   - Only 2 API calls per query instead of many

3. **Privacy**
   - Your internal documentation never leaves your machine
   - Tool logic and data stays local
   - Only high-level queries/responses go to NVIDIA

4. **Flexibility**
   - Can add unlimited tools without API changes
   - Can process sensitive data locally
   - Can work with local databases/files

### What This Demonstrates 🎯

This architecture shows you understand:
- **Hybrid deployment patterns** (common in production)
- **Cost optimization** (minimize expensive GPU calls)
- **Data privacy** (keep sensitive data local)
- **NVIDIA NIM integration** (proper use of inference services)
- **Agent orchestration** (LangGraph managing the flow)

## Verification

To see exactly when NVIDIA API is called, run:
```bash
python3 simple_test.py --vv 2>&1 | grep "Calling NVIDIA API"
```

You'll see:
```
[DEBUG] Calling NVIDIA API with 2 messages   # Iteration 1: Decide what to do
[DEBUG] Calling NVIDIA API with 8 messages   # Iteration 2: Generate answer
```

**Only 2 API calls** for the entire query, even though 3 tools are available and 1 tool was executed!

## Summary

| Component | Runs On | Purpose |
|-----------|---------|---------|
| **LLM Reasoning** | ☁️ NVIDIA NIM API | Decide what to do, generate answers |
| **Tool Execution** | 💻 Your Mac | Execute business logic locally |
| **RAG Search** | 💻 Your Mac | Search documents with ChromaDB |
| **Embeddings** | 💻 Your Mac | SentenceTransformers model |
| **Orchestration** | 💻 Your Mac | LangGraph manages the flow |
| **Guardrails** | 💻 Your Mac | Validate responses locally |
| **State** | 💻 Your Mac | In-memory conversation tracking |

**Bottom line**: NVIDIA Nemotron NIM API is ONLY used for the "brain" (LLM reasoning). Everything else runs on your local machine!
