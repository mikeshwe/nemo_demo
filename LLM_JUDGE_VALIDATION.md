# LLM-as-a-Judge Validation for Error Detection

## Concept

Use a **second LLM call** to judge whether the agent's answer is correct by comparing it to ground truth. This is more robust than regex patterns and can handle nuanced errors.

## Architecture

```
User Query
    ↓
Agent LLM (may use stale data)
    ↓
Agent Answer
    ↓
Judge LLM (compares to ground truth)
    ↓
Validation Result (correct/incorrect + reasoning)
    ↓
If incorrect → Trigger lineage analysis
```

## Implementation

### 1. Ground Truth Format

**`data/ground_truth.json`**:
```json
{
  "validation_queries": [
    {
      "query": "What are the latest deployment requirements for NeMo Retriever?",
      "correct_answer": "NeMo Retriever requires Python 3.11 or later, CUDA 12.0 or later, and Docker 24.0 or later. The system needs at least 16GB RAM and a GPU with 8GB VRAM. For production deployments, use Kubernetes 1.28+ with the NVIDIA GPU Operator installed.",
      "key_facts": [
        "Python 3.11 or later",
        "CUDA 12.0 or later",
        "Docker 24.0 or later",
        "16GB RAM minimum",
        "GPU with 8GB VRAM"
      ],
      "common_errors": {
        "stale_versions": {
          "Python 3.8": "This is the old requirement from 2023",
          "CUDA 11.0": "This was deprecated in Q4 2023",
          "Docker 19.03": "Outdated version from early 2023"
        }
      }
    },
    {
      "query": "Is NeMo Retriever approved for production use?",
      "correct_answer": "Yes, NeMo Retriever is approved for production deployment as of version 1.0, released in September 2023. It has passed all security audits and compliance reviews.",
      "key_facts": [
        "Approved for production",
        "Version 1.0 or later",
        "Security audited",
        "Compliance certified"
      ]
    }
  ]
}
```

### 2. LLM Judge Implementation

**`src/observability/llm_judge.py`**:
```python
"""LLM-as-a-Judge validator for response quality"""
from typing import Dict, Optional, List
import json
from pathlib import Path

class LLMJudge:
    """Use LLM to validate responses against ground truth"""

    JUDGE_SYSTEM_PROMPT = """You are an expert validator for AI assistant responses. Your job is to compare an AI's answer to a ground truth answer and determine if the AI's answer is correct, incorrect, or partially correct.

Focus on:
1. **Factual accuracy**: Are version numbers, requirements, and technical details correct?
2. **Completeness**: Does the answer cover all key points from ground truth?
3. **Staleness**: Does the answer contain outdated information?

Respond in JSON format:
{
  "verdict": "correct" | "incorrect" | "partial",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your decision",
  "errors": [
    {
      "type": "factual_error" | "outdated_info" | "missing_info",
      "description": "What's wrong",
      "severity": "critical" | "major" | "minor"
    }
  ],
  "correct_facts": ["list of correct facts mentioned"],
  "incorrect_facts": ["list of incorrect facts mentioned"],
  "missing_facts": ["list of important facts not mentioned"]
}"""

    def __init__(self, llm_client, ground_truth_path: str = "data/ground_truth.json"):
        """Initialize judge with LLM client and ground truth

        Args:
            llm_client: LLM client (same as agent uses)
            ground_truth_path: Path to ground truth JSON
        """
        self.llm_client = llm_client
        self.ground_truth = self._load_ground_truth(ground_truth_path)

    def _load_ground_truth(self, path: str) -> Dict:
        """Load ground truth data"""
        with open(path) as f:
            data = json.load(f)
            return {
                q["query"]: q for q in data["validation_queries"]
            }

    def validate(self, query: str, agent_answer: str) -> Dict:
        """Validate agent answer using LLM judge

        Args:
            query: Original user query
            agent_answer: Answer from the agent

        Returns:
            Validation result with verdict, errors, and reasoning
        """
        # Find ground truth
        ground_truth = self._find_ground_truth(query)
        if not ground_truth:
            return {
                "verdict": "unknown",
                "confidence": 0.0,
                "reasoning": "No ground truth available for this query",
                "errors": [],
                "has_ground_truth": False
            }

        # Construct judge prompt
        judge_prompt = self._create_judge_prompt(
            query=query,
            agent_answer=agent_answer,
            ground_truth=ground_truth
        )

        # Call judge LLM
        judge_response = self._call_judge_llm(judge_prompt)

        # Parse judge response
        validation_result = self._parse_judge_response(judge_response)
        validation_result["has_ground_truth"] = True
        validation_result["ground_truth"] = ground_truth

        return validation_result

    def _find_ground_truth(self, query: str) -> Optional[Dict]:
        """Find matching ground truth for query"""
        # Exact match
        if query in self.ground_truth:
            return self.ground_truth[query]

        # Fuzzy match on key phrases
        query_lower = query.lower()
        for gt_query, gt_data in self.ground_truth.items():
            # Extract key terms
            if self._queries_similar(query_lower, gt_query.lower()):
                return gt_data

        return None

    def _queries_similar(self, q1: str, q2: str) -> bool:
        """Check if queries are similar enough"""
        # Simple keyword matching
        key_phrases = [
            "deployment requirements",
            "approved for production",
            "security policy",
            "cost estimate"
        ]

        for phrase in key_phrases:
            if phrase in q1 and phrase in q2:
                return True

        return False

    def _create_judge_prompt(self, query: str, agent_answer: str, ground_truth: Dict) -> str:
        """Create prompt for judge LLM"""

        prompt = f"""**User Query:**
{query}

**AI Agent's Answer:**
{agent_answer}

**Ground Truth Answer:**
{ground_truth['correct_answer']}

**Key Facts That Should Be Present:**
{json.dumps(ground_truth['key_facts'], indent=2)}
"""

        # Add common errors if available
        if "common_errors" in ground_truth:
            prompt += f"""
**Common Errors to Watch For:**
{json.dumps(ground_truth['common_errors'], indent=2)}
"""

        prompt += """
**Your Task:**
Compare the AI's answer to the ground truth. Identify:
1. Factual errors (wrong version numbers, incorrect requirements)
2. Outdated information (old versions, deprecated features)
3. Missing critical facts

Provide your verdict in JSON format as specified in your system prompt.
"""

        return prompt

    def _call_judge_llm(self, prompt: str) -> str:
        """Call LLM for judgment"""
        messages = [
            {"role": "system", "content": self.JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_client.chat_completion(
            messages=messages,
            temperature=0.0,  # Deterministic for validation
            max_tokens=1000
        )

        return response.choices[0].message.content

    def _parse_judge_response(self, response: str) -> Dict:
        """Parse JSON response from judge LLM"""
        try:
            # Extract JSON from response (may have markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)

            # Validate required fields
            required = ["verdict", "confidence", "reasoning", "errors"]
            for field in required:
                if field not in result:
                    result[field] = None if field != "errors" else []

            return result

        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "verdict": "error",
                "confidence": 0.0,
                "reasoning": f"Failed to parse judge response: {e}",
                "errors": [{
                    "type": "parse_error",
                    "description": "Could not parse judge LLM response",
                    "severity": "critical"
                }],
                "raw_response": response
            }
```

### 3. Integration with Agent

**Update `src/orchestrator/agent.py`**:
```python
from src.observability.llm_judge import LLMJudge

class Agent:
    def __init__(self, llm_client, tool_registry, max_iterations=10):
        # ... existing init ...
        self.llm_judge = LLMJudge(llm_client)

    def run(self, query):
        """Run agent with LLM judge validation"""

        # ... existing agent execution ...

        final_answer = result.get("answer", "")

        # Validate with LLM judge
        print("\n[Validation] Running LLM judge...")
        validation_result = self.llm_judge.validate(query, final_answer)

        # Add to result
        result["validation"] = validation_result

        # Log validation
        self._log_validation(validation_result, query, final_answer)

        # If validation failed, analyze lineage
        if validation_result["verdict"] == "incorrect":
            print(f"\n⚠️  LLM Judge Verdict: {validation_result['verdict'].upper()}")
            print(f"   Confidence: {validation_result['confidence']:.2f}")
            print(f"   Reasoning: {validation_result['reasoning']}")

            if validation_result.get("errors"):
                print(f"\n   Errors found:")
                for error in validation_result["errors"]:
                    severity_icon = "🔴" if error["severity"] == "critical" else "🟡"
                    print(f"     {severity_icon} [{error['type']}] {error['description']}")

            # Trigger lineage analysis
            if is_lineage_enabled():
                self._analyze_data_lineage(validation_result)

        elif validation_result["verdict"] == "correct":
            print(f"\n✅ LLM Judge Verdict: CORRECT")
            print(f"   Confidence: {validation_result['confidence']:.2f}")

        return result

    def _log_validation(self, validation_result, query, answer):
        """Log validation to OpenTelemetry and Langfuse"""

        verdict = validation_result.get("verdict", "unknown")
        confidence = validation_result.get("confidence", 0.0)
        errors = validation_result.get("errors", [])

        # OpenTelemetry
        if OTEL_AVAILABLE and is_initialized():
            span = trace.get_current_span()
            span.set_attribute("validation.verdict", verdict)
            span.set_attribute("validation.confidence", confidence)
            span.set_attribute("validation.error_count", len(errors))
            span.set_attribute("validation.method", "llm_judge")

            # Add errors as events
            for error in errors:
                span.add_event(
                    name=f"validation_error_{error['type']}",
                    attributes={
                        "description": error["description"],
                        "severity": error["severity"]
                    }
                )

        # Langfuse
        if LANGFUSE_AVAILABLE and is_langfuse_enabled():
            # Add validation score
            score_value = 1.0 if verdict == "correct" else 0.0
            score_generation(
                name="llm_judge_accuracy",
                value=score_value,
                comment=f"{verdict} (confidence: {confidence:.2f}) - {validation_result['reasoning']}"
            )

            # Add confidence score
            score_generation(
                name="validation_confidence",
                value=confidence,
                comment=f"LLM judge confidence in {verdict} verdict"
            )

            # If errors found, add detailed score
            if errors:
                critical_errors = [e for e in errors if e["severity"] == "critical"]
                if critical_errors:
                    score_generation(
                        name="critical_errors",
                        value=0.0,
                        comment="; ".join(e["description"] for e in critical_errors)
                    )

            # Log the judge's reasoning as metadata
            log_llm_generation(
                name="llm_judge_validation",
                model=self.llm_judge.llm_client.model_name,
                input_messages=[
                    {"role": "system", "content": LLMJudge.JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Query: {query}\nAnswer: {answer}"}
                ],
                output=json.dumps(validation_result, indent=2),
                metadata={
                    "validation_type": "llm_judge",
                    "verdict": verdict,
                    "confidence": confidence
                }
            )
```

### 4. Demo Output

**`demo_lineage.py` with LLM judge**:
```python
def demo_flow():
    print("="*70)
    print("Data Lineage Demo with LLM Judge Validation")
    print("="*70)

    # Step 1: Setup stale data
    print("\n[Step 1] Creating stale documentation (45 days old)...")
    inject_stale_data()

    # Step 2: Ingest with lineage
    print("\n[Step 2] Ingesting documents with lineage tracking...")
    run_ingestion()
    # Lineage shows: avg_freshness_days=42

    # Step 3: Query agent
    print("\n[Step 3] Querying agent...")
    query = "What are the latest deployment requirements for NeMo Retriever?"
    result = agent.run(query)

    print(f"\n  Query: {query}")
    print(f"  Answer: {result['answer']}")

    # Step 4: LLM Judge validates
    print("\n[Step 4] LLM Judge Validation:")

    validation = result['validation']

    if validation['verdict'] == 'incorrect':
        print(f"""
  ⚠️  VERDICT: INCORRECT (confidence: {validation['confidence']:.0%})

  Reasoning:
    {validation['reasoning']}

  Errors Detected:
""")
        for error in validation['errors']:
            severity_icon = "🔴" if error['severity'] == 'critical' else "🟡"
            print(f"    {severity_icon} {error['type']}: {error['description']}")

        if validation.get('incorrect_facts'):
            print(f"\n  Incorrect Facts:")
            for fact in validation['incorrect_facts']:
                print(f"    ❌ {fact}")

        if validation.get('missing_facts'):
            print(f"\n  Missing Facts:")
            for fact in validation['missing_facts']:
                print(f"    ⚠️  {fact}")

        print(f"\n  ▶️  Analyzing data lineage for root cause...")
        # Lineage analysis shows stale data

    print(f"""
[Step 5] Root Cause Analysis via Lineage:

  📊 Data Pipeline:
    Source: nemo_retriever_setup.md
    Last Modified: 45 days ago ⚠️
    ↓
    Ingestion Job (30 days ago)
    ↓
    Vector DB: internal_docs.chunks
    Avg Freshness: 42 days ⚠️
    ↓
    Agent Query (just now)
    ↓
    LLM Answer: INCORRECT (stale data used)

  🔍 Root Cause: Source documentation is outdated!

  🔧 Resolution:
    1. Update data/docs/nemo_retriever_setup.md
    2. Re-run ingestion: python scripts/setup_vectorstore.py --lineage
    3. Re-query agent to verify fix

[Step 6] View in Observability Dashboards:
  • Langfuse (https://cloud.langfuse.com):
    - See agent trace with llm_judge_accuracy=0.0 score
    - View judge reasoning in generation metadata
    - Filter traces by validation verdict

  • Marquez (http://localhost:3000):
    - Visual lineage graph showing stale data flow
    - Data quality facets with freshness metrics
    - Impact analysis: which queries affected

  • OpenTelemetry (console):
    - Spans with validation.verdict=incorrect attribute
    - Lineage context linking to stale dataset
    - Complete trace from query → RAG → LLM → validation
""")
```

## Example Judge Response

**Agent Answer (using stale data)**:
```
"NeMo Retriever requires Python 3.8, CUDA 11.0, and Docker 19.03..."
```

**Judge LLM Response**:
```json
{
  "verdict": "incorrect",
  "confidence": 0.95,
  "reasoning": "The answer contains multiple outdated version requirements. Python 3.8, CUDA 11.0, and Docker 19.03 were the requirements in early 2023 but have since been updated. Current requirements are Python 3.11+, CUDA 12.0+, and Docker 24.0+.",
  "errors": [
    {
      "type": "outdated_info",
      "description": "Python 3.8 is outdated. Current requirement is Python 3.11+",
      "severity": "critical"
    },
    {
      "type": "outdated_info",
      "description": "CUDA 11.0 is outdated. Current requirement is CUDA 12.0+",
      "severity": "critical"
    },
    {
      "type": "outdated_info",
      "description": "Docker 19.03 is outdated. Current requirement is Docker 24.0+",
      "severity": "major"
    }
  ],
  "correct_facts": [],
  "incorrect_facts": [
    "Python 3.8",
    "CUDA 11.0",
    "Docker 19.03"
  ],
  "missing_facts": [
    "Python 3.11 or later",
    "CUDA 12.0 or later",
    "16GB RAM minimum"
  ]
}
```

## Benefits of LLM Judge

### vs. Regex Patterns
- ✅ **Flexible**: Handles variations in phrasing
- ✅ **Nuanced**: Can detect semantic errors, not just keyword mismatches
- ✅ **Explainable**: Provides reasoning for verdict
- ✅ **Adaptable**: Works with different answer formats

### vs. Semantic Similarity
- ✅ **Precise**: Can identify specific factual errors
- ✅ **Categorical**: Classifies error types (outdated, missing, wrong)
- ✅ **Actionable**: Points to exact issues to fix

### For Demo
- ✅ **Automated**: No human judgment needed
- ✅ **Transparent**: Shows judge's reasoning
- ✅ **Integrated**: Logs to all observability platforms
- ✅ **Realistic**: This is how production LLM systems actually do validation

## Cost Considerations

**Per validation**: 1 additional LLM call
- **Input tokens**: ~500 (system prompt + ground truth + answers)
- **Output tokens**: ~200 (JSON verdict)
- **Cost**: ~$0.0006 per validation (NVIDIA NIM pricing)

**For demo**: Negligible cost, high value

## Observability Integration

### Langfuse
```python
# Agent LLM generation
Generation 1: "reasoning_iteration_1"
  Input: User query + RAG context (stale)
  Output: Wrong answer
  Cost: $0.0023

# Judge LLM generation
Generation 2: "llm_judge_validation"
  Input: Query + agent answer + ground truth
  Output: {"verdict": "incorrect", ...}
  Cost: $0.0006

# Scores
- llm_judge_accuracy: 0.0
- validation_confidence: 0.95
- critical_errors: 0.0
```

### OpenTelemetry
```python
span.set_attribute("validation.method", "llm_judge")
span.set_attribute("validation.verdict", "incorrect")
span.set_attribute("validation.confidence", 0.95)
span.add_event("validation_error_outdated_info", {
    "description": "Python 3.8 is outdated"
})
```

### OpenLineage
```python
# Link validation failure to data quality
{
  "outputs": [{
    "namespace": "chromadb",
    "name": "internal_docs.chunks",
    "facets": {
      "dataQualityAssertions": {
        "assertions": [{
          "assertion": "produces_correct_llm_answers",
          "success": false,
          "column": "content",
          "measurement": {
            "validation_verdict": "incorrect",
            "validation_confidence": 0.95
          }
        }]
      }
    }
  }]
}
```

## Files to Create/Modify

### New Files
1. `src/observability/llm_judge.py` - Judge implementation
2. `data/ground_truth.json` - Ground truth dataset

### Modified Files
3. `src/orchestrator/agent.py` - Integration
4. `demo_lineage.py` - Show judge in action
5. `docs/OPENLINEAGE.md` - Document LLM judge approach

**Total additional work**: 2-3 hours

## Testing the Judge

```python
# test_llm_judge.py
from src.observability.llm_judge import LLMJudge

judge = LLMJudge(llm_client)

# Test 1: Incorrect answer (stale data)
result = judge.validate(
    query="What are the deployment requirements?",
    agent_answer="Python 3.8, CUDA 11.0, Docker 19.03"
)
assert result["verdict"] == "incorrect"
assert len(result["errors"]) > 0
print(f"✓ Detected stale answer")

# Test 2: Correct answer
result = judge.validate(
    query="What are the deployment requirements?",
    agent_answer="Python 3.11+, CUDA 12.0+, Docker 24.0+"
)
assert result["verdict"] == "correct"
print(f"✓ Validated correct answer")
```

## Recommendation

**Use LLM Judge as primary validation method**:
- More robust than regex
- Production-realistic
- Provides explainable results
- Integrates cleanly with existing observability

Keep regex/fact extraction as fallback for when ground truth is unavailable.
