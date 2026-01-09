"""Policy engine for Trust Plane authorization"""
from typing import List, Dict, Optional, Any
from enum import Enum
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


class PolicyAction(Enum):
    """Policy action types"""
    ALLOW = "ALLOW"
    DENY = "DENY"
    WARN = "WARN"


class PolicyOperator(Enum):
    """Comparison operators for policy rules"""
    LT = "lt"  # less than
    LTE = "lte"  # less than or equal
    GT = "gt"  # greater than
    GTE = "gte"  # greater than or equal
    EQ = "eq"  # equal
    NEQ = "neq"  # not equal


class PolicyRule:
    """Single policy rule

    Example:
        metric: max_freshness_days
        operator: lte
        threshold: 30
        action: DENY
        reason: "Data exceeds freshness threshold"
    """

    def __init__(self, rule_config: Dict):
        """Initialize policy rule from config

        Args:
            rule_config: Rule configuration dict
        """
        self.metric = rule_config.get("metric")
        self.operator = PolicyOperator(rule_config.get("operator", "lte"))
        self.threshold = rule_config.get("threshold")
        self.action = PolicyAction(rule_config.get("action", "DENY"))
        self.reason = rule_config.get("reason", f"{self.metric} failed policy check")

    def evaluate(self, metrics: Dict) -> Optional[PolicyAction]:
        """Evaluate rule against metrics

        Args:
            metrics: Data quality metrics dict

        Returns:
            PolicyAction if rule triggers, None otherwise
        """
        if self.metric not in metrics:
            logger.warning(f"Metric '{self.metric}' not found in dataset metadata")
            return None

        actual_value = metrics[self.metric]

        # Evaluate condition
        triggered = False
        if self.operator == PolicyOperator.LT:
            triggered = actual_value >= self.threshold  # Violates "should be less than"
        elif self.operator == PolicyOperator.LTE:
            triggered = actual_value > self.threshold  # Violates "should be less than or equal"
        elif self.operator == PolicyOperator.GT:
            triggered = actual_value <= self.threshold
        elif self.operator == PolicyOperator.GTE:
            triggered = actual_value < self.threshold
        elif self.operator == PolicyOperator.EQ:
            triggered = actual_value != self.threshold
        elif self.operator == PolicyOperator.NEQ:
            triggered = actual_value == self.threshold

        if triggered:
            logger.debug(
                f"Rule triggered: {self.metric} {actual_value} violates "
                f"{self.operator.value} {self.threshold}"
            )
            return self.action

        return None

    def get_details(self, metrics: Dict) -> Dict:
        """Get detailed evaluation info for logging

        Args:
            metrics: Data quality metrics dict

        Returns:
            Dict with rule details and actual values
        """
        actual_value = metrics.get(self.metric, "N/A")
        return {
            "metric": self.metric,
            "operator": self.operator.value,
            "threshold": self.threshold,
            "actual": actual_value,
            "action": self.action.value,
            "reason": self.reason
        }


class DatasetPolicy:
    """Policy for a specific dataset or dataset pattern"""

    def __init__(self, policy_config: Dict):
        """Initialize dataset policy

        Args:
            policy_config: Policy configuration dict
        """
        self.name = policy_config.get("name")
        self.dataset_pattern = policy_config.get("dataset_pattern", "*")
        self.namespace = policy_config.get("namespace", "*")
        self.enabled = policy_config.get("enabled", True)

        # Load rules
        self.rules = []
        for rule_config in policy_config.get("rules", []):
            self.rules.append(PolicyRule(rule_config))

    def matches_dataset(self, namespace: str, dataset_name: str) -> bool:
        """Check if this policy applies to the dataset

        Args:
            namespace: Dataset namespace
            dataset_name: Dataset name

        Returns:
            True if policy applies
        """
        if not self.enabled:
            return False

        # Simple wildcard matching
        namespace_match = (
            self.namespace == "*" or
            self.namespace == namespace
        )

        dataset_match = (
            self.dataset_pattern == "*" or
            self.dataset_pattern == dataset_name or
            # Pattern *.suffix matches anything.suffix
            (self.dataset_pattern.startswith("*.") and
             dataset_name.endswith(self.dataset_pattern[1:])) or
            # Pattern prefix.* matches prefix.anything
            (self.dataset_pattern.endswith(".*") and
             dataset_name.startswith(self.dataset_pattern[:-2]))
        )

        return namespace_match and dataset_match

    def evaluate(self, metrics: Dict) -> List[Dict]:
        """Evaluate all rules against metrics

        Args:
            metrics: Data quality metrics dict

        Returns:
            List of violations (rule details for triggered rules)
        """
        violations = []

        for rule in self.rules:
            action = rule.evaluate(metrics)
            if action:
                violation = rule.get_details(metrics)
                violation["policy_name"] = self.name
                violations.append(violation)

        return violations


class PolicyEngine:
    """Trust Plane policy engine

    Loads policies from YAML and evaluates them against dataset metadata.
    """

    def __init__(self, policy_file: Optional[str] = None):
        """Initialize policy engine

        Args:
            policy_file: Path to policies YAML file
        """
        self.policies: List[DatasetPolicy] = []
        self.policy_file = policy_file

        if policy_file:
            self.load_policies(policy_file)

    def load_policies(self, policy_file: str):
        """Load policies from YAML file

        Args:
            policy_file: Path to YAML file
        """
        policy_path = Path(policy_file)

        if not policy_path.exists():
            logger.warning(f"Policy file not found: {policy_file}")
            return

        try:
            with open(policy_path, 'r') as f:
                config = yaml.safe_load(f)

            policies_config = config.get("policies", [])
            self.policies = [DatasetPolicy(p) for p in policies_config]

            logger.info(f"✓ Loaded {len(self.policies)} policies from {policy_file}")

        except Exception as e:
            logger.error(f"Failed to load policies from {policy_file}: {e}")

    def evaluate_dataset(self, namespace: str, dataset_name: str, metrics: Dict) -> Dict:
        """Evaluate all applicable policies for a dataset

        Args:
            namespace: Dataset namespace
            dataset_name: Dataset name
            metrics: Data quality metrics

        Returns:
            Dict with:
            - allowed: bool
            - action: ALLOW/DENY/WARN
            - violations: List of policy violations
            - applicable_policies: Number of policies checked
        """
        applicable_policies = [
            p for p in self.policies
            if p.matches_dataset(namespace, dataset_name)
        ]

        if not applicable_policies:
            logger.debug(f"No policies apply to {namespace}/{dataset_name}")
            return {
                "allowed": True,
                "action": "ALLOW",
                "violations": [],
                "applicable_policies": 0,
                "reason": "No policies defined"
            }

        # Collect violations from all applicable policies
        all_violations = []
        for policy in applicable_policies:
            violations = policy.evaluate(metrics)
            all_violations.extend(violations)

        # Determine final action
        if not all_violations:
            return {
                "allowed": True,
                "action": "ALLOW",
                "violations": [],
                "applicable_policies": len(applicable_policies),
                "reason": "All policy checks passed"
            }

        # Check for DENY actions
        deny_violations = [v for v in all_violations if v["action"] == "DENY"]
        if deny_violations:
            return {
                "allowed": False,
                "action": "DENY",
                "violations": all_violations,
                "applicable_policies": len(applicable_policies),
                "reason": "; ".join([v["reason"] for v in deny_violations])
            }

        # Only warnings
        return {
            "allowed": True,
            "action": "WARN",
            "violations": all_violations,
            "applicable_policies": len(applicable_policies),
            "reason": "; ".join([v["reason"] for v in all_violations])
        }
