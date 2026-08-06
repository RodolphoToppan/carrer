from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from carrer.artifacts import (
    PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM,
    PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE,
    accept_claim_based_artifact,
    build_artifact_from_career_claims,
    generate_resume_draft,
)
from carrer.claims import (
    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
    CAREER_CLAIM_FROM_CONTRIBUTION,
    CAREER_CLAIM_SUPPORTED_BY_EVIDENCE,
    accept_career_claim_candidate,
    generate_career_claim_candidates,
)
from carrer.contributions import (
    accept_contribution_analysis,
    analyze_contribution,
    create_contribution,
    promote_contribution_candidate,
)
from carrer.contributions.analysis_review import (
    CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION,
    CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE,
)
from carrer.contributions.candidates import contribution_candidate
from carrer.contributions.service import CONTRIBUTION_SUPPORTED_BY_EVIDENCE
from carrer.domain.hashing import stable_hash
from carrer.domain.models import evidence_node, knowledge_node
from carrer.integrity import (
    graph_integrity_report_id,
    validate_graph_integrity,
    validate_graph_integrity_report,
)
from carrer.integrity.graph import ISSUE_CODES, ISSUE_CONTRACTS
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"
HASH = "a" * 64
OTHER_HASH = "b" * 64


class SensitiveNonJsonValue:
    def __repr__(self) -> str:
        return f"<SensitiveNonJsonValue SECRET at {id(self)}>"


def _node(node_id: str, node_type: str = "EvidenceNode") -> dict[str, Any]:
    properties: dict[str, Any] = {}
    if node_type == "Contribution":
        properties = {
            "title": "Safe title",
            "summary": "",
            "status": "draft",
            "privacy_level": "artifact_safe",
            "confidence": "medium",
            "evidence_refs": ["evidence:a"],
            "observation_refs": [],
            "knowledge_refs": [],
            "source_refs": [],
            "started_at": None,
            "ended_at": None,
            "metadata": {},
        }
    return {"id": node_id, "node_type": node_type, "created_at": NOW, "properties": properties}


def _edge(
    edge_type: str = CONTRIBUTION_SUPPORTED_BY_EVIDENCE,
    source: str = "contribution:a",
    target: str = "evidence:a",
) -> dict[str, Any]:
    return {
        "id": f"edge:{edge_type}:{source}:{target}",
        "edge_type": edge_type,
        "from_node_id": source,
        "to_node_id": target,
        "created_at": NOW,
        "properties": {},
    }


def _audit(*refs: str) -> dict[str, Any]:
    return {
        "id": "audit:1",
        "audit_type": "reviewed",
        "created_at": NOW,
        "actor": "system",
        "target_refs": list(refs),
        "result": "accepted",
        "metadata": {},
    }


def _store() -> JsonGraphStorage:
    store = JsonGraphStorage()
    store.nodes = {
        "contribution:a": _node("contribution:a", "Contribution"),
        "evidence:a": _node("evidence:a"),
    }
    store.edges = [_edge()]
    store.audit_records = [_audit("contribution:a", "evidence:a")]
    return store


def _real_evidence(entity_id: str = "C-1", *, privacy_level: str = "artifact_safe") -> dict[str, Any]:
    return evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id=entity_id,
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        occurred_at=NOW,
        privacy_level=privacy_level,
        metadata={"repository": "repo"},
    )


def _analysis_store(evidence_count: int = 1) -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = [_real_evidence(f"C-{index}") for index in range(evidence_count)]
    for node in evidence:
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=NOW,
        title="Feature delivery",
        evidence_refs=[node["id"] for node in evidence],
        actions=["implemented change"],
        outcomes=["change delivered"],
    )["contribution"]
    analysis = analyze_contribution(store, contribution["id"])
    accepted = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    return store, contribution, accepted


def _claim_store(evidence_count: int = 1) -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any], dict[str, Any]]:
    store, contribution, analysis = _analysis_store(evidence_count)
    candidate = generate_career_claim_candidates(store, analysis["id"])[0]
    claim = accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
    return store, contribution, analysis, claim


def _claim_artifact_store(evidence_count: int = 1) -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store, _, _, claim = _claim_store(evidence_count)
    draft = build_artifact_from_career_claims(
        store,
        claim_ids=[claim["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    artifact = accept_claim_based_artifact(store, draft, decision_actor="human", decided_at=NOW)["artifact"]
    _canonicalize_audit_target_refs(store)
    return store, claim, artifact


def _legacy_artifact_store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = _real_evidence()
    store.create_node(evidence)
    knowledge = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Practical experience with Python.",
        created_at=NOW,
        evidence_refs=[evidence["id"]],
        status="accepted",
        privacy_level="artifact_safe",
        confidence="high",
    )
    store.create_node(knowledge)
    artifact = generate_resume_draft(store)
    _canonicalize_audit_target_refs(store)
    return store, knowledge, artifact


def _canonicalize_audit_target_refs(store: JsonGraphStorage) -> None:
    for audit in store.audit_records:
        audit["target_refs"] = sorted(set(audit["target_refs"]))


def _professional_artifact_issue_stores() -> list[JsonGraphStorage]:
    stores: list[JsonGraphStorage] = []
    store, _, artifact = _claim_artifact_store()
    artifact["id"] = "artifact:" + "b" * 64
    stores.append(store)

    for field, value in (
        ("status", "draft"),
        ("privacy_level", "private"),
        ("artifact_type", "unsupported"),
        ("source_type", []),
        ("claim_refs", [object()]),
        ("evidence_refs", [object()]),
        ("review_actor", SensitiveNonJsonValue()),
        ("claim_refs", ["career_claim:" + "c" * 64]),
        ("evidence_refs", ["evidence:" + "c" * 64]),
        ("evidence_refs", []),
    ):
        store, _, artifact = _claim_artifact_store()
        artifact["properties"][field] = value
        stores.append(store)

    store, _, artifact = _claim_artifact_store()
    store.nodes["career_claim:" + "c" * 64] = dict(
        _node("career_claim:" + "c" * 64, "ArtifactExportReceipt"),
        properties={},
    )
    artifact["properties"]["claim_refs"] = ["career_claim:" + "c" * 64]
    stores.append(store)

    store, claim, _ = _claim_artifact_store()
    claim["properties"]["status"] = "rejected"
    stores.append(store)

    store, claim, _ = _claim_artifact_store()
    claim["properties"]["privacy_level"] = "internal"
    stores.append(store)

    store, _, _ = _claim_artifact_store()
    store.edges = [edge for edge in store.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM]
    stores.append(store)

    store, _, artifact = _claim_artifact_store()
    store.create_edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, artifact["id"], "career_claim:" + "c" * 64)
    stores.append(store)

    store, _, artifact = _claim_artifact_store()
    store.nodes["evidence:" + "c" * 64] = dict(_node("evidence:" + "c" * 64, "ArtifactExportReceipt"), properties={})
    artifact["properties"]["evidence_refs"] = ["evidence:" + "c" * 64]
    stores.append(store)

    store, _, _ = _claim_artifact_store()
    store.edges = [edge for edge in store.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE]
    stores.append(store)

    for value in ([object()], ["knowledge:" + "c" * 64], []):
        store, _, artifact = _legacy_artifact_store()
        artifact["properties"]["knowledge_refs"] = value
        stores.append(store)

    store, _, artifact = _legacy_artifact_store()
    store.nodes["knowledge:" + "c" * 64] = dict(
        _node("knowledge:" + "c" * 64, "ArtifactExportReceipt"),
        properties={},
    )
    artifact["properties"]["knowledge_refs"] = ["knowledge:" + "c" * 64]
    stores.append(store)

    store, _, _ = _legacy_artifact_store()
    store.edges = [edge for edge in store.edges if edge.get("edge_type") != "ARTIFACT_GENERATED_FROM_KNOWLEDGE"]
    stores.append(store)
    return stores


def _api_contribution_store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = _real_evidence("C-1")
    store.create_node(evidence)
    contribution = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=NOW,
        title="Safe contribution",
        evidence_refs=[evidence["id"]],
    )["contribution"]
    return store, contribution, evidence


def _codes(report: dict[str, Any]) -> list[str]:
    return [issue["code"] for issue in report["issues"]]


def _snapshot(store: JsonGraphStorage) -> dict[str, Any]:
    return copy.deepcopy({"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records})


def _report_ids(store: JsonGraphStorage) -> tuple[str, str]:
    report = validate_graph_integrity(store)
    return report["snapshot"]["id"], report["id"]


def _issue_for(report: dict[str, Any], code: str) -> dict[str, Any]:
    return next(issue for issue in report["issues"] if issue["code"] == code)


def _refresh_issue_id(issue: dict[str, Any]) -> None:
    issue["id"] = "graph_integrity_issue:" + stable_hash(
        {
            key: issue.get(key)
            for key in ("code", "severity", "subject_type", "subject_ref", "path", "related_refs", "metadata")
        }
    )


def _refresh_report_id(report: dict[str, Any]) -> None:
    report["id"] = graph_integrity_report_id(report)


def _refresh_after_issue_tamper(report: dict[str, Any]) -> None:
    for issue in report["issues"]:
        _refresh_issue_id(issue)
    report["issues"] = sorted(
        report["issues"],
        key=lambda issue: (
            issue["severity"],
            issue["code"],
            issue["subject_type"],
            issue["subject_ref"],
            issue["path"],
            issue["related_refs"],
            issue["id"],
        ),
    )
    report["summary"]["issue_count"] = len(report["issues"])
    report["summary"]["error_count"] = sum(issue["severity"] == "error" for issue in report["issues"])
    report["summary"]["warning_count"] = sum(issue["severity"] == "warning" for issue in report["issues"])
    report["status"] = "invalid" if report["summary"]["error_count"] else "valid"
    _refresh_report_id(report)


def test_empty_store_is_valid_and_json_serializable() -> None:
    report = validate_graph_integrity(JsonGraphStorage())

    assert report["status"] == "valid"
    assert report["summary"] == {
        "node_count": 0,
        "edge_count": 0,
        "audit_record_count": 0,
        "issue_count": 0,
        "error_count": 0,
        "warning_count": 0,
    }
    assert json.loads(json.dumps(report)) == report
    assert validate_graph_integrity_report(report) is report


def test_valid_store_has_no_issues_and_repeated_calls_are_deterministic() -> None:
    store = _store()

    first = validate_graph_integrity(store)
    second = validate_graph_integrity(store)

    assert first == second
    assert first["status"] == "valid"
    assert first["issues"] == []
    assert first["id"] == graph_integrity_report_id(first)
    assert first["snapshot"] == {
        "id": first["snapshot"]["id"],
        "node_count": 2,
        "edge_count": 1,
        "audit_record_count": 1,
    }
    assert first["snapshot"]["id"].startswith("graph_snapshot:")
    assert validate_graph_integrity_report(first) is first


def test_node_edge_and_audit_order_do_not_change_report() -> None:
    first = _store()
    second = JsonGraphStorage()
    second.nodes = dict(reversed(list(first.nodes.items())))
    second.edges = [copy.deepcopy(_edge("OTHER", "contribution:a", "evidence:a")), copy.deepcopy(first.edges[0])]
    first.edges.append(copy.deepcopy(second.edges[0]))
    second.audit_records = [copy.deepcopy(_audit("evidence:a")), copy.deepcopy(first.audit_records[0])]
    first.audit_records.append(copy.deepcopy(second.audit_records[0]))

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_snapshot_and_report_id_change_for_structural_changes_with_same_counts() -> None:
    first = _store()
    second = _store()
    second.nodes["evidence:a"]["properties"]["marker"] = "different"

    assert first.nodes.keys() == second.nodes.keys()
    assert len(first.edges) == len(second.edges)
    assert len(first.audit_records) == len(second.audit_records)
    assert _report_ids(first) != _report_ids(second)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda store: store.nodes["evidence:a"]["properties"].__setitem__("marker", "changed"),
        lambda store: store.edges[0].__setitem__("edge_type", "SUPPORTS_CHANGED"),
        lambda store: store.audit_records[0].__setitem__("result", "rejected"),
    ],
)
def test_snapshot_and_report_id_change_when_one_valid_record_changes(mutate: Any) -> None:
    store = _store()
    before = _report_ids(store)

    mutate(store)

    assert _report_ids(store) != before


def test_reordering_each_store_section_preserves_snapshot_and_report() -> None:
    first = _store()
    first.nodes["artifact:a"] = _node("artifact:a", "ProfessionalArtifact")
    first.edges.append(_edge("OTHER", "artifact:a", "evidence:a"))
    first.audit_records.append(_audit("artifact:a"))
    first.audit_records[1]["id"] = "audit:2"
    second = JsonGraphStorage()
    second.nodes = dict(reversed(list(first.nodes.items())))
    second.edges = list(reversed(copy.deepcopy(first.edges)))
    second.audit_records = list(reversed(copy.deepcopy(first.audit_records)))

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda store: store.nodes["evidence:a"].__setitem__("id", "evidence:b"), "NODE_KEY_ID_MISMATCH"),
        (lambda store: store.nodes.__setitem__("bad", []), "NODE_NOT_OBJECT"),
        (lambda store: store.nodes["evidence:a"].__setitem__("id", ""), "NODE_ID_INVALID"),
        (lambda store: store.nodes["evidence:a"].__setitem__("node_type", ""), "NODE_TYPE_INVALID"),
        (lambda store: store.nodes["evidence:a"].__setitem__("created_at", "bad"), "NODE_CREATED_AT_INVALID"),
        (lambda store: store.nodes["evidence:a"].__setitem__("properties", []), "NODE_PROPERTIES_INVALID"),
        (lambda store: store.edges.__setitem__(0, []), "EDGE_NOT_OBJECT"),
        (lambda store: store.edges[0].__setitem__("edge_type", ""), "EDGE_TYPE_INVALID"),
        (lambda store: store.edges[0].__setitem__("from_node_id", ""), "EDGE_SOURCE_REF_INVALID"),
        (lambda store: store.edges[0].__setitem__("to_node_id", ""), "EDGE_TARGET_REF_INVALID"),
        (lambda store: store.edges[0].__setitem__("from_node_id", "evidence:missing"), "EDGE_SOURCE_NOT_FOUND"),
        (lambda store: store.edges[0].__setitem__("to_node_id", "contribution:missing"), "EDGE_TARGET_NOT_FOUND"),
        (lambda store: store.audit_records.__setitem__(0, []), "AUDIT_RECORD_NOT_OBJECT"),
        (lambda store: store.audit_records[0].__setitem__("audit_type", ""), "AUDIT_TYPE_INVALID"),
        (lambda store: store.audit_records[0].__setitem__("created_at", "bad"), "AUDIT_CREATED_AT_INVALID"),
        (lambda store: store.audit_records[0].__setitem__("target_refs", [None]), "AUDIT_TARGET_REFS_INVALID"),
        (lambda store: store.audit_records[0].__setitem__("result", ""), "AUDIT_RESULT_INVALID"),
        (lambda store: store.audit_records[0].__setitem__("metadata", []), "AUDIT_METADATA_INVALID"),
    ],
)
def test_structural_issues(mutate: Any, code: str) -> None:
    store = _store()
    mutate(store)

    assert code in _codes(validate_graph_integrity(store))


def test_duplicate_edge_is_a_warning_without_repairing_store() -> None:
    store = _store()
    store.edges.append(copy.deepcopy(store.edges[0]) | {"id": "edge:duplicate-physical-id"})
    before = _snapshot(store)

    report = validate_graph_integrity(store)

    assert "DUPLICATE_EDGE" in _codes(report)
    assert report["status"] == "valid"
    assert _snapshot(store) == before


def test_valid_contribution_from_creation_api_has_no_semantic_issues() -> None:
    store, _, _ = _api_contribution_store()

    report = validate_graph_integrity(store)

    assert [code for code in _codes(report) if code.startswith("CONTRIBUTION_")] == []
    assert validate_graph_integrity_report(report) is report


def test_contribution_invalid_properties_are_reported_without_cascade() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["title"] = ""
    contribution["properties"]["summary"] = ""

    report = validate_graph_integrity(store)

    assert _codes(report).count("CONTRIBUTION_PROPERTIES_INVALID") == 1
    assert "CONTRIBUTION_PROVENANCE_REFS_INVALID" not in _codes(report)


def test_contribution_invalid_status_and_privacy_are_specific() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["status"] = "done"
    contribution["properties"]["privacy_level"] = "public"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert "CONTRIBUTION_PRIVACY_INVALID" in codes


@pytest.mark.parametrize("refs", [[{}], [[]], [f"evidence:{HASH}", object()], ["   "]])
def test_contribution_arbitrary_evidence_refs_are_safe_provenance_issues(refs: list[Any]) -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["evidence_refs"] = refs
    before_edges = copy.deepcopy(store.edges)
    before_audit_records = copy.deepcopy(store.audit_records)

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)
    codes = _codes(report)

    assert "CONTRIBUTION_PROVENANCE_REFS_INVALID" in codes
    assert "CONTRIBUTION_EVIDENCE_NOT_FOUND" not in codes
    assert "CONTRIBUTION_EVIDENCE_TYPE_INVALID" not in codes
    assert "CONTRIBUTION_EVIDENCE_EDGE_MISSING" not in codes
    assert "object at" not in report_json
    assert "builtins.object" not in report_json
    assert validate_graph_integrity_report(report) is report
    assert contribution["properties"]["evidence_refs"] == refs
    assert store.edges == before_edges
    assert store.audit_records == before_audit_records


def test_contribution_arbitrary_non_evidence_provenance_refs_do_not_crash() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"].update(
        observation_refs=[{}],
        knowledge_refs=[[]],
        source_refs=[SensitiveNonJsonValue()],
    )

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)

    assert _codes(report).count("CONTRIBUTION_PROVENANCE_REFS_INVALID") == 3
    assert "SensitiveNonJsonValue SECRET" not in report_json
    assert validate_graph_integrity_report(report) is report


def test_contribution_specific_failure_with_residual_error_reports_both() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["status"] = "done"
    contribution["properties"]["confidence"] = "certain"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert "CONTRIBUTION_PROPERTIES_INVALID" in codes


@pytest.mark.parametrize(
    "mutate",
    [
        lambda props: props.__setitem__("status", "done"),
        lambda props: props.__setitem__("privacy_level", "public"),
        lambda props: props.__setitem__("evidence_refs", [object()]),
    ],
)
def test_contribution_single_specific_failure_does_not_emit_redundant_properties_issue(mutate: Any) -> None:
    store, contribution, _ = _api_contribution_store()
    mutate(contribution["properties"])

    codes = _codes(validate_graph_integrity(store))

    assert any(
        code in codes
        for code in (
            "CONTRIBUTION_STATUS_INVALID",
            "CONTRIBUTION_PRIVACY_INVALID",
            "CONTRIBUTION_PROVENANCE_REFS_INVALID",
        )
    )
    assert "CONTRIBUTION_PROPERTIES_INVALID" not in codes


def test_contribution_evidence_ref_missing_node() -> None:
    store, contribution, _ = _api_contribution_store()
    missing = f"evidence:{HASH}"
    contribution["properties"]["evidence_refs"] = [missing]
    store.edges = []

    issue = _issue_for(validate_graph_integrity(store), "CONTRIBUTION_EVIDENCE_NOT_FOUND")

    assert issue["path"] == f"nodes.{issue['subject_ref']}.properties.evidence_refs"
    assert issue["related_refs"] == [missing]


def test_contribution_evidence_ref_wrong_node_type() -> None:
    store, contribution, _ = _api_contribution_store()
    wrong = f"knowledge:{HASH}"
    store.nodes[wrong] = _node(wrong, "KnowledgeNode")
    contribution["properties"]["evidence_refs"] = [wrong]
    store.edges = [_edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], wrong)]

    issue = _issue_for(validate_graph_integrity(store), "CONTRIBUTION_EVIDENCE_TYPE_INVALID")

    assert issue["related_refs"] == [wrong]


def test_contribution_declared_evidence_without_edge() -> None:
    store, _, evidence = _api_contribution_store()
    store.edges = []

    issue = _issue_for(validate_graph_integrity(store), "CONTRIBUTION_EVIDENCE_EDGE_MISSING")

    assert issue["related_refs"] == [evidence["id"]]


def test_contribution_evidence_edge_to_undeclared_evidence() -> None:
    store, contribution, _ = _api_contribution_store()
    extra = _real_evidence("C-2")
    store.create_node(extra)
    store.create_edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], extra["id"])

    issue = _issue_for(validate_graph_integrity(store), "CONTRIBUTION_EVIDENCE_EDGE_UNDECLARED")

    assert issue["severity"] == "warning"
    assert issue["related_refs"] == [extra["id"]]


def test_contribution_multiple_valid_evidence_refs_have_no_semantic_issues() -> None:
    store = JsonGraphStorage()
    first = _real_evidence("C-1")
    second = _real_evidence("C-2")
    store.create_node(first)
    store.create_node(second)
    create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=NOW,
        title="Two evidences",
        evidence_refs=sorted([second["id"], first["id"]]),
    )

    assert [code for code in _codes(validate_graph_integrity(store)) if code.startswith("CONTRIBUTION_")] == []


def test_contribution_semantic_rules_are_read_only_deterministic_and_respect_filters() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["status"] = "done"
    contribution["properties"]["title"] = "SECRET title"
    before = _snapshot(store)

    skipped = validate_graph_integrity(store, node_types=["EvidenceNode"])
    selected = validate_graph_integrity(store, node_types=["Contribution"])
    warnings = validate_graph_integrity(store, severities=["warning"])
    reordered = JsonGraphStorage()
    reordered.nodes = dict(reversed(list(copy.deepcopy(store.nodes).items())))
    reordered.edges = list(reversed(copy.deepcopy(store.edges)))
    reordered.audit_records = list(reversed(copy.deepcopy(store.audit_records)))

    assert "CONTRIBUTION_STATUS_INVALID" not in _codes(skipped)
    assert "CONTRIBUTION_STATUS_INVALID" in _codes(selected)
    assert all(issue["severity"] == "warning" for issue in warnings["issues"])
    assert validate_graph_integrity(store) == validate_graph_integrity(reordered)
    assert _snapshot(store) == before
    assert "SECRET title" not in json.dumps(selected, sort_keys=True)


def test_promoted_contribution_candidate_has_no_semantic_issues() -> None:
    store = JsonGraphStorage()
    first = _real_evidence("C-1")
    second = _real_evidence("C-2")
    store.create_node(first)
    store.create_node(second)
    candidate = contribution_candidate(
        candidate_type="feature_delivery",
        title="Promoted candidate",
        evidence_refs=[first["id"], second["id"]],
        confidence="medium",
        reasons=["shared_branch"],
    )

    promote_contribution_candidate(
        store,
        candidate,
        created_at=NOW,
        decision_actor="human",
        contribution_type="feature_delivery",
        title="Promoted candidate",
    )

    assert [code for code in _codes(validate_graph_integrity(store)) if code.startswith("CONTRIBUTION_")] == []


def test_persisted_contribution_analysis_created_by_current_apis_has_no_issues() -> None:
    store, _, _ = _analysis_store(evidence_count=2)

    assert all(not code.startswith("CONTRIBUTION_ANALYSIS_") for code in _codes(validate_graph_integrity(store)))


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda store, analysis: store.nodes[analysis["id"]].__setitem__("properties", []),
            "NODE_PROPERTIES_INVALID",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__("status", "rejected"),
            "CONTRIBUTION_ANALYSIS_STATUS_INVALID",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__("privacy_level", "public"),
            "CONTRIBUTION_ANALYSIS_PRIVACY_INVALID",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__("contribution_ref", []),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_REF_INVALID",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__(
                "contribution_ref", "customer:SECRET contribution"
            ),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_NOT_FOUND",
        ),
        (
            lambda store, analysis: store.nodes.pop(analysis["properties"]["contribution_ref"]),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_NOT_FOUND",
        ),
        (
            lambda store, analysis: store.nodes[analysis["properties"]["contribution_ref"]].__setitem__(
                "node_type", "EvidenceNode"
            ),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_TYPE_INVALID",
        ),
        (
            lambda store, _analysis: store.edges.__setitem__(
                slice(None),
                [edge for edge in store.edges if edge["edge_type"] != CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION],
            ),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_MISSING",
        ),
        (
            lambda store, analysis: store.edges.append(
                _edge(
                    CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION,
                    analysis["id"],
                    "contribution:" + stable_hash("undeclared contribution"),
                )
            ),
            "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_UNDECLARED",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__("evidence_refs", [""]),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, analysis: store.nodes[analysis["id"]]["properties"].__setitem__(
                "evidence_refs", [SensitiveNonJsonValue()]
            ),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, analysis: store.nodes.pop(analysis["properties"]["evidence_refs"][0]),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_NOT_FOUND",
        ),
        (
            lambda store, analysis: store.nodes[analysis["properties"]["evidence_refs"][0]].__setitem__(
                "node_type", "Contribution"
            ),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_TYPE_INVALID",
        ),
        (
            lambda store, _analysis: store.edges.__setitem__(
                slice(None),
                [edge for edge in store.edges if edge["edge_type"] != CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE],
            ),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_MISSING",
        ),
        (
            lambda store, analysis: store.edges.append(
                _edge(
                    CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE,
                    analysis["id"],
                    "evidence:" + stable_hash("undeclared evidence"),
                )
            ),
            "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_UNDECLARED",
        ),
    ],
)
def test_contribution_analysis_semantic_issues_are_reported(mutate: Any, code: str) -> None:
    store, _, analysis = _analysis_store(evidence_count=2)

    mutate(store, analysis)

    report = validate_graph_integrity(store)
    assert code in _codes(report)
    assert validate_graph_integrity_report(report) is report
    assert "SECRET" not in json.dumps(report, sort_keys=True)


@pytest.mark.parametrize(
    ("edge_type", "semantic_code"),
    [
        (CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_UNDECLARED"),
        (CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_UNDECLARED"),
    ],
)
@pytest.mark.parametrize("target", [{}, [], object(), None, "", "   "])
def test_contribution_analysis_edges_with_non_textual_targets_are_structural_only(
    edge_type: str,
    semantic_code: str,
    target: object,
) -> None:
    store, _, analysis = _analysis_store(evidence_count=2)
    store.edges.append(
        {
            "edge_type": edge_type,
            "from_node_id": analysis["id"],
            "to_node_id": target,
        }
    )
    before = _snapshot(store)

    first = validate_graph_integrity(store)
    second = validate_graph_integrity(store)
    report_json = json.dumps(first, sort_keys=True)

    assert first == second
    assert "EDGE_TARGET_REF_INVALID" in _codes(first)
    assert semantic_code not in _codes(first)
    assert validate_graph_integrity_report(first) is first
    assert "object at" not in report_json
    assert "builtins.object" not in report_json
    if type(target) is object:
        assert store.edges[-1]["to_node_id"] is target
        assert len(store.edges) == len(before["edges"])
    else:
        assert _snapshot(store) == before


@pytest.mark.parametrize(
    ("edge_type", "semantic_code"),
    [
        (CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_UNDECLARED"),
        (CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_UNDECLARED"),
    ],
)
def test_contribution_analysis_edges_with_non_textual_targets_ignore_edge_order(
    edge_type: str,
    semantic_code: str,
) -> None:
    first, _, analysis = _analysis_store(evidence_count=2)
    first.edges.append({"edge_type": edge_type, "from_node_id": analysis["id"], "to_node_id": {}})
    second = JsonGraphStorage()
    second.nodes = copy.deepcopy(first.nodes)
    second.edges = list(reversed(copy.deepcopy(first.edges)))
    second.audit_records = copy.deepcopy(first.audit_records)

    report = validate_graph_integrity(first)

    assert report == validate_graph_integrity(second)
    assert "EDGE_TARGET_REF_INVALID" in _codes(report)
    assert semantic_code not in _codes(report)


@pytest.mark.parametrize(
    ("edge_type", "semantic_code"),
    [
        (CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_UNDECLARED"),
        (CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_UNDECLARED"),
    ],
)
def test_contribution_analysis_edges_with_unsafe_text_target_use_opaque_refs(
    edge_type: str,
    semantic_code: str,
) -> None:
    store, _, analysis = _analysis_store(evidence_count=2)
    store.edges.append(
        {
            "edge_type": edge_type,
            "from_node_id": analysis["id"],
            "to_node_id": "customer:SECRET target",
        }
    )

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)

    assert "EDGE_TARGET_NOT_FOUND" in _codes(report)
    assert semantic_code in _codes(report)
    assert "SECRET" not in report_json
    assert "customer:SECRET target" not in report_json
    assert validate_graph_integrity_report(report) is report


def test_contribution_analysis_no_cascade_for_invalid_or_missing_refs() -> None:
    missing_store, _, missing = _analysis_store()
    missing_store.nodes.pop(missing["properties"]["contribution_ref"])
    missing_codes = _codes(validate_graph_integrity(missing_store))
    assert "CONTRIBUTION_ANALYSIS_CONTRIBUTION_NOT_FOUND" in missing_codes
    assert "CONTRIBUTION_ANALYSIS_CONTRIBUTION_EDGE_MISSING" not in missing_codes

    wrong_type_store, _, wrong_type = _analysis_store()
    wrong_type_store.nodes[wrong_type["properties"]["evidence_refs"][0]]["node_type"] = "Contribution"
    wrong_type_codes = _codes(validate_graph_integrity(wrong_type_store))
    assert "CONTRIBUTION_ANALYSIS_EVIDENCE_TYPE_INVALID" in wrong_type_codes
    assert "CONTRIBUTION_ANALYSIS_EVIDENCE_EDGE_MISSING" not in wrong_type_codes

    invalid_refs_store, _, invalid_refs = _analysis_store()
    invalid_refs_store.nodes[invalid_refs["id"]]["properties"]["evidence_refs"] = [SensitiveNonJsonValue()]
    invalid_refs_codes = _codes(validate_graph_integrity(invalid_refs_store))
    assert invalid_refs_codes.count("CONTRIBUTION_ANALYSIS_EVIDENCE_REFS_INVALID") == 1
    assert "CONTRIBUTION_ANALYSIS_EVIDENCE_NOT_FOUND" not in invalid_refs_codes


def test_contribution_analysis_specific_and_residual_property_failures_are_not_redundant() -> None:
    isolated, _, isolated_analysis = _analysis_store()
    isolated.nodes[isolated_analysis["id"]]["properties"]["status"] = "rejected"
    isolated_codes = _codes(validate_graph_integrity(isolated))
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in isolated_codes
    assert "CONTRIBUTION_ANALYSIS_PROPERTIES_INVALID" not in isolated_codes

    residual, _, residual_analysis = _analysis_store()
    residual.nodes[residual_analysis["id"]]["properties"].update({"status": "rejected", "confidence": "certain"})
    residual_codes = _codes(validate_graph_integrity(residual))
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in residual_codes
    assert "CONTRIBUTION_ANALYSIS_PROPERTIES_INVALID" in residual_codes


def test_contribution_analysis_filters_order_read_only_json_and_privacy() -> None:
    store, _, analysis = _analysis_store(evidence_count=2)
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"
    store.nodes[analysis["id"]]["properties"]["context_facts"].append({"value": "SECRET customer fact"})
    before = _snapshot(store)

    contribution_only = validate_graph_integrity(store, node_types=["Contribution"])
    analysis_only = validate_graph_integrity(store, node_types=["ContributionAnalysis"])
    warnings_only = validate_graph_integrity(store, severities=["warning"])
    first = validate_graph_integrity(store)

    reordered = JsonGraphStorage()
    reordered.nodes = dict(reversed(list(store.nodes.items())))
    reordered.edges = list(reversed(copy.deepcopy(store.edges)))
    reordered.audit_records = list(reversed(copy.deepcopy(store.audit_records)))

    assert all(not code.startswith("CONTRIBUTION_ANALYSIS_") for code in _codes(contribution_only))
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in _codes(analysis_only)
    assert all(issue["severity"] == "warning" for issue in warnings_only["issues"])
    assert first == validate_graph_integrity(reordered)
    assert json.loads(json.dumps(first)) == first
    assert _snapshot(store) == before
    assert "SECRET customer fact" not in json.dumps(first, sort_keys=True)


def test_contribution_and_analysis_valid_coexist_without_semantic_issues() -> None:
    store, _, _ = _analysis_store(evidence_count=2)

    codes = _codes(validate_graph_integrity(store))

    assert [code for code in codes if code.startswith("CONTRIBUTION_")] == []
    assert [code for code in codes if code.startswith("CONTRIBUTION_ANALYSIS_")] == []


def test_invalid_contribution_does_not_skip_valid_analysis_rules() -> None:
    store, contribution, _ = _analysis_store()
    contribution["properties"]["status"] = "done"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert all(not code.startswith("CONTRIBUTION_ANALYSIS_") for code in codes)


def test_invalid_analysis_does_not_create_contribution_false_positive() -> None:
    store, _, analysis = _analysis_store()
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in codes
    assert all(not code.startswith("CONTRIBUTION_") or code.startswith("CONTRIBUTION_ANALYSIS_") for code in codes)


def test_invalid_contribution_and_analysis_issues_coexist_and_validate() -> None:
    store, contribution, analysis = _analysis_store()
    contribution["properties"]["status"] = "done"
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"

    report = validate_graph_integrity(store)
    codes = _codes(report)

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in codes
    assert report["issues"] == sorted(
        report["issues"],
        key=lambda issue: (
            issue["severity"],
            issue["code"],
            issue["subject_type"],
            issue["subject_ref"],
            issue["path"],
            issue["related_refs"],
            issue["id"],
        ),
    )
    assert validate_graph_integrity_report(report) is report


def test_contribution_and_analysis_semantic_filters_are_cumulative() -> None:
    store, contribution, analysis = _analysis_store()
    contribution["properties"]["status"] = "done"
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"

    contribution_codes = _codes(validate_graph_integrity(store, node_types=["Contribution"]))
    analysis_codes = _codes(validate_graph_integrity(store, node_types=["ContributionAnalysis"]))
    both_codes = _codes(validate_graph_integrity(store, node_types=["Contribution", "ContributionAnalysis"]))

    assert "CONTRIBUTION_STATUS_INVALID" in contribution_codes
    assert all(not code.startswith("CONTRIBUTION_ANALYSIS_") for code in contribution_codes)
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in analysis_codes
    assert all(
        not code.startswith("CONTRIBUTION_") or code.startswith("CONTRIBUTION_ANALYSIS_") for code in analysis_codes
    )
    assert "CONTRIBUTION_STATUS_INVALID" in both_codes
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in both_codes


def test_persisted_career_claim_created_by_current_apis_has_no_claim_issues() -> None:
    store, _, _, _ = _claim_store(evidence_count=2)

    assert all(not code.startswith("CAREER_CLAIM_") for code in _codes(validate_graph_integrity(store)))


def test_full_contribution_analysis_claim_flow_has_no_domain_issues() -> None:
    store, _, _, _ = _claim_store(evidence_count=2)
    domain_prefixes = ("CONTRIBUTION_", "CONTRIBUTION_ANALYSIS_", "CAREER_CLAIM_")

    codes = _codes(validate_graph_integrity(store))

    assert [code for code in codes if code.startswith(domain_prefixes)] == []


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]].__setitem__("properties", []),
            "NODE_PROPERTIES_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("status", "rejected"),
            "CAREER_CLAIM_STATUS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__(
                "privacy_level", "public"
            ),
            "CAREER_CLAIM_PRIVACY_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("confidence", "certain"),
            "CAREER_CLAIM_CONFIDENCE_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("statement", ""),
            "CAREER_CLAIM_PROPERTIES_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"]["metadata"].__setitem__(
                "analysis_ref", []
            ),
            "CAREER_CLAIM_ANALYSIS_REF_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"]["metadata"].__setitem__(
                "analysis_ref", "customer:SECRET analysis"
            ),
            "CAREER_CLAIM_ANALYSIS_REF_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes.pop(
                store.nodes[claim["id"]]["properties"]["metadata"]["analysis_ref"]
            ),
            "CAREER_CLAIM_ANALYSIS_NOT_FOUND",
        ),
        (
            lambda store, claim, _analysis: store.nodes[
                store.nodes[claim["id"]]["properties"]["metadata"]["analysis_ref"]
            ].__setitem__("node_type", "Contribution"),
            "CAREER_CLAIM_ANALYSIS_TYPE_INVALID",
        ),
        (
            lambda store, _claim, _analysis: store.edges.__setitem__(
                slice(None),
                [edge for edge in store.edges if edge["edge_type"] != CAREER_CLAIM_DERIVED_FROM_ANALYSIS],
            ),
            "CAREER_CLAIM_ANALYSIS_EDGE_MISSING",
        ),
        (
            lambda store, claim, _analysis: store.edges.append(
                _edge(
                    CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
                    claim["id"],
                    "contribution_analysis:" + stable_hash("undeclared analysis"),
                )
            ),
            "CAREER_CLAIM_ANALYSIS_EDGE_UNDECLARED",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__(
                "contribution_refs", [{}]
            ),
            "CAREER_CLAIM_CONTRIBUTION_REF_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes.pop(
                store.nodes[claim["id"]]["properties"]["contribution_refs"][0]
            ),
            "CAREER_CLAIM_CONTRIBUTION_NOT_FOUND",
        ),
        (
            lambda store, claim, _analysis: store.nodes[
                store.nodes[claim["id"]]["properties"]["contribution_refs"][0]
            ].__setitem__("node_type", "EvidenceNode"),
            "CAREER_CLAIM_CONTRIBUTION_TYPE_INVALID",
        ),
        (
            lambda store, _claim, _analysis: store.edges.__setitem__(
                slice(None),
                [edge for edge in store.edges if edge["edge_type"] != CAREER_CLAIM_FROM_CONTRIBUTION],
            ),
            "CAREER_CLAIM_CONTRIBUTION_EDGE_MISSING",
        ),
        (
            lambda store, claim, _analysis: store.edges.append(
                _edge(CAREER_CLAIM_FROM_CONTRIBUTION, claim["id"], "contribution:" + stable_hash("undeclared"))
            ),
            "CAREER_CLAIM_CONTRIBUTION_EDGE_UNDECLARED",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("evidence_refs", {}),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("evidence_refs", [[]]),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__(
                "evidence_refs", [SensitiveNonJsonValue()]
            ),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__("evidence_refs", [None]),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__(
                "evidence_refs", ["   "]
            ),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"].__setitem__(
                "evidence_refs", [store.nodes[claim["id"]]["properties"]["evidence_refs"][0], object()]
            ),
            "CAREER_CLAIM_EVIDENCE_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes.pop(store.nodes[claim["id"]]["properties"]["evidence_refs"][0]),
            "CAREER_CLAIM_EVIDENCE_NOT_FOUND",
        ),
        (
            lambda store, claim, _analysis: store.nodes[
                store.nodes[claim["id"]]["properties"]["evidence_refs"][0]
            ].__setitem__("node_type", "Contribution"),
            "CAREER_CLAIM_EVIDENCE_TYPE_INVALID",
        ),
        (
            lambda store, _claim, _analysis: store.edges.__setitem__(
                slice(None),
                [edge for edge in store.edges if edge["edge_type"] != CAREER_CLAIM_SUPPORTED_BY_EVIDENCE],
            ),
            "CAREER_CLAIM_EVIDENCE_EDGE_MISSING",
        ),
        (
            lambda store, claim, _analysis: store.edges.append(
                _edge(CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim["id"], "evidence:" + stable_hash("undeclared"))
            ),
            "CAREER_CLAIM_EVIDENCE_EDGE_UNDECLARED",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"]["metadata"].__setitem__(
                "supporting_fact_refs", ["analysis_fact:" + stable_hash("missing")]
            ),
            "CAREER_CLAIM_SUPPORTING_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]]["properties"]["metadata"].__setitem__(
                "supporting_signal_refs", [None]
            ),
            "CAREER_CLAIM_SUPPORTING_REFS_INVALID",
        ),
        (
            lambda store, claim, _analysis: store.nodes[claim["id"]].__setitem__(
                "id", "career_claim:" + stable_hash("wrong")
            ),
            "CAREER_CLAIM_PROPERTIES_INVALID",
        ),
    ],
)
def test_career_claim_semantic_issues_are_reported(mutate: Any, code: str) -> None:
    store, _, analysis, claim = _claim_store(evidence_count=2)

    mutate(store, claim, analysis)

    report = validate_graph_integrity(store)
    assert code in _codes(report)
    assert validate_graph_integrity_report(report) is report
    assert "SECRET" not in json.dumps(report, sort_keys=True)


def test_career_claim_specific_failures_do_not_cascade() -> None:
    missing, _, _, missing_claim = _claim_store()
    missing.nodes.pop(missing.nodes[missing_claim["id"]]["properties"]["metadata"]["analysis_ref"])
    missing_codes = _codes(validate_graph_integrity(missing))
    assert "CAREER_CLAIM_ANALYSIS_NOT_FOUND" in missing_codes
    assert "CAREER_CLAIM_ANALYSIS_EDGE_MISSING" not in missing_codes

    wrong_type, _, _, wrong_claim = _claim_store()
    wrong_type.nodes[wrong_type.nodes[wrong_claim["id"]]["properties"]["evidence_refs"][0]]["node_type"] = (
        "Contribution"
    )
    wrong_type_codes = _codes(validate_graph_integrity(wrong_type))
    assert "CAREER_CLAIM_EVIDENCE_TYPE_INVALID" in wrong_type_codes
    assert "CAREER_CLAIM_EVIDENCE_EDGE_MISSING" not in wrong_type_codes

    isolated, _, _, isolated_claim = _claim_store()
    isolated.nodes[isolated_claim["id"]]["properties"]["status"] = "rejected"
    isolated_codes = _codes(validate_graph_integrity(isolated))
    assert "CAREER_CLAIM_STATUS_INVALID" in isolated_codes
    assert "CAREER_CLAIM_PROPERTIES_INVALID" not in isolated_codes

    residual, _, _, residual_claim = _claim_store()
    residual.nodes[residual_claim["id"]]["properties"].update({"status": "rejected", "statement": ""})
    residual_codes = _codes(validate_graph_integrity(residual))
    assert "CAREER_CLAIM_STATUS_INVALID" in residual_codes
    assert "CAREER_CLAIM_PROPERTIES_INVALID" in residual_codes


@pytest.mark.parametrize(
    ("field", "edge_type", "not_found_code", "type_invalid_code", "missing_code", "undeclared_code", "node_type"),
    [
        (
            "analysis",
            CAREER_CLAIM_DERIVED_FROM_ANALYSIS,
            "CAREER_CLAIM_ANALYSIS_NOT_FOUND",
            "CAREER_CLAIM_ANALYSIS_TYPE_INVALID",
            "CAREER_CLAIM_ANALYSIS_EDGE_MISSING",
            "CAREER_CLAIM_ANALYSIS_EDGE_UNDECLARED",
            "ContributionAnalysis",
        ),
        (
            "contribution",
            CAREER_CLAIM_FROM_CONTRIBUTION,
            "CAREER_CLAIM_CONTRIBUTION_NOT_FOUND",
            "CAREER_CLAIM_CONTRIBUTION_TYPE_INVALID",
            "CAREER_CLAIM_CONTRIBUTION_EDGE_MISSING",
            "CAREER_CLAIM_CONTRIBUTION_EDGE_UNDECLARED",
            "Contribution",
        ),
    ],
)
@pytest.mark.parametrize("declared_target_state", ["missing", "wrong_type"])
def test_career_claim_declared_single_target_failure_still_reports_undeclared_edge(
    field: str,
    edge_type: str,
    not_found_code: str,
    type_invalid_code: str,
    missing_code: str,
    undeclared_code: str,
    node_type: str,
    declared_target_state: str,
) -> None:
    store, _, _, claim = _claim_store()
    props = store.nodes[claim["id"]]["properties"]
    declared_ref = props["metadata"]["analysis_ref"] if field == "analysis" else props["contribution_refs"][0]
    alternate_ref = f"{declared_ref.split(':', maxsplit=1)[0]}:{stable_hash(field + declared_target_state)}"
    store.nodes[alternate_ref] = _node(alternate_ref, node_type)
    store.edges.append(_edge(edge_type, claim["id"], alternate_ref))
    store.edges.append({"edge_type": edge_type, "from_node_id": claim["id"], "to_node_id": "customer:SECRET target"})
    if declared_target_state == "missing":
        store.nodes.pop(declared_ref)
        expected = not_found_code
        unexpected = type_invalid_code
    else:
        store.nodes[declared_ref]["node_type"] = "EvidenceNode"
        expected = type_invalid_code
        unexpected = not_found_code
    before = _snapshot(store)

    first = validate_graph_integrity(store)
    second = validate_graph_integrity(store)
    reordered = JsonGraphStorage()
    reordered.nodes = copy.deepcopy(store.nodes)
    reordered.edges = list(reversed(copy.deepcopy(store.edges)))
    reordered.audit_records = copy.deepcopy(store.audit_records)
    codes = _codes(first)
    report_json = json.dumps(first, sort_keys=True)
    undeclared = [issue for issue in first["issues"] if issue["code"] == undeclared_code]

    assert first == second
    assert first == validate_graph_integrity(reordered)
    assert expected in codes
    assert undeclared_code in codes
    assert missing_code not in codes
    assert unexpected not in codes
    assert "EDGE_TARGET_NOT_FOUND" in codes
    assert "SECRET" not in report_json
    assert "customer:SECRET target" not in report_json
    assert all(
        ref.startswith(("edge_endpoint:", "contribution_analysis:", "contribution:"))
        for issue in undeclared
        for ref in issue["related_refs"]
    )
    assert validate_graph_integrity_report(first) is first
    assert _snapshot(store) == before


@pytest.mark.parametrize(
    ("edge_type", "semantic_code"),
    [
        (CAREER_CLAIM_DERIVED_FROM_ANALYSIS, "CAREER_CLAIM_ANALYSIS_EDGE_UNDECLARED"),
        (CAREER_CLAIM_FROM_CONTRIBUTION, "CAREER_CLAIM_CONTRIBUTION_EDGE_UNDECLARED"),
        (CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, "CAREER_CLAIM_EVIDENCE_EDGE_UNDECLARED"),
    ],
)
@pytest.mark.parametrize("target", [{}, [], object(), None, "", "   "])
def test_career_claim_edges_with_non_textual_targets_are_structural_only(
    edge_type: str,
    semantic_code: str,
    target: object,
) -> None:
    store, _, _, claim = _claim_store()
    store.edges.append({"edge_type": edge_type, "from_node_id": claim["id"], "to_node_id": target})

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)

    assert "EDGE_TARGET_REF_INVALID" in _codes(report)
    assert semantic_code not in _codes(report)
    assert "object at" not in report_json
    assert "builtins.object" not in report_json
    assert validate_graph_integrity_report(report) is report


def test_career_claim_filters_order_read_only_json_privacy_and_severity() -> None:
    store, contribution, analysis, claim = _claim_store(evidence_count=2)
    contribution["properties"]["status"] = "done"
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"
    store.nodes[claim["id"]]["properties"]["status"] = "rejected"
    store.nodes[claim["id"]]["properties"]["statement"] = "SECRET customer statement"
    before = _snapshot(store)

    contribution_only = _codes(validate_graph_integrity(store, node_types=["Contribution"]))
    analysis_only = _codes(validate_graph_integrity(store, node_types=["ContributionAnalysis"]))
    claim_only = _codes(validate_graph_integrity(store, node_types=["CareerClaim"]))
    combined = _codes(
        validate_graph_integrity(store, node_types=["Contribution", "ContributionAnalysis", "CareerClaim"])
    )
    warnings_only = validate_graph_integrity(store, severities=["warning"])
    first = validate_graph_integrity(store)
    reordered = JsonGraphStorage()
    reordered.nodes = dict(reversed(list(copy.deepcopy(store.nodes).items())))
    reordered.edges = list(reversed(copy.deepcopy(store.edges)))
    reordered.audit_records = list(reversed(copy.deepcopy(store.audit_records)))

    assert "CONTRIBUTION_STATUS_INVALID" in contribution_only
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" not in contribution_only
    assert "CAREER_CLAIM_STATUS_INVALID" not in contribution_only
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in analysis_only
    assert "CAREER_CLAIM_STATUS_INVALID" in claim_only
    assert "CONTRIBUTION_STATUS_INVALID" in combined
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in combined
    assert "CAREER_CLAIM_STATUS_INVALID" in combined
    assert all(issue["severity"] == "warning" for issue in warnings_only["issues"])
    assert first == validate_graph_integrity(reordered)
    assert json.loads(json.dumps(first)) == first
    assert _snapshot(store) == before
    assert "SECRET customer statement" not in json.dumps(first, sort_keys=True)


def test_invalid_claim_does_not_create_contribution_or_analysis_false_positive() -> None:
    store, _, _, claim = _claim_store()
    store.nodes[claim["id"]]["properties"]["status"] = "rejected"

    codes = _codes(validate_graph_integrity(store))

    assert "CAREER_CLAIM_STATUS_INVALID" in codes
    assert all(not code.startswith("CONTRIBUTION_") for code in codes)
    assert all(not code.startswith("CONTRIBUTION_ANALYSIS_") for code in codes)


def test_contribution_analysis_and_claim_invalid_issues_coexist() -> None:
    store, contribution, analysis, claim = _claim_store()
    contribution["properties"]["status"] = "done"
    store.nodes[analysis["id"]]["properties"]["status"] = "rejected"
    store.nodes[claim["id"]]["properties"]["status"] = "rejected"

    report = validate_graph_integrity(store)
    codes = _codes(report)

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert "CONTRIBUTION_ANALYSIS_STATUS_INVALID" in codes
    assert "CAREER_CLAIM_STATUS_INVALID" in codes
    assert validate_graph_integrity_report(report) is report


def test_claim_based_professional_artifact_api_happy_path_has_no_issues() -> None:
    store, _, _ = _claim_artifact_store()

    assert _codes(validate_graph_integrity(store)) == []


def test_legacy_professional_artifact_happy_path_has_no_claim_false_positive() -> None:
    store, _, _ = _legacy_artifact_store()

    assert _codes(validate_graph_integrity(store)) == []


def test_contribution_analysis_claim_artifact_flow_has_no_issues() -> None:
    store, _, _ = _claim_artifact_store(evidence_count=2)

    assert _codes(validate_graph_integrity(store)) == []


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda artifact: artifact.__setitem__("properties", []), "NODE_PROPERTIES_INVALID"),
        (
            lambda artifact: artifact["properties"].__setitem__("status", "draft"),
            "PROFESSIONAL_ARTIFACT_STATUS_INVALID",
        ),
        (
            lambda artifact: artifact["properties"].__setitem__("privacy_level", "private"),
            "PROFESSIONAL_ARTIFACT_PRIVACY_INVALID",
        ),
        (
            lambda artifact: artifact["properties"].__setitem__("artifact_type", "unsupported"),
            "PROFESSIONAL_ARTIFACT_TYPE_INVALID",
        ),
        (
            lambda artifact: artifact["properties"].__setitem__("source_type", []),
            "PROFESSIONAL_ARTIFACT_SOURCE_TYPE_INVALID",
        ),
        (
            lambda artifact: artifact["properties"].__setitem__("review_actor", SensitiveNonJsonValue()),
            "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID",
        ),
        (lambda artifact: artifact.__setitem__("id", "artifact:" + "b" * 64), "PROFESSIONAL_ARTIFACT_ID_INVALID"),
    ],
)
def test_professional_artifact_contract_issues(mutate: Any, code: str) -> None:
    store, _, artifact = _claim_artifact_store()
    mutate(artifact)

    assert code in _codes(validate_graph_integrity(store))


@pytest.mark.parametrize("source_type", ["", "customer", "career-claim", " knowledge ", [], {}, object()])
def test_professional_artifact_unknown_source_type_does_not_select_variant(source_type: object) -> None:
    store, _, artifact = _legacy_artifact_store()
    artifact["properties"]["source_type"] = source_type
    before = None if type(source_type) is object else _snapshot(store)
    before_source_type = artifact["properties"]["source_type"]

    first = validate_graph_integrity(store)
    reordered = copy.deepcopy(store)
    reordered.edges = list(reversed(reordered.edges))

    codes = _codes(first)
    report_json = json.dumps(first, sort_keys=True)

    assert "PROFESSIONAL_ARTIFACT_SOURCE_TYPE_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_REFS_INVALID" not in codes
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_REFS_INVALID" not in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" not in codes
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_EDGE_MISSING" not in codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" not in codes
    assert "object at" not in report_json
    assert validate_graph_integrity_report(first) is first
    assert json.loads(report_json) == first
    assert first == validate_graph_integrity(store)
    assert first == validate_graph_integrity(reordered)
    if before is None:
        assert artifact["properties"]["source_type"] is before_source_type
    else:
        assert _snapshot(store) == before


def test_professional_artifact_unknown_source_type_with_residual_error_keeps_both() -> None:
    store, _, artifact = _legacy_artifact_store()
    artifact["properties"]["source_type"] = "customer"
    artifact["properties"]["review_actor"] = SensitiveNonJsonValue()

    codes = _codes(validate_graph_integrity(store))

    assert "PROFESSIONAL_ARTIFACT_SOURCE_TYPE_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" in codes


def test_claim_based_professional_artifact_unknown_source_type_preserves_variant_without_generic() -> None:
    store, _, artifact = _claim_artifact_store()
    artifact["properties"]["source_type"] = "customer"
    before = _snapshot(store)
    reordered = copy.deepcopy(store)
    reordered.edges = list(reversed(reordered.edges))

    report = validate_graph_integrity(store)
    codes = _codes(report)
    report_json = json.dumps(report, sort_keys=True)

    assert "PROFESSIONAL_ARTIFACT_SOURCE_TYPE_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" not in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_REFS_INVALID" not in codes
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_REFS_INVALID" not in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" not in codes
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_EDGE_MISSING" not in codes
    assert "ArtifactExportReceipt" not in report_json
    assert "SECRET" not in report_json
    assert validate_graph_integrity_report(report) is report
    assert json.loads(report_json) == report
    assert report == validate_graph_integrity(store)
    assert report == validate_graph_integrity(reordered)
    assert _snapshot(store) == before


def test_claim_based_professional_artifact_unknown_source_type_with_residual_error_keeps_both() -> None:
    store, _, artifact = _claim_artifact_store()
    artifact["properties"]["source_type"] = "customer"
    artifact["properties"]["review_actor"] = SensitiveNonJsonValue()

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)
    codes = _codes(report)

    assert "PROFESSIONAL_ARTIFACT_SOURCE_TYPE_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" in codes
    assert "SensitiveNonJsonValue SECRET" not in report_json
    assert "object at" not in report_json
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize("claim_refs", [{}, [], [object()], None, [" "], ["career_claim:" + "c" * 64, []]])
def test_professional_artifact_claim_refs_invalid_values(claim_refs: object) -> None:
    store, _, artifact = _claim_artifact_store()
    artifact["properties"]["claim_refs"] = claim_refs

    codes = _codes(validate_graph_integrity(store))

    assert "PROFESSIONAL_ARTIFACT_CLAIM_REFS_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_NOT_FOUND" not in codes


def test_professional_artifact_claim_ref_target_and_edge_issues() -> None:
    missing, _, missing_artifact = _claim_artifact_store()
    missing_artifact["properties"]["claim_refs"] = ["career_claim:" + "c" * 64]

    wrong_type, _, wrong_artifact = _claim_artifact_store()
    wrong_type.nodes["career_claim:" + "c" * 64] = dict(
        _node("career_claim:" + "c" * 64, "KnowledgeNode"), properties={}
    )
    wrong_artifact["properties"]["claim_refs"] = ["career_claim:" + "c" * 64]

    no_edge, _, _ = _claim_artifact_store()
    no_edge.edges = [
        edge for edge in no_edge.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM
    ]

    assert "PROFESSIONAL_ARTIFACT_CLAIM_NOT_FOUND" in _codes(validate_graph_integrity(missing))
    assert "PROFESSIONAL_ARTIFACT_CLAIM_TYPE_INVALID" in _codes(validate_graph_integrity(wrong_type))
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" in _codes(validate_graph_integrity(no_edge))


def test_professional_artifact_claim_edges_are_independent_from_bad_declared_claim() -> None:
    store, claim, artifact = _claim_artifact_store()
    extra_claim = copy.deepcopy(claim)
    extra_claim["id"] = "career_claim:" + "c" * 64
    store.nodes[extra_claim["id"]] = extra_claim
    artifact["properties"]["claim_refs"] = ["career_claim:" + "d" * 64]
    store.create_edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, artifact["id"], extra_claim["id"])

    codes = _codes(validate_graph_integrity(store))

    assert "PROFESSIONAL_ARTIFACT_CLAIM_NOT_FOUND" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_UNDECLARED" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" not in codes


def test_professional_artifact_type_invalid_claim_still_inspects_undeclared_edge() -> None:
    store, claim, artifact = _claim_artifact_store()
    wrong_ref = "career_claim:" + "c" * 64
    extra_claim = copy.deepcopy(claim)
    extra_claim["id"] = "career_claim:" + "d" * 64
    store.nodes[wrong_ref] = dict(_node(wrong_ref, "KnowledgeNode"), properties={})
    store.nodes[extra_claim["id"]] = extra_claim
    artifact["properties"]["claim_refs"] = [wrong_ref]
    store.create_edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, artifact["id"], extra_claim["id"])

    codes = _codes(validate_graph_integrity(store))

    assert "PROFESSIONAL_ARTIFACT_CLAIM_TYPE_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_UNDECLARED" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" not in codes


def test_professional_artifact_textual_unsafe_and_non_textual_targets() -> None:
    unsafe, _, unsafe_artifact = _claim_artifact_store()
    unsafe.edges.append(
        _edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, unsafe_artifact["id"], "customer:SECRET markdown")
    )
    unsafe_json = json.dumps(validate_graph_integrity(unsafe), sort_keys=True)

    non_text, _, non_text_artifact = _claim_artifact_store()
    non_text.edges.append(
        _edge(PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM, non_text_artifact["id"], "career_claim:" + "c" * 64)
    )
    non_text.edges[-1]["to_node_id"] = []
    non_text_codes = _codes(validate_graph_integrity(non_text))

    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_UNDECLARED" in unsafe_json
    assert "SECRET" not in unsafe_json
    assert "edge_endpoint:" in unsafe_json
    assert "EDGE_TARGET_REF_INVALID" in non_text_codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_UNDECLARED" not in non_text_codes


def test_professional_artifact_claim_privacy_incompatible() -> None:
    store, claim, _ = _claim_artifact_store()
    claim["properties"]["privacy_level"] = "internal"

    assert "PROFESSIONAL_ARTIFACT_CLAIM_PRIVACY_INCOMPATIBLE" in _codes(validate_graph_integrity(store))


def test_professional_artifact_claim_privacy_and_missing_edge_are_independent() -> None:
    store, claim, artifact = _claim_artifact_store()
    claim["properties"]["privacy_level"] = "internal"
    store.edges = [edge for edge in store.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM]
    before = _snapshot(store)
    reordered = copy.deepcopy(store)
    reordered.edges = list(reversed(reordered.edges))

    report = validate_graph_integrity(store)
    codes = _codes(report)

    assert "PROFESSIONAL_ARTIFACT_CLAIM_PRIVACY_INCOMPATIBLE" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" in codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" not in codes
    assert validate_graph_integrity_report(report) is report
    assert report == validate_graph_integrity(store)
    assert report == validate_graph_integrity(reordered)
    assert _snapshot(store) == before


def test_professional_artifact_claim_status_and_missing_edge_are_independent() -> None:
    store, claim, _ = _claim_artifact_store()
    claim["properties"]["status"] = "rejected"
    store.edges = [edge for edge in store.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM]

    codes = _codes(validate_graph_integrity(store))

    assert "PROFESSIONAL_ARTIFACT_CLAIM_STATUS_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_CLAIM_EDGE_MISSING" in codes


@pytest.mark.parametrize("knowledge_refs", [{}, [object()], None, [" "], ["knowledge:" + "c" * 64, []]])
def test_professional_artifact_legacy_knowledge_refs_invalid_values(knowledge_refs: object) -> None:
    store, _, artifact = _legacy_artifact_store()
    artifact["properties"]["knowledge_refs"] = knowledge_refs

    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_REFS_INVALID" in _codes(validate_graph_integrity(store))


def test_professional_artifact_legacy_knowledge_target_and_edge_issues() -> None:
    missing, _, missing_artifact = _legacy_artifact_store()
    missing_artifact["properties"]["knowledge_refs"] = ["knowledge:" + "c" * 64]

    wrong_type, _, wrong_artifact = _legacy_artifact_store()
    wrong_type.nodes["knowledge:" + "c" * 64] = dict(_node("knowledge:" + "c" * 64, "EvidenceNode"), properties={})
    wrong_artifact["properties"]["knowledge_refs"] = ["knowledge:" + "c" * 64]

    no_edge, _, _ = _legacy_artifact_store()
    no_edge.edges = [edge for edge in no_edge.edges if edge.get("edge_type") != "ARTIFACT_GENERATED_FROM_KNOWLEDGE"]

    undeclared, knowledge, undeclared_artifact = _legacy_artifact_store()
    undeclared_artifact["properties"]["knowledge_refs"] = []
    undeclared.create_edge("ARTIFACT_GENERATED_FROM_KNOWLEDGE", undeclared_artifact["id"], knowledge["id"])

    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_NOT_FOUND" in _codes(validate_graph_integrity(missing))
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_TYPE_INVALID" in _codes(validate_graph_integrity(wrong_type))
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_EDGE_MISSING" in _codes(validate_graph_integrity(no_edge))
    assert "PROFESSIONAL_ARTIFACT_KNOWLEDGE_EDGE_UNDECLARED" in _codes(validate_graph_integrity(undeclared))


@pytest.mark.parametrize("evidence_refs", [{}, [object()], None, [" "], ["evidence:" + "c" * 64, []]])
def test_professional_artifact_evidence_refs_invalid_values(evidence_refs: object) -> None:
    store, _, artifact = _claim_artifact_store()
    artifact["properties"]["evidence_refs"] = evidence_refs

    assert "PROFESSIONAL_ARTIFACT_EVIDENCE_REFS_INVALID" in _codes(validate_graph_integrity(store))


def test_professional_artifact_evidence_target_and_edge_issues() -> None:
    missing, _, missing_artifact = _claim_artifact_store()
    missing_artifact["properties"]["evidence_refs"] = ["evidence:" + "c" * 64]

    wrong_type, _, wrong_artifact = _claim_artifact_store()
    wrong_type.nodes["evidence:" + "c" * 64] = dict(
        _node("evidence:" + "c" * 64, "ArtifactExportReceipt"), properties={}
    )
    wrong_artifact["properties"]["evidence_refs"] = ["evidence:" + "c" * 64]

    no_edge, _, _ = _claim_artifact_store()
    no_edge.edges = [
        edge for edge in no_edge.edges if edge.get("edge_type") != PROFESSIONAL_ARTIFACT_SUPPORTED_BY_EVIDENCE
    ]

    undeclared, _, undeclared_artifact = _claim_artifact_store(evidence_count=2)
    undeclared_artifact["properties"]["evidence_refs"] = []

    assert "PROFESSIONAL_ARTIFACT_EVIDENCE_NOT_FOUND" in _codes(validate_graph_integrity(missing))
    assert "PROFESSIONAL_ARTIFACT_EVIDENCE_TYPE_INVALID" in _codes(validate_graph_integrity(wrong_type))
    assert "PROFESSIONAL_ARTIFACT_EVIDENCE_EDGE_MISSING" in _codes(validate_graph_integrity(no_edge))
    assert "PROFESSIONAL_ARTIFACT_EVIDENCE_EDGE_UNDECLARED" in _codes(validate_graph_integrity(undeclared))


def test_professional_artifact_specific_and_residual_generic_behavior() -> None:
    isolated, _, isolated_artifact = _claim_artifact_store()
    isolated_artifact["properties"]["status"] = "draft"
    residual, _, residual_artifact = _claim_artifact_store()
    residual_artifact["properties"]["status"] = "draft"
    residual_artifact["properties"]["review_actor"] = SensitiveNonJsonValue()

    isolated_codes = _codes(validate_graph_integrity(isolated))
    residual_codes = _codes(validate_graph_integrity(residual))

    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" in isolated_codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" not in isolated_codes
    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" in residual_codes
    assert "PROFESSIONAL_ARTIFACT_PROPERTIES_INVALID" in residual_codes


def test_professional_artifact_filters_read_only_json_and_determinism() -> None:
    store, _, artifact = _claim_artifact_store(evidence_count=2)
    artifact["properties"]["status"] = "draft"
    before = _snapshot(store)
    reordered = copy.deepcopy(store)
    reordered.nodes = dict(reversed(list(reordered.nodes.items())))
    reordered.edges = list(reversed(reordered.edges))

    artifact_only = validate_graph_integrity(store, node_types=["ProfessionalArtifact"])
    claim_only = validate_graph_integrity(store, node_types=["CareerClaim"])
    combined = validate_graph_integrity(store, node_types=["CareerClaim", "ProfessionalArtifact"])
    warnings = validate_graph_integrity(store, severities=["warning"])

    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" in _codes(artifact_only)
    assert all(not code.startswith("PROFESSIONAL_ARTIFACT_") for code in _codes(claim_only))
    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" in _codes(combined)
    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" not in _codes(warnings)
    assert validate_graph_integrity(store) == validate_graph_integrity(reordered)
    assert json.loads(json.dumps(artifact_only)) == artifact_only
    assert _snapshot(store) == before


def test_claim_and_professional_artifact_invalid_issues_coexist_without_false_positive() -> None:
    store, claim, artifact = _claim_artifact_store()
    claim["properties"]["status"] = "rejected"
    artifact["properties"]["status"] = "draft"

    codes = _codes(validate_graph_integrity(store))

    assert "CAREER_CLAIM_STATUS_INVALID" in codes
    assert "PROFESSIONAL_ARTIFACT_STATUS_INVALID" in codes


def test_professional_artifact_invalid_does_not_create_false_positive_in_claim() -> None:
    store, _, artifact = _claim_artifact_store()
    artifact["properties"]["status"] = "draft"

    assert [code for code in _codes(validate_graph_integrity(store)) if code.startswith("CAREER_CLAIM_")] == []


def test_export_receipts_remain_outside_professional_artifact_semantics() -> None:
    store, _, _ = _claim_artifact_store()
    store.nodes["artifact_export_receipt:" + "c" * 64] = _node(
        "artifact_export_receipt:" + "c" * 64,
        "ArtifactExportReceipt",
    )
    store.nodes["artifact_export_repair_receipt:" + "c" * 64] = _node(
        "artifact_export_repair_receipt:" + "c" * 64,
        "ArtifactExportRepairReceipt",
    )

    assert _codes(validate_graph_integrity(store)) == []


def test_audit_target_refs_rules_are_conservative() -> None:
    store = _store()
    store.audit_records = [
        _audit("evidence:missing"),
        _audit("claim_based_artifact:in-memory", "career_claim_candidate:in-memory"),
    ]
    store.audit_records[1]["id"] = "audit:2"

    report = validate_graph_integrity(store)

    assert _codes(report).count("AUDIT_TARGET_NOT_FOUND") == 1
    assert report["issues"][0]["related_refs"][0].startswith("audit_target:")


def test_audit_target_refs_duplicate_and_non_canonical_are_warnings() -> None:
    store = _store()
    store.audit_records = [_audit("evidence:a", "contribution:a", "evidence:a")]

    report = validate_graph_integrity(store)

    assert "AUDIT_TARGET_REFS_DUPLICATED" in _codes(report)
    assert "AUDIT_TARGET_REFS_NOT_CANONICAL" in _codes(report)
    assert report["status"] == "valid"


def test_node_key_mismatch_does_not_copy_unsafe_key_or_node_id() -> None:
    store = _store()
    store.nodes["customer:SECRET markdown content"] = {
        "id": "evidence:SECRET other content",
        "node_type": "EvidenceNode",
        "created_at": NOW,
        "properties": {},
    }

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)

    assert "NODE_KEY_ID_MISMATCH" in _codes(report)
    assert "SECRET" not in report_json
    assert "customer:SECRET markdown content" not in report_json
    assert "evidence:SECRET other content" not in report_json


def test_node_key_mismatch_keeps_canonical_refs_readable() -> None:
    key = f"evidence:{HASH}"
    node_id = f"knowledge:{HASH}"
    store = _store()
    store.nodes[key] = _node(node_id)

    issue = _issue_for(validate_graph_integrity(store), "NODE_KEY_ID_MISMATCH")

    assert issue["subject_ref"] == key
    assert issue["related_refs"] == [node_id]


def test_non_textual_node_key_mismatch_is_reported_without_copying_repr() -> None:
    store = _store()
    key = SensitiveNonJsonValue()
    node_id = f"evidence:{HASH}"
    store.nodes[key] = _node(node_id)

    report = validate_graph_integrity(store)
    issue = _issue_for(report, "NODE_KEY_ID_MISMATCH")
    report_json = json.dumps(report, sort_keys=True)

    assert issue["subject_ref"].startswith("node_key:")
    assert issue["related_refs"] == [node_id]
    assert "SensitiveNonJsonValue SECRET" not in report_json
    assert str(id(key)) not in report_json


def test_integer_node_key_mismatch_is_reported() -> None:
    store = _store()
    node_id = f"evidence:{HASH}"
    store.nodes[123] = _node(node_id)

    issue = _issue_for(validate_graph_integrity(store), "NODE_KEY_ID_MISMATCH")

    assert issue["subject_ref"].startswith("node_key:")
    assert issue["related_refs"] == [node_id]


def test_structurally_equivalent_non_textual_node_key_mismatches_are_deterministic() -> None:
    first = _store()
    second = _store()
    first.nodes[SensitiveNonJsonValue()] = _node(f"evidence:{HASH}")
    second.nodes[SensitiveNonJsonValue()] = _node(f"evidence:{HASH}")

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_string_node_key_matching_node_id_has_no_mismatch() -> None:
    store = _store()

    assert "NODE_KEY_ID_MISMATCH" not in _codes(validate_graph_integrity(store))


def test_unsafe_divergent_node_id_is_opaque_in_related_refs() -> None:
    store = _store()
    store.nodes["customer:SECRET markdown content"] = _node("evidence:SECRET other content")

    issue = _issue_for(validate_graph_integrity(store), "NODE_KEY_ID_MISMATCH")

    assert issue["related_refs"][0].startswith("invalid_node_ref:")
    assert "SECRET" not in json.dumps(issue, sort_keys=True)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("from_node_id", "evidence:SECRET source", "EDGE_SOURCE_NOT_FOUND"),
        ("to_node_id", "contribution:SECRET target", "EDGE_TARGET_NOT_FOUND"),
    ],
)
def test_missing_edge_endpoint_related_refs_are_sanitized(field: str, value: str, code: str) -> None:
    store = _store()
    store.edges[0][field] = value

    issue = _issue_for(validate_graph_integrity(store), code)
    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert issue["related_refs"][0].startswith("edge_endpoint:")
    assert "SECRET" not in report_json


def test_missing_edge_endpoint_canonical_refs_stay_readable_and_sorted() -> None:
    source = f"evidence:{HASH}"
    target = f"contribution:{HASH}"
    store = _store()
    store.edges = [_edge("SUPPORTS", source, target), _edge("SUPPORTS", source, target)]

    report = validate_graph_integrity(store)

    source_issue = _issue_for(report, "EDGE_SOURCE_NOT_FOUND")
    target_issue = _issue_for(report, "EDGE_TARGET_NOT_FOUND")
    duplicate = _issue_for(report, "DUPLICATE_EDGE")
    assert source_issue["related_refs"] == [source]
    assert target_issue["related_refs"] == [target]
    assert duplicate["related_refs"] == sorted([source, target])


def test_audit_related_refs_are_sanitized_and_distinct_when_unsafe() -> None:
    store = _store()
    store.audit_records = [_audit("evidence:SECRET one", "evidence:SECRET two", "evidence:SECRET one")]

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)
    duplicated = _issue_for(report, "AUDIT_TARGET_REFS_DUPLICATED")
    not_canonical = _issue_for(report, "AUDIT_TARGET_REFS_NOT_CANONICAL")
    not_found = [issue for issue in report["issues"] if issue["code"] == "AUDIT_TARGET_NOT_FOUND"]

    assert "SECRET" not in report_json
    assert duplicated["related_refs"][0].startswith("audit_target:")
    assert all(ref.startswith("audit_target:") for issue in not_found for ref in issue["related_refs"])
    assert len({ref for issue in not_found for ref in issue["related_refs"]}) == 2
    assert not_canonical["related_refs"] == sorted(set(not_canonical["related_refs"]))


def test_audit_related_refs_keep_canonical_targets_readable() -> None:
    first = f"evidence:{HASH}"
    second = f"contribution:{HASH}"
    store = _store()
    store.audit_records = [_audit(first, second)]

    issue = _issue_for(validate_graph_integrity(store), "AUDIT_TARGET_REFS_NOT_CANONICAL")

    assert issue["related_refs"] == sorted([first, second])


def test_filters_by_severity_and_node_type_with_empty_lists_distinct_from_none() -> None:
    store = _store()
    store.nodes["evidence:a"]["created_at"] = "bad"
    store.edges[0]["to_node_id"] = "contribution:missing"
    store.audit_records = [_audit("evidence:missing")]

    errors = validate_graph_integrity(store, severities=["error"])
    warnings = validate_graph_integrity(store, severities=["warning"])
    empty = validate_graph_integrity(store, severities=[])
    contribution_only = validate_graph_integrity(store, node_types=["Contribution"])

    assert all(issue["severity"] == "error" for issue in errors["issues"])
    assert all(issue["severity"] == "warning" for issue in warnings["issues"])
    assert empty["issues"] == []
    assert empty["status"] == "valid"
    assert "NODE_CREATED_AT_INVALID" not in _codes(contribution_only)
    assert "EDGE_TARGET_NOT_FOUND" in _codes(contribution_only)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"store": object()},
        {"store": _store(), "node_types": "EvidenceNode"},
        {"store": _store(), "node_types": [""]},
        {"store": _store(), "severities": "error"},
        {"store": _store(), "severities": ["fatal"]},
    ],
)
def test_public_arguments_raise_value_error(kwargs: dict[str, Any]) -> None:
    store = kwargs.pop("store")
    with pytest.raises(ValueError):
        validate_graph_integrity(store, **kwargs)


def test_issues_are_ordered_and_related_refs_are_canonical() -> None:
    store = _store()
    store.edges[0]["from_node_id"] = "evidence:missing"
    store.edges[0]["to_node_id"] = "contribution:missing"

    report = validate_graph_integrity(store)

    assert report["issues"] == sorted(
        report["issues"],
        key=lambda issue: (
            issue["severity"],
            issue["code"],
            issue["subject_type"],
            issue["subject_ref"],
            issue["path"],
            issue["related_refs"],
            issue["id"],
        ),
    )
    assert report["issues"][0]["related_refs"] == sorted(set(report["issues"][0]["related_refs"]))


def test_summary_and_status_are_consistent_for_errors_and_warnings_only() -> None:
    store = _store()
    store.edges.append(copy.deepcopy(store.edges[0]))
    warning_only = validate_graph_integrity(store)
    store.nodes["evidence:a"]["id"] = ""
    errors = validate_graph_integrity(store)

    assert warning_only["status"] == "valid"
    assert warning_only["summary"]["warning_count"] == 1
    assert errors["status"] == "invalid"
    assert errors["summary"]["issue_count"] == len(errors["issues"])
    assert errors["summary"]["error_count"] == sum(issue["severity"] == "error" for issue in errors["issues"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report.__setitem__("id", "graph_integrity_report:bad"),
        lambda report: report["summary"].__setitem__("issue_count", 99),
        lambda report: report["summary"].__setitem__("node_count", 99),
        lambda report: report["summary"].__setitem__("edge_count", 99),
        lambda report: report["summary"].__setitem__("audit_record_count", 99),
        lambda report: report["snapshot"].__setitem__("node_count", 99),
        lambda report: report["snapshot"].__setitem__("edge_count", 99),
        lambda report: report["snapshot"].__setitem__("audit_record_count", 99),
        lambda report: report["snapshot"].__setitem__("id", "graph_snapshot:bad"),
        lambda report: report["issues"][0].__setitem__("severity", "warning"),
        lambda report: report.__setitem__("issues", list(reversed(report["issues"]))),
    ],
)
def test_report_validator_rejects_tampering(mutate: Any) -> None:
    store = _store()
    store.nodes["evidence:a"]["id"] = ""
    store.edges[0]["to_node_id"] = "contribution:missing"
    report = validate_graph_integrity(store)
    changed = copy.deepcopy(report)
    mutate(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


def test_report_validator_rejects_snapshot_count_tamper_even_when_report_id_is_recalculated() -> None:
    report = validate_graph_integrity(_store())
    changed = copy.deepcopy(report)
    changed["snapshot"]["node_count"] = 99
    changed["id"] = graph_integrity_report_id(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


@pytest.mark.parametrize(
    "snapshot_id",
    [
        "graph_snapshot:bad",
        "graph_snapshot:" + ("a" * 63),
        "graph_snapshot:" + ("a" * 65),
        "graph_snapshot:" + ("a" * 63) + "g",
        "graph_snapshot:" + ("A" * 64),
        "graph_snapshot:" + ("a" * 64) + "extra",
        "graph_snapshot:",
    ],
)
def test_report_validator_rejects_non_canonical_snapshot_id_after_report_id_recalculation(snapshot_id: str) -> None:
    report = validate_graph_integrity(_store())
    changed = copy.deepcopy(report)
    changed["snapshot"]["id"] = snapshot_id
    _refresh_report_id(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


@pytest.mark.parametrize(
    "filters",
    [
        {"node_types": ["EvidenceNode", "EvidenceNode"], "severities": None},
        {"node_types": ["KnowledgeNode", "EvidenceNode"], "severities": None},
        {"node_types": None, "severities": ["error", "error"]},
        {"node_types": None, "severities": ["warning", "error"]},
    ],
)
def test_report_validator_rejects_non_canonical_filters_after_report_id_recalculation(
    filters: dict[str, list[str] | None],
) -> None:
    report = validate_graph_integrity(_store())
    changed = copy.deepcopy(report)
    changed["filters"] = filters
    _refresh_report_id(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


def test_empty_filters_remain_distinct_from_none() -> None:
    default = validate_graph_integrity(_store())
    empty = validate_graph_integrity(_store(), node_types=[], severities=[])

    assert default["filters"] == {"node_types": None, "severities": None}
    assert empty["filters"] == {"node_types": [], "severities": []}
    assert validate_graph_integrity_report(empty) is empty


def test_generated_canonical_filters_are_accepted() -> None:
    report = validate_graph_integrity(_store(), node_types=["EvidenceNode", "Contribution"], severities=["warning"])

    assert report["filters"] == {"node_types": ["Contribution", "EvidenceNode"], "severities": ["warning"]}
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize(
    "mutate",
    [
        lambda issue: issue.__setitem__("subject_ref", "SECRET subject"),
        lambda issue: issue.__setitem__("related_refs", ["SECRET related"]),
        lambda issue: issue.__setitem__("path", "nodes.SECRET customer"),
        lambda issue: issue.__setitem__("metadata", {"SECRET": "metadata"}),
    ],
)
def test_report_validator_rejects_arbitrary_issue_fields_after_ids_are_recalculated(mutate: Any) -> None:
    store = _store()
    store.nodes["evidence:a"]["id"] = ""
    report = validate_graph_integrity(store)
    changed = copy.deepcopy(report)
    issue = changed["issues"][0]
    mutate(issue)
    _refresh_issue_id(issue)
    _refresh_report_id(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


@pytest.mark.parametrize(
    "metadata",
    [
        {"duplicate_count": 2, "extra": "bad"},
        {"duplicate_count": True},
        {"duplicate_count": 1},
        {"duplicate_count": 0},
    ],
)
def test_report_validator_rejects_invalid_duplicate_edge_metadata(metadata: dict[str, Any]) -> None:
    store = _store()
    store.edges.append(copy.deepcopy(store.edges[0]))
    report = validate_graph_integrity(store)
    changed = copy.deepcopy(report)
    issue = _issue_for(changed, "DUPLICATE_EDGE")
    issue["metadata"] = metadata
    _refresh_issue_id(issue)
    _refresh_report_id(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


@pytest.mark.parametrize(
    ("code", "mutate", "store_mutate"),
    [
        (
            "NODE_ID_INVALID",
            lambda issue: issue.__setitem__("severity", "warning"),
            lambda store: store.nodes["evidence:a"].__setitem__("id", ""),
        ),
        (
            "DUPLICATE_EDGE",
            lambda issue: issue.__setitem__("severity", "error"),
            lambda store: store.edges.append(copy.deepcopy(store.edges[0])),
        ),
        (
            "AUDIT_TARGET_NOT_FOUND",
            lambda issue: issue.__setitem__("severity", "error"),
            lambda store: store.audit_records.__setitem__(0, _audit(f"evidence:{HASH}")),
        ),
        (
            "NODE_ID_INVALID",
            lambda issue: issue.__setitem__("subject_type", "audit_record"),
            lambda store: store.nodes["evidence:a"].__setitem__("id", ""),
        ),
        (
            "AUDIT_RESULT_INVALID",
            lambda issue: issue.__setitem__("subject_type", "edge"),
            lambda store: store.audit_records[0].__setitem__("result", ""),
        ),
        (
            "NODE_PROPERTIES_INVALID",
            lambda issue: issue.__setitem__("path", issue["path"].replace(".properties", ".created_at")),
            lambda store: store.nodes["evidence:a"].__setitem__("properties", []),
        ),
        (
            "EDGE_SOURCE_NOT_FOUND",
            lambda issue: issue.__setitem__("path", issue["path"].replace(".from_node_id", ".to_node_id")),
            lambda store: store.edges[0].__setitem__("from_node_id", f"evidence:{HASH}"),
        ),
        (
            "AUDIT_RESULT_INVALID",
            lambda issue: issue.__setitem__("path", issue["path"].replace(".result", ".metadata")),
            lambda store: store.audit_records[0].__setitem__("result", ""),
        ),
        (
            "EDGE_SOURCE_NOT_FOUND",
            lambda issue: issue.__setitem__("related_refs", []),
            lambda store: store.edges[0].__setitem__("from_node_id", f"evidence:{HASH}"),
        ),
        (
            "NODE_ID_INVALID",
            lambda issue: issue.__setitem__("related_refs", [f"evidence:{HASH}"]),
            lambda store: store.nodes["evidence:a"].__setitem__("id", ""),
        ),
        (
            "DUPLICATE_EDGE",
            lambda issue: issue.__setitem__("related_refs", []),
            lambda store: store.edges.append(copy.deepcopy(store.edges[0])),
        ),
        (
            "DUPLICATE_EDGE",
            lambda issue: issue.__setitem__(
                "related_refs", [f"contribution:{HASH}", f"evidence:{HASH}", f"knowledge:{HASH}"]
            ),
            lambda store: store.edges.append(copy.deepcopy(store.edges[0])),
        ),
    ],
)
def test_report_validator_rejects_issue_contract_mismatch_after_all_ids_are_recalculated(
    code: str,
    mutate: Any,
    store_mutate: Any,
) -> None:
    store = _store()
    store_mutate(store)
    changed = copy.deepcopy(validate_graph_integrity(store))
    issue = _issue_for(changed, code)
    mutate(issue)
    _refresh_after_issue_tamper(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


def test_duplicate_self_edge_with_one_related_ref_is_valid() -> None:
    node_id = f"evidence:{HASH}"
    store = JsonGraphStorage()
    store.nodes = {node_id: _node(node_id)}
    store.edges = [_edge("SELF", node_id, node_id), _edge("SELF", node_id, node_id)]

    report = validate_graph_integrity(store)
    issue = _issue_for(report, "DUPLICATE_EDGE")

    assert issue["related_refs"] == [node_id]
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize(
    ("code", "store_mutate", "new_path"),
    [
        (
            "NODE_ID_INVALID",
            lambda store: store.nodes.__setitem__(f"evidence:{HASH}", _node("")),
            f"nodes.knowledge:{OTHER_HASH}.id",
        ),
        (
            "EDGE_TYPE_INVALID",
            lambda store: store.edges[0].update({"id": f"edge:{HASH}", "edge_type": ""}),
            f"edges.edge:{OTHER_HASH}.edge_type",
        ),
        (
            "AUDIT_RESULT_INVALID",
            lambda store: store.audit_records[0].update({"id": f"audit:{HASH}", "result": ""}),
            f"audit_records.audit:{OTHER_HASH}.result",
        ),
    ],
)
def test_report_validator_rejects_path_ref_that_differs_from_subject_ref(
    code: str,
    store_mutate: Any,
    new_path: str,
) -> None:
    store = _store()
    store_mutate(store)
    changed = copy.deepcopy(validate_graph_integrity(store))
    issue = _issue_for(changed, code)
    issue["path"] = new_path
    _refresh_after_issue_tamper(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


@pytest.mark.parametrize(
    ("code", "store_mutate", "subject_ref", "path"),
    [
        (
            "NODE_ID_INVALID",
            lambda store: store.nodes.__setitem__(f"evidence:{HASH}", _node("")),
            f"audit:{HASH}",
            f"nodes.audit:{HASH}.id",
        ),
        (
            "NODE_ID_INVALID",
            lambda store: store.nodes.__setitem__(f"evidence:{HASH}", _node("")),
            f"edge:{HASH}",
            f"nodes.edge:{HASH}.id",
        ),
        (
            "EDGE_TYPE_INVALID",
            lambda store: store.edges[0].__setitem__("edge_type", ""),
            f"evidence:{HASH}",
            f"edges.evidence:{HASH}.edge_type",
        ),
        (
            "AUDIT_RESULT_INVALID",
            lambda store: store.audit_records[0].__setitem__("result", ""),
            f"evidence:{HASH}",
            f"audit_records.evidence:{HASH}.result",
        ),
    ],
)
def test_report_validator_rejects_subject_ref_prefix_incompatible_with_subject_type(
    code: str,
    store_mutate: Any,
    subject_ref: str,
    path: str,
) -> None:
    store = _store()
    store_mutate(store)
    changed = copy.deepcopy(validate_graph_integrity(store))
    issue = _issue_for(changed, code)
    issue["subject_ref"] = subject_ref
    issue["path"] = path
    _refresh_after_issue_tamper(changed)

    with pytest.raises(ValueError):
        validate_graph_integrity_report(changed)


def test_node_key_subject_ref_remains_valid() -> None:
    store = _store()
    store.nodes["unsafe key"] = []
    report = validate_graph_integrity(store)

    assert _issue_for(report, "NODE_NOT_OBJECT")["subject_ref"].startswith("node_key:")
    assert validate_graph_integrity_report(report) is report


def test_edge_and_audit_fallback_subject_refs_remain_valid() -> None:
    store = _store()
    store.edges[0]["id"] = "unsafe edge id"
    store.edges[0]["edge_type"] = ""
    store.audit_records[0]["id"] = "unsafe audit id"
    store.audit_records[0]["result"] = ""
    report = validate_graph_integrity(store)

    assert _issue_for(report, "EDGE_TYPE_INVALID")["subject_ref"].startswith("edge:")
    assert _issue_for(report, "AUDIT_RESULT_INVALID")["subject_ref"].startswith("audit:")
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize(
    "key",
    [
        f"audit:{HASH}",
        f"edge:{HASH}",
        f"graph_snapshot:{HASH}",
        f"graph_integrity_report:{HASH}",
    ],
)
def test_incompatible_structural_node_key_uses_node_key_fallback(key: str) -> None:
    store = _store()
    store.nodes[key] = []

    report = validate_graph_integrity(store)
    issue = _issue_for(report, "NODE_NOT_OBJECT")

    assert issue["subject_ref"].startswith("node_key:")
    assert issue["path"] == f"nodes.{issue['subject_ref']}"
    assert key not in json.dumps(issue, sort_keys=True)
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize(
    "edge_id", [f"evidence:{HASH}", f"audit:{HASH}", f"career_claim:{HASH}", f"graph_snapshot:{HASH}"]
)
def test_incompatible_structural_edge_id_uses_edge_fallback(edge_id: str) -> None:
    store = _store()
    store.edges[0]["id"] = edge_id
    store.edges[0]["edge_type"] = ""

    report = validate_graph_integrity(store)
    issue = _issue_for(report, "EDGE_TYPE_INVALID")

    assert issue["subject_ref"].startswith("edge:")
    assert issue["subject_ref"] != edge_id
    assert issue["path"] == f"edges.{issue['subject_ref']}.edge_type"
    assert validate_graph_integrity_report(report) is report


@pytest.mark.parametrize(
    "audit_id", [f"career_claim:{HASH}", f"edge:{HASH}", f"evidence:{HASH}", f"graph_snapshot:{HASH}"]
)
def test_incompatible_structural_audit_id_uses_audit_fallback(audit_id: str) -> None:
    store = _store()
    store.audit_records[0]["id"] = audit_id
    store.audit_records[0]["result"] = ""

    report = validate_graph_integrity(store)
    issue = _issue_for(report, "AUDIT_RESULT_INVALID")

    assert issue["subject_ref"].startswith("audit:")
    assert issue["subject_ref"] != audit_id
    assert issue["path"] == f"audit_records.{issue['subject_ref']}.result"
    assert validate_graph_integrity_report(report) is report


def test_incompatible_structural_edge_id_fallback_is_deterministic() -> None:
    first = _store()
    second = _store()
    first.edges = [{"id": f"evidence:{HASH}", "edge_type": "", "from_node_id": "bad", "to_node_id": "bad"}]
    second.edges = [{"to_node_id": "bad", "from_node_id": "bad", "edge_type": "", "id": f"evidence:{HASH}"}]

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_incompatible_structural_subject_refs_never_make_generated_report_invalid() -> None:
    store = _store()
    store.nodes[f"audit:{HASH}"] = []
    store.edges[0]["id"] = f"evidence:{HASH}"
    store.edges[0]["edge_type"] = ""
    store.audit_records[0]["id"] = f"career_claim:{HASH}"
    store.audit_records[0]["result"] = ""

    report = validate_graph_integrity(store)

    assert validate_graph_integrity_report(report) is report


def test_issue_contract_table_matches_issue_codes() -> None:
    assert set(ISSUE_CONTRACTS) == ISSUE_CODES


def test_all_generated_issue_contracts_are_accepted() -> None:
    store = _store()
    valid_analysis_store, contribution, accepted = _analysis_store()
    valid_claim_store, _, _, claim = _claim_store(evidence_count=2)
    store.nodes.update(copy.deepcopy(valid_analysis_store.nodes))
    store.nodes.update(copy.deepcopy(valid_claim_store.nodes))
    store.edges.extend(copy.deepcopy(valid_analysis_store.edges))
    store.edges.extend(copy.deepcopy(valid_claim_store.edges))
    store.audit_records.extend(copy.deepcopy(valid_analysis_store.audit_records))
    store.audit_records.extend(copy.deepcopy(valid_claim_store.audit_records))

    safe_evidence = f"evidence:{HASH}"
    extra_evidence = f"evidence:{OTHER_HASH}"
    wrong_ref = f"knowledge:{OTHER_HASH}"
    store.nodes[safe_evidence] = _node(safe_evidence)
    store.nodes[extra_evidence] = _node(extra_evidence)
    store.nodes[wrong_ref] = _node(wrong_ref, "KnowledgeNode")
    store.nodes[f"contribution:{HASH}"] = _node(f"contribution:{HASH}", "Contribution")
    store.nodes[f"contribution:{HASH}"]["properties"].update(
        title="",
        summary="",
        status="done",
        privacy_level="public",
        evidence_refs=[safe_evidence],
    )
    store.nodes[f"contribution:{OTHER_HASH}"] = _node(f"contribution:{OTHER_HASH}", "Contribution")
    store.nodes[f"contribution:{OTHER_HASH}"]["properties"]["evidence_refs"] = [f"evidence:{'c' * 64}"]
    store.nodes[f"contribution:{'c' * 64}"] = _node(f"contribution:{'c' * 64}", "Contribution")
    store.nodes[f"contribution:{'c' * 64}"]["properties"]["evidence_refs"] = [wrong_ref]
    store.nodes[f"contribution:{'d' * 64}"] = _node(f"contribution:{'d' * 64}", "Contribution")
    store.nodes[f"contribution:{'d' * 64}"]["properties"].update(
        evidence_refs=[],
        observation_refs=[],
        knowledge_refs=[],
        source_refs=[],
    )
    store.nodes[f"contribution:{'e' * 64}"] = _node(f"contribution:{'e' * 64}", "Contribution")
    store.nodes[f"contribution:{'e' * 64}"]["properties"].update(title="", summary="", evidence_refs=[safe_evidence])

    evidence_ref = accepted["properties"]["evidence_refs"][0]
    missing_edges = copy.deepcopy(accepted)
    missing_edges["id"] = "contribution_analysis:" + stable_hash("missing edges")
    missing_edges["properties"]["id"] = missing_edges["id"]
    store.nodes[missing_edges["id"]] = missing_edges

    bad_contract = copy.deepcopy(accepted)
    bad_contract["id"] = f"contribution_analysis:{OTHER_HASH}"
    bad_contract["properties"].update(
        {
            "id": f"contribution_analysis:{OTHER_HASH}",
            "status": "rejected",
            "privacy_level": "public",
            "confidence": "certain",
        }
    )
    store.nodes[bad_contract["id"]] = bad_contract

    missing_refs = copy.deepcopy(accepted)
    missing_refs["id"] = "contribution_analysis:" + stable_hash("missing refs")
    missing_refs["properties"].update(
        {
            "id": missing_refs["id"],
            "contribution_ref": f"contribution:{'f' * 64}",
            "evidence_refs": [f"evidence:{'f' * 64}"],
        }
    )
    store.nodes[missing_refs["id"]] = missing_refs

    type_invalid = copy.deepcopy(accepted)
    type_invalid["id"] = "contribution_analysis:" + stable_hash("type invalid")
    type_invalid["properties"].update(
        {
            "id": type_invalid["id"],
            "contribution_ref": evidence_ref,
            "evidence_refs": [contribution["id"]],
        }
    )
    store.nodes[type_invalid["id"]] = type_invalid

    invalid_refs = copy.deepcopy(accepted)
    invalid_refs["id"] = "contribution_analysis:" + stable_hash("invalid refs")
    invalid_refs["properties"].update(
        {"id": invalid_refs["id"], "contribution_ref": [], "evidence_refs": [SensitiveNonJsonValue()]}
    )
    store.nodes[invalid_refs["id"]] = invalid_refs

    claim_bad_contract = copy.deepcopy(claim)
    claim_bad_contract["id"] = "career_claim:" + stable_hash("bad claim contract")
    claim_bad_contract["properties"].update(
        status="rejected", privacy_level="public", confidence="certain", statement=""
    )
    store.nodes[claim_bad_contract["id"]] = claim_bad_contract

    claim_invalid_refs = copy.deepcopy(claim)
    claim_invalid_refs["id"] = "career_claim:" + stable_hash("invalid claim refs")
    claim_invalid_refs["properties"]["metadata"]["analysis_ref"] = []
    claim_invalid_refs["properties"]["metadata"]["supporting_signal_refs"] = [None]
    claim_invalid_refs["properties"]["contribution_refs"] = [[]]
    claim_invalid_refs["properties"]["evidence_refs"] = [SensitiveNonJsonValue()]
    store.nodes[claim_invalid_refs["id"]] = claim_invalid_refs

    claim_missing_refs = copy.deepcopy(claim)
    claim_missing_refs["id"] = "career_claim:" + stable_hash("missing claim refs")
    claim_missing_refs["properties"]["metadata"]["analysis_ref"] = f"contribution_analysis:{'f' * 64}"
    claim_missing_refs["properties"]["contribution_refs"] = [f"contribution:{'f' * 64}"]
    claim_missing_refs["properties"]["evidence_refs"] = [f"evidence:{'f' * 64}"]
    store.nodes[claim_missing_refs["id"]] = claim_missing_refs

    claim_type_invalid = copy.deepcopy(claim)
    claim_type_invalid["id"] = "career_claim:" + stable_hash("type invalid claim refs")
    claim_type_invalid["properties"]["metadata"]["analysis_ref"] = contribution["id"]
    claim_type_invalid["properties"]["contribution_refs"] = [claim["properties"]["evidence_refs"][0]]
    claim_type_invalid["properties"]["evidence_refs"] = [contribution["id"]]
    store.nodes[claim_type_invalid["id"]] = claim_type_invalid

    store.nodes["bad"] = []
    store.nodes[f"knowledge:{HASH}"] = _node(f"observation:{HASH}")
    store.nodes["evidence:a"]["id"] = ""
    store.nodes["contribution:a"]["node_type"] = ""
    store.nodes["contribution:a"]["created_at"] = "bad"
    store.nodes["contribution:a"]["properties"] = []
    store.edges = [
        [],
        {"edge_type": "", "from_node_id": "", "to_node_id": ""},
        _edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, f"contribution:{'c' * 64}", wrong_ref),
        _edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, f"contribution:{'d' * 64}", extra_evidence),
        _edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, f"contribution:{'e' * 64}", safe_evidence),
        _edge("MISSING", f"evidence:{'e' * 64}", f"contribution:{'f' * 64}"),
        _edge("DUP", f"evidence:{HASH}", f"contribution:{HASH}"),
        _edge("DUP", f"evidence:{HASH}", f"contribution:{HASH}"),
    ]
    store.edges.append(_edge(CONTRIBUTION_ANALYSIS_OF_CONTRIBUTION, accepted["id"], f"contribution:{OTHER_HASH}"))
    store.edges.append(_edge(CONTRIBUTION_ANALYSIS_SUPPORTED_BY_EVIDENCE, accepted["id"], f"evidence:{OTHER_HASH}"))
    store.edges = [
        edge for edge in store.edges if not isinstance(edge, dict) or edge.get("from_node_id") != claim["id"]
    ]
    store.edges.append(_edge(CAREER_CLAIM_DERIVED_FROM_ANALYSIS, claim["id"], accepted["id"]))
    store.edges.append(_edge(CAREER_CLAIM_FROM_CONTRIBUTION, claim["id"], f"contribution:{HASH}"))
    store.edges.append(_edge(CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, claim["id"], extra_evidence))
    store.audit_records = [
        [],
        {"audit_type": "", "created_at": "bad", "target_refs": [None], "result": "", "metadata": []},
        _audit(f"evidence:{HASH}", f"evidence:{HASH}"),
        _audit(f"evidence:{'e' * 64}"),
    ]

    report = validate_graph_integrity(store)
    generated_codes = set(_codes(report))
    for artifact_store in _professional_artifact_issue_stores():
        artifact_report = validate_graph_integrity(artifact_store)
        generated_codes.update(_codes(artifact_report))
        assert validate_graph_integrity_report(artifact_report) is artifact_report

    assert generated_codes == ISSUE_CODES
    assert validate_graph_integrity_report(report) is report


def test_generated_paths_and_fallback_refs_are_accepted_by_validator() -> None:
    store = _store()
    store.nodes["customer:SECRET"] = []
    store.edges[0]["from_node_id"] = "evidence:SECRET"

    report = validate_graph_integrity(store)

    assert validate_graph_integrity_report(report) is report


def test_non_json_values_use_safe_structural_identity_without_repr_content() -> None:
    first = _store()
    second = _store()
    first.nodes[SensitiveNonJsonValue()] = []
    second.nodes[SensitiveNonJsonValue()] = []

    first_report = validate_graph_integrity(first)
    second_report = validate_graph_integrity(second)
    report_json = json.dumps(first_report, sort_keys=True)

    assert first_report == second_report
    assert "SECRET" not in report_json
    assert str(id(next(key for key in first.nodes if not isinstance(key, str)))) not in report_json
    assert all(not issue["subject_ref"].startswith("<SensitiveNonJsonValue") for issue in first_report["issues"])
    assert "node_key:" in report_json


def test_invalid_string_node_key_is_hashed_in_subject_ref() -> None:
    store = _store()
    store.nodes["SECRET raw key"] = []
    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET raw key" not in report_json
    assert "node_key:" in report_json


@pytest.mark.parametrize("key", ["customer:SECRET markdown content", "customer:\nSECRET"])
def test_unsafe_textual_node_key_is_never_copied(key: str) -> None:
    store = _store()
    store.nodes[key] = []
    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert key not in report_json
    assert "node_key:" in report_json


def test_canonical_node_key_can_be_exposed_directly() -> None:
    ref = f"evidence:{HASH}"
    store = _store()
    store.nodes[ref] = []

    issue = _issue_for(validate_graph_integrity(store), "NODE_NOT_OBJECT")

    assert issue["subject_ref"] == ref
    assert issue["path"] == f"nodes.{ref}"


def test_structurally_equivalent_unsafe_text_node_keys_are_deterministic() -> None:
    first = _store()
    second = _store()
    first.nodes["customer:SECRET markdown content"] = []
    second.nodes["customer:SECRET markdown content"] = []

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_non_json_value_repr_secret_inside_valid_node_is_not_reported() -> None:
    store = _store()
    store.nodes["evidence:a"]["properties"]["bad"] = SensitiveNonJsonValue()
    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert "SensitiveNonJsonValue SECRET" not in report_json


@pytest.mark.parametrize("edge_id", ["SECRET customer markdown", "edge:\nSECRET"])
def test_unsafe_edge_id_is_never_copied(edge_id: str) -> None:
    store = _store()
    store.edges = [_edge()]
    store.edges[0]["id"] = edge_id
    store.edges[0]["edge_type"] = ""

    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert edge_id not in report_json


def test_canonical_edge_id_can_be_exposed_directly() -> None:
    ref = f"edge:{HASH}"
    store = _store()
    store.edges[0]["id"] = ref
    store.edges[0]["edge_type"] = ""

    issue = _issue_for(validate_graph_integrity(store), "EDGE_TYPE_INVALID")

    assert issue["subject_ref"] == ref


def test_edge_fallback_is_deterministic_and_dict_order_independent() -> None:
    first = JsonGraphStorage()
    second = JsonGraphStorage()
    first.edges = [{"id": "SECRET", "edge_type": "", "from_node_id": "bad", "to_node_id": "bad"}]
    second.edges = [{"to_node_id": "bad", "from_node_id": "bad", "edge_type": "", "id": "SECRET"}]

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


@pytest.mark.parametrize("audit_id", ["SECRET rejection reason", " audit:bad ", "audit:\nSECRET"])
def test_unsafe_audit_id_is_never_copied(audit_id: str) -> None:
    store = _store()
    store.audit_records = [_audit("evidence:a")]
    store.audit_records[0]["id"] = audit_id
    store.audit_records[0]["target_refs"] = [None]

    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert audit_id not in report_json


def test_canonical_audit_id_can_be_exposed_directly() -> None:
    ref = f"audit:{HASH}"
    store = _store()
    store.audit_records[0]["id"] = ref
    store.audit_records[0]["target_refs"] = [None]

    issue = _issue_for(validate_graph_integrity(store), "AUDIT_TARGET_REFS_INVALID")

    assert issue["subject_ref"] == ref


def test_audit_fallback_is_deterministic() -> None:
    first = _store()
    second = _store()
    first.audit_records[0]["id"] = "SECRET"
    second.audit_records[0] = {
        "metadata": {},
        "result": "accepted",
        "target_refs": ["contribution:a", "evidence:a"],
        "created_at": NOW,
        "audit_type": "reviewed",
        "actor": "system",
        "id": "SECRET",
    }

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_actor_does_not_change_snapshot_report_or_fallback_issue_identity() -> None:
    first = _store()
    second = _store()
    for store, actor in ((first, "SECRET actor one"), (second, "SECRET actor two")):
        store.audit_records[0]["id"] = "not-safe"
        store.audit_records[0]["actor"] = actor
        store.audit_records[0]["target_refs"] = [None]

    first_report = validate_graph_integrity(first)
    second_report = validate_graph_integrity(second)

    assert first_report["snapshot"]["id"] == second_report["snapshot"]["id"]
    assert first_report["id"] == second_report["id"]
    assert first_report["issues"] == second_report["issues"]
    assert "SECRET actor" not in json.dumps(first_report, sort_keys=True)


def test_non_json_sorting_is_not_based_on_memory_address() -> None:
    first = JsonGraphStorage()
    second = JsonGraphStorage()
    first.nodes = {SensitiveNonJsonValue(): [], "z": []}
    second.nodes = {"z": [], SensitiveNonJsonValue(): []}

    assert validate_graph_integrity(first) == validate_graph_integrity(second)


def test_invalid_audit_target_refs_do_not_skip_independent_envelope_validation() -> None:
    store = _store()
    store.audit_records = [_audit("evidence:a")]
    store.audit_records[0]["target_refs"] = [None]
    store.audit_records[0]["result"] = ""
    store.audit_records[0]["metadata"] = []
    before = _snapshot(store)

    report = validate_graph_integrity(store)

    assert "AUDIT_TARGET_REFS_INVALID" in _codes(report)
    assert "AUDIT_RESULT_INVALID" in _codes(report)
    assert "AUDIT_METADATA_INVALID" in _codes(report)
    assert "AUDIT_TARGET_NOT_FOUND" not in _codes(report)
    assert "AUDIT_TARGET_REFS_DUPLICATED" not in _codes(report)
    assert "AUDIT_TARGET_REFS_NOT_CANONICAL" not in _codes(report)
    assert _snapshot(store) == before


def test_execution_is_fully_read_only_even_with_invalid_data() -> None:
    store = _store()
    store.nodes["evidence:a"]["properties"] = []
    store.edges.append([])
    store.audit_records.append([])
    before = _snapshot(store)

    validate_graph_integrity(store)

    assert _snapshot(store) == before


def test_report_does_not_copy_sensitive_content() -> None:
    store = _store()
    secret = "SECRET customer markdown statement"
    store.nodes["evidence:a"]["properties"] = {"metadata": {"content": secret}, "statement": secret}
    store.nodes["evidence:a"]["created_at"] = "bad"
    store.audit_records[0]["metadata"] = {"reason": secret}

    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert secret not in report_json


def test_report_does_not_copy_secret_from_key_node_id_edge_endpoint_or_audit_target() -> None:
    store = _store()
    store.nodes["customer:SECRET key"] = {
        "id": "evidence:SECRET node id",
        "node_type": "EvidenceNode",
        "created_at": NOW,
        "properties": {},
    }
    store.edges[0]["from_node_id"] = "evidence:SECRET endpoint"
    store.audit_records[0]["target_refs"] = ["evidence:SECRET audit target"]

    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert "customer:SECRET key" not in report_json
    assert "evidence:SECRET node id" not in report_json
    assert "evidence:SECRET endpoint" not in report_json
    assert "evidence:SECRET audit target" not in report_json


def test_complete_claim_export_flow_shape_has_no_structural_false_positives() -> None:
    store, _, _, claim = _claim_store()
    ids = [
        ("artifact:a", "ProfessionalArtifact"),
        ("artifact_export_receipt:a", "ArtifactExportReceipt"),
    ]
    store.nodes.update({node_id: _node(node_id, node_type) for node_id, node_type in ids})
    store.edges.extend(
        [
            _edge("PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM", "artifact:a", claim["id"]),
            _edge("ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT", "artifact_export_receipt:a", "artifact:a"),
        ]
    )
    store.audit_records = [
        _audit("artifact_export_receipt:a", "claim_based_artifact_export_candidate:in-memory"),
    ]

    assert [code for code in _codes(validate_graph_integrity(store)) if code.startswith("CAREER_CLAIM_")] == []
