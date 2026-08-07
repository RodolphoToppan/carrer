"""Thin application workflow for explicit career intelligence steps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from carrer.artifacts import (
    accept_artifact_export_repair,
    accept_claim_based_artifact,
    accept_claim_based_artifact_export,
    build_artifact_export_repair_candidate,
    build_artifact_from_career_claims,
    build_claim_based_artifact_export_candidate,
    check_artifact_export_integrity,
    get_artifact_export_receipt,
    get_claim_based_professional_artifact,
    list_artifact_export_receipts,
    list_claim_based_professional_artifacts,
    reject_artifact_export_repair,
    reject_claim_based_artifact,
    reject_claim_based_artifact_export,
)
from carrer.claims import (
    accept_career_claim_candidate,
    generate_career_claim_candidates,
    get_career_claim,
    list_career_claims,
    reject_career_claim_candidate,
)
from carrer.contributions import (
    accept_contribution_analysis,
    analyze_contribution,
    create_contribution,
    find_contribution_candidates,
    get_contribution,
    get_contribution_analysis,
    list_contribution_analyses,
    list_contributions,
    promote_contribution_candidate,
    reject_contribution_analysis,
    reject_contribution_candidate,
)
from carrer.integrity import validate_graph_integrity
from carrer.storage.json_graph_storage import JsonGraphStorage


class CareerWorkflow:
    """Coordinate existing use cases without owning domain rules."""

    def __init__(self, store: JsonGraphStorage) -> None:
        self.store = store

    def discover_contribution_candidates(self) -> list[dict[str, Any]]:
        return find_contribution_candidates(self.store)

    def list_contributions(self) -> list[dict[str, Any]]:
        return list_contributions(self.store)

    def get_contribution(self, contribution_id: str) -> dict[str, Any] | None:
        return get_contribution(self.store, contribution_id)

    def create_contribution(self, **kwargs: Any) -> dict[str, Any]:
        return create_contribution(self.store, **kwargs)

    def promote_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return promote_contribution_candidate(self.store, candidate, **kwargs)

    def reject_contribution_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_contribution_candidate(self.store, candidate, **kwargs)

    def analyze_contribution(self, contribution_id: str) -> dict[str, Any]:
        return analyze_contribution(self.store, contribution_id)

    def accept_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return accept_contribution_analysis(self.store, analysis, **kwargs)

    def reject_contribution_analysis(self, analysis: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_contribution_analysis(self.store, analysis, **kwargs)

    def list_contribution_analyses(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list_contribution_analyses(self.store, **kwargs)

    def get_contribution_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        return get_contribution_analysis(self.store, analysis_id)

    def generate_career_claim_candidates(self, analysis_id: str) -> list[dict[str, Any]]:
        return generate_career_claim_candidates(self.store, analysis_id)

    def accept_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return accept_career_claim_candidate(self.store, candidate, **kwargs)

    def reject_career_claim_candidate(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_career_claim_candidate(self.store, candidate, **kwargs)

    def list_career_claims(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list_career_claims(self.store, **kwargs)

    def get_career_claim(self, claim_id: str) -> dict[str, Any] | None:
        return get_career_claim(self.store, claim_id)

    def build_claim_based_artifact(self, **kwargs: Any) -> dict[str, Any]:
        return build_artifact_from_career_claims(self.store, **kwargs)

    def accept_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return accept_claim_based_artifact(self.store, artifact, **kwargs)

    def reject_claim_based_artifact(self, artifact: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_claim_based_artifact(self.store, artifact, **kwargs)

    def list_claim_based_artifacts(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list_claim_based_professional_artifacts(self.store, **kwargs)

    def get_claim_based_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        return get_claim_based_professional_artifact(self.store, artifact_id)

    def build_export_candidate(self, artifact_id: str, **kwargs: Any) -> dict[str, Any]:
        return build_claim_based_artifact_export_candidate(self.store, artifact_id, **kwargs)

    def accept_export(
        self,
        candidate: dict[str, Any],
        *,
        output_directory: str | Path,
        decision_actor: str,
        decided_at: str,
    ) -> dict[str, Any]:
        return accept_claim_based_artifact_export(
            self.store,
            candidate,
            output_directory=output_directory,
            decision_actor=decision_actor,
            decided_at=decided_at,
        )

    def reject_export(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_claim_based_artifact_export(self.store, candidate, **kwargs)

    def list_export_receipts(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list_artifact_export_receipts(self.store, **kwargs)

    def get_export_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        return get_artifact_export_receipt(self.store, receipt_id)

    def check_export_integrity(self, receipt_id: str, **kwargs: Any) -> dict[str, Any]:
        return check_artifact_export_integrity(self.store, receipt_id, **kwargs)

    def build_repair_candidate(self, report: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return build_artifact_export_repair_candidate(self.store, report, **kwargs)

    def accept_repair(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return accept_artifact_export_repair(self.store, candidate, **kwargs)

    def reject_repair(self, candidate: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return reject_artifact_export_repair(self.store, candidate, **kwargs)

    def graph_integrity(self, **kwargs: Any) -> dict[str, Any]:
        return validate_graph_integrity(self.store, **kwargs)
