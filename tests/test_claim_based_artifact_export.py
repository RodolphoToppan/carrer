from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import carrer.artifacts.claim_export_review as claim_export_review
import carrer.artifacts.claim_review as claim_review
from carrer.artifacts import (
    ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT,
    ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
    ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE,
    accept_artifact_export_repair,
    accept_claim_based_artifact,
    accept_claim_based_artifact_export,
    artifact_export_integrity_report_id,
    artifact_export_receipt_id,
    artifact_export_repair_candidate_id,
    artifact_export_repair_receipt_id,
    build_artifact_export_repair_candidate,
    build_artifact_from_career_claims,
    build_claim_based_artifact_export_candidate,
    check_artifact_export_integrity,
    claim_based_artifact_export_candidate_id,
    get_artifact_export_receipt,
    list_artifact_export_receipts,
    reject_artifact_export_repair,
    reject_claim_based_artifact_export,
    validate_artifact_export_integrity_report,
    validate_artifact_export_receipt_contract,
    validate_artifact_export_repair_acceptance_audit,
    validate_artifact_export_repair_candidate,
    validate_artifact_export_repair_receipt_contract,
    validate_claim_based_artifact_export_candidate,
    validate_original_artifact_export_acceptance_audit,
    validate_persisted_artifact_export_receipt,
    validate_persisted_artifact_export_repair_receipt,
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


def _accepted_repair(output_dir: Path) -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    accept_artifact_export_repair(
        store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
    )
    return store, receipt, candidate


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records}, sort_keys=True
    )


def _set_path(value: dict[str, Any], path: list[str], replacement: object) -> None:
    current = value
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = replacement


def _refresh_audit_id(store: JsonGraphStorage, audit: dict[str, Any]) -> None:
    audit["id"] = "audit:" + stable_hash(
        [
            audit.get("audit_type"),
            audit.get("target_refs"),
            audit.get("result"),
            audit.get("metadata"),
            audit.get("created_at"),
            store.audit_records.index(audit),
        ]
    )


def _refresh_repair_audit_fingerprint(audit: dict[str, Any], candidate: dict[str, Any]) -> None:
    audit["metadata"]["original_decision_fingerprint"] = stable_hash(
        [
            candidate["id"],
            candidate["report_id"],
            candidate["receipt_id"],
            audit["metadata"]["actor"],
            audit["metadata"]["decided_at"],
            candidate["issue_codes"],
            candidate["repair_actions"],
            audit["metadata"]["repaired_edge_count"],
            audit["metadata"]["temporary_file_removed"],
        ]
    )


def _refresh_report_id(report: dict[str, Any]) -> None:
    report["id"] = artifact_export_integrity_report_id(
        report["receipt_id"],
        report["output_directory"],
        report["expected_content_hash"],
        [issue["code"] for issue in report["issues"]],
    )


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


def test_integrity_report_is_consistent_read_only_and_deterministic(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    before = _snapshot(store)

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    again = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report == again
    assert _snapshot(store) == before
    assert report["status"] == "consistent"
    assert report["issues"] == []
    assert report["checks"] == {
        "receipt_contract_valid": True,
        "persisted_contract_valid": True,
        "file_exists": True,
        "file_content_matches": True,
        "temporary_file_exists": False,
        "artifact_edge_valid": True,
        "claim_edges_valid": True,
        "evidence_edges_valid": True,
        "original_audit_valid": True,
    }
    assert report["id"] == artifact_export_integrity_report_id(
        receipt["id"], report["output_directory"], receipt["properties"]["content_hash"], []
    )
    assert validate_artifact_export_integrity_report(report) is report


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda store, receipt, _output_dir: store.nodes.pop(receipt["id"]), "receipt_not_found"),
        (
            lambda store, receipt, _output_dir: store.nodes[receipt["id"]].__setitem__("node_type", "Other"),
            "receipt_wrong_node_type",
        ),
        (
            lambda store, receipt, _output_dir: store.nodes[receipt["id"]]["properties"].__setitem__(
                "source_type", "legacy"
            ),
            "receipt_wrong_source_type",
        ),
        (
            lambda store, receipt, _output_dir: store.nodes[receipt["id"]]["properties"].__setitem__(
                "file_name", "../x.md"
            ),
            "receipt_contract_invalid",
        ),
        (lambda store, _receipt, _output_dir: store.audit_records.clear(), "original_acceptance_audit_missing"),
        (
            lambda store, _receipt, _output_dir: store.audit_records.append(copy.deepcopy(store.audit_records[-1])),
            "original_acceptance_audit_duplicate",
        ),
        (
            lambda store, _receipt, _output_dir: store.audit_records[-1].__setitem__("actor", "other"),
            "original_acceptance_audit_invalid",
        ),
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).unlink(),
            "export_file_missing",
        ),
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).write_text(
                "changed", encoding="utf-8"
            ),
            "export_file_content_mismatch",
        ),
    ],
)
def test_integrity_report_blocks_receipt_audit_and_file_divergences(mutate: Any, code: str, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    mutate(store, receipt, output_dir)

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report["status"] == "blocked"
    assert code in {issue["code"] for issue in report["issues"]}


def test_integrity_separates_original_audit_from_persisted_validation(output_dir: Path) -> None:
    store, artifact, _, receipt = _accepted_export(output_dir)
    store.nodes[artifact["id"]]["properties"]["items"][0]["text"] += " stale"
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    codes = {issue["code"] for issue in report["issues"]}
    assert "receipt_persisted_validation_invalid" in codes
    assert "original_acceptance_audit_invalid" not in codes

    store, artifact, _, receipt = _accepted_export(output_dir / "both")
    store.audit_records[-1]["actor"] = "other"
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir / "both", checked_at=NOW)
    assert "original_acceptance_audit_invalid" in {issue["code"] for issue in report["issues"]}

    store.nodes[artifact["id"]]["properties"]["items"][0]["text"] += " stale"
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir / "both", checked_at=NOW)
    codes = {issue["code"] for issue in report["issues"]}
    assert {"original_acceptance_audit_invalid", "receipt_persisted_validation_invalid"} <= codes


@pytest.mark.parametrize(
    "bad_record",
    [
        None,
        [],
        "invalid",
        {"audit_type": "claim_based_artifact_export_accepted", "metadata": []},
        {"audit_type": "claim_based_artifact_export_accepted"},
    ],
)
def test_malformed_persisted_audits_are_value_errors_and_block_integrity(bad_record: object, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.audit_records.append(bad_record)

    with pytest.raises(ValueError) as exc:
        validate_original_artifact_export_acceptance_audit(store, receipt)

    assert type(exc.value.__cause__) not in {AttributeError, TypeError, KeyError, IndexError}
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    assert report["status"] == "blocked"
    assert "original_acceptance_audit_invalid" in {issue["code"] for issue in report["issues"]}


def test_integrity_preserves_exact_markdown_line_endings(monkeypatch: pytest.MonkeyPatch, output_dir: Path) -> None:
    crlf_content = "line one\r\nline two\r\n"
    monkeypatch.setattr(claim_review, "render_claim_based_artifact_markdown", lambda _artifact: crlf_content)
    store, artifact = _store()
    candidate = _candidate(store, artifact)
    first = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="reviewer", decided_at=DECIDED_AT
    )
    receipt = first["receipt"]
    target = output_dir / receipt["properties"]["file_name"]
    second = accept_claim_based_artifact_export(
        store, candidate, output_directory=output_dir, decision_actor="again", decided_at="2026-01-05T00:00:00Z"
    )

    assert first["created"] is True
    assert first["written"] is True
    assert second["created"] is False
    assert second["written"] is False
    assert target.read_bytes() == crlf_content.encode("utf-8")
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    assert report["status"] == "consistent"
    assert report["checks"]["file_content_matches"] is True

    target.write_text(crlf_content.replace("\r\n", "\n"), encoding="utf-8", newline="")
    with pytest.raises(ValueError, match="content"):
        accept_claim_based_artifact_export(
            store, candidate, output_directory=output_dir, decision_actor="again", decided_at="2026-01-06T00:00:00Z"
        )
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    assert report["status"] == "blocked"
    assert "export_file_content_mismatch" in {issue["code"] for issue in report["issues"]}


@pytest.mark.parametrize(
    ("edge_type", "code"),
    [
        (ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, "artifact_edge_missing"),
        (ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, "claim_edge_missing"),
        (ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, "evidence_edge_missing"),
    ],
)
def test_integrity_report_classifies_missing_edges_as_repairable(edge_type: str, code: str, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [
        edge for edge in store.edges if not (edge["from_node_id"] == receipt["id"] and edge["edge_type"] == edge_type)
    ]

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report["status"] == "repairable"
    assert {issue["code"] for issue in report["issues"]} == {code}


@pytest.mark.parametrize(
    ("edge_type", "code"),
    [
        (ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, "artifact_edge_unexpected"),
        (ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, "claim_edge_unexpected"),
        (ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, "evidence_edge_unexpected"),
    ],
)
def test_integrity_report_blocks_unexpected_export_edges(edge_type: str, code: str, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges.append(
        {
            "id": f"edge:unexpected:{edge_type}",
            "edge_type": edge_type,
            "from_node_id": receipt["id"],
            "to_node_id": "unexpected:1",
            "created_at": NOW,
            "properties": {},
        }
    )
    store.edges.append(
        {
            "id": "edge:ignored",
            "edge_type": "OTHER_NAMESPACE",
            "from_node_id": receipt["id"],
            "to_node_id": "unexpected:1",
            "created_at": NOW,
            "properties": {},
        }
    )

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report["status"] == "blocked"
    assert code in {issue["code"] for issue in report["issues"]}


@pytest.mark.parametrize("bad_target", [None, 123, ""])
def test_integrity_blocks_malformed_official_export_edges(bad_target: object, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges.append(
        {
            "id": f"edge:malformed:{bad_target!r}",
            "edge_type": ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM,
            "from_node_id": receipt["id"],
            "to_node_id": bad_target,
            "created_at": NOW,
            "properties": {},
        }
    )

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report["status"] == "blocked"
    assert "claim_edge_unexpected" in {issue["code"] for issue in report["issues"]}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda report: report["checks"].__setitem__("file_exists", False), "file_exists"),
        (lambda report: report["checks"].__setitem__("original_audit_valid", False), "original_audit_valid"),
    ],
)
def test_consistent_report_rejects_contradictory_checks(mutate: Any, message: str, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    mutate(report)
    with pytest.raises(ValueError, match=message):
        validate_artifact_export_integrity_report(report)


@pytest.mark.parametrize(
    ("prepare", "mutate", "message"),
    [
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).write_text(
                "changed", encoding="utf-8"
            ),
            lambda report: report["checks"].__setitem__("file_content_matches", True),
            "file_content_matches",
        ),
        (
            lambda store, receipt, _output_dir: setattr(
                store,
                "edges",
                [
                    edge
                    for edge in store.edges
                    if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT
                    or edge["from_node_id"] != receipt["id"]
                ],
            ),
            lambda report: report["checks"].__setitem__("artifact_edge_valid", True),
            "artifact_edge_valid",
        ),
        (
            lambda _store, receipt, output_dir: (
                output_dir / ("." + receipt["properties"]["file_name"] + ".tmp")
            ).write_text("tmp", encoding="utf-8"),
            lambda report: report["checks"].__setitem__("temporary_file_exists", False),
            "temporary_file_exists",
        ),
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).unlink(),
            lambda report: report["checks"].__setitem__("file_content_matches", True),
            "file_content_matches",
        ),
    ],
)
def test_report_validator_rejects_issue_check_contradictions(
    prepare: Any, mutate: Any, message: str, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    prepare(store, receipt, output_dir)
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    mutate(report)
    with pytest.raises(ValueError, match=message):
        validate_artifact_export_integrity_report(report)


@pytest.mark.parametrize(
    ("prepare", "missing_code", "message"),
    [
        (
            lambda store, receipt, _output_dir: setattr(
                store,
                "edges",
                [
                    edge
                    for edge in store.edges
                    if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT
                    or edge["from_node_id"] != receipt["id"]
                ],
            ),
            "artifact_edge_missing",
            "artifact_edge_valid",
        ),
        (
            lambda store, receipt, _output_dir: setattr(
                store,
                "edges",
                [
                    edge
                    for edge in store.edges
                    if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM or edge["from_node_id"] != receipt["id"]
                ],
            ),
            "claim_edge_missing",
            "claim_edges_valid",
        ),
        (
            lambda store, receipt, _output_dir: setattr(
                store,
                "edges",
                [
                    edge
                    for edge in store.edges
                    if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE
                    or edge["from_node_id"] != receipt["id"]
                ],
            ),
            "evidence_edge_missing",
            "evidence_edges_valid",
        ),
        (
            lambda _store, receipt, output_dir: (
                output_dir / ("." + receipt["properties"]["file_name"] + ".tmp")
            ).write_text("tmp", encoding="utf-8"),
            "export_temp_file_present",
            "temporary_file_exists",
        ),
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).unlink(),
            "export_file_missing",
            "file_exists",
        ),
        (
            lambda _store, receipt, output_dir: (output_dir / receipt["properties"]["file_name"]).write_text(
                "changed", encoding="utf-8"
            ),
            "export_file_content_mismatch",
            "file_content_matches",
        ),
        (
            lambda store, _receipt, _output_dir: store.audit_records[-1].__setitem__("actor", "other"),
            "original_acceptance_audit_invalid",
            "original_audit_valid",
        ),
        (
            lambda store, receipt, _output_dir: store.nodes[receipt["properties"]["source_artifact_id"]]["properties"][
                "items"
            ][0].__setitem__("text", "stale"),
            "receipt_persisted_validation_invalid",
            "persisted_contract_valid",
        ),
    ],
)
def test_blocked_report_rejects_negative_checks_without_matching_issue(
    prepare: Any, missing_code: str, message: str, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    prepare(store, receipt, output_dir)
    if missing_code != "original_acceptance_audit_invalid":
        store.audit_records[-1]["actor"] = "other"
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    report["issues"] = [issue for issue in report["issues"] if issue["code"] != missing_code]
    _refresh_report_id(report)

    with pytest.raises(ValueError, match=message):
        validate_artifact_export_integrity_report(report)


def test_temporary_file_only_is_repairable(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    tmp = output_dir / ("." + receipt["properties"]["file_name"] + ".tmp")
    tmp.write_text("residual", encoding="utf-8")

    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)

    assert report["status"] == "repairable"
    assert {issue["code"] for issue in report["issues"]} == {"export_temp_file_present"}


def test_repair_candidate_is_deterministic_read_only_and_rejects_non_repairable_reports(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    before = _snapshot(store)

    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    again = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)

    assert candidate == again
    assert _snapshot(store) == before
    assert candidate["issue_codes"] == ["claim_edge_missing"]
    assert candidate["repair_actions"] == ["create_missing_claim_edges"]
    assert candidate["id"] == artifact_export_repair_candidate_id(candidate["report_id"], candidate["repair_actions"])
    assert validate_artifact_export_repair_candidate(candidate) is candidate
    store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"], receipt["properties"]["claim_refs"][0])
    store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"], receipt["properties"]["claim_refs"][1])
    with pytest.raises(ValueError):
        build_artifact_export_repair_candidate(
            store,
            check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW),
            created_at=DRAFT_AT,
        )
    (output_dir / receipt["properties"]["file_name"]).write_text("changed", encoding="utf-8")
    blocked = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    with pytest.raises(ValueError):
        build_artifact_export_repair_candidate(store, blocked, created_at=DRAFT_AT)


def test_repair_candidate_detects_report_tampering_and_staleness(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    tampered = copy.deepcopy(report)
    tampered["issues"][0]["details"]["refs"] = ["artifact:other"]

    with pytest.raises(ValueError, match="stale or tampered"):
        build_artifact_export_repair_candidate(store, tampered, created_at=DRAFT_AT)

    stale = copy.deepcopy(report)
    store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"], receipt["properties"]["source_artifact_id"])
    with pytest.raises(ValueError, match="stale or tampered"):
        build_artifact_export_repair_candidate(store, stale, created_at=DRAFT_AT)


def test_accept_repair_creates_edges_removes_tmp_audits_and_returns_consistent_report(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    tmp = output_dir / ("." + receipt["properties"]["file_name"] + ".tmp")
    tmp.write_text("residual", encoding="utf-8")
    store.edges = [edge for edge in store.edges if not edge["edge_type"].startswith("ARTIFACT_EXPORT_RECEIPT")]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)

    result = accept_artifact_export_repair(
        store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
    )
    final = result["report"]

    assert final["status"] == "consistent"
    assert result["decision"] == "accepted"
    assert result["applied"] is True
    assert not tmp.exists()
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"]) == {
        receipt["properties"]["source_artifact_id"]
    }
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_FOR_CLAIM, receipt["id"]) == set(
        receipt["properties"]["claim_refs"]
    )
    assert _edge_targets(store, ARTIFACT_EXPORT_RECEIPT_SUPPORTED_BY_EVIDENCE, receipt["id"]) == set(
        receipt["properties"]["evidence_refs"]
    )
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "artifact_export_repair_accepted"
    assert audit["metadata"]["applied"] is True
    assert audit["metadata"]["repair_actions"] == candidate["repair_actions"]
    assert audit["metadata"]["temporary_file_removed"] is True
    repair_receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    assert validate_artifact_export_repair_receipt_contract(repair_receipt) is repair_receipt
    assert repair_receipt["node_type"] == "ArtifactExportRepairReceipt"
    assert repair_receipt["properties"]["audit_id"] == audit["id"]
    assert repair_receipt["properties"]["actor"] == "reviewer"
    assert repair_receipt["properties"]["decided_at"] == DECIDED_AT
    assert str(output_dir) not in json.dumps(audit)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda node: node["properties"].__setitem__("actor", "other"),
        lambda node: node["properties"].__setitem__("decided_at", "2027-01-01T00:00:00Z"),
        lambda node: node["properties"].__setitem__("repaired_edge_count", 99),
        lambda node: (
            node["properties"].__setitem__("actor", "other"),
            node["properties"].__setitem__(
                "original_decision_fingerprint",
                stable_hash(
                    [
                        node["properties"]["repair_candidate_id"],
                        node["properties"]["report_id"],
                        node["properties"]["receipt_id"],
                        "other",
                        node["properties"]["decided_at"],
                        node["properties"]["issue_codes"],
                        node["properties"]["repair_actions"],
                        node["properties"]["repaired_edge_count"],
                        node["properties"]["temporary_file_removed"],
                    ]
                ),
            ),
        ),
    ],
)
def test_repair_receipt_is_immutable_for_same_id(mutate: Any, output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    original = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    same = copy.deepcopy(original)
    persisted, created = store.create_node(same)
    assert persisted == original
    assert created is False
    persisted["properties"]["actor"] = "attacker"
    assert store.nodes[original["id"]] == original

    changed = copy.deepcopy(original)
    mutate(changed)
    with pytest.raises(ValueError, match="immutable"):
        store.create_node(changed)
    assert store.nodes[original["id"]] == original


def test_repair_receipt_cannot_be_updated_or_jointly_replaced_through_official_apis(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    audit = store.audit_records[-1]

    with pytest.raises(ValueError, match="immutable"):
        store.update_node(receipt["id"], {"actor": "attacker"})

    changed = copy.deepcopy(receipt)
    changed["properties"]["actor"] = "attacker"
    changed["properties"]["decided_at"] = "2027-01-01T00:00:00Z"
    changed["created_at"] = "2027-01-01T00:00:00Z"
    changed["properties"]["original_decision_fingerprint"] = stable_hash(
        [
            candidate["id"],
            candidate["report_id"],
            candidate["receipt_id"],
            "attacker",
            "2027-01-01T00:00:00Z",
            candidate["issue_codes"],
            candidate["repair_actions"],
            receipt["properties"]["repaired_edge_count"],
            receipt["properties"]["temporary_file_removed"],
        ]
    )
    with pytest.raises(ValueError, match="immutable"):
        store.create_node(changed)

    duplicate = copy.deepcopy(audit)
    duplicate["metadata"]["actor"] = "attacker"
    duplicate["metadata"]["decided_at"] = "2027-01-01T00:00:00Z"
    duplicate["actor"] = "attacker"
    duplicate["created_at"] = "2027-01-01T00:00:00Z"
    _refresh_repair_audit_fingerprint(duplicate, candidate)
    store.audit_records.append(duplicate)
    with pytest.raises(ValueError, match="exactly one"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


def test_persisted_repair_receipt_rejects_duplicate_or_divergent_nodes(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    original = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    duplicate = copy.deepcopy(original)
    duplicate["id"] = "artifact_export_repair_receipt:duplicate"
    store.nodes[duplicate["id"]] = duplicate
    with pytest.raises(ValueError, match="exactly one"):
        validate_persisted_artifact_export_repair_receipt(store, candidate)

    store.nodes.pop(duplicate["id"])
    changed = copy.deepcopy(original)
    changed["properties"]["actor"] = "other"
    store.nodes[original["id"]] = changed
    with pytest.raises(ValueError):
        validate_persisted_artifact_export_repair_receipt(store, candidate)


def test_accept_repair_does_not_audit_success_when_repair_receipt_persistence_fails(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    original_create_node = store.create_node

    def fail_repair_receipt(node: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        if node.get("node_type") == "ArtifactExportRepairReceipt":
            raise OSError("repair receipt unavailable")
        return original_create_node(node)

    monkeypatch.setattr(store, "create_node", fail_repair_receipt)
    with pytest.raises(OSError, match="repair receipt unavailable"):
        accept_artifact_export_repair(
            store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
        )

    assert not any(
        record["audit_type"] == "artifact_export_repair_accepted" and record["metadata"]["applied"] is True
        for record in store.audit_records
    )
    assert artifact_export_repair_receipt_id(candidate["id"]) not in store.nodes
    current = check_artifact_export_integrity(
        store, receipt["id"], output_directory=output_dir, checked_at="2026-01-05T00:00:00Z"
    )
    assert current["status"] == "consistent"
    with pytest.raises(ValueError, match="no previous successful"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="first",
            decided_at=DECIDED_AT,
            verified_at="2026-01-05T00:01:00Z",
        )


def test_accept_repair_recovers_deterministically_after_audit_append_failure(output_dir: Path) -> None:
    class FailingAuditList(list):
        def __init__(self, values: list[dict[str, Any]]) -> None:
            super().__init__(values)
            self.fail_once = True

        def append(self, value: dict[str, Any]) -> None:
            if (
                self.fail_once
                and value.get("audit_type") == "artifact_export_repair_accepted"
                and value.get("metadata", {}).get("applied") is True
            ):
                self.fail_once = False
                raise OSError("audit store unavailable")
            super().append(value)

    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    store.audit_records = FailingAuditList(store.audit_records)

    with pytest.raises(OSError, match="audit store unavailable"):
        accept_artifact_export_repair(
            store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
        )

    repair_receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    assert validate_artifact_export_repair_receipt_contract(repair_receipt) is repair_receipt
    assert not any(
        record["audit_type"] == "artifact_export_repair_accepted" and record["metadata"]["applied"] is True
        for record in store.audit_records
    )
    with pytest.raises(ValueError, match="original actor and decided_at"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )

    result = accept_artifact_export_repair(
        store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-06T00:01:00Z"
    )

    assert result["applied"] is False
    audits = [
        record
        for record in store.audit_records
        if record["audit_type"] == "artifact_export_repair_accepted" and record["metadata"]["applied"] is True
    ]
    assert len(audits) == 1
    assert audits[0]["id"] == repair_receipt["properties"]["audit_id"]


def test_accept_repair_is_idempotent_for_same_candidate(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    first = accept_artifact_export_repair(
        store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
    )
    edge_count = len(store.edges)

    second = accept_artifact_export_repair(
        store,
        candidate,
        decision_actor="second",
        decided_at="2026-01-06T00:00:00Z",
        verified_at="2026-01-06T00:01:00Z",
    )

    assert first["applied"] is True
    assert second["applied"] is False
    assert second["repaired_edge_count"] == 0
    assert second["temporary_file_removed"] is False
    assert len(store.edges) == edge_count
    audits = [record for record in store.audit_records if record["audit_type"] == "artifact_export_repair_accepted"]
    assert [record["metadata"]["applied"] for record in audits] == [True, False]
    assert audits[-1]["metadata"]["actor"] == "second"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda audit, _candidate: audit.__setitem__("target_refs", ["other"]),
        lambda audit, _candidate: audit.__setitem__("actor", "other"),
        lambda audit, _candidate: audit.__setitem__("created_at", "2026-01-07T00:00:00Z"),
        lambda audit, _candidate: audit["metadata"].__setitem__("actor", "other"),
        lambda audit, _candidate: audit["metadata"].__setitem__("decided_at", "2026-01-07T00:00:00Z"),
        lambda audit, _candidate: audit["metadata"].__setitem__("report_id", "other"),
        lambda audit, _candidate: audit["metadata"].__setitem__("repair_candidate_id", "other"),
        lambda audit, _candidate: audit["metadata"].__setitem__("repair_candidate_hash", "other"),
        lambda audit, _candidate: audit["metadata"].__setitem__("receipt_id", "other"),
        lambda audit, _candidate: audit["metadata"].__setitem__("issue_codes", []),
        lambda audit, _candidate: audit["metadata"].__setitem__("repair_actions", ["remove_stale_temp_file"]),
        lambda audit, _candidate: audit["metadata"].__setitem__("initial_status", "consistent"),
        lambda audit, _candidate: audit["metadata"].__setitem__("final_status", "repairable"),
        lambda audit, _candidate: audit["metadata"].__setitem__("applied", False),
        lambda audit, _candidate: audit["metadata"].__setitem__("repaired_edge_count", -1),
        lambda audit, _candidate: audit["metadata"].__setitem__("temporary_file_removed", "yes"),
    ],
)
def test_idempotent_repair_validates_original_acceptance_audit_contract(mutate: Any, output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    mutate(audit, candidate)
    _refresh_audit_id(store, audit)

    with pytest.raises(ValueError):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


def test_idempotent_repair_validates_original_acceptance_audit_id(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    store.audit_records[-1]["id"] = "audit:bad"

    with pytest.raises(ValueError, match="audit id"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


def test_repair_acceptance_audit_requires_original_applied_success(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    original = copy.deepcopy(store.audit_records[-1])
    store.audit_records = [
        record for record in store.audit_records if record.get("audit_type") != "artifact_export_repair_accepted"
    ]
    with pytest.raises(ValueError, match="no previous successful"):
        validate_artifact_export_repair_acceptance_audit(store, candidate)

    store.audit_records.append(original)
    duplicate = copy.deepcopy(original)
    store.audit_records.append(duplicate)
    with pytest.raises(ValueError, match="exactly one"):
        validate_artifact_export_repair_acceptance_audit(store, candidate)


def test_repair_acceptance_audit_validation_is_independent_from_audit_order(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    reordered = copy.deepcopy(store)
    reordered.audit_records = list(reversed(reordered.audit_records))

    audit = validate_artifact_export_repair_acceptance_audit(reordered, candidate)

    assert len(store.audit_records) > 1
    assert audit["id"] == receipt["properties"]["audit_id"]


def test_repair_acceptance_audit_ignores_later_idempotent_audits(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    accept_artifact_export_repair(
        store,
        candidate,
        decision_actor="second",
        decided_at="2026-01-06T00:00:00Z",
        verified_at="2026-01-06T00:01:00Z",
    )
    accept_artifact_export_repair(
        store,
        candidate,
        decision_actor="third",
        decided_at="2026-01-07T00:00:00Z",
        verified_at="2026-01-07T00:01:00Z",
    )

    audit = validate_artifact_export_repair_acceptance_audit(store, candidate)
    assert audit["metadata"]["applied"] is True
    assert [
        record["metadata"]["applied"]
        for record in store.audit_records
        if record["audit_type"] == "artifact_export_repair_accepted"
    ] == [True, False, False]


def test_repair_acceptance_audit_rejects_top_actor_different_from_metadata_actor(output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    audit["actor"] = "other"
    _refresh_audit_id(store, audit)

    with pytest.raises(ValueError, match="does not match"):
        validate_artifact_export_repair_acceptance_audit(store, candidate)


def test_idempotent_repair_rejects_joint_actor_timestamp_tampering_after_audit_id_recalculation(
    output_dir: Path,
) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    audit["actor"] = "attacker"
    audit["metadata"]["actor"] = "attacker"
    audit["created_at"] = "2027-01-01T00:00:00Z"
    audit["metadata"]["decided_at"] = "2027-01-01T00:00:00Z"
    _refresh_repair_audit_fingerprint(audit, candidate)
    _refresh_audit_id(store, audit)

    with pytest.raises(ValueError, match="does not match"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


def test_idempotent_repair_rejects_joint_decision_field_tampering_after_audit_id_recalculation(
    output_dir: Path,
) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    audit["target_refs"] = [candidate["receipt_id"], candidate["report_id"], candidate["id"]]
    audit["actor"] = "attacker"
    audit["created_at"] = "2027-01-01T00:00:00Z"
    audit["metadata"].update(
        {
            "actor": "attacker",
            "decided_at": "2027-01-01T00:00:00Z",
            "report_id": candidate["report_id"],
            "repair_candidate_id": candidate["id"],
            "receipt_id": candidate["receipt_id"],
            "issue_codes": candidate["issue_codes"],
            "repair_actions": candidate["repair_actions"],
            "repaired_edge_count": 2,
            "temporary_file_removed": False,
        }
    )
    _refresh_repair_audit_fingerprint(audit, candidate)
    _refresh_audit_id(store, audit)

    with pytest.raises(ValueError, match="does not match|repaired_edge_count"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, [], {}])
def test_repair_acceptance_audit_rejects_non_strict_repaired_edge_count(value: object, output_dir: Path) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    audit["metadata"]["repaired_edge_count"] = value
    receipt["properties"]["repaired_edge_count"] = value
    _refresh_repair_audit_fingerprint(audit, candidate)
    _refresh_audit_id(store, audit)
    receipt["properties"]["audit_id"] = audit["id"]
    receipt["properties"]["original_decision_fingerprint"] = audit["metadata"]["original_decision_fingerprint"]

    with pytest.raises(ValueError, match="repaired_edge_count"):
        validate_artifact_export_repair_acceptance_audit(store, candidate)


@pytest.mark.parametrize("value", [0, 1, 2])
def test_repair_acceptance_audit_accepts_strict_integer_repaired_edge_count_when_mutation_exists(
    value: int, output_dir: Path
) -> None:
    store, _, candidate = _accepted_repair(output_dir)
    audit = store.audit_records[-1]
    receipt = store.nodes[artifact_export_repair_receipt_id(candidate["id"])]
    audit["metadata"]["repaired_edge_count"] = value
    audit["metadata"]["temporary_file_removed"] = value == 0
    _refresh_repair_audit_fingerprint(audit, candidate)
    _refresh_audit_id(store, audit)
    receipt["properties"]["repaired_edge_count"] = value
    receipt["properties"]["temporary_file_removed"] = value == 0
    receipt["properties"]["audit_id"] = audit["id"]
    receipt["properties"]["original_decision_fingerprint"] = audit["metadata"]["original_decision_fingerprint"]

    assert validate_artifact_export_repair_acceptance_audit(store, candidate) is audit


def test_idempotent_repair_rejects_diverged_file_or_bad_previous_audit(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    accept_artifact_export_repair(
        store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
    )
    (output_dir / receipt["properties"]["file_name"]).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )

    store, _, _, receipt = _accepted_export(output_dir / "audit")
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(
        store, receipt["id"], output_directory=output_dir / "audit", checked_at=NOW
    )
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    accept_artifact_export_repair(
        store, candidate, decision_actor="first", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
    )
    store.audit_records[-1]["metadata"]["repair_candidate_hash"] = "bad"
    with pytest.raises(ValueError, match="previous repair acceptance audit"):
        accept_artifact_export_repair(
            store,
            candidate,
            decision_actor="second",
            decided_at="2026-01-06T00:00:00Z",
            verified_at="2026-01-06T00:01:00Z",
        )


def test_consistent_state_without_previous_repair_audit_does_not_fabricate_idempotent_success(
    output_dir: Path,
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    store.create_edge(ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT, receipt["id"], receipt["properties"]["source_artifact_id"])

    with pytest.raises(ValueError, match="no previous successful"):
        accept_artifact_export_repair(
            store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
        )


def test_accept_repair_is_restartable_and_does_not_audit_on_failure(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if edge["edge_type"] != ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    audit_count = len(store.audit_records)

    def fail_create_edge(*args: object, **kwargs: object) -> None:
        raise OSError("edge store unavailable")

    monkeypatch.setattr(store, "create_edge", fail_create_edge)
    with pytest.raises(OSError):
        accept_artifact_export_repair(
            store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
        )

    assert len(store.audit_records) == audit_count


def test_partial_repair_failure_can_resume_with_new_candidate(
    monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    store.edges = [edge for edge in store.edges if not edge["edge_type"].startswith("ARTIFACT_EXPORT_RECEIPT")]
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    original_create_edge = store.create_edge
    calls = 0

    def fail_second(edge_type: str, from_node_id: str, to_node_id: str, **properties: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("second edge failed")
        original_create_edge(edge_type, from_node_id, to_node_id, **properties)

    monkeypatch.setattr(store, "create_edge", fail_second)
    with pytest.raises(OSError, match="second edge failed"):
        accept_artifact_export_repair(
            store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, verified_at="2026-01-05T00:00:00Z"
        )
    assert not any(record["audit_type"] == "artifact_export_repair_accepted" for record in store.audit_records)

    monkeypatch.setattr(store, "create_edge", original_create_edge)
    current = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    assert current["status"] == "repairable"
    assert "artifact_edge_missing" not in {issue["code"] for issue in current["issues"]}
    resumed = build_artifact_export_repair_candidate(store, current, created_at="2026-01-06T00:00:00Z")
    result = accept_artifact_export_repair(
        store,
        resumed,
        decision_actor="reviewer",
        decided_at="2026-01-06T00:01:00Z",
        verified_at="2026-01-06T00:02:00Z",
    )
    assert result["report"]["status"] == "consistent"


def test_reject_repair_only_audits_and_preserves_reason(output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    tmp = output_dir / ("." + receipt["properties"]["file_name"] + ".tmp")
    tmp.write_text("residual", encoding="utf-8")
    report = check_artifact_export_integrity(store, receipt["id"], output_directory=output_dir, checked_at=NOW)
    candidate = build_artifact_export_repair_candidate(store, report, created_at=DRAFT_AT)
    before = _snapshot(store)

    result = reject_artifact_export_repair(
        store, candidate, decision_actor="reviewer", decided_at=DECIDED_AT, reason="manual review"
    )

    assert result["decision"] == "rejected"
    assert result["reason"] == "manual review"
    assert tmp.exists()
    assert json.loads(_snapshot(store))["nodes"] == json.loads(before)["nodes"]
    assert json.loads(_snapshot(store))["edges"] == json.loads(before)["edges"]
    audit = store.audit_records[-1]
    assert audit["audit_type"] == "artifact_export_repair_rejected"
    assert audit["metadata"]["reason"] == "manual review"
    assert str(output_dir) not in json.dumps(audit)


@pytest.mark.parametrize("checked_at", ["2026-01-02T03:04:05", "bad", 123])
def test_integrity_and_repair_reject_invalid_timestamps(checked_at: object, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    with pytest.raises(ValueError):
        check_artifact_export_integrity(
            store,
            receipt["id"],
            output_directory=output_dir,
            checked_at=checked_at,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("output_directory", [None, 123, Path("tests/.does-not-exist")])
def test_integrity_rejects_invalid_output_directory(output_directory: object, output_dir: Path) -> None:
    store, _, _, receipt = _accepted_export(output_dir)
    with pytest.raises(ValueError):
        check_artifact_export_integrity(
            store,
            receipt["id"],
            output_directory=output_directory,  # type: ignore[arg-type]
            checked_at=NOW,
        )


def _edge_targets(store: JsonGraphStorage, edge_type: str, from_node_id: str) -> set[str]:
    return {
        edge["to_node_id"]
        for edge in store.edges
        if edge["edge_type"] == edge_type and edge["from_node_id"] == from_node_id
    }
