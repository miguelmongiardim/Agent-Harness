from __future__ import annotations

from dataclasses import dataclass

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ContextManifest,
    ContextManifestItem,
    PolicyDecision,
    ProviderInputManifest,
    ProviderInputRecord,
    RunProviderRecord,
    Sensitivity,
)
from agent_harness.utils import sha256_text, stable_id


@dataclass(frozen=True)
class ProviderInputBuildResult:
    manifest: ProviderInputManifest
    decisions: list[tuple[str | None, PolicyDecision]]


def build_provider_input_manifest(
    run_id: str,
    task_id: str,
    context: ContextManifest,
    provider: RunProviderRecord,
    policy: PolicyEngine,
    denied_sensitivities: set[Sensitivity] | None = None,
) -> ProviderInputBuildResult:
    sources = {source.source_id: source for source in context.sources}
    manifest_items = context.items or _legacy_manifest_items(context)
    records: list[ProviderInputRecord] = []
    decisions: list[tuple[str | None, PolicyDecision]] = []

    for item in manifest_items:
        source = sources.get(item.source_id)
        path = item.path if item.path is not None else source.path if source is not None else None
        raw_sensitivity = source.sensitivity if source is not None else item.sensitivity
        sensitivity = _coerce_sensitivity(raw_sensitivity)
        action, decision = policy.evaluate_provider_input(
            sensitivity,
            provider,
            path=path,
            denied_sensitivities=denied_sensitivities,
        )
        text = None
        content_hash = None
        redaction_status = "none"
        redactions_applied: list[str] = []
        effective_sensitivity = sensitivity
        included = decision.allowed and not decision.approval_required
        untrusted = action == "allow_untrusted"

        if action == "redact":
            redacted, redactions_applied = policy.redact_text(item.text or "")
            effective_sensitivity = _coerce_sensitivity(
                policy.profile.provider_input_redact_reclassify.get(sensitivity, "unknown")
            )
            if not redactions_applied:
                redactions_applied = ["provider_input:redacted"]
            redaction_status = (
                "reclassified" if effective_sensitivity != sensitivity else "redacted"
            )
            action, decision = policy.evaluate_provider_input(
                effective_sensitivity,
                provider,
                path=path,
                denied_sensitivities=denied_sensitivities,
            )
            included = decision.allowed and not decision.approval_required
            untrusted = action == "allow_untrusted"
            if included:
                text = redacted
                content_hash = sha256_text(redacted)
        elif decision.allowed:
            text = item.text
            content_hash = item.content_hash

        records.append(
            ProviderInputRecord(
                record_id=stable_id(
                    "provider-input",
                    run_id,
                    provider.provider_profile_id,
                    item.chunk_id,
                ),
                manifest_item_id=item.item_id,
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                path=path,
                sensitivity=sensitivity,
                effective_sensitivity=effective_sensitivity,
                policy_action=action,
                included=included,
                untrusted=untrusted,
                redaction_status=redaction_status,  # type: ignore[arg-type]
                redactions_applied=redactions_applied,
                trust_zone=provider.trust_zone,
                provider_profile_id=provider.provider_profile_id,
                policy_decision_id=decision.decision_id,
                policy_reason=decision.reason,
                text=text,
                content_hash=content_hash,
            )
        )
        decisions.append((path, decision))

    return ProviderInputBuildResult(
        manifest=ProviderInputManifest(
            run_id=run_id,
            task_id=task_id,
            provider_profile_id=provider.provider_profile_id,
            trust_zone=provider.trust_zone,
            records=records,
        ),
        decisions=decisions,
    )


def _coerce_sensitivity(value: str) -> Sensitivity:
    return value  # type: ignore[return-value]


def _legacy_manifest_items(context: ContextManifest) -> list[ContextManifestItem]:
    sources = {source.source_id: source for source in context.sources}
    items: list[ContextManifestItem] = []
    for chunk in context.chunks:
        source = sources.get(chunk.source_id)
        items.append(
            ContextManifestItem(
                item_id=stable_id("manifest-item", chunk.source_id, chunk.chunk_id, "legacy"),
                source_id=chunk.source_id,
                chunk_id=chunk.chunk_id,
                source_kind="retrieval" if source and source.kind == "retrieval" else "file",
                path=source.path if source is not None else None,
                content_hash=chunk.content_hash,
                text=chunk.text,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                sensitivity=chunk.sensitivity,
                retrieval_method="direct" if source and source.kind == "file" else "lexical",
                policy_allowed=True,
                policy_decision_id=source.policy_decision_id if source is not None else "",
                policy_reason="legacy manifest item",
            )
        )
    return items
