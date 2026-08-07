from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from carrer.application import CareerWorkflow
from carrer.artifacts import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    build_artifact_from_career_claims,
)
from carrer.domain.models import evidence_node
from carrer.integrity import validate_graph_integrity
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"
NEXT = "2026-01-03T03:04:05+00:00"
LATER = "2026-01-04T03:04:05+00:00"


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records},
        sort_keys=True,
    )


def _store(*, privacy_level: str = "artifact_safe") -> JsonGraphStorage:
    store = JsonGraphStorage()
    store.create_node(
        {
            "id": "source:test",
            "node_type": "Source",
            "created_at": NOW,
            "properties": {"id": "test", "name": "Test Source", "visibility": privacy_level},
        }
    )
    store.create_node(
        evidence_node(
            source_id="test",
            source_entity_type="work_item",
            source_entity_id="WI-1",
            evidence_type="WORK_ITEM_EXISTS",
            captured_at=NOW,
            occurred_at=NOW,
            privacy_level=privacy_level,
            metadata={"state": "closed", "title": "Repair audit determinism"},
        )
    )
    return store


def _promoted_workflow(privacy_level: str = "artifact_safe") -> tuple[CareerWorkflow, dict[str, Any]]:
    workflow = CareerWorkflow(_store(privacy_level=privacy_level))
    candidate = workflow.discover_contribution_candidates()[0]
    contribution = workflow.promote_contribution_candidate(
        candidate,
        created_at=NOW,
        decision_actor="human",
        status="draft",
    )["contribution"]
    return workflow, contribution


def test_workflow_runs_explicit_steps_without_implicit_acceptance_or_hidden_side_effects() -> None:
    workflow = CareerWorkflow(_store())
    output_dir = Path("tests/.tmp_application_workflow")
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True)

    try:
        before = _snapshot(workflow.store)
        contribution_candidates = workflow.discover_contribution_candidates()
        assert _snapshot(workflow.store) == before
        assert workflow.store.nodes_by_type("Contribution") == []

        contribution = workflow.promote_contribution_candidate(
            contribution_candidates[0],
            created_at=NOW,
            decision_actor="human",
        )["contribution"]
        assert workflow.list_contributions() == [contribution]

        before = _snapshot(workflow.store)
        analysis = workflow.analyze_contribution(contribution["id"])
        assert _snapshot(workflow.store) == before
        assert workflow.store.nodes_by_type("ContributionAnalysis") == []

        accepted_analysis = workflow.accept_contribution_analysis(
            analysis,
            decision_actor="human",
            decided_at=NOW,
        )["analysis"]
        assert workflow.get_contribution_analysis(accepted_analysis["id"]) == accepted_analysis

        before = _snapshot(workflow.store)
        claim_candidates = workflow.generate_career_claim_candidates(accepted_analysis["id"])
        assert _snapshot(workflow.store) == before
        assert workflow.store.nodes_by_type("CareerClaim") == []

        claim = workflow.accept_career_claim_candidate(
            claim_candidates[0],
            decision_actor="human",
            decided_at=NEXT,
        )["claim"]
        assert workflow.get_career_claim(claim["id"]) == claim

        before = _snapshot(workflow.store)
        artifact_draft = workflow.build_claim_based_artifact(
            claim_ids=[claim["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NEXT,
        )
        assert _snapshot(workflow.store) == before
        assert workflow.store.nodes_by_type("ProfessionalArtifact") == []

        artifact = workflow.accept_claim_based_artifact(
            artifact_draft,
            decision_actor="human",
            decided_at=NEXT,
        )["artifact"]
        assert workflow.get_claim_based_artifact(artifact["id"]) == artifact

        before = _snapshot(workflow.store)
        export_candidate = workflow.build_export_candidate(
            artifact["id"],
            export_scope="external",
            export_format="markdown",
            created_at=LATER,
        )
        assert _snapshot(workflow.store) == before
        assert not (output_dir / export_candidate["file_name"]).exists()
        assert workflow.store.nodes_by_type("ArtifactExportReceipt") == []

        receipt = workflow.accept_export(
            export_candidate,
            output_directory=output_dir,
            decision_actor="human",
            decided_at=LATER,
        )["receipt"]
        assert (output_dir / receipt["properties"]["file_name"]).read_text(encoding="utf-8") == export_candidate[
            "content"
        ]
        assert workflow.get_export_receipt(receipt["id"]) == receipt
        assert workflow.list_export_receipts() == [receipt]

        workflow.store.edges = [
            edge
            for edge in workflow.store.edges
            if not (edge["edge_type"] == ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT and edge["from_node_id"] == receipt["id"])
        ]
        report = workflow.check_export_integrity(receipt["id"], output_directory=output_dir, checked_at=LATER)
        repair_candidate = workflow.build_repair_candidate(report, created_at=LATER)
        assert workflow.store.nodes_by_type("ArtifactExportRepairReceipt") == []

        repair = workflow.accept_repair(
            repair_candidate,
            decision_actor="human",
            decided_at=LATER,
            verified_at=LATER,
        )
        assert repair["report"]["status"] == "consistent"
        assert workflow.store.nodes_by_type("ArtifactExportRepairReceipt")
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_read_only_operations_and_graph_integrity_do_not_mutate_store() -> None:
    workflow, contribution = _promoted_workflow()
    analysis = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claim = workflow.accept_career_claim_candidate(
        workflow.generate_career_claim_candidates(analysis["id"])[0],
        decision_actor="human",
        decided_at=NOW,
    )["claim"]

    before = _snapshot(workflow.store)
    assert workflow.discover_contribution_candidates()
    assert workflow.analyze_contribution(contribution["id"])
    assert workflow.generate_career_claim_candidates(analysis["id"])
    assert workflow.build_claim_based_artifact(
        claim_ids=[claim["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    assert workflow.graph_integrity() == validate_graph_integrity(workflow.store)
    assert _snapshot(workflow.store) == before


def test_stale_and_tampered_candidates_are_rejected_by_original_contracts() -> None:
    workflow, contribution = _promoted_workflow()
    analysis = workflow.analyze_contribution(contribution["id"])
    workflow.store.nodes[contribution["id"]]["properties"]["actions"] = ["changed action"]

    with pytest.raises(ValueError, match="current deterministic analysis"):
        workflow.accept_contribution_analysis(analysis, decision_actor="human", decided_at=NOW)

    workflow, contribution = _promoted_workflow()
    accepted = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    tampered = workflow.generate_career_claim_candidates(accepted["id"])[0]
    tampered["statement"] = "Invented impact."

    with pytest.raises(ValueError, match="current deterministic candidate"):
        workflow.accept_career_claim_candidate(tampered, decision_actor="human", decided_at=NOW)


def test_privacy_and_errors_are_delegated_without_masking() -> None:
    workflow, contribution = _promoted_workflow(privacy_level="internal")
    analysis = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claim = workflow.accept_career_claim_candidate(
        workflow.generate_career_claim_candidates(analysis["id"])[0],
        decision_actor="human",
        decided_at=NOW,
    )["claim"]

    with pytest.raises(ValueError, match="privacy is incompatible"):
        workflow.build_claim_based_artifact(
            claim_ids=[claim["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="Contribution not found"):
        workflow.analyze_contribution("contribution:missing")


def test_existing_public_apis_remain_compatible() -> None:
    workflow, contribution = _promoted_workflow()
    analysis = workflow.accept_contribution_analysis(
        workflow.analyze_contribution(contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claim = workflow.accept_career_claim_candidate(
        workflow.generate_career_claim_candidates(analysis["id"])[0],
        decision_actor="human",
        decided_at=NOW,
    )["claim"]

    assert workflow.build_claim_based_artifact(
        claim_ids=[claim["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    ) == build_artifact_from_career_claims(
        workflow.store,
        claim_ids=[claim["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
