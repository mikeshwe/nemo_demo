"""File exporter for OpenTelemetry traces and metrics

This module provides a file-based exporter that saves traces to JSON
and generates visualizations from the collected telemetry data.
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class JSONFileSpanExporter(SpanExporter):
    """Exports spans to a JSON file"""

    def __init__(self, file_path: str):
        """Initialize the file exporter

        Args:
            file_path: Path to output JSON file
        """
        self.file_path = file_path
        self.spans: List[Dict[str, Any]] = []

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        """Export spans to internal buffer

        Args:
            spans: List of spans to export

        Returns:
            SpanExportResult.SUCCESS
        """
        for span in spans:
            span_dict = {
                "name": span.name,
                "trace_id": format(span.context.trace_id, '032x'),
                "span_id": format(span.context.span_id, '016x'),
                "parent_id": format(span.parent.span_id, '016x') if span.parent else None,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "duration_ms": (span.end_time - span.start_time) / 1_000_000,  # Convert ns to ms
                "attributes": dict(span.attributes) if span.attributes else {},
                "events": [
                    {
                        "name": event.name,
                        "timestamp": event.timestamp,
                        "attributes": dict(event.attributes) if event.attributes else {}
                    }
                    for event in span.events
                ],
                "status": {
                    "status_code": span.status.status_code.name,
                    "description": span.status.description
                }
            }
            self.spans.append(span_dict)

        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush spans to file

        Args:
            timeout_millis: Timeout in milliseconds

        Returns:
            True if successful
        """
        if not self.spans:
            return True

        try:
            with open(self.file_path, 'w') as f:
                json.dump({
                    "exported_at": datetime.now().isoformat(),
                    "span_count": len(self.spans),
                    "spans": self.spans
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to write spans to {self.file_path}: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown the exporter"""
        self.force_flush()


class TelemetryAnalyzer:
    """Analyzes telemetry data and generates visualizations"""

    def __init__(self, spans: List[Dict[str, Any]]):
        """Initialize analyzer with spans

        Args:
            spans: List of span dictionaries
        """
        self.spans = spans
        self.root_spans = [s for s in spans if s.get('parent_id') is None]
        self.agent_runs = [s for s in spans if s['name'] == 'agent.run']
        self.iterations = [s for s in spans if s['name'] == 'agent.iteration']
        self.tool_calls = [s for s in spans if s['name'].startswith('tool.')]
        self.llm_calls = [s for s in spans if s['name'] == 'openai.chat']

    def generate_summary(self) -> str:
        """Generate text summary of telemetry"""
        lines = []
        lines.append("=" * 80)
        lines.append("TELEMETRY SUMMARY")
        lines.append("=" * 80)
        lines.append("")

        # Overall stats
        lines.append("📊 Overall Statistics:")
        lines.append(f"  Total Spans: {len(self.spans)}")
        lines.append(f"  Agent Runs: {len(self.agent_runs)}")
        lines.append(f"  Iterations: {len(self.iterations)}")
        lines.append(f"  Tool Calls: {len(self.tool_calls)}")
        lines.append(f"  LLM API Calls: {len(self.llm_calls)}")
        lines.append("")

        # Agent run details
        if self.agent_runs:
            lines.append("🤖 Agent Execution:")
            for run in self.agent_runs:
                attrs = run['attributes']
                lines.append(f"  Query: {attrs.get('agent.query', 'N/A')}")
                lines.append(f"  Iterations: {attrs.get('agent.final_iterations', 'N/A')}")
                lines.append(f"  Tool Calls: {attrs.get('agent.tool_calls', 'N/A')}")
                lines.append(f"  Success: {attrs.get('agent.success', 'N/A')}")
                lines.append(f"  Duration: {run['duration_ms']:.2f} ms")
            lines.append("")

        # LLM stats
        if self.llm_calls:
            lines.append("🧠 LLM API Calls:")
            total_tokens = sum(s['attributes'].get('llm.usage.total_tokens', 0) for s in self.llm_calls)
            total_input = sum(s['attributes'].get('gen_ai.usage.input_tokens', 0) for s in self.llm_calls)
            total_output = sum(s['attributes'].get('gen_ai.usage.output_tokens', 0) for s in self.llm_calls)
            avg_duration = sum(s['duration_ms'] for s in self.llm_calls) / len(self.llm_calls)

            lines.append(f"  Total Calls: {len(self.llm_calls)}")
            lines.append(f"  Total Tokens: {total_tokens}")
            lines.append(f"  Input Tokens: {total_input}")
            lines.append(f"  Output Tokens: {total_output}")
            lines.append(f"  Avg Duration: {avg_duration:.2f} ms")
            lines.append("")

        return "\n".join(lines)

    def generate_timeline(self) -> str:
        """Generate ASCII timeline of execution"""
        if not self.spans:
            return ""

        lines = []
        lines.append("=" * 80)
        lines.append("EXECUTION TIMELINE")
        lines.append("=" * 80)
        lines.append("")

        # Get min and max times
        min_time = min(s['start_time'] for s in self.spans)
        max_time = max(s['end_time'] for s in self.spans)
        duration_ns = max_time - min_time

        # Group spans by depth
        span_tree = self._build_span_tree()

        def format_span(span: Dict, depth: int = 0):
            indent = "  " * depth
            duration_ms = span['duration_ms']
            name = span['name']

            # Create a simple bar
            bar_width = 40
            if duration_ns > 0:
                start_offset = (span['start_time'] - min_time) / duration_ns
                span_width = (span['end_time'] - span['start_time']) / duration_ns
                start_pos = int(start_offset * bar_width)
                bar_len = max(1, int(span_width * bar_width))
            else:
                start_pos = 0
                bar_len = 1

            bar = " " * start_pos + "█" * bar_len
            bar = bar[:bar_width].ljust(bar_width)

            lines.append(f"{indent}{name:30s} [{bar}] {duration_ms:8.2f} ms")

        def traverse(span_id: Optional[str], depth: int = 0):
            children = span_tree.get(span_id, [])
            for child in children:
                format_span(child, depth)
                traverse(child['span_id'], depth + 1)

        # Start from root spans
        traverse(None)

        lines.append("")
        return "\n".join(lines)

    def generate_token_usage_chart(self) -> str:
        """Generate ASCII bar chart of token usage"""
        if not self.llm_calls:
            return ""

        lines = []
        lines.append("=" * 80)
        lines.append("TOKEN USAGE PER LLM CALL")
        lines.append("=" * 80)
        lines.append("")

        max_tokens = max(s['attributes'].get('llm.usage.total_tokens', 0) for s in self.llm_calls)

        for i, call in enumerate(self.llm_calls, 1):
            total = call['attributes'].get('llm.usage.total_tokens', 0)
            input_tokens = call['attributes'].get('gen_ai.usage.input_tokens', 0)
            output_tokens = call['attributes'].get('gen_ai.usage.output_tokens', 0)

            # Create bar
            bar_width = 50
            if max_tokens > 0:
                filled = int((total / max_tokens) * bar_width)
            else:
                filled = 0

            bar = "█" * filled + "░" * (bar_width - filled)

            lines.append(f"Call {i:2d}: [{bar}] {total:5d} tokens (in: {input_tokens}, out: {output_tokens})")

        lines.append("")
        return "\n".join(lines)

    def generate_tool_timing_chart(self) -> str:
        """Generate chart of tool execution times"""
        if not self.tool_calls:
            return ""

        lines = []
        lines.append("=" * 80)
        lines.append("TOOL EXECUTION TIMING")
        lines.append("=" * 80)
        lines.append("")

        # Group by tool name
        tool_stats = {}
        for call in self.tool_calls:
            name = call['attributes'].get('tool.name', call['name'])
            if name not in tool_stats:
                tool_stats[name] = []
            tool_stats[name].append(call['duration_ms'])

        # Calculate stats
        for tool_name, durations in tool_stats.items():
            count = len(durations)
            avg = sum(durations) / count
            min_dur = min(durations)
            max_dur = max(durations)

            # Create bar
            bar_width = 40
            max_time = max(max(times) for times in tool_stats.values())
            if max_time > 0:
                filled = int((avg / max_time) * bar_width)
            else:
                filled = 0

            bar = "█" * filled + "░" * (bar_width - filled)

            lines.append(f"{tool_name:30s}")
            lines.append(f"  Count: {count:3d}   Avg: {avg:7.2f} ms   Min: {min_dur:7.2f} ms   Max: {max_dur:7.2f} ms")
            lines.append(f"  [{bar}]")
            lines.append("")

        return "\n".join(lines)

    def generate_full_report(self) -> str:
        """Generate complete telemetry report with all visualizations"""
        sections = [
            self.generate_summary(),
            self.generate_timeline(),
            self.generate_token_usage_chart(),
            self.generate_tool_timing_chart()
        ]

        return "\n".join(filter(None, sections))

    def _build_span_tree(self) -> Dict[Optional[str], List[Dict]]:
        """Build tree of spans by parent-child relationships"""
        tree = {}
        for span in self.spans:
            parent_id = span.get('parent_id')
            if parent_id not in tree:
                tree[parent_id] = []
            tree[parent_id].append(span)

        # Sort children by start time
        for children in tree.values():
            children.sort(key=lambda s: s['start_time'])

        return tree


def save_telemetry_report(json_path: str, output_path: str) -> None:
    """Load telemetry JSON and generate report

    Args:
        json_path: Path to JSON telemetry file
        output_path: Path to output report file
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        spans = data.get('spans', [])
        analyzer = TelemetryAnalyzer(spans)
        report = analyzer.generate_full_report()

        with open(output_path, 'w') as f:
            f.write(report)

        print(f"\n✅ Telemetry report saved to: {output_path}")
        print(f"   JSON data saved to: {json_path}")

    except Exception as e:
        print(f"Failed to generate telemetry report: {e}")
