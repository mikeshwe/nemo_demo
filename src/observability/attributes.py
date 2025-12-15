"""Semantic conventions and attribute keys for AI observability"""

# Agent attributes
AGENT_QUERY = "agent.query"
AGENT_MAX_ITERATIONS = "agent.max_iterations"
AGENT_FINAL_ITERATIONS = "agent.final_iterations"
AGENT_TOOL_CALLS = "agent.tool_calls"
AGENT_SUCCESS = "agent.success"

# Iteration attributes
ITERATION_NUMBER = "iteration.number"
ITERATION_TYPE = "iteration.type"

# LLM attributes
LLM_MODEL = "llm.model"
LLM_TEMPERATURE = "llm.temperature"
LLM_MAX_TOKENS = "llm.max_tokens"
LLM_TOOL_CALLS_COUNT = "llm.tool_calls_count"
LLM_HAS_FINAL_ANSWER = "llm.has_final_answer"
LLM_MESSAGE_COUNT = "llm.message_count"
LLM_RESPONSE_TIME_MS = "llm.response_time_ms"

# Tool attributes
TOOL_NAME = "tool.name"
TOOL_ARGUMENTS = "tool.arguments"
TOOL_SUCCESS = "tool.success"
TOOL_RESULT_SIZE = "tool.result_size"
TOOL_ERROR = "tool.error"
TOOL_EXECUTION_TIME_MS = "tool.execution_time_ms"

# Guardrails attributes
GUARDRAILS_TYPE = "guardrails.type"  # "nemo" or "fallback"
GUARDRAILS_CHECK_TYPE = "guardrails.check_type"  # "input" or "output"
GUARDRAILS_PASSED = "guardrails.passed"
GUARDRAILS_REJECTION_REASON = "guardrails.rejection_reason"
GUARDRAILS_INPUT_LENGTH = "guardrails.input_length"
GUARDRAILS_OUTPUT_LENGTH = "guardrails.output_length"
GUARDRAILS_PATTERN_MATCHED = "guardrails.pattern_matched"

# RAG attributes
RAG_QUERY = "rag.query"
RAG_QUERY_LENGTH = "rag.query_length"
RAG_TOP_K = "rag.top_k"
RAG_RESULTS_COUNT = "rag.results_count"
RAG_TOP_SCORE = "rag.top_score"
RAG_SEARCH_TIME_MS = "rag.search_time_ms"

# Embedding attributes
EMBEDDING_MODEL = "embedding.model"
EMBEDDING_TEXT_LENGTH = "embedding.text_length"
EMBEDDING_DIMENSION = "embedding.dimension"
EMBEDDING_TIME_MS = "embedding.time_ms"

# State attributes
STATE_SHOULD_CONTINUE = "state.should_continue"
STATE_HAS_FINAL_ANSWER = "state.has_final_answer"
STATE_MESSAGE_COUNT = "state.message_count"

# Event names
EVENT_AGENT_START = "agent_start"
EVENT_AGENT_COMPLETE = "agent_complete"
EVENT_AGENT_ERROR = "agent_error"
EVENT_INPUT_BLOCKED = "input_blocked"
EVENT_OUTPUT_BLOCKED = "output_blocked"
EVENT_TOOL_CALL = "tool_call"
EVENT_ITERATION_START = "iteration_start"
EVENT_ITERATION_COMPLETE = "iteration_complete"
