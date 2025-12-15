# NVIDIA GenAIOps Interview Prototype: Complete Specification

> **⚠️ DISCLAIMER:** This document represents the original project specification and vision from December 2025. It describes the intended architecture and goals for this prototype. The actual implementation may differ in some details. For current implementation details, please refer to the main [README.md](../README.md) and [ARCHITECTURE_BREAKDOWN.md](ARCHITECTURE_BREAKDOWN.md).

## 1. Executive Summary & Goal

**Project Goal:** Demonstrate advanced proficiency in NVIDIA's accelerated computing technologies for Generative AI Operations (GenAIOps) by building a working **Agentic AI** prototype. This agent will function as a **"DevOps Knowledge Agent"** that performs complex, multi-step queries by reasoning, calling specialized tools, synthesizing answers, and enforcing safety.

**Application Name:** GenAIOps Documentation Assistant Agent

**Core Demonstration:** Showcasing a **Hybrid Deployment** strategy where the Agent Orchestrator runs locally on macOS, but the core intelligence (LLM inference) is accelerated and containerized via **remote NVIDIA NIMs (Inference Microservices)**. This proves both architectural and operational understanding.

---

## 2. Core Technologies to Integrate

| Technology | Role in Prototype | Implementation Strategy |
| :--- | :--- | :--- |
| **NVIDIA AI Blueprint (Agentic AI)** | Provides the foundational orchestration and architectural reference (The ReAct Loop). | **Adaptation:** Use the conceptual structure of an NVIDIA Agentic Blueprint to guide the Python/LangChain Orchestrator's design. |
| **NVIDIA NIMs (Inference Microservices)** | Provides high-performance, containerized LLM services via an OpenAI-compatible API, supporting **Tool Calling** (Function Calling). | **Hybrid API:** Use the **NVIDIA API Catalog** (with free trial credits) to access and call the Nemotron LLM NIM endpoint. The NIM's robust tool-calling capability is essential here. |
| **NVIDIA Nemotron** | The underlying Foundation Model used by the LLM NIM endpoint, critical for complex **reasoning** and **tool-use**. | **Model Selection:** Specify a Nemotron model (e.g., Nemotron-4-340B or a smaller variant via NIM) in the API call configuration. |
| **NVIDIA NeMo Microservices** | Enforces enterprise safety and security around the GenAI interaction. | **Integration:** Implement the **NeMo Guardrails** logic (or a simulated policy-checking function) to check the final response for policy compliance. |
| **NVIDIA NeMo Agent Toolkit** | Provides **GenAIOps** capabilities for fine-grained **observability**, profiling, and debugging of the agent's complex workflow. | **Integration:** Instrument the Python Orchestrator and all tool calls (including the NIM inference calls) to export **latency**, **token usage**, and **tool tracing** data in **OpenTelemetry (OTel)** format. |

---

## 3. Hybrid Deployment Constraints (MacBook Optimization)

The full prototype is designed for a target NVIDIA GPU environment, but must run on a macOS machine using a hybrid strategy to bypass local VRAM limitations:

* **Local Components (macOS):** Python Agent Orchestrator (LangChain), Agent Memory/State (Redis/SQLite in Docker), the custom Tool functions, and the **OpenTelemetry Collector** (for observability data ingestion).
* **Remote Components (NVIDIA API Catalog):** The Nemotron LLM NIM and any required Embedding/Reranker NIMs are accessed via secure API keys. **This is free for trial/development use.**

---

## 4. Agent Toolset Specification

The Agent Orchestrator will expose these functions for the Nemotron NIM to use, simulating internal enterprise APIs/data sources:

| Tool Name | Simulated Functionality | Type of Demonstration |
| :--- | :--- | :--- |
| `InternalDocsSearch` | Performs a RAG query against a local document set (simulates access to internal deployment guides). Requires a local vector store setup. | **RAG-as-a-Tool** |
| `SecurityPolicyChecker` | Checks a local data structure (Python dictionary/list) to see if a given library (`NeMo Retriever`) is on the approved list. Returns `True` or `False`. | **Compliance Check/Policy Guardrail** |
| `CostEstimator` | Takes parameters (e.g., `model_size`, `tokens_per_month`) and calculates a mock GPU inference cost. | **Data Extraction & Calculation** |

---

## 5. Prototype Architecture Diagram

The agent runs locally but utilizes remote, high-performance NIMs for the core LLM intelligence. **The addition of the Observability node is key to demonstrating GenAIOps maturity.**

```mermaid
graph TD
    A[User Query: "Deploy NeMo feature..."] --> B{Agent Orchestrator / Planner (Local Python/LangChain)};
    B --> F[2. NeMo/Memory Component (Local Redis/DB)];
    F --> B;
    B --> C{1. LLM/Nemotron Model (Remote NIM API)};
    C --> D{Decides Action: Which Tool to Call?};
    D -- Call SecurityPolicyChecker --> E1[Tool: SecurityPolicyChecker];
    D -- Call InternalDocsSearch --> E2[Tool: InternalDocsSearch (Local RAG)];
    D -- Call CostEstimator --> E3[Tool: CostEstimator];
    E1 --> B;
    E2 --> B;
    E3 --> B;
    B -- Final Answer --> G{Guardrails Check (NeMo Logic)};
    G --> H[Final Agent Response];
    B -- Telemetry Data (Latency, Tokens, Trace) --> J[3. Observability/Telemetry (OTEL/NeMo Agent Toolkit)];
    C -- Telemetry Data (Latency, Tokens) --> J;
    E1 -- Telemetry Data (Latency) --> J;
    E2 -- Telemetry Data (Latency) --> J;
    E3 -- Telemetry Data (Latency) --> J;