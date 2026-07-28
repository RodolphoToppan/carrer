import copy
import json
from pathlib import Path

import pytest

from carrer.ingestion.normalization import normalize_source_export
from carrer.ingestion.service import ingest_fixture, load_source_input
from carrer.ingestion.validation import validate_source_export_v1
from carrer.storage.json_graph_storage import JsonGraphStorage

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "characterization_source_export.json"


def _load_characterization_export() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_validation_accepts_valid_source_export_v1() -> None:
    export = _load_characterization_export()
    validate_source_export_v1(export)


def test_validation_rejects_invalid_format_payload_shape() -> None:
    export = {"format": "source_export_v2", "records": "not-a-list"}
    with pytest.raises(ValueError) as exc_info:
        validate_source_export_v1(export)

    assert "records must be a list" in str(exc_info.value)


def test_validation_rejects_missing_required_field() -> None:
    export = _load_characterization_export()
    del export["engineer"]["display_name"]

    with pytest.raises(ValueError) as exc_info:
        validate_source_export_v1(export)

    assert "missing engineer field: display_name" in str(exc_info.value)


def test_validation_rejects_invalid_entity_type() -> None:
    export = _load_characterization_export()
    export["records"][0]["source_entity_type"] = "unsupported_entity"

    with pytest.raises(ValueError) as exc_info:
        validate_source_export_v1(export)

    assert "unsupported source_entity_type" in str(exc_info.value)


def test_validation_rejects_invalid_privacy_level() -> None:
    export = _load_characterization_export()
    export["records"][0]["privacy_level"] = "top_secret"

    with pytest.raises(ValueError) as exc_info:
        validate_source_export_v1(export)

    assert "unsupported privacy_level" in str(exc_info.value)


def test_normalization_is_deterministic_for_equivalent_input() -> None:
    export = _load_characterization_export()
    variant = copy.deepcopy(export)
    variant["records"][0]["type"] = variant["records"][0].pop("source_entity_type")

    normalized_a = normalize_source_export(export)
    normalized_b = normalize_source_export(variant)

    assert normalized_a == normalized_b


def test_normalization_preserves_payload_without_unwanted_changes() -> None:
    export = _load_characterization_export()
    raw_payload = copy.deepcopy(export["records"][0]["payload"])

    normalized = normalize_source_export(export)
    normalized_payload = normalized["records"][0]["payload"]

    assert normalized_payload["title"] == raw_payload["title"]
    assert normalized_payload["description"] == raw_payload["description"]
    assert normalized_payload["state"] == raw_payload["state"]


def test_normalization_keeps_only_explicit_domain_and_technologies() -> None:
    export = _load_characterization_export()
    export["records"][0]["payload"] = {
        "title": "Python integration for order processing",
        "description": "Implement API and webhook workflow for marketplace orders",
        "technologies": ["Python", "python", "REST APIs", "REST APIs"],
        "domain": "",
    }

    normalized = normalize_source_export(export)
    normalized_payload = normalized["records"][0]["payload"]

    # Ingestion normalization is structural: no semantic inference from text.
    assert normalized_payload["technologies"] == ["Python", "REST APIs"]
    assert "domain" not in normalized_payload


def test_normalization_applies_current_optional_field_defaults() -> None:
    export = _load_characterization_export()
    export["records"][0].pop("privacy_level", None)

    normalized = normalize_source_export(export)

    assert normalized["records"][0]["privacy_level"] == "artifact_safe"


def test_ingestion_creates_and_reuses_engineer_source_identity_and_evidence() -> None:
    fixture = load_source_input(FIXTURE_PATH)
    store = JsonGraphStorage()

    first = ingest_fixture(fixture, store)
    second = ingest_fixture(fixture, store)

    assert first == {"records_created": 11, "records_reused": 1}
    assert second == {"records_created": 0, "records_reused": 12}
    assert len(store.nodes_by_type("Engineer")) == 1
    assert len(store.nodes_by_type("SourceIdentity")) == 1
    assert len(store.nodes_by_type("Source")) == 1


def test_ingestion_preserves_entity_change_behavior_and_dedup_contract() -> None:
    fixture = load_source_input(FIXTURE_PATH)
    store = JsonGraphStorage()

    ingest_fixture(fixture, store)

    commit_nodes = [
        node for node in store.nodes_by_type("EvidenceNode") if node["properties"]["source_entity_id"] == "abc123def456"
    ]
    assert len(commit_nodes) == 2
    assert len({node["properties"]["content_hash"] for node in commit_nodes}) == 2


def test_ingestion_preserves_evidence_relationships() -> None:
    fixture = {
        "captured_at": "2026-01-01T00:00:00Z",
        "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
        "source": {"id": "azure", "type": "azure_devops_export", "name": "Azure", "visibility": "private"},
        "records": [
            {
                "type": "work_item",
                "external_id": "ADO-WI-1",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {
                    "title": "Child card",
                    "relationships": [{"type": "System.LinkTypes.Hierarchy-Reverse", "external_id": "ADO-WI-2"}],
                },
            },
            {
                "type": "work_item",
                "external_id": "ADO-WI-2",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {"title": "Parent feature"},
            },
        ],
    }
    store = JsonGraphStorage()

    ingest_fixture(fixture, store)

    edges = [edge for edge in store.edges if edge["edge_type"] == "EVIDENCE_RELATED_TO_EVIDENCE"]
    assert len(edges) == 1
    assert edges[0]["properties"]["source_relation_type"] == "System.LinkTypes.Hierarchy-Reverse"


def test_ingestion_preserves_privacy_level() -> None:
    fixture = load_source_input(FIXTURE_PATH)
    store = JsonGraphStorage()

    ingest_fixture(fixture, store)

    levels = {node["properties"]["privacy_level"] for node in store.nodes_by_type("EvidenceNode")}
    assert {"private", "internal", "artifact_safe"}.issubset(levels)


def test_ingestion_identity_is_stable_for_payload_key_order() -> None:
    fixture = {
        "captured_at": "2026-01-01T00:00:00Z",
        "engineer": {"id": "engineer-1", "display_name": "Rodolpho", "primary_email_hash": "hash"},
        "source": {"id": "gitlab", "type": "gitlab_user_api", "name": "GitLab", "visibility": "private"},
        "records": [
            {
                "type": "commit",
                "external_id": "C-1",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {"message": "Fix bug", "branch": "main"},
            },
            {
                "type": "commit",
                "external_id": "C-1",
                "occurred_at": "2026-01-01T00:00:00Z",
                "privacy_level": "internal",
                "payload": {"branch": "main", "message": "Fix bug"},
            },
        ],
    }
    store = JsonGraphStorage()

    result = ingest_fixture(fixture, store)

    assert result == {"records_created": 1, "records_reused": 1}
