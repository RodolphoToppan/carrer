from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import carrer.artifacts.claim_export_review as claim_export_review
from carrer.artifacts import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
    accept_claim_based_artifact,
    accept_claim_based_artifact_export,
    artifact_export_receipt_id,
    build_artifact_from_career_claims,
    build_claim_based_artifact_export_candidate,
    claim_based_artifact_export_candidate_id,
    get_artifact_export_receipt,
    list_artifact_export_receipts,
    reject_claim_based_artifact_export,
    validate_artifact_export_receipt_contract,
    validate_claim_based_artifact_export_candidate,
    validate_persisted_artifact_export_receipt,
)
from carrer.claims import accept_career_claim_candidate, generate_career_claim_candidates
from carrer.contributions import accept_contribution_analysis, analyze_contribution, create_contribution
from carrer.domain.hashing import stable_hash
from carrer.domain.models import evidence_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"
DRAFT_AT = "2026-01-03T00:00:00Z"
DECIDED_AT = "2026-01-04T05:06:07-03:00"


def _evidence(entity_type: str, entity_id: str, *, privacy_level: str = "artifact_safe") -> dict[str, Any]:
    return evidence_node(
        source_id="test",
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type={
            "commit": "COMMIT_EXISTS",
            "merge_request": "MERGE_REQUEST_EXISTS",
            "work_item": "WORK_ITEM_EXISTS",
        }[entity_type],
        captured_at=NOW,
        occurred_at=NOW,
        privacy_level=privacy_level,
        metadata={"state": "merged", "latency_after_ms": 300},
    )


def _store(*, privacy_level: str = "artifact_safe") -> tuple[JsonGraphStorage, dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = [
        _evidence("commit", "C-1", privacy_level=privacy_level),
        _evidence("merge_request", "MR-1", privacy_level=privacy_level),
        _evidence("work_item", "WI-1", privacy_level=privacy_level),
    ]
    for node in evidence:
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=[node["id"] for node in evidence],
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
        privacy_level=privacy_level,
    )["contribution"]
    analysis = accept_contribution_analysis(
        store,
        analyze_contribution(store, contribution["id"]),
        decision_actor="human",
        decided_at=NOW,
    )["analysis"]
    claims = [
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
        for candidate in generate_career_claim_candidates(store, analysis["id"])
    ]
    artifact = accept_claim_based_artifact(
        store,
        build_artifact_from_career_claims(
            store,
            claim_ids=[claim["id"] for claim in claims[:2]],
            artifact_type="resume_claims",
            audience="internal" if privacy_level == "internal" else "public",
            created_at=DRAFT_AT,
        ),
        decision_actor="reviewer",
        decided_at=DECIDED_AT,
    )["artifact"]
    return store, artifact


@pytest.fixture
def output_dir(request: pytest.FixtureRequest) -> Path:
    base = Path("tests/.tmp_claim_export") / re.sub(r"[^a-zA-Z0-9_.-]+", "_", request.node.name)
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    yield base
    shutil.rmtree(base, ignore_errors=True)


def _candidate(
    store: JsonGraphStorage,
    artifact: dict[str, Any],
    *,
    scope: str = "external",
    created_at: str = "2026-02-01T10:11:12Z",
) -> dict[str, Any]:
    return build_claim_based_artifact_export_candidate(
        store,
        artifact["id"],
        export_scope=scope,
        export_format="markdown",
        created_at=created_at,
    )


def _accepted_export(output_dir: Path) -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any], dict[str, Any]]:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]
    return store, artifact, candidate, receipt


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}, sort_keys=True
    )


def _set_path(value: dict[str, Any], path: list[str], replacement: object) -> None:
    current = value
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = replacement


def test_candidate_is_deterministic_read_only_and_preserves_content() -> None:
    store, artifact = _store()
    before = _snapshot(store)

    candidate = _candidate(store, artifact)
    again = _candidate(store, artifact)

    assert candidate == again
    assert _snapshot(store) == before
    assert candidate["content"] == artifact["properties"]["content"]
    assert candidate["content_hash"] == stable_hash(artifact["properties"]["content"])
    assert candidate["file_name"].endswith(".md")
    assert "/" not in candidate["file_name"]
    assert "\\" not in candidate["file_name"]
    assert ".." not in candidate["file_name"]
    assert candidate["id"] == claim_based_artifact_export_candidate_id(
        artifact["id"], "external", "markdown", candidate["content_hash"]
    )


def test_candidate_hash_and_id_change_when_content_changes() -> None:
    first_store, first_artifact = _store()
    second_store, second_artifact = _store()

    first = _candidate(first_store, first_artifact)
    second_store.nodes[second_artifact["id"]]["properties"]["items"][0]["text"] += " Changed."
    second_store.nodes[second_artifact["id"]]["properties"]["content"] = (
        "# Career Claims\n\n"
        + "\n".join(f"- {item['text']}" for item in second_store.nodes[second_artifact["id"]]["properties"]["items"])
        + "\n"
    )
    second = _candidate(second_store, second_artifact)

    assert first["content_hash"] != second["content_hash"]
    assert first["id"] != second["id"]


@pytest.mark.parametrize(
    "created_at", ["2026-02-01T10:11:12Z", "2026-02-01T10:11:12+02:00", "2026-02-01T10:11:12-03:00"]
)
def test_candidate_accepts_iso8601_with_timezone(created_at: str) -> None:
    store, artifact = _store()
    assert _candidate(store, artifact, created_at=created_at)["created_at"] == created_at


@pytest.mark.parametrize("created_at", ["2026-02-01T10:11:12", "bad", 123])
def test_candidate_rejects_invalid_timestamps(created_at: object) -> None:
    store, artifact = _store()
    with pytest.raises(ValueError):
        build_claim_based_artifact_export_candidate(
            store,
            artifact["id"],
            export_scope="external",
            export_format="markdown",
            created_at=created_at,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("privacy", "scope", "allowed"),
    [
        ("internal", "internal", True),
        ("internal", "external", False),
        ("artifact_safe", "internal", True),
        ("artifact_safe", "external", True),
    ],
)
def test_privacy_scope_matrix(privacy: str, scope: str, allowed: bool) -> None:
    store, artifact = _store(privacy_level=privacy)
    if allowed:
        assert _candidate(store, artifact, scope=scope)["export_scope"] == scope
    else:
        with pytest.raises(ValueError):
            _candidate(store, artifact, scope=scope)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("export_scope", "public"),
        ("export_format", "pdf"),
        ("source_artifact_id", "artifact:missing"),
    ],
)
def test_candidate_validation_rejects_invalid_fields(field: str, value: object) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    candidate[field] = value
    with pytest.raises(ValueError):
        validate_claim_based_artifact_export_candidate(candidate)


def test_candidate_created_at_is_not_part_of_identity_but_changes_structure() -> None:
    store, artifact = _store()
    first = _candidate(store, artifact, created_at="2026-02-01T10:11:12Z")
    second = _candidate(store, artifact, created_at="2026-02-01T10:11:12+02:00")

    assert first["id"] == second["id"]
    assert first != second


def test_candidate_generation_rejects_missing_wrong_legacy_invalid_and_bad_arguments() -> None:
    store, artifact = _store()
    store.create_node({"id": "other:1", "node_type": "Other", "created_at": NOW, "properties": {}})
    store.create_node(
        {
            "id": "artifact:legacy",
            "node_type": "ProfessionalArtifact",
            "created_at": DRAFT_AT,
            "properties": {
                "artifact_type": "Resume",
                "knowledge_refs": [],
                "status": "draft",
                "privacy_level": "draft_private",
            },
        }
    )
    invalid_claim_based = copy.deepcopy(artifact)
    invalid_claim_based["id"] = "artifact:invalid"
    invalid_claim_based["properties"]["status"] = "draft"
    store.nodes[invalid_claim_based["id"]] = invalid_claim_based

    bad_calls = [
        {"artifact_id": "artifact:missing", "export_scope": "external", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": "other:1", "export_scope": "external", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": "artifact:legacy", "export_scope": "external", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": "artifact:invalid", "export_scope": "external", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": artifact["id"], "export_scope": "public", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": artifact["id"], "export_scope": "external", "export_format": "pdf", "created_at": NOW},
        {"artifact_id": 123, "export_scope": "external", "export_format": "markdown", "created_at": NOW},
        {"artifact_id": artifact["id"], "export_scope": 123, "export_format": "markdown", "created_at": NOW},
        {"artifact_id": artifact["id"], "export_scope": "external", "export_format": 123, "created_at": NOW},
    ]
    for kwargs in bad_calls:
        with pytest.raises(ValueError):
            build_claim_based_artifact_export_candidate(store, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["id"], "claim_based_artifact_export_candidate:other"),
        (["source_artifact_id"], "artifact:missing"),
        (["source_artifact_created_at"], "2026-02-01T10:11:12Z"),
        (["artifact_type"], "linkedin_claims"),
        (["audience"], "internal"),
        (["privacy_level"], "internal"),
        (["export_scope"], "internal"),
        (["file_name"], "../x.md"),
        (["content"], "changed"),
        (["content_hash"], "changed"),
        (["traceability", "claim_refs"], ["career_claim:a"]),
        (["traceability", "evidence_refs"], ["evidence:a"]),
        (["metadata", "source_type"], "other"),
        (["metadata", "artifact_version"], "v2"),
        (["metadata", "claim_count"], 99),
        (["metadata", "evidence_count"], 99),
        (["metadata", "warning_count"], 99),
    ],
)
def test_accept_and_reject_detect_tampered_candidate(path: list[str], value: object, output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    changed = copy.deepcopy(candidate)
    _set_path(changed, path, value)

    with pytest.raises(ValueError):
        accept_claim_based_artifact_export(
            store, changed, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
        )
    with pytest.raises(ValueError):
        reject_claim_based_artifact_export(store, changed, decision_actor="reviewer", decided_at=DECIDED_AT)


def test_accept_and_reject_detect_stale_candidate(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    store.nodes[artifact["id"]]["properties"]["items"][0]["text"] += " Changed."
    store.nodes[artifact["id"]]["properties"]["content"] = (
        "# Career Claims\n\n"
        + "\n".join(f"- {item['text']}" for item in store.nodes[artifact["id"]]["properties"]["items"])
        + "\n"
    )

    with pytest.raises(ValueError, match="current deterministic export candidate"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
        )
    with pytest.raises(ValueError, match="current deterministic export candidate"):
        reject_claim_based_artifact_export(store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT)


def test_accept_writes_file_persists_receipt_edges_and_safe_audit(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)

    result = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )

    receipt = result["receipt"]
    target = output_dir / candidate["file_name"]
    assert result["created"] is True
    assert result["written"] is True
    assert target.read_text(encoding="utf-8") == candidate["content"]
    assert receipt["id"] == artifact_export_receipt_id(candidate["id"])
    assert receipt["created_at"] == DECIDED_AT
    assert receipt["properties"]["reviewed_at"] == DECIDED_AT
    assert receipt["properties"]["candidate_created_at"] == candidate["created_at"]
    assert receipt["properties"]["output_path"] == candidate["file_name"]
    assert "content" not in receipt["properties"]
    assert validate_persisted_artifact_export_receipt(store, receipt) is receipt
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"]) == {artifact["id"]}
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"]) == set(
        candidate["traceability"]["claim_refs"]
    )
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, receipt["id"]) == set(
        candidate["traceability"]["evidence_refs"]
    )
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "claim_based_artifact_export_accepted"
    assert audit["metadata"]["created"] is True
    assert audit["metadata"]["written"] is True
    assert audit["metadata"]["candidate_created_at"] == candidate["created_at"]
    assert candidate["content"] not in json.dumps(audit)


@pytest.mark.parametrize(
    "candidate_created_at",
    ["2026-02-01T10:11:12Z", "2026-02-01T10:11:12+02:00", "2026-02-01T10:11:12-03:00"],
)
def test_receipt_preserves_candidate_created_at_exactly(candidate_created_at: str, output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact, created_at=candidate_created_at)

    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]

    assert receipt["properties"]["candidate_created_at"] == candidate_created_at
    assert receipt["created_at"] == DECIDED_AT
    assert receipt["properties"]["reviewed_at"] == DECIDED_AT
    assert validate_persisted_artifact_export_receipt(store, receipt) is receipt


def test_existing_receipt_rejects_same_id_candidate_with_different_created_at(output_dir: Path) -> None:
    store, artifact = _store()
    first = _candidate(store, artifact, created_at="2026-02-01T10:11:12Z")
    second = _candidate(store, artifact, created_at="2026-02-01T10:11:12+02:00")
    accept_claim_based_artifact_export(
        store, first, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )

    with pytest.raises(ValueError, match="created_at"):
        accept_claim_based_artifact_export(
            store, second, output_directory=output_dir, decision_actor="again", decided_at="2026-02-02T00:00:00Z"
        )


def test_accept_is_idempotent_and_does_not_overwrite_first_review(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    first = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="first", decided_at=DECIDED_AT
    )
    edge_count = len(store.edges)
    second_at = "2026-02-02T00:00:00+02:00"

    second = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="second", decided_at=second_at
    )

    assert second["created"] is False
    assert second["written"] is False
    assert second["receipt"] == first["receipt"]
    assert second["receipt"]["properties"]["review_actor"] == "first"
    assert second["receipt"]["properties"]["reviewed_at"] == DECIDED_AT
    assert len(store.edges) == edge_count
    assert store.audit_records[-1]["metadata"]["actor"] == "second"
    assert store.audit_records[-1]["metadata"]["decided_at"] == second_at


def test_accept_rejects_preexisting_file_without_receipt_and_missing_file_with_receipt(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    (output_dir / candidate["file_name"]).write_text(candidate["content"], encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
        )
    (output_dir / candidate["file_name"]).unlink()
    accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )
    (output_dir / candidate["file_name"]).unlink()
    with pytest.raises(ValueError, match="file is missing"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="again", decided_at="2026-02-02T00:00:00Z"
        )


def test_accept_rejects_existing_file_with_different_content(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )
    (output_dir / candidate["file_name"]).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="content"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="again", decided_at="2026-02-02T00:00:00Z"
        )


def test_reject_only_audits_and_preserves_reason(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    before = _snapshot(store)

    result = reject_claim_based_artifact_export(
        store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, reason="  no thanks  "
    )

    assert result["decision"] == "rejected"
    assert result["reason"] == "  no thanks  "
    assert not (output_dir / candidate["file_name"]).exists()
    assert json.loads(_snapshot(store))["nodes"] == json.loads(before)["nodes"]
    assert json.loads(_snapshot(store))["edges"] == json.loads(before)["edges"]
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "claim_based_artifact_export_rejected"
    assert audit["metadata"]["reason"] == "  no thanks  "
    assert candidate["content"] not in json.dumps(audit)


@pytest.mark.parametrize(
    ("scope", "privacy", "allowed"),
    [
        ("internal", "internal", True),
        ("internal", "artifact_safe", True),
        ("external", "artifact_safe", True),
        ("external", "internal", False),
    ],
)
def test_receipt_contract_enforces_scope_privacy_matrix(
    scope: str, privacy: str, allowed: bool, output_dir: Path
) -> None:
    _, _, _, receipt = _accepted_export(output_dir)
    changed = copy.deepcopy(receipt)
    changed["properties"]["export_scope"] = scope
    changed["properties"]["privacy_level"] = privacy

    if allowed:
        assert validate_artifact_export_receipt_contract(changed) is changed
    else:
        with pytest.raises(ValueError):
            validate_artifact_export_receipt_contract(changed)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["properties", "output_path"], "other.md"),
        (["properties", "candidate_created_at"], ""),
        (["properties", "candidate_created_at"], "2026-02-01T10:11:12"),
        (["properties", "file_name"], "../x.md"),
        (["properties", "file_name"], "x/y.md"),
        (["properties", "file_name"], "x\\y.md"),
        (["properties", "file_name"], "x.txt"),
        (["properties", "file_name"], ""),
        (["properties", "claim_refs"], "career_claim:a"),
        (["properties", "metadata", "claim_count"], "2"),
    ],
)
def test_receipt_contract_rejects_path_and_type_errors(path: list[str], value: object, output_dir: Path) -> None:
    _, _, _, receipt = _accepted_export(output_dir)
    changed = copy.deepcopy(receipt)
    _set_path(changed, path, value)

    with pytest.raises(ValueError):
        validate_artifact_export_receipt_contract(changed)


def test_receipt_contract_requires_candidate_created_at(output_dir: Path) -> None:
    _, _, _, receipt = _accepted_export(output_dir)
    changed = copy.deepcopy(receipt)
    changed["properties"].pop("candidate_created_at")

    with pytest.raises(ValueError):
        validate_artifact_export_receipt_contract(changed)


def test_persisted_receipt_requires_store_and_original_acceptance_audit(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir / "joint")
    assert validate_persisted_artifact_export_receipt(store, receipt) is receipt
    with pytest.raises(TypeError):
        validate_persisted_artifact_export_receipt(receipt)  # type: ignore[call-arg]

    without_audit = copy.deepcopy(store)
    without_audit.audit_records = []
    with pytest.raises(ValueError, match="original export acceptance audit"):
        validate_persisted_artifact_export_receipt(without_audit, receipt)


@pytest.mark.parametrize(
    ("audit_path", "value"),
    [
        (["actor"], "other"),
        (["created_at"], "2026-02-02T00:00:00Z"),
        (["metadata", "actor"], "other"),
        (["metadata", "decided_at"], "2026-02-02T00:00:00Z"),
        (["metadata", "candidate_id"], "candidate:other"),
        (["metadata", "candidate_created_at"], "2026-02-02T00:00:00Z"),
        (["metadata", "source_artifact_id"], "artifact:other"),
        (["metadata", "written"], False),
    ],
)
def test_persisted_receipt_rejects_original_audit_mismatch(
    audit_path: list[str], value: object, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir / "joint")
    audit = next(
        record for record in store.audit_records if record["audit_type"] == "claim_based_artifact_export_accepted"
    )
    _set_path(audit, audit_path, value)

    with pytest.raises(ValueError, match="original export acceptance audit"):
        validate_persisted_artifact_export_receipt(store, receipt)


def test_persisted_receipt_rejects_duplicate_original_audit_and_joint_review_tampering(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir / "joint-review")
    original = next(
        record for record in store.audit_records if record["audit_type"] == "claim_based_artifact_export_accepted"
    )
    store.audit_records.append(copy.deepcopy(original))
    with pytest.raises(ValueError, match="exactly one"):
        validate_persisted_artifact_export_receipt(store, receipt)

    store, _, _, receipt = _accepted_export(output_dir / "joint-review-second")
    changed = copy.deepcopy(receipt)
    changed["created_at"] = "2026-02-02T00:00:00Z"
    changed["properties"]["review_actor"] = "other"
    changed["properties"]["reviewed_at"] = "2026-02-02T00:00:00Z"
    with pytest.raises(ValueError):
        validate_persisted_artifact_export_receipt(store, changed)

    store, _, _, receipt = _accepted_export(output_dir / "joint-candidate-created-at")
    changed = copy.deepcopy(receipt)
    changed["properties"]["candidate_created_at"] = "2026-02-02T00:00:00Z"
    audit = next(
        record for record in store.audit_records if record["audit_type"] == "claim_based_artifact_export_accepted"
    )
    audit["metadata"]["candidate_created_at"] = "2026-02-02T00:00:00Z"
    with pytest.raises(ValueError):
        validate_persisted_artifact_export_receipt(store, changed)


def test_idempotent_audits_do_not_replace_original_review(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    first = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="first", decided_at=DECIDED_AT
    )
    accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="second", decided_at="2026-02-02T00:00:00Z"
    )

    assert validate_persisted_artifact_export_receipt(store, first["receipt"]) is first["receipt"]


def test_atomic_write_failure_leaves_no_persisted_export_state(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)

    def fail_after_tmp(target: Path, content: str) -> None:
        tmp = target.with_name("." + target.name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.unlink()
        raise OSError("disk full")

    monkeypatch.setattr(claim_export_review, "_atomic_write", fail_after_tmp)
    with pytest.raises(OSError, match="disk full"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
        )

    assert store.nodes_by_type("ArtifactExportReceipt") == []
    assert not any(edge["edge_type"].startswith("ARTIFACT_EXPORT_RECEIPT") for edge in store.edges)
    assert not any(record["audit_type"] == "claim_based_artifact_export_accepted" for record in store.audit_records)
    assert not (output_dir / candidate["file_name"]).exists()
    assert not (output_dir / ("." + candidate["file_name"] + ".tmp")).exists()


def test_real_atomic_write_cleans_tmp_when_replace_fails(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)

    def fail_replace(source: str | Path, target: str | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(claim_export_review.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
        )

    assert store.nodes_by_type("ArtifactExportReceipt") == []
    assert not any(edge["edge_type"].startswith("ARTIFACT_EXPORT_RECEIPT") for edge in store.edges)
    assert not any(record["audit_type"] == "claim_based_artifact_export_accepted" for record in store.audit_records)
    assert not (output_dir / candidate["file_name"]).exists()
    assert not (output_dir / ("." + candidate["file_name"] + ".tmp")).exists()


@pytest.mark.parametrize("output_directory", [None, 123, []])
def test_output_directory_invalid_types_do_not_write_graph_or_files(output_directory: object) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    before = _snapshot(store)

    with pytest.raises(ValueError):
        accept_claim_based_artifact_export(
            store,
            candidate,
            output_directory=output_directory,  # type: ignore[arg-type]
            decision_actor="reviewer",
            decided_at=DECIDED_AT,
        )

    assert _snapshot(store) == before


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["properties", "source_artifact_id"], "artifact:other"),
        (["properties", "export_candidate_id"], "candidate:other"),
        (["properties", "export_scope"], "internal"),
        (["properties", "export_format"], "pdf"),
        (["properties", "privacy_level"], "internal"),
        (["properties", "file_name"], "other.md"),
        (["properties", "content_hash"], "other"),
        (["properties", "candidate_created_at"], "2026-02-02T00:00:00Z"),
        (["properties", "output_path"], "other.md"),
        (["properties", "status"], "pending"),
        (["properties", "review_actor"], "other"),
        (["properties", "reviewed_at"], "2026-02-02T00:00:00Z"),
        (["properties", "claim_refs"], ["career_claim:other", "career_claim:z"]),
        (["properties", "evidence_refs"], ["evidence:other", "evidence:z", "evidence:y"]),
        (["properties", "metadata", "artifact_type"], "linkedin_claims"),
        (["properties", "metadata", "audience"], "internal"),
        (["properties", "metadata", "artifact_version"], "v2"),
        (["properties", "metadata", "claim_count"], 99),
        (["properties", "metadata", "evidence_count"], 99),
        (["properties", "metadata", "warning_count"], 99),
    ],
)
def test_receipt_validator_detects_tampering(path: list[str], value: object, output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]
    changed = copy.deepcopy(receipt)
    _set_path(changed, path, value)

    with pytest.raises(ValueError):
        validate_persisted_artifact_export_receipt(store, changed)


def test_receipt_queries_validate_filter_and_sort(output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact, scope="internal")
    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]
    store.create_node({"id": "other:1", "node_type": "Other", "created_at": NOW, "properties": {}})
    store.create_node(
        {
            "id": "artifact_export_receipt:other-source",
            "node_type": "ArtifactExportReceipt",
            "created_at": NOW,
            "properties": {"source_type": "legacy"},
        }
    )

    assert get_artifact_export_receipt(store, receipt["id"]) == receipt
    assert get_artifact_export_receipt(store, "artifact_export_receipt:missing") is None
    assert get_artifact_export_receipt(store, "other:1") is None
    assert get_artifact_export_receipt(store, "artifact_export_receipt:other-source") is None
    assert list_artifact_export_receipts(store) == [receipt]
    assert list_artifact_export_receipts(store, source_artifact_id=artifact["id"]) == [receipt]
    assert list_artifact_export_receipts(store, export_scope="internal") == [receipt]
    assert list_artifact_export_receipts(store, export_format="markdown") == [receipt]
    assert list_artifact_export_receipts(store, export_scope="external") == []
    with pytest.raises(ValueError):
        list_artifact_export_receipts(store, export_scope="public")
    store.nodes[receipt["id"]]["properties"]["content_hash"] = "bad"
    with pytest.raises(ValueError):
        get_artifact_export_receipt(store, receipt["id"])
    with pytest.raises(ValueError):
        list_artifact_export_receipts(store)


def test_public_apis_reject_structurally_invalid_stores(output_dir: Path) -> None:
    class Empty:
        pass

    bad = Empty()
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]

    with pytest.raises(ValueError):
        build_claim_based_artifact_export_candidate(
            bad,
            artifact["id"],
            export_scope="external",
            export_format="markdown",
            created_at=NOW,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        accept_claim_based_artifact_export(
            bad,
            candidate,
            output_directory=output_dir,
            decision_actor="reviewer",
            decided_at=DECIDED_AT,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        reject_claim_based_artifact_export(bad, candidate, decision_actor="reviewer", decided_at=DECIDED_AT)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        validate_persisted_artifact_export_receipt(bad, receipt)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        get_artifact_export_receipt(bad, receipt["id"])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        list_artifact_export_receipts(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nodes", None),
        ("edges", None),
        ("audit_records", None),
        ("create_node", None),
        ("create_edge", None),
        ("nodes_by_type", None),
    ],
)
def test_public_apis_reject_invalid_store_attribute_types(field: str, value: object, output_dir: Path) -> None:
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    receipt = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )["receipt"]
    setattr(store, field, value)

    if field == "nodes":
        with pytest.raises(ValueError):
            build_claim_based_artifact_export_candidate(
                store, artifact["id"], export_scope="external", export_format="markdown", created_at=NOW
            )
        with pytest.raises(ValueError):
            get_artifact_export_receipt(store, receipt["id"])
    if field in {"nodes", "edges", "audit_records", "create_node", "create_edge"}:
        with pytest.raises(ValueError):
            accept_claim_based_artifact_export(
                store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
            )
    if field in {"nodes", "edges", "audit_records"}:
        with pytest.raises(ValueError):
            reject_claim_based_artifact_export(store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT)
        with pytest.raises(ValueError):
            validate_persisted_artifact_export_receipt(store, receipt)
    if field in {"nodes", "nodes_by_type"}:
        with pytest.raises(ValueError):
            list_artifact_export_receipts(store)


def _edge_targets(store: JsonGraphStorage, edge_type: str, from_node_id: str) -> set[str]:
    return {
        edge["to_node_id"]
        for edge in store.edges
        if edge["edge_type"] == edge_type and edge["from_node_id"] == from_node_id
    }
