# agent_harness.exporters

## Purpose

`agent_harness.exporters` owns conversion of stored run evidence into external
report formats. It reads run summaries and related artifacts, then writes JSON,
Markdown, or SARIF views for inspection and downstream tooling.

Exporters are format adapters over existing evidence. They should not rerun
tasks, re-evaluate policy, or mutate run state.

## Key Files

| File | Role |
| --- | --- |
| `json_report.py` | Writes JSON exports of run summaries and selected artifact references. |
| `markdown.py` | Renders human-readable Markdown reports for run evidence. |
| `sarif.py` | Emits SARIF output suitable for security/code-scanning style consumers. |
| `__init__.py` | Exports `export_json`, `export_markdown`, and `export_sarif`. |

## Boundaries

Keep export behavior deterministic and grounded in stored artifacts. If an
export needs new data, add that data to the owning run artifact or schema first
instead of deriving it from private runtime state.
