"""Durable modern CLI journey with explicit human decisions and local export repair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_interfaces_cli import NEXT, NOW, _basic_store, _run

from carrer.artifacts import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
    PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM,
)
from carrer.artifacts.claim_export_repair import (
    artifact_export_repair_candidate_id,
    validate_artifact_export_repair_acceptance_audit,
)
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
)
from carrer.contributions.analysis_review import CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION
from carrer.contributions.service import CONTRIBUTION_SUPPORTED_BY_EVIDENCE
from carrer.storage.json_graph_storage import JsonGraphStorage

REVIEW = ["--actor", "human", "--decided-at", NEXT]


def _json(path: Path, *command: str) -> Any:
    code, stdout, stderr = _run(["--store", str(path), "--json", *command])
    assert (code, stderr) == (0, ""), (command, stdout, stderr)
    return json.loads(stdout)


def _preview(path: Path, *command: str) -> Any:
    before = path.read_bytes()
    result = _json(path, *command)
    assert path.read_bytes() == before
    return result


@pytest.fixture
def accepted_export(tmp_path: Path) -> Path:
    """Each scenario independently traverses every review boundary through cli.run."""
    path = tmp_path / "graph.json"
    _basic_store().save(path)
    initial = JsonGraphStorage.load(path)
    assert len(initial.nodes_by_type("EvidenceNode")) == 1
    assert not initial.edges
    assert not initial.audit_records

    candidates = _preview(path, "contributions", "discover")
    assert len(candidates) == 1
    selected = candidates[0]
    promoted = _json(path, "contributions", "promote", "--candidate-id", selected["id"], *REVIEW)
    assert promoted["decision"] == "promoted"
    assert promoted["candidate_id"] == selected["id"]
    contribution = promoted["contribution"]
    assert JsonGraphStorage.load(path).nodes_by_type("Contribution") == [contribution]

    analysis_args = ["--contribution-id", contribution["id"]]
    draft_analysis = _preview(path, "analyses", "generate", *analysis_args)
    analysis_result = _json(path, "analyses", "accept", *analysis_args, *REVIEW)
    assert analysis_result["decision"] == "accepted"
    analysis = analysis_result["analysis"]
    assert analysis["id"] == draft_analysis["id"]
    assert JsonGraphStorage.load(path).nodes_by_type("ContributionAnalysis") == [analysis]

    claims = _preview(path, "claims", "generate", "--analysis-id", analysis["id"])
    assert claims
    selected_claim = claims[0]
    claim_result = _json(
        path,
        "claims",
        "accept",
        "--analysis-id",
        analysis["id"],
        "--candidate-id",
        selected_claim["id"],
        *REVIEW,
    )
    assert claim_result["decision"] == "accepted"
    claim = claim_result["claim"]
    assert JsonGraphStorage.load(path).nodes_by_type("CareerClaim") == [claim]

    artifact_args = [
        "--claim-id",
        claim["id"],
        "--artifact-type",
        "resume_claims",
        "--audience",
        "public",
        "--created-at",
        NOW,
    ]
    draft_artifact = _preview(path, "artifacts", "build", *artifact_args)
    artifact_result = _json(path, "artifacts", "accept", *artifact_args, *REVIEW)
    assert artifact_result["decision"] == "accepted"
    artifact = artifact_result["artifact"]
    assert artifact["properties"]["source_artifact_id"] == draft_artifact["id"]
    assert JsonGraphStorage.load(path).nodes_by_type("ProfessionalArtifact") == [artifact]

    export_args = [
        "--artifact-id",
        artifact["id"],
        "--export-scope",
        "external",
        "--export-format",
        "markdown",
        "--created-at",
        NEXT,
    ]
    candidate = _preview(path, "exports", "build", *export_args)
    output = tmp_path / "exports"
    assert not output.exists()
    result = _json(path, "exports", "accept", *export_args, "--output-directory", str(output), *REVIEW)
    reloaded = JsonGraphStorage.load(path)
    [receipt] = reloaded.nodes_by_type("ArtifactExportReceipt")
    assert result == {"receipt": receipt, "decision": "accepted", "created": True, "written": True}
    assert receipt["properties"]["export_candidate_id"] == candidate["id"]
    final = output / receipt["properties"]["file_name"]
    assert final.suffix == ".md"
    assert final.is_file()
    assert final.read_bytes() == candidate["content"].encode("utf-8")
    assert not reloaded.nodes_by_type("ArtifactExportRepairReceipt")
    return path


def _export_paths(path: Path) -> tuple[Path, Path, list[str]]:
    [receipt] = JsonGraphStorage.load(path).nodes_by_type("ArtifactExportReceipt")
    output = path.parent / "exports"
    final = output / receipt["properties"]["file_name"]
    temp = output / f".{final.name}.tmp"
    args = ["--receipt-id", receipt["id"], "--output-directory", str(output), "--checked-at", NEXT]
    return final, temp, args


def _assert_no_repair(path: Path) -> None:
    store = JsonGraphStorage.load(path)
    assert not store.nodes_by_type("ArtifactExportRepairReceipt")
    assert not [r for r in store.audit_records if r["audit_type"].startswith("artifact_export_repair_")]


def test_complete_journey_repairs_edges_and_temp_with_current_state_only_cli(accepted_export: Path) -> None:
    path = accepted_export
    final, temp, args = _export_paths(path)
    original_content = final.read_bytes()
    # Capture the expected consistent report BEFORE breaking or repairing this export.
    consistent = _preview(path, "exports", "integrity", *args)
    assert consistent["status"] == "consistent"
    assert consistent["issues"] == []
    original = JsonGraphStorage.load(path)
    [receipt] = original.nodes_by_type("ArtifactExportReceipt")
    broken = JsonGraphStorage.load(path)
    broken.edges = [
        edge
        for edge in broken.edges
        if not (edge["from_node_id"] == receipt["id"] and edge["edge_type"] == ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT)
    ]
    assert len(broken.edges) == len(original.edges) - 1
    temp.write_bytes(b"residual export write")
    broken.save(path)
    durable_broken = path.read_bytes()

    report = _preview(path, "exports", "integrity", *args)
    codes = ["artifact_edge_missing", "export_temp_file_present"]
    actions = ["create_missing_artifact_edge", "remove_stale_temp_file"]
    assert report["status"] == "repairable"
    assert sorted(issue["code"] for issue in report["issues"]) == codes
    expected_candidate = {
        "id": artifact_export_repair_candidate_id(report["id"], actions),
        "candidate_type": "artifact_export_repair",
        "created_at": NEXT,
        "report_id": report["id"],
        "report_checked_at": NEXT,
        "receipt_id": receipt["id"],
        "source_artifact_id": report["source_artifact_id"],
        "repair_actions": actions,
        "issue_codes": codes,
        "output_directory": report["output_directory"],
        "file_name": final.name,
        "content_hash": report["expected_content_hash"],
        "traceability": report["traceability"],
        "metadata": {key: report["metadata"][key] for key in ("export_scope", "export_format", "privacy_level")},
    }
    candidate = _preview(path, "exports", "repair", "build", *args, "--created-at", NEXT)
    assert candidate == expected_candidate
    assert path.read_bytes() == durable_broken
    assert temp.read_bytes() == b"residual export write"
    assert final.read_bytes() == original_content
    _assert_no_repair(path)

    accept = ["exports", "repair", "accept", *args, "--created-at", NEXT, *REVIEW, "--verified-at", NEXT]
    assert _json(path, *accept) == {
        "report": consistent,
        "decision": "accepted",
        "applied": True,
        "repaired_edge_count": 1,
        "temporary_file_removed": True,
    }
    reloaded = JsonGraphStorage.load(path)
    assert not temp.exists()
    assert final.read_bytes() == original_content
    [repair_receipt] = reloaded.nodes_by_type("ArtifactExportRepairReceipt")
    assert repair_receipt["properties"]["repair_candidate_id"] == candidate["id"]
    assert repair_receipt["properties"]["receipt_id"] == receipt["id"]
    audit = validate_artifact_export_repair_acceptance_audit(reloaded, candidate)
    assert audit["audit_type"] == "artifact_export_repair_accepted"
    assert reloaded.audit_records == [*original.audit_records, audit]
    assert reloaded.nodes == {**original.nodes, repair_receipt["id"]: repair_receipt}

    # Traverse only canonical persisted edges, all the way back to the initial evidence.
    [artifact] = reloaded.nodes_by_type("ProfessionalArtifact")
    [claim] = reloaded.nodes_by_type("CareerClaim")
    [analysis] = reloaded.nodes_by_type("ContributionAnalysis")
    [contribution] = reloaded.nodes_by_type("Contribution")
    [evidence] = reloaded.nodes_by_type("EvidenceNode")
    expected_edges = {
        (ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"], artifact["id"]),
        (ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"], claim["id"]),
        (ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, receipt["id"], evidence["id"]),
        (PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, artifact["id"], claim["id"]),
        (CAREER_CLAIM_DERIVED_FROM_ANALYSIS, claim["id"], analysis["id"]),
        (CAREER_CLAIM_FROM_CONTRIBUTION, claim["id"], contribution["id"]),
        (CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim["id"], evidence["id"]),
        (CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, analysis["id"], contribution["id"]),
        (CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], evidence["id"]),
    }
    actual_edges = {(e["edge_type"], e["from_node_id"], e["to_node_id"]) for e in reloaded.edges}
    assert expected_edges <= actual_edges
    assert len(reloaded.edges) == len(original.edges)
    assert _preview(path, "exports", "integrity", *args) == consistent

    durable_repaired = path.read_bytes()
    reject = ["exports", "repair", "reject", *args, "--created-at", NEXT, *REVIEW, "--reason", "review"]
    for command in (accept, reject):
        code, stdout, stderr = _run(["--store", str(path), "--json", *command])
        assert (code, stdout) == (1, "")
        assert "requires a repairable report" in stderr
        assert path.read_bytes() == durable_repaired
        assert final.read_bytes() == original_content
        assert not temp.exists()
        current = JsonGraphStorage.load(path)
        assert current.nodes_by_type("ArtifactExportRepairReceipt") == [repair_receipt]
        assert current.audit_records == reloaded.audit_records


def test_blocked_export_content_is_never_repaired(accepted_export: Path) -> None:
    path = accepted_export
    final, temp, args = _export_paths(path)
    graph_before = path.read_bytes()
    content_before = final.read_bytes()
    tampered = content_before + b"\nIntentional E2E content mismatch.\n"
    final.write_bytes(tampered)

    report = _preview(path, "exports", "integrity", *args)
    assert report["status"] == "blocked"
    assert [issue["code"] for issue in report["issues"]] == ["export_file_content_mismatch"]
    code, stdout, stderr = _run(
        [
            "--store",
            str(path),
            "--json",
            "exports",
            "repair",
            "build",
            *args,
            "--created-at",
            NEXT,
        ]
    )
    assert (code, stdout) == (1, "")
    assert "requires a repairable report" in stderr
    assert path.read_bytes() == graph_before
    assert final.read_bytes() == tampered
    assert not temp.exists()
    _assert_no_repair(path)


def test_repair_reject_is_audit_only_and_allows_later_accept(accepted_export: Path) -> None:
    path = accepted_export
    final, temp, args = _export_paths(path)
    content_before = final.read_bytes()
    consistent = _preview(path, "exports", "integrity", *args)
    before = JsonGraphStorage.load(path)
    temp.write_bytes(b"residual")
    report = _preview(path, "exports", "integrity", *args)
    assert report["status"] == "repairable"
    assert [issue["code"] for issue in report["issues"]] == ["export_temp_file_present"]
    candidate = _preview(path, "exports", "repair", "build", *args, "--created-at", NEXT)
    assert _json(
        path,
        "exports",
        "repair",
        "reject",
        *args,
        "--created-at",
        NEXT,
        *REVIEW,
        "--reason",
        "review later",
    ) == {
        "candidate_id": candidate["id"],
        "receipt_id": candidate["receipt_id"],
        "decision": "rejected",
        "reason": "review later",
    }
    rejected = JsonGraphStorage.load(path)
    assert rejected.nodes == before.nodes
    assert rejected.edges == before.edges
    assert rejected.audit_records[:-1] == before.audit_records
    audit = rejected.audit_records[-1]
    assert audit["audit_type"] == "artifact_export_repair_rejected"
    assert audit["result"] == "rejected"
    assert audit["target_refs"] == [candidate["receipt_id"], candidate["report_id"], candidate["id"]]
    assert audit["actor"] == "human"
    assert audit["metadata"]["reason"] == "review later"
    assert not rejected.nodes_by_type("ArtifactExportRepairReceipt")
    assert temp.read_bytes() == b"residual"
    assert final.read_bytes() == content_before
    assert _preview(path, "exports", "integrity", *args) == report
    assert _json(
        path,
        "exports",
        "repair",
        "accept",
        *args,
        "--created-at",
        NEXT,
        *REVIEW,
        "--verified-at",
        NEXT,
    ) == {
        "report": consistent,
        "decision": "accepted",
        "applied": True,
        "repaired_edge_count": 0,
        "temporary_file_removed": True,
    }
    accepted = JsonGraphStorage.load(path)
    [repair_receipt] = accepted.nodes_by_type("ArtifactExportRepairReceipt")
    assert repair_receipt["properties"]["repair_candidate_id"] == candidate["id"]
    acceptance = validate_artifact_export_repair_acceptance_audit(accepted, candidate)
    assert accepted.audit_records == [*rejected.audit_records, acceptance]
    assert accepted.edges == before.edges
    assert not temp.exists()
    assert final.read_bytes() == content_before
    assert _preview(path, "exports", "integrity", *args) == consistent
