from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from agent_harness.config import load_mapping
from agent_harness.policy import PolicyEngine
from agent_harness.retrieval_indexes import query_index
from agent_harness.schemas import (
    HarnessConfig,
    RetrievalScorecardFixture,
    RetrievalScorecardQuery,
)
from agent_harness.utils import now_utc, write_json

RetrievalScorecardMode = Literal["lexical", "dense", "hybrid"]


def run_retrieval_scorecard(
    project_root: Path,
    config: HarnessConfig,
    policy: PolicyEngine,
    fixture_path: Path,
    index_id: str,
    *,
    k: int,
    output: Path | None = None,
) -> dict[str, Any]:
    if k < 1:
        raise ValueError("retrieval scorecard --k must be at least 1")
    project_root = project_root.resolve()
    fixture = load_retrieval_scorecard_fixture(fixture_path)
    compared_modes = list(dict.fromkeys(fixture.compared_modes))

    query_reports: list[dict[str, Any]] = []
    per_mode_metrics: dict[str, list[dict[str, Any]]] = {mode: [] for mode in compared_modes}
    for query in fixture.queries:
        mode_reports: dict[str, Any] = {}
        for mode in compared_modes:
            mode_report = _score_query_mode(
                project_root,
                config,
                policy,
                index_id,
                query,
                mode=mode,
                k=k,
            )
            mode_reports[mode] = mode_report
            per_mode_metrics[mode].append(mode_report)
        query_reports.append(
            {
                "query_id": query.query_id,
                "query": query.query,
                "allowed_sensitivities": query.allowed_sensitivities,
                "modes": mode_reports,
            }
        )

    backend_comparison = [
        _backend_metric_row(
            mode,
            mode_reports,
            min_precision_at_k=fixture.min_precision_at_k,
            min_recall_at_k=fixture.min_recall_at_k,
        )
        for mode, mode_reports in per_mode_metrics.items()
    ]
    status = "passed" if all(row["status"] == "passed" for row in backend_comparison) else "failed"
    scorecard_path = output or (
        project_root / config.artifact_root / "retrieval-scorecards" / f"{index_id}.json"
    )
    report: dict[str, Any] = {
        "schema_version": "retrieval_scorecard.v1",
        "status": status,
        "index_id": index_id,
        "k": k,
        "compared_modes": compared_modes,
        "fixture_path": _project_relative(project_root, fixture_path.resolve()),
        "scorecard_path": _project_relative(project_root, scorecard_path.resolve()),
        "generated_at": now_utc().isoformat(),
        "thresholds": {
            "min_precision_at_k": fixture.min_precision_at_k,
            "min_recall_at_k": fixture.min_recall_at_k,
        },
        "metrics": {
            row["mode"]: {
                "precision_at_k": row["precision_at_k"],
                "recall_at_k": row["recall_at_k"],
                "query_count": row["query_count"],
                "status": row["status"],
            }
            for row in backend_comparison
        },
        "queries": query_reports,
        "backend_comparison": backend_comparison,
        "remote_embeddings": False,
    }
    write_json(scorecard_path, report)
    return report


def load_retrieval_scorecard_fixture(path: Path) -> RetrievalScorecardFixture:
    raw = load_mapping(path)
    queries = raw.get("queries")
    if isinstance(queries, dict):
        raw["queries"] = [
            {"query_id": query_id, **value}
            for query_id, value in queries.items()
            if isinstance(value, dict)
        ]
    return RetrievalScorecardFixture.model_validate(raw)


def _score_query_mode(
    project_root: Path,
    config: HarnessConfig,
    policy: PolicyEngine,
    index_id: str,
    query: RetrievalScorecardQuery,
    *,
    mode: RetrievalScorecardMode,
    k: int,
) -> dict[str, Any]:
    query_result = query_index(
        project_root,
        config,
        index_id,
        query.query,
        mode=mode,
        limit=k,
    )
    expected = list(dict.fromkeys(query.expected_chunks))
    allowed_sensitivities = set(query.allowed_sensitivities)
    hits: set[str] = set()
    unexpected_chunks: list[dict[str, Any]] = []
    rejected_chunks: list[dict[str, Any]] = []
    scored_results = [_scorecard_result(policy, result) for result in _result_items(query_result)]
    accepted_results: list[dict[str, Any]] = []

    for result in scored_results:
        if result["sensitivity"] not in allowed_sensitivities:
            rejected_chunks.append({**result, "reason": "sensitivity_not_allowed"})
            continue
        accepted_results.append(result)
        matched = _matching_expected_chunk(result, expected)
        if matched is None:
            unexpected_chunks.append({**result, "reason": "not_expected"})
        else:
            hits.add(matched)

    hit_chunks = [expected_chunk for expected_chunk in expected if expected_chunk in hits]
    missed_chunks = [expected_chunk for expected_chunk in expected if expected_chunk not in hits]
    precision_at_k = len(hit_chunks) / k
    recall_at_k = len(hit_chunks) / len(expected) if expected else 1.0
    return {
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "expected_chunks": expected,
        "hit_chunks": hit_chunks,
        "missed_chunks": missed_chunks,
        "unexpected_chunks": unexpected_chunks,
        "rejected_chunks": rejected_chunks,
        "results": accepted_results,
        "retrieval": query_result["retrieval"],
    }


def _result_items(query_result: dict[str, Any]) -> list[dict[str, Any]]:
    results = query_result.get("results")
    if not isinstance(results, list):
        raise ValueError("retrieval query result must contain a results list")
    return [result for result in results if isinstance(result, dict)]


def _scorecard_result(
    policy: PolicyEngine,
    result: dict[str, Any],
) -> dict[str, Any]:
    path = str(result["path"])
    scores = result.get("scores")
    return {
        "chunk_id": str(result["chunk_id"]),
        "path": path,
        "start_line": int(result["start_line"]),
        "end_line": int(result["end_line"]),
        "sensitivity": policy.classify_path(path),
        "retrieval_method": str(result["retrieval_method"]),
        "scores": dict(scores) if isinstance(scores, dict) else {},
    }


def _matching_expected_chunk(
    result: dict[str, Any],
    expected_chunks: list[str],
) -> str | None:
    refs = {
        str(result["chunk_id"]),
        str(result["path"]),
        f"{result['path']}#L{result['start_line']}-L{result['end_line']}",
    }
    for expected in expected_chunks:
        if expected in refs:
            return expected
    return None


def _backend_metric_row(
    mode: str,
    query_reports: list[dict[str, Any]],
    *,
    min_precision_at_k: float,
    min_recall_at_k: float,
) -> dict[str, Any]:
    query_count = len(query_reports)
    precision_at_k = sum(float(report["precision_at_k"]) for report in query_reports) / query_count
    recall_at_k = sum(float(report["recall_at_k"]) for report in query_reports) / query_count
    disallowed_results = sum(len(report["rejected_chunks"]) for report in query_reports)
    status = (
        "passed"
        if precision_at_k >= min_precision_at_k and recall_at_k >= min_recall_at_k
        else "failed"
    )
    return {
        "mode": mode,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "query_count": query_count,
        "unexpected_disallowed_results": disallowed_results,
        "status": status,
    }


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)
