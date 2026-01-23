# Active Trust Plane for Agentic AI

A production-ready Agentic AI prototype demonstrating **data quality management** for AI agents with **Trust Plane (proactive)** and **LLM Judge (reactive)** validation patterns. This demo showcases how **Trust Plane moves data lineage from passive metadata to active governance middleware**, using lineage data to enforce quality policies before queries execute. Features **true bidirectional traceability** with OpenLineage: **forward lineage** (data issue → impacted tools) for impact analysis and **backward lineage** (agent error → stale data) for root cause analysis. Real ChromaDB and Marquez integration.

## 🚀 Overview

This project showcases:
- **Trust Plane (Proactive)**: Pre-query authorization that prevents stale data from reaching agents
- **LLM Judge (Reactive)**: Post-query validation that detects errors in agent responses
- **Bidirectional Traceability**:
  - **Forward**: Data issue → impacted tools (impact analysis)
  - **Backward**: Agent error → stale data (root cause analysis)
- **OpenLineage Integration**: Real-time data lineage with Marquez visualization
- **Agentic Architecture**: LangGraph orchestration with ReAct loop, RAG, and specialized tools
- **NeMo Guardrails**: Input/output validation with NVIDIA's NeMo Guardrails framework
- **AI Observability**: Dual observability with OpenTelemetry (infrastructure) and Langfuse (LLM analytics)

## 🎯 Quick Start: Main Demo

The **main demo** shows proactive vs reactive data quality management:

```bash
# Start Marquez backend for lineage visualization
docker-compose -f docker-compose-marquez.yml up -d

# Run the full traceability demo (default: both modes)
python3 demo_full_traceability.py

# Or run specific modes:
python3 demo_full_traceability.py --mode proactive  # Trust Plane blocks stale data
python3 demo_full_traceability.py --mode reactive   # LLM Judge detects errors
python3 demo_full_traceability.py --mode both       # Side-by-side comparison
```

### What the Demo Shows

**Step 1: Ingestion with Lineage Tracking**:
- 📝 Ingests stale document (45 days old) to ChromaDB
- 📝 Tracks producer_run_id in document metadata
- 📝 Emits OpenLineage events with data quality metrics

**Step 2: Bootstrap Lineage Graph**:
- 🔧 Runs test query to establish tool→dataset dependencies
- 🔧 Emits OpenLineage events for tool execution
- 🔧 Builds lineage graph: ingestion → dataset → tool → agent
- 🔧 Enables forward impact analysis (realistic production pattern)

**Step 3: Impact Analysis (Forward Lineage)**:
- 📊 Queries Marquez for tools consuming the stale dataset
- 📊 Identifies affected tools from actual lineage graph
- 📊 Predicts downstream impact before user queries
- 📊 Demonstrates forward lineage: data issue → impacted tools

**Step 4: Proactive Mode (Trust Plane)**:
- ✅ Checks data quality BEFORE agent query
- ✅ Blocks queries if data is stale (>30 days)
- ✅ Agent never sees outdated information
- ✅ Uses backward lineage for automatic root cause

**Step 4: Reactive Mode (LLM Judge)**:
- ❌ Agent uses stale data to generate answer
- ❌ User sees incorrect information
- ✅ LLM Judge detects error AFTER response
- ✅ Uses backward lineage for automatic root cause (too late!)

**Key Insight**: Bootstrap builds lineage graph → Forward analysis predicts impact → Proactive prevents errors → Reactive detects them (too late)

See [README_FULL_TRACEABILITY.md](README_FULL_TRACEABILITY.md) for detailed demo guide.

## 🏗️ Architecture

### Data Quality Management Flow

```
┌─────────────────────┐
│   Agent Query       │
└──────────┬──────────┘
           │
    ┌──────▼──────────┐
    │  Trust Plane    │ ◄─── Proactive: Check data quality BEFORE query
    │  (Enforcer)     │      ✓ Block if stale (>30 days)
    └──────┬──────────┘      ✓ Automatic root cause
           │
    ┌──────▼──────────┐
    │  RAG Retrieval  │ ◄─── producer_run_id in metadata
    │   (ChromaDB)    │      Links data → ingestion job
    └──────┬──────────┘
           │
    ┌──────▼──────────┐
    │  Agent Answer   │
    └──────┬──────────┘
           │
    ┌──────▼──────────┐
    │   LLM Judge     │ ◄─── Reactive: Validate answer AFTER response
    │  (Validation)   │      ✗ Detect outdated info (too late)
    └──────┬──────────┘
           │
    ┌──────▼──────────┐
    │  OpenLineage    │ ◄─── Bidirectional traceability
    │  Root Cause     │      Agent error → stale file
    └─────────────────┘
           │
    ┌──────▼──────────┐
    │   Marquez UI    │ ◄─── Visual lineage graph
    │  (Visualization)│      http://localhost:3001
    └─────────────────┘
```

### Agentic AI Architecture

The agent uses a **ReAct (Reasoning + Acting)** pattern with input/output guardrails:

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
└────────────────────┬────────────────────────────────────────┘
                     │
           ┌─────────▼──────────┐
           │  NeMo Guardrails   │  ◄─── Input validation
           │   (Input Check)    │
           └─────────┬──────────┘
                     │
           ┌─────────▼──────────┐
           │  LangGraph Agent   │  (Local - macOS)
           │   Orchestrator     │  ReAct Loop
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
   │ChromaDB │  (Vector Store + Lineage Metadata)
   └─────────┘
        │
      ┌─▼─────────────────┐
      │  NVIDIA NIM API   │  (Remote GPU Inference)
      │  Llama 3.1 70B    │
      └───────────────────┘
        │
   ┌────▼──────────┐
   │NeMo Guardrails│  ◄─── Output validation
   │ (Output Check)│
   └───────────────┘
```

### How producer_run_id Enables Lineage

The `producer_run_id` is the key mechanism that links RAG chunks to agents, enabling bidirectional traceability:

**1. During Ingestion:**
```python
# Ingestion job stores lineage metadata in each chunk
chunk_metadata = {
    "title": "NeMo Retriever Guide",
    "source": "stale_nemo_guide.md",
    "lineage.producer_run_id": "abc123..."  # UUID of ingestion job run
}
# Stored in ChromaDB with the document chunk
```

**2. During Agent Query:**
```python
# Tool retrieves chunks from ChromaDB
chunks = vectorstore.search("What is NeMo?")
# Each chunk contains: chunk['metadata']['lineage.producer_run_id'] = "abc123..."

# Tool extracts producer_run_ids and propagates via OTel span
span.set_attribute("lineage.input_run_ids", "abc123,...")

# Agent reads span attribute and emits OpenLineage event
openlineage_event = {
    "inputs": [{
        "namespace": "chromadb",
        "name": "internal_docs.chunks",
        "facets": {
            "producerRunId": {"producerRunId": "abc123..."}  # Same ID!
        }
    }]
}
```

**3. In Marquez:**
```
Lineage Graph:
  ingestion_job (abc123...) → chromadb/internal_docs.chunks → agent_query

This enables:
  - Backward: agent_query → dataset → ingestion_job (root cause)
  - Forward: dataset → agent_query (impact analysis)
```

**Key Points:**
- The `producer_run_id` flows from **ChromaDB metadata** → **OTel span attribute** → **OpenLineage event** → **Marquez storage**
- Without it, we'd have no way to connect RAG chunks back to their source or forward to their consumers
- This is what enables Trust Plane to check data quality and perform automatic root cause analysis
- Run with `-vv` flag to see the actual metadata at each step

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

## 🔍 LLM Observability with Langfuse

In addition to OpenTelemetry, this demo includes **Langfuse** integration for LLM-specific observability with an interactive web dashboard.

### Why Langfuse?

Langfuse provides specialized observability for LLM applications:

- 🔭 **Interactive Traces**: Visual exploration of agent execution with drill-down
- 💰 **Automatic Cost Tracking**: Calculate USD costs per query based on token usage
- 📊 **Quality Metrics**: Track success rates and efficiency scores
- 🎯 **Prompt Management**: Version control and A/B testing for prompts
- 👥 **User Feedback**: Collect and analyze user ratings
- 📈 **Analytics Dashboard**: Aggregate insights across multiple runs

### Quick Start with Langfuse Cloud

1. **Sign up for Langfuse Cloud** (free tier available):
   - Go to https://cloud.langfuse.com
   - Create an account (GitHub, Google, or email)
   - Create a project and get your API keys

2. **Configure API Keys**:

```bash
# Add to your .env file
echo "LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key" >> .env
echo "LANGFUSE_SECRET_KEY=sk-lf-your-secret-key" >> .env
echo "LANGFUSE_HOST=https://us.cloud.langfuse.com" >> .env
```

3. **Run Agent with Langfuse**:

```bash
# Any script with --langfuse flag
python simple_test.py --langfuse
python demo_queries.py --langfuse
python main.py --langfuse
```

4. **Explore Traces**: Open https://cloud.langfuse.com and click "Traces" to see:
   - Complete execution timeline
   - LLM calls with input/output/tokens
   - Tool executions with arguments/results
   - Cost per query (in USD)
   - Success and efficiency scores

### What's Logged to Langfuse

- ✅ **Agent Runs**: Complete traces with query, iterations, tool calls
- ✅ **LLM Generations**: Every LLM call with full context, tokens, and costs
- ✅ **Tool Executions**: All tool calls with inputs and outputs
- ✅ **Cost Tracking**: Automatic USD cost calculation per call
- ✅ **Quality Scores**: Success (1.0 or 0.0) and efficiency (0.0-1.0) metrics

### Dual Observability

This demo uses **both** OpenTelemetry and Langfuse:

- **OpenTelemetry**: Infrastructure-level tracing (console export)
- **Langfuse**: LLM-specific analytics (web dashboard)

They work independently and can be enabled separately:

```bash
# OpenTelemetry only (default)
python simple_test.py

# Langfuse only
python simple_test.py --langfuse

# Both (recommended for full visibility)
python simple_test.py --langfuse --save-telemetry report.txt
```

### Alternative: Local Langfuse (Optional)

If you prefer to run Langfuse locally instead of using the cloud:

```bash
# Start local Langfuse with Docker (requires Docker Desktop)
docker-compose -f docker-compose.langfuse.yml up -d

# Open local dashboard
open http://localhost:3000

# Stop when done
docker-compose -f docker-compose.langfuse.yml down
```

For detailed Langfuse configuration, cost tracking, debugging workflows, and local deployment, see [docs/LANGFUSE.md](docs/LANGFUSE.md).

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

### Main Demo: Data Quality Management (Proactive vs Reactive)

**Recommended starting point** - Run the full traceability demo:

```bash
# Start Marquez backend (required for lineage visualization)
docker-compose -f docker-compose-marquez.yml up -d

# Run the demo (default: both modes for comparison)
python3 demo_full_traceability.py

# Run specific modes:
python3 demo_full_traceability.py --mode proactive  # Trust Plane prevents stale data
python3 demo_full_traceability.py --mode reactive   # LLM Judge detects errors after
python3 demo_full_traceability.py --mode both       # Side-by-side comparison

# Verbose mode for detailed tracing:
python3 demo_full_traceability.py --mode both -v    # Show tracking details
python3 demo_full_traceability.py --mode both -vv   # Show all metadata
```

**Output includes**:
- Real-time data ingestion with lineage tracking
- Proactive blocking or reactive detection
- Automatic root cause analysis via bidirectional traceability
- Live Marquez API queries showing real data quality metrics
- Instructions for exploring Marquez UI

**See**: [README_FULL_TRACEABILITY.md](README_FULL_TRACEABILITY.md) and [QUICK_START_MODES.md](QUICK_START_MODES.md)

### Quick Test

Run a simple test to verify the agent works:

```bash
python3 simple_test.py

# Or with verbosity control:
python3 simple_test.py --quiet      # Clean output only
python3 simple_test.py --verbose    # Show debug messages
python3 simple_test.py --vv         # Show all details
```

### Demo Queries

Run multiple agent queries to test different tools:

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

### Main Demo Documentation
- **[README_FULL_TRACEABILITY.md](README_FULL_TRACEABILITY.md)** - Full traceability demo guide
- **[QUICK_START_MODES.md](QUICK_START_MODES.md)** - Quick reference for demo modes
- **[BIDIRECTIONAL_TRACEABILITY.md](BIDIRECTIONAL_TRACEABILITY.md)** - Architecture and data lineage
- **[DATA_QUALITY_SUMMARY.md](DATA_QUALITY_SUMMARY.md)** - Trust Plane overview
- **[LLM_JUDGE_VALIDATION.md](LLM_JUDGE_VALIDATION.md)** - LLM Judge validation framework
- **[OTEL_OPENLINEAGE_CORRELATION.md](OTEL_OPENLINEAGE_CORRELATION.md)** - OTel + OpenLineage integration
- **[MARQUEZ_SETUP.md](MARQUEZ_SETUP.md)** - Marquez backend setup

### Agent & Observability Documentation
- **[USAGE.md](docs/USAGE.md)** - Verbosity levels and command-line options
- **[OBSERVABILITY.md](docs/OBSERVABILITY.md)** - OpenTelemetry instrumentation guide
- **[LANGFUSE.md](docs/LANGFUSE.md)** - Langfuse LLM observability integration
- **[NEMO_GUARDRAILS_INTEGRATION.md](docs/NEMO_GUARDRAILS_INTEGRATION.md)** - NeMo Guardrails setup
- **[ARCHITECTURE_BREAKDOWN.md](docs/ARCHITECTURE_BREAKDOWN.md)** - What runs locally vs NVIDIA API
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Version history

## 📁 Project Structure

```
nemo-demo/
├── demo_full_traceability.py        # 🎯 MAIN DEMO: Proactive vs Reactive
├── demo_data_quality.py             # Data quality validation demo
├── main.py                          # Interactive CLI (original agent)
├── simple_test.py                   # Quick agent test
├── demo_queries.py                  # Multiple query demos
│
├── README_FULL_TRACEABILITY.md      # Main demo guide
├── QUICK_START_MODES.md             # Quick reference
├── BIDIRECTIONAL_TRACEABILITY.md    # Architecture
├── DATA_QUALITY_SUMMARY.md          # Trust Plane overview
├── LLM_JUDGE_VALIDATION.md          # LLM Judge docs
├── OTEL_OPENLINEAGE_CORRELATION.md  # Observability
│
├── docker-compose-marquez.yml       # Marquez backend (Postgres + API + Web)
│
├── config/                          # Configuration
│   ├── settings.py                  # Environment settings + OpenLineage
│   └── policies.py                  # Approved libraries list
│
├── src/
│   ├── llm/                         # NVIDIA API client
│   │   ├── nvidia_client.py
│   │   └── prompts.py
│   │
│   ├── tools/                       # Agent tools
│   │   ├── base.py
│   │   ├── security_checker.py
│   │   ├── cost_estimator.py
│   │   ├── docs_search.py
│   │   └── registry.py
│   │
│   ├── rag/                         # RAG components
│   │   ├── embeddings.py
│   │   └── vectorstore.py           # ChromaDB with lineage metadata
│   │
│   ├── orchestrator/                # LangGraph agent
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── graph.py
│   │   └── agent.py                 # Agent with lineage tracking
│   │
│   ├── guardrails/                  # NeMo Guardrails
│   │   └── nemo_guardrails.py       # Input/output validation
│   │
│   ├── observability/               # Observability
│   │   ├── lineage/                 # OpenLineage integration
│   │   │   ├── client.py            # Lineage client
│   │   │   ├── emitter.py           # Event emitter
│   │   │   ├── context.py           # Context manager
│   │   │   └── metrics.py           # Data quality metrics
│   │   └── ...                      # OpenTelemetry (future)
│   │
│   ├── ingestion/                   # Data ingestion
│   │   └── lineage_tracker.py       # Ingestion with lineage tracking
│   │
│   ├── trust_plane/                 # Trust Plane (Proactive)
│   │   ├── enforcer.py              # Authorization enforcement
│   │   ├── policy.py                # Policy definitions
│   │   └── policies.yaml            # Data quality policies
│   │
│   ├── validation/                  # LLM Judge (Reactive)
│   │   ├── judge.py                 # LLM Judge validation
│   │   └── verdict.py               # Verdict model
│   │
│   └── utils/                       # Utilities
│       └── logger.py
│
├── data/
│   ├── docs/                        # Sample documentation
│   │   ├── deployment_guide.md
│   │   └── nemo_retriever_setup.md
│   └── ground_truth.json            # Ground truth for LLM Judge
│
├── scripts/                         # Setup scripts
│   ├── setup_vectorstore.py
│   └── test_nvidia_api.py
│
├── tests/                           # Test suites
│   ├── test_lineage.py              # OpenLineage tests
│   ├── test_trust_plane.py          # Trust Plane tests
│   ├── test_llm_judge.py            # LLM Judge tests
│   ├── test_marquez_api.py          # Marquez API tests
│   └── test_data_quality.py         # End-to-end tests
│
└── docs/                            # Additional documentation
    ├── USAGE.md
    ├── OBSERVABILITY.md
    ├── LANGFUSE.md
    └── ...
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
| **Data Quality** | Trust Plane + LLM Judge | Proactive blocking + Reactive detection |
| **Data Lineage** | OpenLineage + Marquez | Bidirectional traceability and visualization |
| **Agent Orchestration** | LangGraph | ReAct loop state machine |
| **LLM Inference** | NVIDIA API (Llama 3.1 70B) | Reasoning and decision making |
| **Vector Database** | ChromaDB | Document embeddings + lineage metadata |
| **Embeddings** | SentenceTransformers | Local text embeddings |
| **Guardrails** | NeMo Guardrails | Input/output validation |
| **Tracing** | OpenTelemetry | Infrastructure observability |
| **LLM Analytics** | Langfuse | LLM-specific observability |
| **CLI** | Python | Interactive interface |

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
