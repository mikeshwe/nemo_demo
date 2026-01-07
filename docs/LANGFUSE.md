# Langfuse LLM Observability Integration

## Overview

This GenAIOps Documentation Assistant Agent demo includes **Langfuse** integration for advanced LLM observability and analytics. Langfuse provides a web-based dashboard for exploring traces, analyzing costs, debugging agent behavior, and managing prompts.

### Why Langfuse?

While OpenTelemetry provides infrastructure-level observability, Langfuse specializes in LLM-specific observability:

- **Interactive Traces**: Visual exploration of agent execution flows with drill-down capabilities
- **Cost Tracking**: Automatic calculation of LLM API costs per query/session
- **Quality Scoring**: Track success rates, efficiency metrics, and custom scores
- **Prompt Management**: Version control and A/B testing for system prompts
- **Analytics Dashboard**: Aggregate metrics across multiple runs
- **User Feedback**: Collect and analyze user ratings

## Architecture

### Dual Observability Strategy

This demo uses **complementary observability tools**:

1. **OpenTelemetry** (Infrastructure)
   - Distributed tracing across services
   - System performance metrics
   - Standard OTLP protocol
   - Production-ready monitoring

2. **Langfuse** (LLM-Specific)
   - LLM call analytics
   - Token usage and cost tracking
   - Quality/efficiency scoring
   - Interactive trace exploration

Both systems run **independently** and can be enabled/disabled separately via CLI flags.

### Instrumentation Points

Langfuse captures data at every critical point in the agent lifecycle:

```
Agent Run (Trace)
├── Reasoning Iteration 1 (Generation)
│   ├── Input Guardrails Check
│   ├── LLM Call (auto-logged with usage)
│   └── Cost Score ($0.0023)
├── Tool Execution (Span)
│   ├── security_policy_checker
│   └── Result logged
├── Reasoning Iteration 2 (Generation)
│   ├── LLM Call
│   └── Cost Score ($0.0019)
└── Quality Scores
    ├── Success: 1.0
    └── Efficiency: 0.8 (2/10 iterations)
```

## Getting Started

### Quick Start with Langfuse Cloud (Recommended)

The fastest way to get started is with Langfuse Cloud - no Docker required!

#### 1. Sign Up for Langfuse Cloud

Visit **https://cloud.langfuse.com** and create a free account.

#### 2. Get Your API Keys

1. Create a new project in the Langfuse dashboard
2. Navigate to **Settings** → **API Keys**
3. Copy your **Public Key** (starts with `pk-lf-`) and **Secret Key** (starts with `sk-lf-`)

#### 3. Configure Your Environment

Add your API keys to `.env`:

```bash
# Langfuse Cloud Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

#### 4. Run the Demo

```bash
# Install dependencies (includes langfuse SDK)
pip install -r requirements.txt

# Run with Langfuse enabled
python simple_test.py --langfuse
```

#### 5. View Your Traces

Open **https://cloud.langfuse.com** and navigate to the **Traces** tab to explore your agent's execution!

### Alternative: Local Langfuse with Docker (Optional)

If you prefer to run Langfuse locally:

#### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- All base demo dependencies installed

#### Installation

1. **Install Langfuse Python SDK**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Local Langfuse Instance**:
   ```bash
   # Start Langfuse (PostgreSQL + Web UI)
   docker-compose -f docker-compose.langfuse.yml up -d

   # Check status
   docker-compose -f docker-compose.langfuse.yml ps

   # View logs
   docker-compose -f docker-compose.langfuse.yml logs -f langfuse-server
   ```

3. **Configure Environment** (optional for local):

   For local Docker, the demo uses default keys. Optionally add to `.env`:
   ```bash
   LANGFUSE_HOST=http://localhost:3000
   LANGFUSE_PUBLIC_KEY=pk-lf-local
   LANGFUSE_SECRET_KEY=sk-lf-local
   ```

4. **Run and Explore**:
   ```bash
   python simple_test.py --langfuse
   ```

   Then open **http://localhost:3000** to view traces locally.

### First Run Examples

Run any demo script with the `--langfuse` flag:

```bash
# Simple test query
python simple_test.py --langfuse

# Multiple demo queries
python demo_queries.py --langfuse

# Interactive chat mode
python main.py --langfuse
```

## Usage Guide

### Enabling Langfuse

All CLI scripts support the `--langfuse` flag:

```bash
# Enable Langfuse for a single query
python simple_test.py --langfuse

# Combine with other flags
python simple_test.py --langfuse --verbose

# Save telemetry to file AND use Langfuse
python demo_queries.py --langfuse --save-telemetry telemetry.txt
```

### Exploring Traces in the Dashboard

1. **Open Dashboard**: Navigate to https://cloud.langfuse.com (or http://localhost:3000 for local)
2. **View Traces**: Click "Traces" in the sidebar
3. **Drill Down**: Click any trace to see:
   - Full execution timeline
   - LLM generations with input/output
   - Tool executions with arguments
   - Cost per call
   - Quality scores

### Understanding the Data

#### Traces

Each `agent.run()` call creates a **trace** representing the full query lifecycle:

- **Name**: `agent_run_{timestamp}`
- **Metadata**:
  - `query`: User's question
  - `max_iterations`: Agent configuration
  - `tool_count`: Number of available tools
- **Tags**: `environment:demo`, `agent:genaiops`

#### Generations (LLM Calls)

Each LLM API call is logged as a **generation**:

- **Name**: `reasoning_iteration_1`, `reasoning_iteration_2`, etc.
- **Model**: `meta/llama-3.1-70b-instruct`
- **Input**: Full message history sent to LLM
- **Output**: Assistant's response
- **Usage**:
  - `prompt_tokens`: Input token count
  - `completion_tokens`: Output token count
  - `total_tokens`: Sum
- **Metadata**:
  - `temperature`: 0.2
  - `max_tokens`: 1024
  - `has_tool_calls`: true/false
  - `iteration`: Iteration number

#### Spans (Tool Executions)

Each tool call is logged as a **span**:

- **Name**: Tool name (e.g., `security_policy_checker`)
- **Input**: Tool arguments as JSON
- **Output**: Tool result as JSON
- **Metadata**:
  - `success`: true/false

#### Scores

Quality metrics are logged as **scores** on the trace:

1. **Cost Score**
   - **Value**: USD cost (e.g., 0.0023)
   - **Comment**: Breakdown by input/output tokens
   - **Logged**: After each LLM call

2. **Success Score**
   - **Value**: 1.0 (success) or 0.0 (failure)
   - **Comment**: Error message if failed
   - **Logged**: At end of agent run

3. **Efficiency Score**
   - **Value**: 0.0-1.0 (higher is better)
   - **Calculation**: `1 - (iterations_used / max_iterations)`
   - **Comment**: "Used 2/10 iterations"
   - **Logged**: At end of agent run

### Cost Tracking

Langfuse automatically calculates and tracks LLM costs:

#### Pricing

The demo uses NVIDIA NIM pricing (configured in `src/observability/cost_calculator.py`):

```python
PRICING = {
    "meta/llama-3.1-70b-instruct": {
        "input": 0.00088,   # per 1K tokens
        "output": 0.00088
    },
    "meta/llama-3.1-8b-instruct": {
        "input": 0.00020,
        "output": 0.00020
    }
}
```

#### Viewing Costs

In the Langfuse dashboard:

1. **Per-Trace Costs**: View "cost" score on each trace
2. **Aggregate Costs**: Use the Analytics tab to sum costs across runs
3. **Cost Breakdown**: See prompt vs completion token costs in score comments

### Debugging with Langfuse

#### Scenario: Agent Gives Wrong Answer

1. Open trace in dashboard
2. Review each LLM generation:
   - Check input messages for context
   - Verify tool results were accurate
   - Look for reasoning errors
3. Check tool execution spans for failures
4. Review guardrails metadata for blocked content

#### Scenario: Agent Takes Too Many Iterations

1. Sort traces by efficiency score (low to high)
2. Identify patterns in low-efficiency runs
3. Check if specific queries cause loops
4. Review tool execution order

#### Scenario: Costs Too High

1. Filter traces by cost score
2. Identify expensive queries
3. Check token usage patterns:
   - Large prompt tokens = context too large
   - Large completion tokens = verbose responses
4. Optimize prompts or add result caching

## Advanced Features

### Custom Metadata

Add custom metadata to traces programmatically:

```python
from src.observability.langfuse_integration import trace_agent_run

with trace_agent_run(
    query="Is NeMo approved?",
    metadata={
        "user_id": "demo_user",
        "session_id": "abc123",
        "environment": "production"
    }
):
    # ... agent execution
```

### User Feedback (Future Enhancement)

Langfuse supports collecting user feedback on responses:

```python
from src.observability.langfuse_integration import score_generation

# After user rates the response
score_generation(
    name="user_rating",
    value=4.5,  # 1-5 stars
    comment="Helpful and accurate"
)
```

### Prompt Management (Future Enhancement)

Use Langfuse's prompt management for versioning:

```python
# Fetch prompt from Langfuse instead of hardcoding
from langfuse import Langfuse

langfuse = Langfuse()
prompt = langfuse.get_prompt("agent-system-prompt", version=2)
system_message = prompt.compile()
```

## Configuration Reference

### Environment Variables

**For Langfuse Cloud (Recommended)**:

```bash
# Langfuse Cloud Configuration
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key-here
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

Get your keys from: https://cloud.langfuse.com → Settings → API Keys

**For Local Docker Setup (Optional)**:

```bash
# Local Langfuse Configuration
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-local
LANGFUSE_SECRET_KEY=sk-lf-local
```

### Docker Compose Configuration (Local Setup Only)

If using local Docker, the `docker-compose.langfuse.yml` file configures:

- **PostgreSQL Database**
  - Image: `postgres:15`
  - Data persistence via named volume
  - Healthcheck for reliable startup

- **Langfuse Server**
  - Image: `langfuse/langfuse:2`
  - Port: 3000
  - Pre-configured local API keys:
    - Public: `pk-lf-local`
    - Secret: `sk-lf-local`

To customize, edit `docker-compose.langfuse.yml`.

### Graceful Degradation

Langfuse failures **never break agent execution**:

- If initialization fails, agent continues without Langfuse
- If logging fails, exceptions are caught and logged
- `is_langfuse_enabled()` guards all instrumentation

You'll see warnings like:

```
⚠️  Langfuse initialization failed, continuing without it
```

## Architecture Details

### Integration Points

Langfuse is instrumented at these locations:

#### 1. Agent Orchestrator (`src/orchestrator/agent.py`)

```python
def run(self, query):
    if LANGFUSE_AVAILABLE and is_langfuse_enabled():
        with trace_agent_run(query=query, metadata={...}):
            result = self._execute_agent(...)
            self._add_langfuse_scores(result)
            return result
```

- Creates trace for entire run
- Adds success/efficiency scores at end

#### 2. Reasoning Node (`src/orchestrator/nodes.py`)

```python
response = llm_client.chat_completion(...)

if LANGFUSE_AVAILABLE and is_langfuse_enabled():
    log_llm_generation(
        name=f"reasoning_iteration_{iteration}",
        model=llm_client.model_name,
        input_messages=messages,
        output=assistant_message.content,
        metadata={...},
        usage={...}
    )
    log_cost_to_langfuse(model, usage)
```

- Logs every LLM call with full context
- Calculates and logs cost

#### 3. Tool Registry (`src/tools/registry.py`)

```python
result = tool.execute(**kwargs)

if LANGFUSE_AVAILABLE and is_langfuse_enabled():
    log_tool_execution(
        name=name,
        input_args=kwargs,
        output=result,
        metadata={"success": result["success"]}
    )
```

- Logs every tool execution
- Captures args and results

### Data Flow

```
User Query
    ↓
Agent.run() → Create Langfuse Trace
    ↓
Reasoning Node → Log LLM Generation + Cost
    ↓
Tool Execution → Log Tool Span
    ↓
Reasoning Node → Log LLM Generation + Cost
    ↓
Agent.run() → Add Success/Efficiency Scores
    ↓
Langfuse.flush() → Send to Dashboard
```

## Troubleshooting

### No Traces Appearing in Dashboard

**Symptom**: Dashboard loads but shows no data

**Solutions**:

1. **Verify `--langfuse` flag is used**:
   ```bash
   python simple_test.py --langfuse
   ```

2. **Check initialization succeeded** - Look for this message:
   ```
   [INFO] ✓ Langfuse initialized (host: https://us.cloud.langfuse.com)
   ```

3. **Check for warnings** - If you see warnings, Langfuse is not fully enabled:
   ```
   ⚠️  Langfuse initialization failed, continuing without it
   ```

4. **Verify API keys** (Cloud) - Check `.env` has correct credentials:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://us.cloud.langfuse.com
   ```

5. **Wait a moment** - Cloud traces may take 5-10 seconds to appear

### Authentication Errors

**Symptom**: `401 Unauthorized` or authentication warnings

**Solution**:

1. **Verify `.env` configuration**:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
   LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
   LANGFUSE_HOST=https://us.cloud.langfuse.com
   ```

2. **Regenerate keys** from https://cloud.langfuse.com if needed

3. **Check host URL** - Should be `https://us.cloud.langfuse.com` (or `https://eu.cloud.langfuse.com` for EU)

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'langfuse'`

**Solution**:

```bash
pip install -r requirements.txt
# or
pip install langfuse>=2.0.0
```

### Local Docker Issues (If Using Local Setup)

**Symptom**: http://localhost:3000 not accessible

**Solutions**:

```bash
# Check if containers are running
docker-compose -f docker-compose.langfuse.yml ps

# Restart services
docker-compose -f docker-compose.langfuse.yml restart

# Check logs for errors
docker-compose -f docker-compose.langfuse.yml logs langfuse-server

# Verify port is not in use
lsof -i :3000
```

## Performance Impact

Langfuse has **minimal performance overhead**:

- **Async Operations**: All network calls are async (non-blocking)
- **Batching**: Data is batched and sent in background
- **Lazy Initialization**: Only initialized when `--langfuse` flag is used
- **Graceful Degradation**: Failures don't slow down agent

Typical overhead: **< 50ms per agent run**

## Production Deployment

### Langfuse Cloud (Recommended)

Langfuse Cloud is the **recommended option for production** - it's managed, scalable, and requires no infrastructure:

1. **Sign up** at https://cloud.langfuse.com
2. **Create a project** and obtain API keys
3. **Configure environment**:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-lf-your-key
   LANGFUSE_SECRET_KEY=sk-lf-your-key
   LANGFUSE_HOST=https://us.cloud.langfuse.com
   ```
4. **Deploy** - Same code works in production, just enable `--langfuse` flag

**Benefits**:
- ✅ No infrastructure management
- ✅ Automatic scaling
- ✅ Built-in backups and high availability
- ✅ Latest features automatically
- ✅ Free tier available

### Self-Hosted Langfuse (Enterprise)

For enterprise deployments requiring data sovereignty, self-host Langfuse:

1. Follow: https://langfuse.com/docs/deployment/self-host
2. Update `LANGFUSE_HOST` in `.env`
3. Configure auth keys
4. Scale PostgreSQL for production

### Security Considerations

- **API Keys**: Never commit `.env` to version control
- **Data Privacy**: LLM inputs/outputs are sent to Langfuse (review privacy policy)
- **Network Security**: Use HTTPS for Langfuse Cloud or secure self-hosted deployment
- **Access Control**: Configure Langfuse user roles appropriately

## Comparison: OpenTelemetry vs Langfuse

| Feature | OpenTelemetry | Langfuse |
|---------|---------------|----------|
| **Focus** | Infrastructure | LLM Apps |
| **Protocol** | OTLP (standard) | HTTP API (proprietary) |
| **Traces** | Distributed spans | Nested generations/spans |
| **Dashboard** | Jaeger/Tempo | Langfuse UI |
| **LLM Metadata** | Custom attributes | Native support |
| **Cost Tracking** | Manual | Automatic |
| **Prompt Mgmt** | No | Yes |
| **User Feedback** | No | Yes |
| **Open Source** | ✅ | ✅ |
| **Self-Hostable** | ✅ | ✅ |

**Recommendation**: Use **both** for comprehensive observability!

## References

- **Langfuse Documentation**: https://langfuse.com/docs
- **Langfuse GitHub**: https://github.com/langfuse/langfuse
- **Python SDK**: https://langfuse.com/docs/sdk/python
- **OpenAI Integration**: https://langfuse.com/docs/integrations/openai
- **Self-Hosting Guide**: https://langfuse.com/docs/deployment/self-host

## Next Steps

1. **Sign Up**: Create a free account at https://cloud.langfuse.com
2. **Configure**: Add your API keys to `.env` file
3. **Run Demo**: Execute `python demo_queries.py --langfuse` to generate sample traces
4. **Explore Dashboard**: Visit https://cloud.langfuse.com and navigate to Traces tab
5. **Analyze Costs**: Check aggregate costs in the Analytics tab
6. **Debug Issues**: Use trace drill-down to understand agent behavior
7. **Customize Metadata**: Add user_id, session_id to traces for production use
8. **Export Data**: Use Langfuse API to export data for custom reporting

For questions or issues, see the main README or create a GitHub issue.
