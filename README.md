# GenAIOps Documentation Assistant Agent

A production-ready Agentic AI prototype demonstrating NVIDIA's accelerated computing technologies for Generative AI Operations (GenAIOps). This agent functions as a **"DevOps Knowledge Agent"** that performs complex, multi-step queries using reasoning, specialized tools, and safety guardrails.

## 🚀 Overview

This project showcases:
- **Hybrid Deployment**: Local LangGraph orchestration + Remote NVIDIA LLM API inference
- **ReAct Loop**: Reasoning and Acting pattern for multi-step problem solving
- **RAG (Retrieval-Augmented Generation)**: ChromaDB-powered document search
- **Agent Tools**: Security policy checking, cost estimation, and documentation search
- **NeMo Guardrails**: Enterprise-grade safety validation with NVIDIA's NeMo Guardrails
- **AI Observability**: OpenTelemetry instrumentation for comprehensive tracing and monitoring

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
└────────────────────┬────────────────────────────────────────┘
                     │
           ┌─────────▼──────────┐
           │  LangGraph Agent   │  (Local - macOS)
           │   Orchestrator     │
           └─────────┬──────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼────┐  ┌───▼────┐  ┌───▼─────┐
   │ Docs    │  │Security│  │  Cost   │  (Local Tools)
   │ Search  │  │Checker │  │Estimator│
   └────┬────┘  └────────┘  └─────────┘
        │
   ┌────▼────┐
   │ChromaDB │  (Local Vector Store)
   └─────────┘

      ┌─────────────────┐
      │  NVIDIA NIM API │  (Remote GPU Inference)
      │   Llama 3.1 70B │
      └─────────────────┘

   ┌────────────┐
   │NeMo        │  (Local Safety Layer)
   │Guardrails  │
   └────────────┘
```

## 🔭 AI Observability

This demo includes comprehensive OpenTelemetry instrumentation for AI observability, demonstrating production-ready monitoring practices for agentic AI systems.

### What's Instrumented

- ✅ **Agent Execution**: Complete agent runs with query, iterations, and tool calls
- ✅ **LLM API Calls**: Auto-instrumented OpenAI SDK capturing all NVIDIA API calls
- ✅ **Tool Executions**: Individual tool calls with arguments, results, and timing
- ✅ **Guardrails**: Input/output validation with NeMo Guardrails or fallback
- ✅ **RAG Operations**: Embedding generation and vector search with ChromaDB
- ✅ **Iterations**: Each reasoning step with decision tracking

### Viewing Telemetry

All scripts automatically export OpenTelemetry traces to console/stdout for easy demo visibility:

```bash
# Run any script to see traces
python simple_test.py

# Traces will appear in JSON format showing:
# - Span hierarchy (parent → child relationships)
# - Timing information (duration of each operation)
# - Custom attributes (iteration count, tool names, success/failure)
# - Auto-instrumented LLM calls (model, temperature, tokens, prompts)
```

### Saving Telemetry Reports

Export telemetry to a file with visualizations and metrics:

```bash
# Save telemetry report with default name (telemetry_report.txt)
python simple_test.py --save-telemetry telemetry_report.txt

# This creates two files:
# - telemetry_report.txt (human-readable report with ASCII graphs)
# - telemetry_report.json (raw telemetry data)

# Use with quiet mode for clean output
python simple_test.py --quiet --save-telemetry my_report.txt
```

**What's in the report:**
- 📊 **Summary Statistics**: Total spans, iterations, tool calls, LLM API calls
- ⏱️ **Execution Timeline**: ASCII visualization of span hierarchy and timing
- 🪙 **Token Usage Chart**: Bar chart showing token consumption per LLM call
- 🔧 **Tool Timing**: Performance metrics for each tool execution

**Example output:**
```
================================================================================
TELEMETRY SUMMARY
================================================================================

📊 Overall Statistics:
  Total Spans: 12
  Agent Runs: 1
  Iterations: 2
  Tool Calls: 2
  LLM API Calls: 4

🤖 Agent Execution:
  Query: Is NeMo Retriever approved for production?
  Iterations: 2
  Tool Calls: 1
  Success: True
  Duration: 17735.24 ms

🧠 LLM API Calls:
  Total Calls: 4
  Total Tokens: 2664
  Input Tokens: 2618
  Output Tokens: 46
  Avg Duration: 4128.53 ms

================================================================================
EXECUTION TIMELINE
================================================================================

agent.run                      [████████████████████████████████████████] 17735.24 ms
  agent.iteration                [████████                                ]  3754.85 ms
    guardrails.input_check         [  ███                                   ]  1358.60 ms
    openai.chat                    [     ██                                 ]  1221.40 ms
  agent.tool_execution           [        █                               ]     0.27 ms
  agent.iteration                [        ███████████████████████████████ ] 13976.06 ms
```

### Trace Structure

Each agent run creates a hierarchical trace:

```
agent.run (root span)
├── agent.iteration (reasoning step)
│   ├── guardrails.input_check (safety validation)
│   ├── openai.chat (LLM API call - auto-instrumented)
│   ├── agent.tool_execution
│   │   └── tool.execute.security_policy_checker
│   └── guardrails.output_check (safety validation)
└── agent.iteration (final answer)
    ├── openai.chat (LLM API call)
    └── guardrails.output_check
```

### Production Export

While this demo uses console export, the instrumentation is production-ready and can export to:

- **Jaeger** / **Zipkin**: Distributed tracing visualization
- **Prometheus**: Metrics collection and alerting
- **Datadog** / **New Relic** / **Honeycomb**: Cloud observability platforms
- **OTLP**: Any OpenTelemetry-compatible backend

See [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) for detailed configuration and advanced usage.

## 📋 Prerequisites

- **Python**: 3.10 or higher
- **Operating System**: macOS, Linux, or Windows
- **Internet Connection**: Required for NVIDIA API access
- **NVIDIA API Key**: Free from NVIDIA API Catalog

## 🔑 Getting an NVIDIA API Key

1. **Visit NVIDIA API Catalog**
   - Go to [https://build.nvidia.com](https://build.nvidia.com)
   - Click "Sign In" or "Get Started"

2. **Create an Account** (if you don't have one)
   - Sign up with your email address
   - Verify your email
   - Complete your profile

3. **Access the API Catalog**
   - Once logged in, you'll see various NVIDIA models
   - Look for "Nemotron" or "LLama" models

4. **Generate API Key**
   - Click on any model (e.g., "llama-3.1-nemotron-70b-instruct")
   - Look for the "Get API Key" or "API Key" section
   - Click "Generate API Key"
   - **Copy the key immediately** (you won't see it again!)

5. **Save Your API Key**
   - Store it securely (e.g., password manager)
   - You'll add it to the `.env` file in the next steps

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd nemo-demo
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- LangGraph (agent orchestration)
- OpenAI SDK (for NVIDIA API compatibility)
- ChromaDB (vector database)
- SentenceTransformers (embeddings)
- Python-dotenv (environment management)

### 4. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your NVIDIA API key
nano .env  # or use your preferred editor
```

Update the `.env` file:

```bash
NVIDIA_API_KEY=your_actual_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-70b-instruct
```

### 5. Initialize Vector Store

```bash
python scripts/setup_vectorstore.py
```

This will:
- Load the sample documentation files
- Generate embeddings using SentenceTransformers
- Index documents in ChromaDB
- Run a test query to verify setup

**Expected Output:**
```
✓ Successfully indexed 12 document chunks!

Search Results:
1. NeMo Retriever Setup and Configuration Guide (score: 0.847)
   ...
```

### 6. Test NVIDIA API Connection

```bash
python scripts/test_nvidia_api.py
```

**Expected Output:**
```
✓ SUCCESS! NVIDIA API is working correctly.
```

## 🎯 Usage

### Quick Test

Run a simple test to verify everything works:

```bash
python3 simple_test.py

# Or with verbosity control:
python3 simple_test.py --quiet      # Clean output only
python3 simple_test.py --verbose    # Show debug messages
python3 simple_test.py --vv         # Show all details
```

### Demo Queries

Run multiple demo queries:

```bash
python3 demo_queries.py

# Recommended for demos:
python3 demo_queries.py --quiet     # Clean output for presentations
```

### Interactive Mode

Start the agent in interactive mode:

```bash
python3 main.py

# Or with verbosity control:
python3 main.py --quiet      # Minimal logging
python3 main.py --verbose    # Debug mode
python3 main.py --vv         # Very verbose
```

**Verbosity Levels**:
- `--quiet` / `-q`: Errors only (cleanest output)
- (default): Info, warnings, and errors
- `--verbose` / `-v`: Add debug messages
- `--vv`: Show all internal details

See [USAGE.md](docs/USAGE.md) for complete verbosity guide.

**Note**: For programmatic testing, use `simple_test.py` or `demo_queries.py` instead of interactive mode.

You'll see:

```
======================================================================
               GenAIOps Documentation Assistant Agent
                    Powered by NVIDIA Nemotron
======================================================================

Initializing components...
  [1/6] Connecting to NVIDIA API...
  [2/6] Loading embedding model...
  [3/6] Connecting to vector store...
  [4/6] Registering agent tools...
  [5/6] Setting up guardrails...
  [6/6] Building LangGraph agent...

✅ All components initialized successfully!

Available tools:
  • security_policy_checker
  • cost_estimator
  • internal_docs_search

Type your questions or 'exit' to quit
----------------------------------------------------------------------

🧑 You:
```

### Example Queries

#### 1. Documentation Search (RAG)
```
🧑 You: How do I deploy NeMo Retriever?

🤖 Agent: Based on the internal documentation, here are the steps to deploy NeMo Retriever:

1. Install Prerequisites:
   - NVIDIA drivers and CUDA Toolkit 12.2+
   - Python 3.10+
   - Docker with NVIDIA Container Toolkit

2. Set Up Vector Database (e.g., Milvus):
   wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml
   docker-compose up -d

3. Deploy NeMo Retriever Embeddings:
   docker pull nvcr.io/nvidia/nemo-retriever-embedding-microservice:latest
   docker run -d --gpus all -p 8080:8080 ...

4. Deploy Reranking Microservice:
   docker pull nvcr.io/nvidia/nemo-retriever-reranking-microservice:latest
   docker run -d --gpus all -p 8081:8081 ...

[Full detailed steps would be provided...]

📊 Metadata:
  • Tool Calls: 1
  • Iterations: 2
  • Guardrails: ✅ PASSED
```

#### 2. Security Policy Check
```
🧑 You: Is NeMo Retriever approved for production use?

🤖 Agent: Yes, NeMo Retriever is approved for production deployment according to our security policies.
✓ NeMo Retriever is approved for production deployment.

Policy version: 1.0
Status: APPROVED

📊 Metadata:
  • Tool Calls: 1
  • Iterations: 2
  • Guardrails: ✅ PASSED
```

#### 3. Cost Estimation
```
🧑 You: What's the cost of running a medium-sized model with 5 million tokens per month?

🤖 Agent: Based on the cost estimation:

- Model Size: medium (13B-70B parameters)
- GPU Type: NVIDIA A100
- Monthly Tokens: 5,000,000
- Estimated Monthly Cost: $2.50 USD
- Daily Cost: ~$0.08 USD
- Yearly Cost: ~$30.00 USD

This is based on $0.50 per 1 million tokens for medium-sized models.

📊 Metadata:
  • Tool Calls: 1
  • Iterations: 2
  • Guardrails: ✅ PASSED
```

#### 4. Multi-Step Reasoning
```
🧑 You: I need to deploy NeMo Retriever. First check if it's approved, then estimate the cost for 10M tokens monthly on a medium GPU.

🤖 Agent: I'll help you with that deployment plan.

First, let me check the security approval...
✓ NeMo Retriever IS APPROVED for production deployment.

Now, let me calculate the cost estimate...
For NeMo Retriever deployment with 10M tokens/month:
- GPU Type: NVIDIA A100 (medium)
- Monthly Cost: $5.00 USD
- Daily Cost: $0.17 USD
- Yearly Cost: $60.00 USD

Deployment Recommendation:
Since NeMo Retriever is approved and the cost is reasonable, you can proceed with deployment following these steps:
[Steps would be provided from documentation search...]

📊 Metadata:
  • Tool Calls: 3
  • Iterations: 4
  • Guardrails: ✅ PASSED
```

## 🧪 Example Queries to Try

1. **Simple RAG**: "What are the GPU requirements for NeMo Retriever?"
2. **Policy Check**: "Is TensorRT approved for use?"
3. **Cost Analysis**: "Compare costs between small and large model sizes for 1M tokens"
4. **Multi-step**: "I want to deploy a large model processing 20M tokens monthly. Check if it's approved and give me the cost breakdown."
5. **Complex**: "What's the recommended GPU for NeMo Retriever and what would it cost to run at scale?"

## 📚 Documentation

Detailed documentation is available in the [docs/](docs/) folder:
- **[USAGE.md](docs/USAGE.md)** - Verbosity levels and command-line options
- **[ARCHITECTURE_BREAKDOWN.md](docs/ARCHITECTURE_BREAKDOWN.md)** - What runs locally vs NVIDIA API
- **[STATUS.md](docs/STATUS.md)** - Current project status
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Version history

## 📁 Project Structure

```
nemo-demo/
├── main.py                          # CLI entry point
├── docs/                            # Documentation
│   ├── spec.md                      # Original specification
│   ├── USAGE.md                     # Usage guide
│   ├── ARCHITECTURE_BREAKDOWN.md    # System architecture
│   └── ...                          # More docs
├── config/                          # Configuration
│   ├── settings.py                  # Environment settings
│   └── policies.py                  # Approved libraries list
├── src/
│   ├── llm/                         # NVIDIA API client
│   │   ├── nvidia_client.py
│   │   └── prompts.py
│   ├── tools/                       # Agent tools
│   │   ├── base.py
│   │   ├── security_checker.py
│   │   ├── cost_estimator.py
│   │   ├── docs_search.py
│   │   └── registry.py
│   ├── rag/                         # RAG components
│   │   ├── embeddings.py
│   │   └── vectorstore.py
│   ├── orchestrator/                # LangGraph agent
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── graph.py
│   │   └── agent.py
│   ├── guardrails/                  # Safety checks
│   │   └── policy_checker.py
│   └── utils/                       # Utilities
│       └── logger.py
├── data/docs/                       # Sample documentation
│   ├── deployment_guide.md
│   └── nemo_retriever_setup.md
└── scripts/                         # Setup scripts
    ├── setup_vectorstore.py
    └── test_nvidia_api.py
```

## 🔧 Troubleshooting

### Issue: "NVIDIA_API_KEY not set"

**Solution:**
1. Ensure `.env` file exists (copy from `.env.example`)
2. Verify your API key is correctly pasted
3. No quotes around the API key value
4. Restart the terminal/reload environment

### Issue: "Failed to connect to NVIDIA API"

**Possible causes:**
- Invalid API key
- Network connectivity issues
- API endpoint temporarily unavailable

**Solutions:**
1. Verify API key at [https://build.nvidia.com](https://build.nvidia.com)
2. Check internet connection
3. Try again in a few minutes

### Issue: "Vector store not found"

**Solution:**
Run the setup script:
```bash
python scripts/setup_vectorstore.py
```

### Issue: "Out of Memory" during embedding

**Solution:**
This happens with large documents. The default chunking (1000 chars) should work fine. If issues persist:
1. Reduce chunk size in `scripts/setup_vectorstore.py`
2. Process fewer documents at once

### Issue: Agent gives incorrect answers

**Common causes:**
- Document not indexed in vector store
- Query too vague
- Model hallucinating

**Solutions:**
1. Ensure all docs are indexed (`setup_vectorstore.py`)
2. Ask more specific questions
3. Try rephrasing your query

## 🔐 Security & Privacy

- **Local Processing**: All orchestration and tool execution happens locally
- **API Calls**: Only LLM inference calls NVIDIA API (no data stored)
- **Guardrails**: Response validation prevents policy violations
- **API Key**: Never commit `.env` file to version control

## 🚀 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Agent Orchestration | LangGraph | ReAct loop state machine |
| LLM Inference | NVIDIA API (Llama 3.1 70B) | Reasoning and decision making |
| Vector Database | ChromaDB | Document embeddings storage |
| Embeddings | SentenceTransformers | Local text embeddings |
| Guardrails | NeMo Guardrails | Enterprise safety validation |
| CLI | Python | Interactive interface |

## 📊 Performance

- **Cold Start**: ~5-10 seconds (loading models)
- **Query Latency**: ~2-5 seconds per iteration
- **Tool Execution**: <1 second per tool
- **Max Iterations**: 10 (configurable)

## 🎓 Learning Resources

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **NVIDIA NIM**: https://docs.nvidia.com/nim/
- **ChromaDB**: https://docs.trychroma.com/
- **NVIDIA API Catalog**: https://build.nvidia.com

## 🤝 Contributing

This is a production-ready prototype. For enterprise deployment:
1. Add comprehensive error handling and retry logic
2. Implement conversation persistence (SQLite/Redis)
3. Expand test coverage with unit and integration tests
4. Add monitoring and observability (metrics, logging)
5. Configure custom NeMo Guardrails policies for your organization

## 📝 License

[Your License Here]

## 👤 Author

[Your Name/Contact]

---

**Built with NVIDIA technologies for GenAIOps**
