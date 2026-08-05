from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from carrer.contributions import create_contribution, promote_contribution_candidate
from carrer.contributions.candidates import contribution_candidate
from carrer.contributions.service import CONTRIBUTION_SUPPORTED_BY_EVIDENCE
from carrer.domain.hashing import stable_hash
from carrer.domain.models import evidence_node
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


def _codes(report: dict[str, Any]) -> list[str]:
    return [issue["code"] for issue in report["issues"]]


def _snapshot(store: JsonGraphStorage) -> dict[str, Any]:
    return copy.deepcopy({"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records})


def _report_ids(store: JsonGraphStorage) -> tuple[str, str]:
    report = validate_graph_integrity(store)
    return report["snapshot"]["id"], report["id"]


def _api_contribution_store() -> tuple[JsonGraphStorage, dict[str, Any], dict[str, Any]]:
    store = JsonGraphStorage()
    evidence = evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id="C-1",
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        payload={"message": "safe"},
    )
    store.create_node(evidence)
    contribution = create_contribution(
        store,
        contribution_type="feature_delivery",
        created_at=NOW,
        title="Safe contribution",
        evidence_refs=[evidence["id"]],
    )["contribution"]
    return store, contribution, evidence


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


def test_contribution_invalid_evidence_refs_type_reports_provenance_refs_invalid() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["evidence_refs"] = [object()]

    report = validate_graph_integrity(store)
    report_json = json.dumps(report, sort_keys=True)

    assert "CONTRIBUTION_PROVENANCE_REFS_INVALID" in _codes(report)
    assert "object at" not in report_json
    assert validate_graph_integrity_report(report) is report


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
    assert "builtins.object" not in report_json
    assert validate_graph_integrity_report(report) is report


def test_contribution_status_invalid_with_residual_confidence_error() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["status"] = "done"
    contribution["properties"]["confidence"] = "certain"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_STATUS_INVALID" in codes
    assert "CONTRIBUTION_PROPERTIES_INVALID" in codes


def test_contribution_privacy_invalid_with_residual_missing_title_or_summary() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["privacy_level"] = "public"
    contribution["properties"]["title"] = ""
    contribution["properties"]["summary"] = ""

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_PRIVACY_INVALID" in codes
    assert "CONTRIBUTION_PROPERTIES_INVALID" in codes


def test_contribution_provenance_invalid_with_residual_timestamp_error() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["evidence_refs"] = [object()]
    contribution["properties"]["started_at"] = "not-a-date"

    codes = _codes(validate_graph_integrity(store))

    assert "CONTRIBUTION_PROVENANCE_REFS_INVALID" in codes
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
    extra = evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id="C-2",
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        payload={"message": "safe extra"},
    )
    store.create_node(extra)
    store.create_edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], extra["id"])

    issue = _issue_for(validate_graph_integrity(store), "CONTRIBUTION_EVIDENCE_EDGE_UNDECLARED")

    assert issue["severity"] == "warning"
    assert issue["related_refs"] == [extra["id"]]


def test_contribution_multiple_valid_evidence_refs_have_no_semantic_issues() -> None:
    store = JsonGraphStorage()
    first = evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id="C-1",
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        payload={"message": "one"},
    )
    second = evidence_node(
        source_id="test",
        source_entity_type="commit",
        source_entity_id="C-2",
        evidence_type="COMMIT_EXISTS",
        captured_at=NOW,
        payload={"message": "two"},
    )
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


def test_contribution_semantic_report_ignores_store_order_and_stays_json_serializable() -> None:
    first, contribution, _ = _api_contribution_store()
    first.edges = []
    second = JsonGraphStorage()
    second.nodes = dict(reversed(list(copy.deepcopy(first.nodes).items())))
    second.edges = list(reversed(copy.deepcopy(first.edges)))
    second.audit_records = list(reversed(copy.deepcopy(first.audit_records)))

    first_report = validate_graph_integrity(first)
    second_report = validate_graph_integrity(second)

    assert first_report == second_report
    assert json.loads(json.dumps(first_report)) == first_report
    assert contribution["id"] in first.nodes


def test_contribution_semantic_rules_are_read_only_and_respect_filters() -> None:
    store, contribution, _ = _api_contribution_store()
    contribution["properties"]["status"] = "done"
    before = _snapshot(store)

    skipped = validate_graph_integrity(store, node_types=["EvidenceNode"])
    selected = validate_graph_integrity(store, node_types=["Contribution"])
    warnings = validate_graph_integrity(store, severities=["warning"])

    assert "CONTRIBUTION_STATUS_INVALID" not in _codes(skipped)
    assert "CONTRIBUTION_STATUS_INVALID" in _codes(selected)
    assert warnings["issues"] == []
    assert _snapshot(store) == before


def test_contribution_semantic_warning_respects_severity_filter() -> None:
    store, contribution, _ = _api_contribution_store()
    extra = f"evidence:{HASH}"
    store.nodes[extra] = _node(extra, "EvidenceNode")
    store.edges.append(_edge(CONTRIBUTION_SUPPORTED_BY_EVIDENCE, contribution["id"], extra))

    report = validate_graph_integrity(store, severities=["warning"])

    assert _codes(report) == ["CONTRIBUTION_EVIDENCE_EDGE_UNDECLARED"]
    assert report["status"] == "valid"


def test_contribution_semantic_issues_do_not_copy_sensitive_content() -> None:
    store, contribution, _ = _api_contribution_store()
    secret = "SECRET customer title and actor"
    contribution["properties"]["title"] = secret
    contribution["properties"]["status"] = "done"
    contribution["properties"]["evidence_refs"] = ["evidence:SECRET unsafe"]
    store.audit_records[0]["actor"] = secret
    store.edges = []

    report_json = json.dumps(validate_graph_integrity(store), sort_keys=True)

    assert "SECRET" not in report_json
    assert secret not in report_json


def test_contribution_issue_id_ignores_sensitive_invalid_values_until_structure_changes() -> None:
    first, first_contribution, _ = _api_contribution_store()
    second = copy.deepcopy(first)
    first_contribution["properties"]["status"] = "SECRET one"
    second_contribution = next(node for node in second.nodes.values() if node.get("node_type") == "Contribution")
    second_contribution["properties"]["status"] = "SECRET two"

    first_issue = _issue_for(validate_graph_integrity(first), "CONTRIBUTION_STATUS_INVALID")
    second_issue = _issue_for(validate_graph_integrity(second), "CONTRIBUTION_STATUS_INVALID")

    assert first_issue["id"] == second_issue["id"]


def test_contributions_generated_by_current_apis_have_no_semantic_false_positives() -> None:
    store, _, evidence = _api_contribution_store()
    candidate = contribution_candidate(
        candidate_type="change_delivery",
        title="Promoted contribution",
        evidence_refs=[evidence["id"]],
        source_refs=[],
        confidence="medium",
        status="proposed",
        privacy_level="artifact_safe",
        started_at=NOW,
        ended_at=NOW,
        signals=["commit"],
        reasons=["explicit_evidence_relationship"],
        metadata={"evidence_count": 1},
    )

    promote_contribution_candidate(store, candidate, created_at=NOW, decision_actor="human")

    assert [code for code in _codes(validate_graph_integrity(store)) if code.startswith("CONTRIBUTION_")] == []


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
    safe_evidence = f"evidence:{HASH}"
    extra_evidence = f"evidence:{OTHER_HASH}"
    wrong_ref = f"knowledge:{OTHER_HASH}"
    store.nodes["bad"] = []
    store.nodes[f"knowledge:{HASH}"] = _node(f"observation:{HASH}")
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
        evidence_refs=[], observation_refs=[], knowledge_refs=[], source_refs=[]
    )
    store.nodes[f"contribution:{'e' * 64}"] = _node(f"contribution:{'e' * 64}", "Contribution")
    store.nodes[f"contribution:{'e' * 64}"]["properties"].update(title="", summary="", evidence_refs=[safe_evidence])
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
    store.audit_records = [
        [],
        {"audit_type": "", "created_at": "bad", "target_refs": [None], "result": "", "metadata": []},
        _audit(f"evidence:{HASH}", f"evidence:{HASH}"),
        _audit(f"evidence:{'e' * 64}"),
    ]

    report = validate_graph_integrity(store)

    assert set(_codes(report)) == ISSUE_CODES
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
    store = JsonGraphStorage()
    ids = [
        ("evidence:a", "EvidenceNode"),
        ("contribution:a", "Contribution"),
        ("contribution_analysis:a", "ContributionAnalysis"),
        ("career_claim:a", "CareerClaim"),
        ("artifact:a", "ProfessionalArtifact"),
        ("artifact_export_receipt:a", "ArtifactExportReceipt"),
    ]
    store.nodes = {node_id: _node(node_id, node_type) for node_id, node_type in ids}
    store.edges = [
        _edge("CONTRIBUTION_SUPPORTED_BY_EVIDENCE", "contribution:a", "evidence:a"),
        _edge("CONTRIBUTION_ANALYSIS_FOR_CONTRIBUTION", "contribution_analysis:a", "contribution:a"),
        _edge("CAREER_CLAIM_FROM_ANALYSIS", "career_claim:a", "contribution_analysis:a"),
        _edge("PROFESSIONAL_ARTIFACT_DERIVED_FROM_CLAIM", "artifact:a", "career_claim:a"),
        _edge("ARTIFACT_EXPORT_RECEIPT_FOR_ARTIFACT", "artifact_export_receipt:a", "artifact:a"),
    ]
    store.audit_records = [
        _audit("artifact_export_receipt:a", "claim_based_artifact_export_candidate:in-memory"),
    ]

    assert validate_graph_integrity(store)["issues"] == []
