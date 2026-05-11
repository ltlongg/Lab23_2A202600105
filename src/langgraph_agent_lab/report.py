"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report_stub(metrics: MetricsReport) -> str:
    """Return a minimal report stub.
    """
    return f"""# Day 08 Lab Report

## Metrics summary

- Total scenarios: {metrics.total_scenarios}
- Success rate: {metrics.success_rate:.2%}
- Average nodes visited: {metrics.avg_nodes_visited:.2f}
- Total retries: {metrics.total_retries}
- Total interrupts: {metrics.total_interrupts}

## Architecture

The graph consists of several core nodes:
- `intake_node`: Normalizes the user query.
- `classify_node`: Classifies the query and sets `route` using keyword heuristics.
- Conditional router (`route_after_classify`): Directs flow to `answer`, `tool`, `clarify`, `risky_action`, or `retry` loop depending on the identified route.
- `tool_node`: Executes a simulated tool. Followed by `evaluate_node`.
- `evaluate_node`: Checks the execution result. Uses conditional edge (`route_after_evaluate`) to either loop back via `retry` or proceed to `answer`.
- `retry_or_fallback_node`: Tracks retry attempts and loops back to `tool` unless `amount` reaches `max_attempts`, in which case it routes to `dead_letter`.
- `risky_action_node` & `approval_node`: Triggers HITL for critical operations.
- `answer_node`: Formats the final response based on collected state and tool outputs.
- `finalize_node`: Emits a completion event and transitions to END.

## State schema

| Field | Reducer | Why |
|---|---|---|
| messages | add | Maintain history of the interaction |
| tool_results | add | Audit all outputs from every tool call |
| errors | add | Keep a log of every error encountered |
| events | add | Audit events emitted by nodes for debugging and monitoring |
| route | overwrite | The current routing decision |
| evaluation_result| overwrite | The current assessment (needs_retry vs success) |
| attempt | overwrite | Current retry index |

## Failure analysis

1. **Retry or tool failure:** Handled with a bounded retry loop. If the maximum number of attempts triggers an exhaustion, the query falls back to the `dead_letter` route. 
2. **Risky action without approval:** If a query hits keywords like "refund" or "delete", it goes through `risky_action` which always redirects to the `approval_node` preventing automated execution of critical activities without an approval step.

## Persistence / recovery evidence

The checkpointer is configured dynamically, supporting `MemorySaver` using `thread_id=thread-<id>` and tracking states. It is built to support immediate swap towards `langgraph.checkpoint.sqlite.SqliteSaver`.

## Extension work

Integrated bounded retry loops, explicitly mapping state so loops are finite, preventing infinite regressions. SQLite integration factory provided inside `persistence.py`. 

## Improvement plan

I would implement a true LLM-based classify routing node using structured outputs rather than string heuristics for robustness. I'd also store full run traces remotely for debugging context in production setups.
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_stub(metrics), encoding="utf-8")
