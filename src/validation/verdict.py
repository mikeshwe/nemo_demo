"""Verdict data structures for LLM Judge"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class VerdictType(Enum):
    """Verdict type classification"""
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    PARTIAL = "PARTIAL"
    UNCLEAR = "UNCLEAR"


@dataclass
class Verdict:
    """LLM Judge verdict on answer correctness

    Attributes:
        verdict: CORRECT, INCORRECT, PARTIAL, or UNCLEAR
        confidence: Confidence score 0.0-1.0
        reasoning: Detailed explanation of the verdict
        errors: List of specific errors found
        key_facts_missing: Missing important facts
        key_facts_incorrect: Incorrectly stated facts
        is_correct: Convenience property (verdict == CORRECT)
        raw_response: Raw JSON response from judge LLM
    """
    verdict: VerdictType
    confidence: float
    reasoning: str
    errors: List[str] = field(default_factory=list)
    key_facts_missing: List[str] = field(default_factory=list)
    key_facts_incorrect: List[str] = field(default_factory=list)
    raw_response: Optional[Dict] = None

    @property
    def is_correct(self) -> bool:
        """Check if answer is correct

        Returns:
            True if verdict is CORRECT
        """
        return self.verdict == VerdictType.CORRECT

    @property
    def is_incorrect(self) -> bool:
        """Check if answer is incorrect

        Returns:
            True if verdict is INCORRECT
        """
        return self.verdict == VerdictType.INCORRECT

    @property
    def has_errors(self) -> bool:
        """Check if errors were found

        Returns:
            True if any errors exist
        """
        return len(self.errors) > 0 or len(self.key_facts_incorrect) > 0

    def to_dict(self) -> Dict:
        """Convert to dict for logging

        Returns:
            Dict representation
        """
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "errors": self.errors,
            "key_facts_missing": self.key_facts_missing,
            "key_facts_incorrect": self.key_facts_incorrect,
            "is_correct": self.is_correct,
            "has_errors": self.has_errors
        }

    def __str__(self) -> str:
        """String representation"""
        status = "✓" if self.is_correct else "✗"
        return (
            f"{status} {self.verdict.value} "
            f"(confidence: {self.confidence:.2f})\n"
            f"Reasoning: {self.reasoning}"
        )


@dataclass
class GroundTruthEntry:
    """Ground truth entry for a specific query

    Attributes:
        query: The user query
        expected_answer: The correct answer
        key_facts: List of critical facts that must be present
        common_errors: Known common errors (e.g., outdated info)
        metadata: Additional metadata for this query
    """
    query: str
    expected_answer: str
    key_facts: List[str] = field(default_factory=list)
    common_errors: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'GroundTruthEntry':
        """Create from dict

        Args:
            data: Dict with ground truth data

        Returns:
            GroundTruthEntry instance
        """
        return cls(
            query=data.get("query", ""),
            expected_answer=data.get("expected_answer", ""),
            key_facts=data.get("key_facts", []),
            common_errors=data.get("common_errors", []),
            metadata=data.get("metadata", {})
        )

    def to_dict(self) -> Dict:
        """Convert to dict

        Returns:
            Dict representation
        """
        return {
            "query": self.query,
            "expected_answer": self.expected_answer,
            "key_facts": self.key_facts,
            "common_errors": self.common_errors,
            "metadata": self.metadata
        }
