"""LLM-as-a-Judge for answer validation"""
import json
from pathlib import Path
from typing import Dict, Optional, List
import logging

from .verdict import Verdict, VerdictType, GroundTruthEntry

logger = logging.getLogger(__name__)


JUDGE_SYSTEM_PROMPT = """You are an expert fact-checker evaluating the accuracy of AI assistant answers against ground truth documentation.

Your task is to compare the assistant's answer to the expected correct answer and determine if it is factually accurate.

Focus on:
1. Factual correctness - Are the key facts correct?
2. Completeness - Are important details missing?
3. Version accuracy - Are version numbers, dates, or requirements correct?
4. Misleading information - Could the answer lead to wrong conclusions?

Be strict but fair. Small phrasing differences are okay if the meaning is correct.

You must respond ONLY with valid JSON in this exact format:
{
  "verdict": "CORRECT" | "INCORRECT" | "PARTIAL" | "UNCLEAR",
  "confidence": 0.0-1.0,
  "reasoning": "Detailed explanation of your verdict",
  "errors": ["specific error 1", "specific error 2"],
  "key_facts_missing": ["missing fact 1"],
  "key_facts_incorrect": ["incorrect fact 1"]
}

Verdict types:
- CORRECT: Answer is factually accurate and complete
- INCORRECT: Answer contains wrong information or critical omissions
- PARTIAL: Some facts correct, some missing/wrong
- UNCLEAR: Cannot determine due to ambiguity
"""


def create_judge_prompt(
    query: str,
    agent_answer: str,
    ground_truth: GroundTruthEntry
) -> str:
    """Create prompt for judge LLM

    Args:
        query: User's question
        agent_answer: Agent's response
        ground_truth: Expected correct answer with key facts

    Returns:
        Formatted prompt string
    """
    prompt = f"""# Query
{query}

# Agent's Answer
{agent_answer}

# Expected Correct Answer
{ground_truth.expected_answer}

# Key Facts That Must Be Present
"""
    for i, fact in enumerate(ground_truth.key_facts, 1):
        prompt += f"{i}. {fact}\n"

    if ground_truth.common_errors:
        prompt += "\n# Common Errors to Watch For\n"
        for error in ground_truth.common_errors:
            prompt += f"- {error.get('description', 'Unknown error')}\n"

    prompt += """
# Your Task
Evaluate if the agent's answer is factually correct compared to the expected answer.
Check if all key facts are present and accurate.

Respond with JSON only."""

    return prompt


def parse_judge_response(response_text: str) -> Dict:
    """Parse judge LLM response to extract JSON

    Args:
        response_text: Raw LLM response

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If JSON cannot be extracted
    """
    # Try to extract JSON from response
    response_text = response_text.strip()

    # Remove markdown code blocks if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse judge response as JSON: {e}")
        logger.error(f"Response text: {response_text[:200]}")
        raise ValueError(f"Judge response is not valid JSON: {e}")


def validate_answer(
    query: str,
    agent_answer: str,
    ground_truth: GroundTruthEntry,
    llm_client,
    judge_model: str = "meta/llama-3.1-70b-instruct"
) -> Verdict:
    """Validate agent answer using LLM-as-a-Judge

    This makes a second LLM call to validate the agent's answer
    against the ground truth expected answer.

    Args:
        query: User's question
        agent_answer: Agent's response to validate
        ground_truth: Ground truth entry with expected answer
        llm_client: LLM client for judge
        judge_model: Model to use for judge (default: llama-3.1-70b)

    Returns:
        Verdict with correctness assessment

    Example:
        >>> verdict = validate_answer(
        ...     query="Is NeMo approved?",
        ...     agent_answer="Yes",
        ...     ground_truth=ground_truth_entry,
        ...     llm_client=client
        ... )
        >>> if not verdict.is_correct:
        ...     print(f"Error: {verdict.reasoning}")
    """
    try:
        # Create judge prompt
        judge_prompt = create_judge_prompt(query, agent_answer, ground_truth)

        logger.debug("Calling judge LLM...")
        logger.debug(f"Judge prompt length: {len(judge_prompt)} chars")

        # Call judge LLM
        response = llm_client.chat.completions.create(
            model=judge_model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=0.1,  # Low temperature for consistent verdicts
            max_tokens=1000
        )

        response_text = response.choices[0].message.content
        logger.debug(f"Judge response: {response_text[:200]}")

        # Parse JSON response
        verdict_data = parse_judge_response(response_text)

        # Create Verdict object
        verdict = Verdict(
            verdict=VerdictType(verdict_data.get("verdict", "UNCLEAR")),
            confidence=float(verdict_data.get("confidence", 0.0)),
            reasoning=verdict_data.get("reasoning", "No reasoning provided"),
            errors=verdict_data.get("errors", []),
            key_facts_missing=verdict_data.get("key_facts_missing", []),
            key_facts_incorrect=verdict_data.get("key_facts_incorrect", []),
            raw_response=verdict_data
        )

        logger.info(
            f"Judge verdict: {verdict.verdict.value} "
            f"(confidence: {verdict.confidence:.2f})"
        )

        if verdict.has_errors:
            logger.warning(f"Errors detected: {verdict.errors}")

        return verdict

    except Exception as e:
        logger.error(f"Judge validation failed: {e}", exc_info=True)

        # Return UNCLEAR verdict on error
        return Verdict(
            verdict=VerdictType.UNCLEAR,
            confidence=0.0,
            reasoning=f"Validation failed due to error: {str(e)}",
            errors=[f"Judge error: {str(e)}"]
        )


def load_ground_truth(file_path: Optional[str] = None) -> Dict[str, GroundTruthEntry]:
    """Load ground truth dataset from JSON file

    Args:
        file_path: Path to ground truth JSON file
                   (default: data/ground_truth.json)

    Returns:
        Dict mapping query to GroundTruthEntry

    Example:
        >>> ground_truth = load_ground_truth()
        >>> entry = ground_truth.get("Is NeMo Retriever approved?")
        >>> print(entry.expected_answer)
    """
    if not file_path:
        file_path = "data/ground_truth.json"

    file_path = Path(file_path)

    if not file_path.exists():
        logger.warning(f"Ground truth file not found: {file_path}")
        return {}

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        ground_truth = {}
        for entry_data in data.get("entries", []):
            entry = GroundTruthEntry.from_dict(entry_data)
            ground_truth[entry.query] = entry

        logger.info(f"✓ Loaded {len(ground_truth)} ground truth entries from {file_path}")
        return ground_truth

    except Exception as e:
        logger.error(f"Failed to load ground truth from {file_path}: {e}")
        return {}


def find_matching_ground_truth(
    query: str,
    ground_truth_db: Dict[str, GroundTruthEntry]
) -> Optional[GroundTruthEntry]:
    """Find matching ground truth entry for a query

    Uses exact match first, then case-insensitive match.

    Args:
        query: User query
        ground_truth_db: Dict of ground truth entries

    Returns:
        Matching GroundTruthEntry or None
    """
    # Exact match
    if query in ground_truth_db:
        return ground_truth_db[query]

    # Case-insensitive match
    query_lower = query.lower().strip()
    for gt_query, entry in ground_truth_db.items():
        if gt_query.lower().strip() == query_lower:
            return entry

    logger.debug(f"No ground truth found for query: {query}")
    return None
