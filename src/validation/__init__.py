"""LLM-as-a-Judge validation for reactive error detection

This module provides LLM-based validation of agent answers against
ground truth to detect errors AFTER they occur and trace them back
to data quality issues.

Components:
- Judge: LLM-as-a-Judge for answer validation
- Verdict: Structured verdict data with confidence and reasoning
- Ground Truth: Expected answers and key facts

Usage:
    from src.validation import validate_answer, load_ground_truth

    ground_truth = load_ground_truth()
    verdict = validate_answer(
        query="Is NeMo Retriever approved?",
        agent_answer="Yes, it's approved for production use.",
        ground_truth=ground_truth
    )

    if not verdict.is_correct:
        print(f"Error detected: {verdict.reasoning}")
        print(f"Errors: {verdict.errors}")
"""
from .judge import validate_answer, load_ground_truth
from .verdict import Verdict

__all__ = [
    'validate_answer',
    'load_ground_truth',
    'Verdict'
]
