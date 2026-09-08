"""Synthetic value experiment: preserve generated wording, including its weaknesses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_interfaces_cli import NEXT, NOW, _run
from test_modern_journey_e2e import _json, _preview

from carrer.ingestion.service import ingest_fixture, load_source_input
from carrer.storage.json_graph_storage import JsonGraphStorage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/resume_validation_source_export.json"
GOLDEN = ROOT / "examples/expected/resume_claims_validation.md"
REVIEW = ["--actor", "synthetic-validation-only", "--decided-at", NEXT]
FORBIDDEN = ("SYNTHETIC_PRIVATE_CANARY", "SYNTHETIC_INTERNAL_CANARY", "987654", "876543")


def _journey(directory: Path) -> dict[str, Any]:
    directory.mkdir()
    path = directory / "graph.json"
    store = JsonGraphStorage()
    assert ingest_fixture(load_source_input(SOURCE), store) == {"records_created": 10, "records_reused": 0}
    evidence_before = {node["id"]: node for node in store.nodes_by_type("EvidenceNode")}
    store.save(path)
    discovered = _preview(path, "contributions", "discover")
    assert sorted(len(item["evidence_refs"]) for item in discovered) == [1, 1, 2, 2, 2, 2]

    # Exhaustive acceptance is authorized only for this fixed synthetic experiment.
    # It is factual acceptance, NOT a judgement that these statements belong in a CV.
    generated_ids = []
    for candidate in discovered:
        contribution = _json(path, "contributions", "promote", "--candidate-id", candidate["id"], *REVIEW)[
            "contribution"
        ]
        args = ["--contribution-id", contribution["id"]]
        draft = _preview(path, "analyses", "generate", *args)
        analysis = _json(path, "analyses", "accept", *args, *REVIEW)["analysis"]
        assert analysis["id"] == draft["id"]
        claims = _preview(path, "claims", "generate", "--analysis-id", analysis["id"])
        for claim in claims:
            generated_ids.append(claim["id"])
            accepted = _json(
                path, "claims", "accept", "--analysis-id", analysis["id"], "--candidate-id", claim["id"], *REVIEW
            )["claim"]
            assert accepted["properties"]["statement"] == claim["statement"]

    store = JsonGraphStorage.load(path)
    claims = store.nodes_by_type("CareerClaim")
    safe = [claim for claim in claims if claim["properties"]["privacy_level"] == "artifact_safe"]
    selected = [arg for claim in safe for arg in ("--claim-id", claim["id"])]
    args = [*selected, "--artifact-type", "resume_claims", "--audience", "public", "--created-at", NOW]
    draft = _preview(path, "artifacts", "build", *args)
    artifact = _json(path, "artifacts", "accept", *args, *REVIEW)["artifact"]
    output = directory / "exports"
    args = [
        "--artifact-id",
        artifact["id"],
        "--export-scope",
        "external",
        "--export-format",
        "markdown",
        "--created-at",
        NEXT,
    ]
    export = _preview(path, "exports", "build", *args)
    receipt = _json(path, "exports", "accept", *args, "--output-directory", str(output), *REVIEW)["receipt"]
    content = (output / receipt["properties"]["file_name"]).read_bytes()
    assert content == export["content"].encode("utf-8")
    integrity = _preview(
        path,
        "exports",
        "integrity",
        "--receipt-id",
        receipt["id"],
        "--output-directory",
        str(output),
        "--checked-at",
        NEXT,
    )
    graph = _preview(path, "integrity", "graph")
    store = JsonGraphStorage.load(path)
    assert {node["id"]: node for node in store.nodes_by_type("EvidenceNode")} == evidence_before
    assert integrity["status"] == "consistent"
    assert graph["status"] == "valid"
    assert integrity["issues"] == []
    # Existing analysis acceptance emits unsorted audit refs. Preserve and expose
    # these warnings; do not repair the experiment to manufacture a zero count.
    assert [(issue["code"], issue["severity"]) for issue in graph["issues"]] == [
        ("AUDIT_TARGET_REFS_NOT_CANONICAL", "warning")
    ] * 6

    edges = {(edge["edge_type"], edge["from_node_id"], edge["to_node_id"]) for edge in store.edges}
    for claim in claims:
        props = claim["properties"]
        assert props["status"] == "accepted"
        analysis_id = props["metadata"]["analysis_ref"]
        assert ("CAREER_CLAIM_DERIVED_FROM_ANALYSIS", claim["id"], analysis_id) in edges
        for ref in props["contribution_refs"]:
            assert store.nodes[ref]["node_type"] == "Contribution"
            assert ("CAREER_CLAIM_FROM_CONTRIBUTION", claim["id"], ref) in edges
            assert ("CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION", analysis_id, ref) in edges
            for evidence_id in props["evidence_refs"]:
                assert store.nodes[evidence_id]["node_type"] == "EvidenceNode"
                assert ("CAREER_CLAIM_SUPPORTED_BY_EVIDENCE", claim["id"], evidence_id) in edges
                assert ("CONTRIBUTION_SUPPORTED_BY_EVIDENCE", ref, evidence_id) in edges

    for item in draft["items"]:
        assert ("PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM", artifact["id"], item["claim_ref"]) in edges
        assert ("ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM", receipt["id"], item["claim_ref"]) in edges
        assert all(
            store.nodes[ref]["properties"]["privacy_level"] == "artifact_safe"
            for ref in item["traceability"]["evidence_refs"]
        )

    metrics = {
        "evidence_count": len(store.nodes_by_type("EvidenceNode")),
        "contribution_count": len(store.nodes_by_type("Contribution")),
        "analysis_count": len(store.nodes_by_type("ContributionAnalysis")),
        "claim_count": len(claims),
        "artifact_claim_count": len(draft["items"]),
        "exported_bullet_count": sum(line.startswith(b"- ") for line in content.splitlines()),
        "orphan_claim_count": sum(
            not c["properties"]["contribution_refs"]
            or any(ref not in store.nodes for ref in c["properties"]["contribution_refs"])
            for c in claims
        ),
        "claims_without_evidence_count": sum(not c["properties"]["evidence_refs"] for c in claims),
        "privacy_violation_count": sum(term.encode() in content for term in FORBIDDEN)
        + sum(item["privacy_level"] != "artifact_safe" for item in draft["items"]),
        "integrity_issue_count": len(integrity["issues"]) + len(graph["issues"]),
    }
    report = {
        "metrics": metrics,
        "artifact_id": artifact["id"],
        "bullets": draft["items"],
        "generated_candidate_count": len(generated_ids),
    }
    (directory / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {"path": path, "content": content, "report": report, "claims": claims, "generated_ids": generated_ids}


def test_resume_value_validation(tmp_path: Path) -> None:
    first = _journey(tmp_path / "first")
    second = _journey(tmp_path / "second")
    # Normalize checkout line endings only; independent exports must match byte-for-byte.
    assert first["content"] == second["content"] == GOLDEN.read_text(encoding="utf-8").encode("utf-8")
    assert first["report"] == second["report"]
    assert first["report"]["metrics"] == {
        "evidence_count": 10,
        "contribution_count": 6,
        "analysis_count": 6,
        "claim_count": 20,
        "artifact_claim_count": 14,
        "exported_bullet_count": 14,
        "orphan_claim_count": 0,
        "claims_without_evidence_count": 0,
        "privacy_violation_count": 0,
        "integrity_issue_count": 6,
    }
    # Technical success does not imply value: the golden intentionally retains generic bullets.
    assert b"Observed latency metric: 800 ms." in first["content"]
    assert b"Observed latency metric: 300 ms." in first["content"]
    assert not any(term.encode() in first["content"] for term in (*FORBIDDEN, "Led", "75%", "revenue"))


@pytest.mark.parametrize("privacy", ["private", "internal", "unaccepted"])
def test_resume_artifact_rejects_ineligible_claims(tmp_path: Path, privacy: str) -> None:
    result = _journey(tmp_path / "journey")
    if privacy == "unaccepted":
        claim_id = result["generated_ids"][0]  # A candidate ID is not an accepted CareerClaim ID.
    else:
        claim_id = next(c["id"] for c in result["claims"] if c["properties"]["privacy_level"] == privacy)
    path = result["path"]
    before = path.read_bytes()
    code, _, stderr = _run(
        [
            "--store",
            str(path),
            "--json",
            "artifacts",
            "build",
            "--claim-id",
            claim_id,
            "--artifact-type",
            "resume_claims",
            "--audience",
            "public",
            "--created-at",
            NOW,
        ]
    )
    assert code != 0
    assert "privacy" in stderr if privacy != "unaccepted" else "not found" in stderr
    assert path.read_bytes() == before
