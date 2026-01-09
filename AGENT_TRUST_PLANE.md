# Agent Trust Plane: Proactive Data Quality Control

## Concept

An **Agent Trust Plane** that acts as a gatekeeper between the agent and data sources, using OpenLineage metadata to **prevent** the agent from using stale or low-quality data, rather than just detecting errors after the fact.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Execution                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ (wants to call RAG tool)
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT TRUST PLANE                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. Data Quality Policy Engine                             │  │
│  │    - Check freshness thresholds                           │  │
│  │    - Validate data quality metrics                        │  │
│  │    - Query OpenLineage for dataset metadata               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 2. Decision Engine                                        │  │
│  │    ALLOW    - Data meets quality thresholds               │  │
│  │    DENY     - Data too stale/poor quality                 │  │
│  │    WARN     - Data borderline, log warning                │  │
│  │    FALLBACK - Use alternative data source                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                           ↓                                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 3. Observability Integration                              │  │
│  │    - Log decision to OTel (span events)                   │  │
│  │    - Log to Langfuse (metadata)                           │  │
│  │    - Emit OpenLineage quality assertion                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├─ ALLOW → Execute RAG tool
             ├─ DENY  → Return error, trigger data refresh
             ├─ WARN  → Execute but flag in observability
             └─ FALLBACK → Use alternative source (e.g., web search)
```

## Data Quality Policies

### Policy Configuration

**`config/data_quality_policies.yaml`**:
```yaml
# Data Quality Policies for Agent Trust Plane

policies:
  - name: "rag_data_freshness"
    description: "RAG vector store data must be fresh"
    scope:
      datasets:
        - "chromadb://internal_docs.chunks"
    rules:
      - metric: "avg_freshness_days"
        operator: "<="
        threshold: 7
        severity: "critical"
        action: "deny"
        message: "Data is too stale (>{threshold} days old)"

      - metric: "avg_freshness_days"
        operator: "<="
        threshold: 14
        severity: "warning"
        action: "warn"
        message: "Data freshness borderline (>{threshold} days)"

    fallback:
      enabled: true
      strategy: "web_search"
      message: "Using web search due to stale local data"

  - name: "rag_data_completeness"
    description: "RAG must have sufficient documents"
    scope:
      datasets:
        - "chromadb://internal_docs.chunks"
    rules:
      - metric: "row_count"
        operator: ">="
        threshold: 50
        severity: "critical"
        action: "deny"
        message: "Insufficient documents in vector store"

  - name: "source_data_staleness"
    description: "Source documents must be recent"
    scope:
      datasets:
        - "file://data/docs/*"
    rules:
      - metric: "max_freshness_days"
        operator: "<="
        threshold: 30
        severity: "warning"
        action: "warn"
        message: "Source documents may be outdated"

# Default action when no policy matches
default_action: "allow"

# Alerting thresholds
alerting:
  denial_rate_threshold: 0.1  # Alert if >10% of requests denied
  warning_rate_threshold: 0.3  # Alert if >30% of requests warned
```

## Implementation

### 1. Trust Plane Core

**`src/trust_plane/__init__.py`**:
```python
"""Agent Trust Plane - Proactive data quality control"""
from .engine import TrustPlaneEngine
from .policies import PolicyLoader, DataQualityPolicy
from .decision import TrustDecision

__all__ = [
    'TrustPlaneEngine',
    'PolicyLoader',
    'DataQualityPolicy',
    'TrustDecision'
]
```

**`src/trust_plane/decision.py`**:
```python
"""Trust decision types"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict

class TrustAction(Enum):
    """Trust plane decision actions"""
    ALLOW = "allow"          # Proceed with operation
    DENY = "deny"            # Block operation
    WARN = "warn"            # Allow but log warning
    FALLBACK = "fallback"    # Use alternative source

@dataclass
class TrustDecision:
    """Result of trust plane evaluation"""
    action: TrustAction
    reason: str
    policy_name: str
    dataset_name: str
    metrics: Dict[str, float]
    violations: List[Dict]
    fallback_strategy: Optional[str] = None

    def is_allowed(self) -> bool:
        """Check if operation is allowed"""
        return self.action in [TrustAction.ALLOW, TrustAction.WARN]

    def requires_fallback(self) -> bool:
        """Check if fallback is needed"""
        return self.action == TrustAction.FALLBACK

    def is_denied(self) -> bool:
        """Check if operation is denied"""
        return self.action == TrustAction.DENY
```

**`src/trust_plane/engine.py`**:
```python
"""Trust Plane Engine - Main evaluation logic"""
from typing import Dict, List, Optional
import logging
from datetime import datetime

from .decision import TrustDecision, TrustAction
from .policies import PolicyLoader, DataQualityPolicy
from src.observability.lineage import get_lineage_client, is_lineage_enabled

# OpenTelemetry imports
try:
    from src.observability import get_tracer, is_initialized
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# Langfuse imports
try:
    from src.observability.langfuse_integration import (
        is_langfuse_enabled,
        score_generation,
        log_tool_execution
    )
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

logger = logging.getLogger(__name__)

class TrustPlaneEngine:
    """Agent Trust Plane - Validates data quality before tool execution"""

    def __init__(self, policy_file: str = "config/data_quality_policies.yaml"):
        """Initialize trust plane

        Args:
            policy_file: Path to data quality policies
        """
        self.policy_loader = PolicyLoader(policy_file)
        self.policies = self.policy_loader.load_policies()

        # Statistics
        self.stats = {
            "total_checks": 0,
            "allowed": 0,
            "denied": 0,
            "warned": 0,
            "fallback": 0
        }

        logger.info(f"Trust Plane initialized with {len(self.policies)} policies")

    def authorize_dataset_access(
        self,
        dataset_namespace: str,
        dataset_name: str,
        operation: str = "read"
    ) -> TrustDecision:
        """Check if agent is authorized to access dataset

        Args:
            dataset_namespace: Dataset namespace (e.g., "chromadb")
            dataset_name: Dataset name (e.g., "internal_docs.chunks")
            operation: Operation type (read, write)

        Returns:
            TrustDecision with action and reason
        """
        self.stats["total_checks"] += 1

        dataset_uri = f"{dataset_namespace}://{dataset_name}"

        # Log to observability
        if OTEL_AVAILABLE and is_initialized():
            tracer = get_tracer()
            with tracer.start_as_current_span("trust_plane.authorize") as span:
                span.set_attribute("trust_plane.dataset", dataset_uri)
                span.set_attribute("trust_plane.operation", operation)

                decision = self._evaluate_dataset(
                    dataset_namespace,
                    dataset_name,
                    operation
                )

                span.set_attribute("trust_plane.decision", decision.action.value)
                span.set_attribute("trust_plane.policy", decision.policy_name)

                if decision.is_denied():
                    span.add_event("trust_plane_denial", {
                        "reason": decision.reason,
                        "policy": decision.policy_name
                    })
                elif decision.action == TrustAction.WARN:
                    span.add_event("trust_plane_warning", {
                        "reason": decision.reason
                    })
        else:
            decision = self._evaluate_dataset(
                dataset_namespace,
                dataset_name,
                operation
            )

        # Log to Langfuse
        if LANGFUSE_AVAILABLE and is_langfuse_enabled():
            log_tool_execution(
                name="trust_plane_check",
                input_args={
                    "dataset": dataset_uri,
                    "operation": operation
                },
                output={
                    "action": decision.action.value,
                    "reason": decision.reason,
                    "metrics": decision.metrics
                },
                metadata={
                    "policy": decision.policy_name,
                    "violations": len(decision.violations)
                }
            )

            # Add trust score
            trust_score = 1.0 if decision.is_allowed() else 0.0
            score_generation(
                name="data_trust_score",
                value=trust_score,
                comment=f"{decision.action.value}: {decision.reason}"
            )

        # Update stats
        if decision.action == TrustAction.ALLOW:
            self.stats["allowed"] += 1
        elif decision.action == TrustAction.DENY:
            self.stats["denied"] += 1
        elif decision.action == TrustAction.WARN:
            self.stats["warned"] += 1
        elif decision.action == TrustAction.FALLBACK:
            self.stats["fallback"] += 1

        # Log decision
        self._log_decision(decision)

        return decision

    def _evaluate_dataset(
        self,
        namespace: str,
        name: str,
        operation: str
    ) -> TrustDecision:
        """Evaluate dataset against policies"""

        dataset_uri = f"{namespace}://{name}"

        # Find applicable policies
        applicable_policies = self._find_policies(dataset_uri)

        if not applicable_policies:
            # No policies, use default action
            return TrustDecision(
                action=TrustAction.ALLOW,
                reason="No applicable policies found",
                policy_name="default",
                dataset_name=dataset_uri,
                metrics={},
                violations=[]
            )

        # Get dataset metadata from OpenLineage
        dataset_metadata = self._get_dataset_metadata(namespace, name)

        if not dataset_metadata:
            # Can't get metadata, be conservative
            return TrustDecision(
                action=TrustAction.WARN,
                reason="Unable to retrieve dataset metadata from lineage",
                policy_name="default",
                dataset_name=dataset_uri,
                metrics={},
                violations=[]
            )

        # Evaluate each policy
        violations = []
        highest_severity_action = TrustAction.ALLOW
        policy_triggered = None

        for policy in applicable_policies:
            policy_violations = policy.evaluate(dataset_metadata)

            if policy_violations:
                violations.extend(policy_violations)

                # Get highest severity action
                for violation in policy_violations:
                    action = TrustAction(violation["action"])
                    if self._action_severity(action) > self._action_severity(highest_severity_action):
                        highest_severity_action = action
                        policy_triggered = policy

        # Build decision
        if highest_severity_action == TrustAction.ALLOW:
            reason = "All data quality checks passed"
            policy_name = "all_policies"
        else:
            reason = "; ".join(v["message"] for v in violations)
            policy_name = policy_triggered.name if policy_triggered else "unknown"

        decision = TrustDecision(
            action=highest_severity_action,
            reason=reason,
            policy_name=policy_name,
            dataset_name=dataset_uri,
            metrics=dataset_metadata.get("metrics", {}),
            violations=violations
        )

        # Add fallback strategy if applicable
        if decision.action == TrustAction.FALLBACK and policy_triggered:
            decision.fallback_strategy = policy_triggered.fallback.get("strategy")

        return decision

    def _find_policies(self, dataset_uri: str) -> List[DataQualityPolicy]:
        """Find policies applicable to dataset"""
        applicable = []

        for policy in self.policies:
            if policy.applies_to(dataset_uri):
                applicable.append(policy)

        return applicable

    def _get_dataset_metadata(self, namespace: str, name: str) -> Optional[Dict]:
        """Get dataset metadata from OpenLineage

        This queries the OpenLineage backend (Marquez) for dataset facets
        """
        if not is_lineage_enabled():
            logger.warning("OpenLineage not enabled, cannot retrieve metadata")
            return None

        # In production, this would query Marquez API
        # For now, we'll get from local cache/context

        # Try to get from lineage client
        lineage_client = get_lineage_client()
        if not lineage_client:
            return None

        # Get latest dataset metadata
        # This should be cached from the last ingestion job
        metadata = lineage_client.get_dataset_metadata(namespace, name)

        return metadata

    def _action_severity(self, action: TrustAction) -> int:
        """Get severity level of action (higher = more severe)"""
        severity_map = {
            TrustAction.ALLOW: 0,
            TrustAction.WARN: 1,
            TrustAction.FALLBACK: 2,
            TrustAction.DENY: 3
        }
        return severity_map.get(action, 0)

    def _log_decision(self, decision: TrustDecision):
        """Log trust decision"""
        if decision.is_denied():
            logger.warning(
                f"Trust Plane DENIED access to {decision.dataset_name}: "
                f"{decision.reason}"
            )
        elif decision.action == TrustAction.WARN:
            logger.warning(
                f"Trust Plane WARNING for {decision.dataset_name}: "
                f"{decision.reason}"
            )
        elif decision.requires_fallback():
            logger.info(
                f"Trust Plane FALLBACK for {decision.dataset_name}: "
                f"{decision.reason} (using {decision.fallback_strategy})"
            )
        else:
            logger.debug(
                f"Trust Plane ALLOWED access to {decision.dataset_name}"
            )

    def get_stats(self) -> Dict:
        """Get trust plane statistics"""
        total = self.stats["total_checks"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "denial_rate": self.stats["denied"] / total,
            "warning_rate": self.stats["warned"] / total,
            "fallback_rate": self.stats["fallback"] / total
        }
```

**`src/trust_plane/policies.py`**:
```python
"""Data quality policy definitions"""
import yaml
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class PolicyRule:
    """Individual policy rule"""
    metric: str          # e.g., "avg_freshness_days"
    operator: str        # e.g., "<=", ">=", "==", "!="
    threshold: float     # e.g., 7
    severity: str        # "critical", "warning", "info"
    action: str          # "deny", "warn", "allow"
    message: str         # Human-readable message

    def evaluate(self, metric_value: float) -> bool:
        """Check if rule is violated

        Returns:
            True if rule is violated, False otherwise
        """
        if self.operator == "<=":
            return metric_value > self.threshold
        elif self.operator == ">=":
            return metric_value < self.threshold
        elif self.operator == "==":
            return metric_value != self.threshold
        elif self.operator == "!=":
            return metric_value == self.threshold
        elif self.operator == "<":
            return metric_value >= self.threshold
        elif self.operator == ">":
            return metric_value <= self.threshold

        return False

@dataclass
class DataQualityPolicy:
    """Data quality policy"""
    name: str
    description: str
    scope: Dict[str, Any]
    rules: List[PolicyRule]
    fallback: Dict[str, Any]

    def applies_to(self, dataset_uri: str) -> bool:
        """Check if policy applies to dataset"""
        datasets = self.scope.get("datasets", [])

        for pattern in datasets:
            # Simple wildcard matching
            if self._matches_pattern(dataset_uri, pattern):
                return True

        return False

    def _matches_pattern(self, uri: str, pattern: str) -> bool:
        """Check if URI matches pattern (supports wildcards)"""
        if pattern == uri:
            return True

        # Handle wildcards
        if "*" in pattern:
            # Convert pattern to regex
            import re
            regex_pattern = pattern.replace("*", ".*")
            return re.match(regex_pattern, uri) is not None

        return False

    def evaluate(self, dataset_metadata: Dict) -> List[Dict]:
        """Evaluate dataset against policy rules

        Returns:
            List of violations (empty if no violations)
        """
        violations = []

        metrics = dataset_metadata.get("metrics", {})

        for rule in self.rules:
            metric_value = metrics.get(rule.metric)

            if metric_value is None:
                # Metric not available
                continue

            if rule.evaluate(metric_value):
                violations.append({
                    "rule": rule.metric,
                    "operator": rule.operator,
                    "threshold": rule.threshold,
                    "actual_value": metric_value,
                    "severity": rule.severity,
                    "action": rule.action,
                    "message": rule.message.format(threshold=rule.threshold)
                })

        return violations

class PolicyLoader:
    """Load policies from YAML"""

    def __init__(self, policy_file: str):
        self.policy_file = policy_file

    def load_policies(self) -> List[DataQualityPolicy]:
        """Load policies from file"""
        with open(self.policy_file) as f:
            config = yaml.safe_load(f)

        policies = []

        for policy_def in config.get("policies", []):
            # Parse rules
            rules = []
            for rule_def in policy_def.get("rules", []):
                rules.append(PolicyRule(
                    metric=rule_def["metric"],
                    operator=rule_def["operator"],
                    threshold=rule_def["threshold"],
                    severity=rule_def["severity"],
                    action=rule_def["action"],
                    message=rule_def["message"]
                ))

            policy = DataQualityPolicy(
                name=policy_def["name"],
                description=policy_def["description"],
                scope=policy_def["scope"],
                rules=rules,
                fallback=policy_def.get("fallback", {})
            )

            policies.append(policy)

        return policies
```

### 2. Lineage Client Extension

**Update `src/observability/lineage/client.py`**:
```python
class LineageClient:
    """OpenLineage client with metadata caching"""

    def __init__(self, ...):
        # ... existing init ...
        self._metadata_cache = {}  # Cache dataset metadata

    def cache_dataset_metadata(
        self,
        namespace: str,
        name: str,
        metadata: Dict
    ):
        """Cache dataset metadata for trust plane queries"""
        key = f"{namespace}/{name}"
        self._metadata_cache[key] = {
            "metadata": metadata,
            "timestamp": datetime.now()
        }

    def get_dataset_metadata(
        self,
        namespace: str,
        name: str
    ) -> Optional[Dict]:
        """Get cached dataset metadata"""
        key = f"{namespace}/{name}"

        cached = self._metadata_cache.get(key)
        if not cached:
            return None

        # Check if cache is stale (> 1 hour)
        age = (datetime.now() - cached["timestamp"]).total_seconds()
        if age > 3600:
            return None

        return cached["metadata"]
```

**Update `scripts/setup_vectorstore.py`**:
```python
from src.observability.lineage import get_lineage_client

def index_documents_with_lineage(...):
    # ... existing ingestion ...

    # Calculate metrics
    metrics = {
        "row_count": len(all_documents),
        "avg_freshness_days": avg_freshness,
        "max_freshness_days": max(freshness_days.values()),
        "source_file_count": len(markdown_files)
    }

    # Cache metadata for trust plane
    lineage_client = get_lineage_client()
    if lineage_client:
        lineage_client.cache_dataset_metadata(
            namespace="chromadb",
            name="internal_docs.chunks",
            metadata={"metrics": metrics}
        )

    # ... emit lineage events ...
```

### 3. Agent Integration

**Update `src/tools/docs_search.py`**:
```python
from src.trust_plane import TrustPlaneEngine, TrustAction

class DocsSearchTool(BaseTool):
    def __init__(self, vectorstore, embedding_model):
        super().__init__(
            name="docs_search",
            description="Search internal documentation"
        )
        self.vectorstore = vectorstore
        self.embedding_model = embedding_model

        # Initialize trust plane
        try:
            self.trust_plane = TrustPlaneEngine()
        except Exception as e:
            logger.warning(f"Trust Plane not available: {e}")
            self.trust_plane = None

    def execute(self, query: str, **kwargs) -> Dict:
        """Execute with trust plane authorization"""

        # AUTHORIZATION CHECK (NEW!)
        if self.trust_plane:
            decision = self.trust_plane.authorize_dataset_access(
                dataset_namespace="chromadb",
                dataset_name="internal_docs.chunks",
                operation="read"
            )

            if decision.is_denied():
                # DATA ACCESS DENIED
                return {
                    "success": False,
                    "error": f"Trust Plane denied access: {decision.reason}",
                    "trust_decision": decision.action.value,
                    "trust_reason": decision.reason,
                    "data_quality_violations": decision.violations,
                    "suggested_action": "Refresh source data and re-ingest"
                }

            elif decision.requires_fallback():
                # USE FALLBACK STRATEGY
                return self._execute_fallback(
                    query,
                    decision.fallback_strategy
                )

            elif decision.action == TrustAction.WARN:
                # PROCEED WITH WARNING
                logger.warning(
                    f"Trust Plane warning for RAG: {decision.reason}"
                )
                # Continue but add warning to result

        # Proceed with normal RAG
        results = self.vectorstore.similarity_search(
            query_text=query,
            embedding_function=self.embedding_model,
            k=kwargs.get("k", 3)
        )

        response = {
            "success": True,
            "results": results,
            "num_results": len(results)
        }

        # Add trust plane info if available
        if self.trust_plane and decision.action == TrustAction.WARN:
            response["trust_warning"] = decision.reason
            response["data_quality_metrics"] = decision.metrics

        return response

    def _execute_fallback(self, query: str, strategy: str) -> Dict:
        """Execute fallback strategy when data trust fails"""

        if strategy == "web_search":
            # Use web search instead of RAG
            logger.info("Using web search fallback due to stale RAG data")

            # Implement web search (placeholder)
            return {
                "success": True,
                "fallback": True,
                "fallback_strategy": "web_search",
                "message": "Used web search due to stale local documentation",
                "results": []  # Web search results
            }

        # Unknown fallback strategy
        return {
            "success": False,
            "error": f"Unknown fallback strategy: {strategy}"
        }
```

### 4. Demo Script

**`demo_trust_plane.py`**:
```python
#!/usr/bin/env python3
"""Agent Trust Plane Demo

Shows proactive data quality control preventing LLM errors
"""

def demo_flow():
    print("="*70)
    print("Agent Trust Plane Demo: Proactive Data Quality Control")
    print("="*70)

    # Step 1: Configure policies
    print("\n[Step 1] Configuring Data Quality Policies...")
    print("""
  Policy: rag_data_freshness
    - avg_freshness_days <= 7 (critical, deny)
    - avg_freshness_days <= 14 (warning, warn)
    - Fallback: web_search
    """)

    # Step 2: Ingest stale data (45 days old)
    print("\n[Step 2] Ingesting stale documentation...")
    inject_stale_data()  # Creates 45-day-old docs
    run_ingestion()
    print("  ✓ Ingested with avg_freshness_days = 42")

    # Step 3: Query agent (trust plane blocks RAG)
    print("\n[Step 3] Agent attempts to query RAG...")
    query = "What are the latest deployment requirements for NeMo Retriever?"

    print(f"\n  Query: {query}")
    print(f"\n  ▶️  Agent wants to call RAG tool...")
    print(f"  ▶️  Trust Plane checking data quality...")

    result = agent.run(query)

    # Step 4: Trust Plane Decision
    print("\n[Step 4] Trust Plane Decision:")

    trust_decision = result.get("trust_decision")

    if trust_decision == "deny":
        print(f"""
  🛑 ACCESS DENIED

  Reason: {result['trust_reason']}

  Data Quality Violations:
""")
        for violation in result.get("data_quality_violations", []):
            print(f"    ❌ {violation['rule']}: {violation['actual_value']} {violation['operator']} {violation['threshold']}")
            print(f"       {violation['message']}")

        print(f"""
  🔒 RAG tool was BLOCKED from executing
  💡 LLM never received stale data
  ✅ Error prevented proactively!

  Suggested Action: {result['suggested_action']}
        """)

    elif trust_decision == "fallback":
        print(f"""
  ⚠️  FALLBACK TRIGGERED

  Reason: {result['trust_reason']}
  Strategy: {result['fallback_strategy']}

  📡 Using web search instead of stale RAG data
  ✅ Agent gets fresh data from alternative source
        """)

    # Step 5: Show in observability
    print("\n[Step 5] Observability Integration:")
    print(f"""
  OpenTelemetry:
    Span: trust_plane.authorize
      - trust_plane.decision = "deny"
      - trust_plane.dataset = "chromadb://internal_docs.chunks"
      - Event: trust_plane_denial
        → reason: "Data too stale (>7 days old)"

  Langfuse:
    Tool: trust_plane_check
      - Input: chromadb://internal_docs.chunks
      - Output: {{"action": "deny", ...}}
    Score: data_trust_score = 0.0
      - Comment: "deny: Data is too stale"

  OpenLineage:
    Dataset: chromadb://internal_docs.chunks
      - Facet: dataQualityAssertions
        → assertion: "data_freshness_acceptable"
        → success: false
        → measurement: avg_freshness_days=42
    """)

    # Step 6: Fix and retry
    print("\n[Step 6] Refreshing data and retrying...")
    print("  ▶️  Updating source documentation...")
    update_fresh_docs()

    print("  ▶️  Re-ingesting with lineage...")
    run_ingestion()
    print("  ✓ New avg_freshness_days = 0")

    print("\n  ▶️  Retrying agent query...")
    result = agent.run(query)

    trust_decision = result.get("trust_decision")

    if trust_decision == "allow":
        print(f"""
  ✅ ACCESS ALLOWED

  Trust Plane: All data quality checks passed
  ✓ RAG tool executed successfully
  ✓ LLM received fresh, high-quality data
  ✓ Answer correct!

  Answer: {result['answer']}
        """)

    print("\n[Summary] Trust Plane Benefits:")
    print("""
  1. ✅ Prevented LLM from using stale data
  2. ✅ Error caught BEFORE inference (proactive)
  3. ✅ Clear guidance on how to fix (refresh data)
  4. ✅ Fallback to alternative source (resilient)
  5. ✅ Full observability across all platforms
  6. ✅ Policy-driven, configurable thresholds
    """)
```

## Key Benefits

### 1. **Proactive vs Reactive**

**Without Trust Plane** (reactive):
```
LLM uses stale data → Wrong answer → LLM Judge detects error → Analyze lineage
```

**With Trust Plane** (proactive):
```
RAG tool request → Trust Plane checks lineage → Blocks stale data → No error occurs
```

### 2. **Policy-Driven**

```yaml
# Easy to configure thresholds
rules:
  - metric: "avg_freshness_days"
    threshold: 7      # Adjust based on use case
    action: "deny"
```

### 3. **Multiple Response Options**

- **DENY**: Block completely, return error
- **WARN**: Allow but log warning
- **FALLBACK**: Use alternative source (web search)
- **ALLOW**: Proceed normally

### 4. **Full Observability**

Every decision logged to:
- **OTel**: Spans, events, attributes
- **Langfuse**: Tool executions, scores
- **OpenLineage**: Quality assertions

### 5. **Cost Savings**

- No wasted LLM calls on bad data
- No judge LLM call needed if data rejected
- Cheaper to check metadata than run inference

## File Structure

```
nemo-demo/
├── config/
│   └── data_quality_policies.yaml          [NEW]
├── src/
│   ├── trust_plane/                        [NEW]
│   │   ├── __init__.py
│   │   ├── engine.py                       # Core trust plane
│   │   ├── decision.py                     # Decision types
│   │   └── policies.py                     # Policy loader
│   ├── observability/
│   │   └── lineage/
│   │       └── client.py                   [MODIFIED] Add metadata cache
│   └── tools/
│       └── docs_search.py                  [MODIFIED] Add trust check
├── scripts/
│   └── setup_vectorstore.py                [MODIFIED] Cache metadata
└── demo_trust_plane.py                     [NEW]
```

## Demo Output

```bash
$ python demo_trust_plane.py

======================================================================
Agent Trust Plane Demo: Proactive Data Quality Control
======================================================================

[Step 1] Configuring Data Quality Policies...
  ✓ Loaded policy: rag_data_freshness
    - Rule: avg_freshness_days <= 7 (DENY)
    - Fallback: web_search

[Step 2] Ingesting stale documentation...
  ✓ Created docs (45 days old)
  ✓ Ingested: avg_freshness_days = 42

[Step 3] Agent query: "What are deployment requirements?"
  ▶️  Agent calls RAG tool...
  ▶️  Trust Plane checking data quality...

[Step 4] Trust Plane Decision:

  🛑 ACCESS DENIED

  Reason: Data is too stale (>7 days old)

  Violations:
    ❌ avg_freshness_days: 42 > 7
       Data is too stale (>7 days old)

  🔒 RAG tool BLOCKED before execution
  💡 LLM never received stale data
  ✅ Error prevented proactively!

  Suggested Action: Refresh source data and re-ingest

[Step 5] Observability shows denial in all platforms

[Step 6] Refreshing data...
  ✓ Updated docs (0 days old)
  ✓ Re-ingested: avg_freshness_days = 0
  ✓ Retrying query...

  ✅ ACCESS ALLOWED
  ✓ All quality checks passed
  ✓ Answer: Python 3.11+, CUDA 12.0+... (CORRECT!)
```

## Integration Summary

```
┌──────────────────────────────────────────────────────────────┐
│                  Complete Observability Stack                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  OpenLineage (Data Lineage)                                 │
│  └─> Tracks data flow, freshness, quality metrics           │
│      └─> Trust Plane queries for authorization              │
│                                                              │
│  OpenTelemetry (Execution Tracing)                          │
│  └─> trust_plane.authorize span                             │
│      └─> Links to lineage run IDs                           │
│                                                              │
│  Langfuse (LLM Analytics)                                    │
│  └─> Logs trust decisions as tool executions                │
│      └─> data_trust_score metric                            │
│                                                              │
│  LLM Judge (Post-hoc Validation)                            │
│  └─> Validates answers that passed trust plane              │
│      └─> Double-check for errors                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Implementation Time

- **Phase 1**: Trust Plane core (3-4 hours)
- **Phase 2**: Policy engine (2-3 hours)
- **Phase 3**: Tool integration (1-2 hours)
- **Phase 4**: Lineage metadata caching (1 hour)
- **Phase 5**: Demo script (1-2 hours)
- **Phase 6**: Documentation (1-2 hours)

**Total**: 9-14 hours

Would you like me to start implementing this?
