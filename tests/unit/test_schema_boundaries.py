from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PHASE2_BOUNDARY_CONTRACTS = {
    "benchmarks": {
        "BenchmarkAdapterEvidence",
        "BenchmarkAdapterId",
        "BenchmarkCaseRecord",
        "BenchmarkKind",
        "BenchmarkPackRecord",
        "BenchmarkResult",
    },
    "evals": {"EvalInvariant", "EvalResult", "EvalSpec"},
    "mcp": {
        "McpAccessLogRecord",
        "McpPromptList",
        "McpPromptResponse",
        "McpResourceEnvelope",
        "McpResourceList",
    },
    "operator": {
        "OperatorApprovalDecisionRequest",
        "OperatorApprovalDecisionResponse",
        "OperatorApprovalListResponse",
        "OperatorArtifactStatus",
        "OperatorContextResponse",
        "OperatorHealthResponse",
        "OperatorPolicyResponse",
        "OperatorRunDetailResponse",
        "OperatorRunListResponse",
    },
    "runtimes": {"RuntimeAdapterRecord"},
    "security": {
        "SecurityFinding",
        "SecurityFindingsReport",
        "SecurityGateDecision",
        "SecurityPolicyAction",
        "SecuritySeverity",
    },
    "skills": {
        "SkillDetail",
        "SkillManifest",
        "SkillManifestRecord",
        "SkillRegistryRecord",
        "SkillRequestedBy",
        "SkillResolutionRecord",
        "SkillResolutionReport",
        "SkillSpec",
        "SkillValidationReport",
    },
}


@pytest.mark.xfail(
    strict=True,
    reason="V10 Phase 0 guard: Phase 4 removes agent_harness.schemas",
)
def test_root_schema_aggregator_is_removed() -> None:
    root_schema = PROJECT_ROOT / "src" / "agent_harness" / "schemas.py"
    assert not root_schema.exists(), "agent_harness.schemas must not be reintroduced"

    offenders = []
    for search_root in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
        for path in search_root.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            if "agent_harness.schemas" in text:
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []


def test_template_schema_module_owns_template_contracts() -> None:
    from agent_harness.templates.schema import (
        TemplateApplyRecord,
        TemplateDetail,
        TemplateFile,
        TemplateProposedWrite,
        TemplateRegistryRecord,
        TemplateSpec,
    )

    template_contracts = [
        TemplateApplyRecord,
        TemplateDetail,
        TemplateFile,
        TemplateProposedWrite,
        TemplateRegistryRecord,
        TemplateSpec,
    ]
    assert {contract.__module__ for contract in template_contracts} == {
        "agent_harness.templates.schema"
    }


def test_template_package_imports_template_contracts_from_owner_module() -> None:
    offenders: list[str] = []
    template_names = {
        "TemplateApplyRecord",
        "TemplateDetail",
        "TemplateFile",
        "TemplateProposedWrite",
        "TemplateRegistryRecord",
        "TemplateSpec",
    }
    for path in (PROJECT_ROOT / "src" / "agent_harness" / "templates").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "agent_harness.schemas":
                continue
            imported = {alias.name for alias in node.names}
            template_imports = sorted(imported & template_names)
            if template_imports:
                relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                offenders.append(f"{relative_path}: {', '.join(template_imports)}")

    assert offenders == []


def test_root_schema_template_names_reexport_owner_contracts_during_transition() -> None:
    from agent_harness.schemas import TemplateSpec as RootTemplateSpec
    from agent_harness.templates.schema import TemplateSpec

    assert RootTemplateSpec is TemplateSpec


def test_skills_schema_module_owns_skill_contracts() -> None:
    from agent_harness.skills.schema import (
        SkillDetail,
        SkillManifest,
        SkillManifestRecord,
        SkillRegistryRecord,
        SkillRequestedBy,
        SkillResolutionRecord,
        SkillResolutionReport,
        SkillSpec,
        SkillValidationReport,
    )

    skill_contracts = [
        SkillDetail,
        SkillManifest,
        SkillManifestRecord,
        SkillRegistryRecord,
        SkillRequestedBy,
        SkillResolutionRecord,
        SkillResolutionReport,
        SkillSpec,
        SkillValidationReport,
    ]
    assert {contract.__module__ for contract in skill_contracts} == {
        "agent_harness.skills.schema"
    }


def test_operator_schema_module_owns_operator_contracts() -> None:
    from agent_harness.operator.schema import (
        OperatorApprovalDecisionRequest,
        OperatorApprovalDecisionResponse,
        OperatorApprovalListResponse,
        OperatorArtifactStatus,
        OperatorContextResponse,
        OperatorHealthResponse,
        OperatorPolicyResponse,
        OperatorRunDetailResponse,
        OperatorRunListResponse,
    )

    operator_contracts = [
        OperatorApprovalDecisionRequest,
        OperatorApprovalDecisionResponse,
        OperatorApprovalListResponse,
        OperatorArtifactStatus,
        OperatorContextResponse,
        OperatorHealthResponse,
        OperatorPolicyResponse,
        OperatorRunDetailResponse,
        OperatorRunListResponse,
    ]
    assert {contract.__module__ for contract in operator_contracts} == {
        "agent_harness.operator.schema"
    }


def test_security_schema_module_owns_security_contracts() -> None:
    from agent_harness.security.schema import (
        SecurityFinding,
        SecurityFindingsReport,
        SecurityGateDecision,
    )

    security_contracts = [
        SecurityFinding,
        SecurityFindingsReport,
        SecurityGateDecision,
    ]
    assert {contract.__module__ for contract in security_contracts} == {
        "agent_harness.security.schema"
    }


def test_runtimes_schema_module_owns_runtime_contracts() -> None:
    from agent_harness.runtimes.schema import RuntimeAdapterRecord

    assert RuntimeAdapterRecord.__module__ == "agent_harness.runtimes.schema"


def test_evals_schema_module_owns_eval_contracts() -> None:
    from agent_harness.evals.schema import EvalInvariant, EvalResult, EvalSpec

    eval_contracts = [EvalInvariant, EvalResult, EvalSpec]
    assert {contract.__module__ for contract in eval_contracts} == {
        "agent_harness.evals.schema"
    }


def test_benchmarks_schema_module_owns_benchmark_contracts() -> None:
    from agent_harness.benchmarks.schema import (
        BenchmarkAdapterEvidence,
        BenchmarkCaseRecord,
        BenchmarkPackRecord,
        BenchmarkResult,
    )

    benchmark_contracts = [
        BenchmarkAdapterEvidence,
        BenchmarkCaseRecord,
        BenchmarkPackRecord,
        BenchmarkResult,
    ]
    assert {contract.__module__ for contract in benchmark_contracts} == {
        "agent_harness.benchmarks.schema"
    }


def test_mcp_schema_module_owns_mcp_contracts() -> None:
    from agent_harness.mcp.schema import (
        McpAccessLogRecord,
        McpPromptList,
        McpPromptResponse,
        McpResourceEnvelope,
        McpResourceList,
    )

    mcp_contracts = [
        McpAccessLogRecord,
        McpPromptList,
        McpPromptResponse,
        McpResourceEnvelope,
        McpResourceList,
    ]
    assert {contract.__module__ for contract in mcp_contracts} == {
        "agent_harness.mcp.schema"
    }


def test_config_package_preserves_loader_exports_and_owns_config_contracts() -> None:
    from agent_harness.config import load_config
    from agent_harness.config.schema import HarnessConfig

    assert callable(load_config)
    assert HarnessConfig.__module__ == "agent_harness.config.schema"


def test_model_schema_module_owns_provider_contracts() -> None:
    from agent_harness.model.schema import (
        ProviderActionEnvelope,
        ProviderCallAudit,
        ProviderCallAuditManifest,
        ProviderInputManifest,
        ProviderInputRecord,
        ProviderProfileConfig,
        ProviderUseApprovalBinding,
        RunProviderRecord,
    )

    model_contracts = [
        ProviderActionEnvelope,
        ProviderCallAudit,
        ProviderCallAuditManifest,
        ProviderInputManifest,
        ProviderInputRecord,
        ProviderProfileConfig,
        ProviderUseApprovalBinding,
        RunProviderRecord,
    ]
    assert {contract.__module__ for contract in model_contracts} == {
        "agent_harness.model.schema"
    }


def test_policy_schema_module_owns_policy_contracts() -> None:
    from agent_harness.policy.schema import (
        ApprovalPolicyContract,
        MigrationPolicyContract,
        PolicyDecision,
        PolicyProfile,
        ProviderInputPolicyContract,
        ProviderTrustPolicyContract,
        ScannerPolicyContract,
        SensitivityRule,
        TemplateCapabilityPolicyContract,
    )

    policy_contracts = [
        ApprovalPolicyContract,
        MigrationPolicyContract,
        PolicyDecision,
        PolicyProfile,
        ProviderInputPolicyContract,
        ProviderTrustPolicyContract,
        ScannerPolicyContract,
        SensitivityRule,
        TemplateCapabilityPolicyContract,
    ]
    assert {contract.__module__ for contract in policy_contracts} == {
        "agent_harness.policy.schema"
    }


def test_tools_schema_module_owns_tool_contracts() -> None:
    from agent_harness.tools.schema import GitCommitPlan, ToolCall, ToolObservation, ToolSpec

    tool_contracts = [GitCommitPlan, ToolCall, ToolObservation, ToolSpec]
    assert {contract.__module__ for contract in tool_contracts} == {
        "agent_harness.tools.schema"
    }


def test_storage_schema_module_owns_storage_contracts() -> None:
    from agent_harness.storage.schema import (
        AppliedTemplateRecord,
        ApprovalRecord,
        Checkpoint,
        RunEvent,
        RunSummary,
        TemplateSkillRecommendationRecord,
        WorkspaceMetadata,
    )

    storage_contracts = [
        AppliedTemplateRecord,
        ApprovalRecord,
        Checkpoint,
        RunEvent,
        RunSummary,
        TemplateSkillRecommendationRecord,
        WorkspaceMetadata,
    ]
    assert {contract.__module__ for contract in storage_contracts} == {
        "agent_harness.storage.schema"
    }


def test_tasks_schema_module_owns_task_contracts() -> None:
    from agent_harness.tasks.schema import TaskSpec

    assert TaskSpec.__module__ == "agent_harness.tasks.schema"


def test_context_schema_module_owns_context_contracts() -> None:
    from agent_harness.context.schema import (
        ContextChunk,
        ContextManifest,
        ContextManifestItem,
        ContextSource,
        DenseRetrievalMetadata,
        RetrievalBackendManifest,
        RetrievalIndexChunk,
        RetrievalIndexManifest,
        RetrievalIndexSource,
        RetrievalProvenance,
        RetrievalScorecardFixture,
        RetrievalScorecardQuery,
    )

    context_contracts = [
        ContextChunk,
        ContextManifest,
        ContextManifestItem,
        ContextSource,
        DenseRetrievalMetadata,
        RetrievalBackendManifest,
        RetrievalIndexChunk,
        RetrievalIndexManifest,
        RetrievalIndexSource,
        RetrievalProvenance,
        RetrievalScorecardFixture,
        RetrievalScorecardQuery,
    ]
    assert {contract.__module__ for contract in context_contracts} == {
        "agent_harness.context.schema"
    }


def test_phase3_production_modules_do_not_import_from_root_schema() -> None:
    offenders: list[str] = []
    source_root = PROJECT_ROOT / "src" / "agent_harness"
    root_schema = source_root / "schemas.py"
    for path in source_root.rglob("*.py"):
        if path == root_schema:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "agent_harness.schemas":
                imported = ", ".join(alias.name for alias in node.names)
                relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                offenders.append(f"{relative_path}: from import {imported}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "agent_harness.schemas":
                        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                        offenders.append(f"{relative_path}: import {alias.name}")

    assert offenders == []


def test_phase2_boundary_packages_do_not_import_moved_contracts_from_root_schema() -> None:
    offenders: list[str] = []
    source_root = PROJECT_ROOT / "src" / "agent_harness"
    for package_name, contract_names in PHASE2_BOUNDARY_CONTRACTS.items():
        for path in (source_root / package_name).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if node.module != "agent_harness.schemas":
                    continue
                imported = {alias.name for alias in node.names}
                moved_imports = sorted(imported & contract_names)
                if moved_imports:
                    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                    offenders.append(f"{relative_path}: {', '.join(moved_imports)}")

    assert offenders == []
