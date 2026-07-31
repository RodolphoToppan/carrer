from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from career_intelligence_mvp import run_pipeline
from carrer.artifacts import (
    build_artifact_from_career_claims,
    build_artifact_from_claim_nodes,
    claim_based_artifact,
    claim_based_artifact_id,
    render_claim_based_artifact_markdown,
    validate_claim_based_artifact,
)
from carrer.claims import accept_career_claim_candidate, generate_career_claim_candidates
from carrer.claims.review import CAREER_CLAIM_SUPPORTED_BY_EVIDENCE, validate_persisted_career_claim
from carrer.contributions import accept_contribution_analysis, analyze_contribution, create_contribution
from carrer.domain.models import evidence_node, knowledge_node
from carrer.storage.json_graph_storage import JsonGraphStorage

NOW = "2026-01-02T03:04:05+00:00"


def _evidence(
    entity_type: str,
    entity_id: str,
    *,
    privacy_level: str = "artifact_safe",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_type = {
        "commit": "COMMIT_EXISTS",
        "merge_request": "MERGE_REQUEST_EXISTS",
        "work_item": "WORK_ITEM_EXISTS",
    }[entity_type]
    return evidence_node(
        source_id="test",
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type=evidence_type,
        captured_at=NOW,
        occurred_at=NOW,
        privacy_level=privacy_level,
        metadata=metadata or {},
    )


def _store(*, privacy_level: str = "artifact_safe") -> tuple[JsonGraphStorage, list[dict[str, Any]]]:
    store = JsonGraphStorage()
    nodes = [
        _evidence("commit", "C-1", privacy_level=privacy_level, metadata={"latency_after_ms": 300}),
        _evidence("merge_request", "MR-1", privacy_level=privacy_level, metadata={"state": "merged"}),
        _evidence("work_item", "WI-1", privacy_level=privacy_level, metadata={"state": "closed"}),
    ]
    for node in reversed(nodes):
        store.create_node(node)
    contribution = create_contribution(
        store,
        contribution_type="incident_fix",
        created_at=NOW,
        title="Retry fix",
        evidence_refs=[node["id"] for node in nodes],
        actions=["reviewed retry behavior"],
        outcomes=["bug resolved"],
        privacy_level=privacy_level,
    )["contribution"]
    analysis = analyze_contribution(store, contribution["id"])
    accepted = accept_contribution_analysis(store, analysis, decision_actor="human", decided_at=NOW)["analysis"]
    claims = [
        accept_career_claim_candidate(store, candidate, decision_actor="human", decided_at=NOW)["claim"]
        for candidate in generate_career_claim_candidates(store, accepted["id"])
    ]
    return store, sorted(claims, key=lambda claim: claim["id"])


def _snapshot(store: JsonGraphStorage) -> str:
    return json.dumps(
        {"nodes": store.nodes, "edges": store.edges, "audit_records": store.audit_records},
        sort_keys=True,
    )


def test_package_exports_legacy_and_claim_based_symbols_directly() -> None:
    from carrer.artifacts import (
        artifact_markdown,
        artifact_traceability,
        build_render_validate_trace,
        generate_linkedin_draft,
        generate_resume_draft,
        generate_skill_matrix,
        linkedin_markdown,
        resume_markdown,
        validate_artifact,
    )

    assert generate_skill_matrix
    assert generate_resume_draft
    assert generate_linkedin_draft
    assert artifact_markdown
    assert resume_markdown
    assert linkedin_markdown
    assert validate_artifact
    assert artifact_traceability
    assert build_render_validate_trace
    assert build_artifact_from_career_claims
    assert claim_based_artifact


def test_builds_resume_claim_artifact_read_only_with_traceability_and_deterministic_id() -> None:
    store, claims = _store()
    claim_ids = [claims[1]["id"], claims[0]["id"]]
    before = _snapshot(store)

    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=claim_ids,
        artifact_type="resume_claims",
        audience="public",
        created_at="2026-01-03T00:00:00Z",
    )
    again = build_artifact_from_career_claims(
        store,
        claim_ids=list(reversed(claim_ids)),
        artifact_type="resume_claims",
        audience="public",
        created_at="2026-01-03T00:00:00-03:00",
    )

    assert _snapshot(store) == before
    assert artifact["id"] == again["id"]
    assert artifact["id"] == claim_based_artifact_id("resume_claims", "public", claim_ids)
    assert artifact["created_at"] == "2026-01-03T00:00:00Z"
    assert artifact["privacy_level"] == "artifact_safe"
    assert artifact["metadata"] == {
        "artifact_version": "v1",
        "source_type": "career_claim",
        "claim_count": 2,
        "claim_types": sorted({claim["properties"]["claim_type"] for claim in claims[:2]}),
    }
    assert [item["text"] for item in artifact["items"]] == [
        claim["properties"]["statement"]
        for claim in sorted(claims[:2], key=lambda claim: (claim["properties"]["claim_type"], claim["id"]))
    ]
    first_trace = artifact["items"][0]["traceability"]
    assert first_trace["claim_ref"] == artifact["items"][0]["claim_ref"]
    assert first_trace["candidate_ref"]
    assert first_trace["analysis_ref"]
    assert first_trace["contribution_ref"]
    assert first_trace["evidence_refs"]
    assert first_trace["supporting_fact_refs"] or first_trace["supporting_signal_refs"]
    assert artifact["traceability"]["claim_refs"] == sorted(claim_ids)
    assert validate_claim_based_artifact(artifact) is artifact


def test_linkedin_rendering_preserves_statement_order_and_newline() -> None:
    store, claims = _store()
    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claims[0]["id"]],
        artifact_type="linkedin_claims",
        audience="public",
        created_at="2026-01-03T00:00:00+02:00",
    )
    before = copy.deepcopy(artifact)

    markdown = render_claim_based_artifact_markdown(artifact)

    assert markdown == f"# Selected Career Claims\n\n- {artifact['items'][0]['text']}\n"
    assert artifact == before
    assert artifact["warnings"] == sorted({"single_claim_artifact", "claim_has_candidate_warnings"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("claim_ids", "not-list", "claim_ids"),
        ("claim_ids", [], "claim_ids"),
        ("claim_ids", [""], "claim_ids"),
        ("artifact_type", "resume", "artifact_type"),
        ("artifact_type", [], "artifact_type"),
        ("audience", "friends", "audience"),
        ("audience", {}, "audience"),
        ("created_at", "not-a-date", "created_at"),
        ("created_at", "2026-01-03T00:00:00", "created_at"),
    ],
)
def test_store_api_validates_public_arguments(field: str, value: object, message: str) -> None:
    store, claims = _store()
    kwargs: dict[str, Any] = {
        "claim_ids": [claims[0]["id"]],
        "artifact_type": "resume_claims",
        "audience": "public",
        "created_at": "2026-01-03T00:00:00Z",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=message):
        build_artifact_from_career_claims(store, **kwargs)


def test_duplicate_missing_wrong_type_and_invalid_claim_fail() -> None:
    store, claims = _store()
    with pytest.raises(ValueError, match="deduplicated"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[claims[0]["id"], claims[0]["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="not found"):
        build_artifact_from_career_claims(
            store,
            claim_ids=["career_claim:missing"],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )
    wrong = knowledge_node(
        knowledge_type="TECHNOLOGY_EXPERIENCE",
        statement="Python",
        created_at=NOW,
        evidence_refs=claims[0]["properties"]["evidence_refs"],
    )
    store.create_node(wrong)
    with pytest.raises(ValueError, match="CareerClaim"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[wrong["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )
    store.nodes[claims[0]["id"]]["properties"]["status"] = "rejected"
    with pytest.raises(ValueError, match="accepted"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[claims[0]["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )


def test_provenance_edges_targets_and_refs_are_revalidated() -> None:
    store, claims = _store()
    claim = claims[0]
    store.edges = [
        edge
        for edge in store.edges
        if not (
            edge["edge_type"] == CAREER_CLAIM_SUPPORTED_BY_EVIDENCE
            and edge["from_node_id"] == claim["id"]
            and edge["to_node_id"] == claim["properties"]["evidence_refs"][0]
        )
    ]
    with pytest.raises(ValueError, match="provenance edges"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[claim["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )

    store, claims = _store()
    claim = claims[0]
    target = claim["properties"]["metadata"]["analysis_ref"]
    store.nodes[target]["node_type"] = "KnowledgeNode"
    with pytest.raises(ValueError, match="ContributionAnalysis"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[claim["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )


def test_privacy_by_audience_is_all_or_fail_and_never_mutates_claim_privacy() -> None:
    store, claims = _store(privacy_level="internal")
    before_privacy = claims[0]["properties"]["privacy_level"]

    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claims[0]["id"]],
        artifact_type="resume_claims",
        audience="internal",
        created_at=NOW,
    )

    assert artifact["privacy_level"] == "internal"
    assert store.nodes[claims[0]["id"]]["properties"]["privacy_level"] == before_privacy
    with pytest.raises(ValueError, match="privacy is incompatible"):
        build_artifact_from_career_claims(
            store,
            claim_ids=[claims[0]["id"]],
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
        )

    private_store, private_claims = _store(privacy_level="private")
    with pytest.raises(ValueError, match="privacy is incompatible"):
        build_artifact_from_career_claims(
            private_store,
            claim_ids=[private_claims[0]["id"]],
            artifact_type="resume_claims",
            audience="internal",
            created_at=NOW,
        )


def test_pure_contract_and_renderer_enforce_privacy_by_audience() -> None:
    store, claims = _store()
    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claims[0]["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    item = copy.deepcopy(artifact["items"][0])

    exported_item = copy.deepcopy(item)
    exported_item["privacy_level"] = "exported"
    assert (
        claim_based_artifact(
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
            items=[exported_item],
        )["privacy_level"]
        == "exported"
    )

    internal_item = copy.deepcopy(item)
    internal_item["privacy_level"] = "internal"
    assert (
        claim_based_artifact(
            artifact_type="resume_claims",
            audience="internal",
            created_at=NOW,
            items=[internal_item],
        )["privacy_level"]
        == "internal"
    )
    with pytest.raises(ValueError, match="privacy is incompatible"):
        claim_based_artifact(
            artifact_type="resume_claims",
            audience="public",
            created_at=NOW,
            items=[internal_item],
        )

    private_item = copy.deepcopy(item)
    private_item["privacy_level"] = "private"
    with pytest.raises(ValueError, match="privacy is incompatible"):
        claim_based_artifact(
            artifact_type="resume_claims",
            audience="internal",
            created_at=NOW,
            items=[private_item],
        )

    tampered = copy.deepcopy(artifact)
    tampered["items"][0]["privacy_level"] = "internal"
    with pytest.raises(ValueError, match="privacy is incompatible"):
        validate_claim_based_artifact(tampered)
    with pytest.raises(ValueError, match="privacy is incompatible"):
        render_claim_based_artifact_markdown(tampered)


@pytest.mark.parametrize("privacy_level", [[], {}, 1, None])
def test_validation_and_rendering_reject_non_string_artifact_privacy_level(privacy_level: object) -> None:
    store, claims = _store()
    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claims[0]["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    artifact["privacy_level"] = privacy_level

    with pytest.raises(ValueError, match="privacy_level"):
        validate_claim_based_artifact(artifact)
    with pytest.raises(ValueError, match="privacy_level"):
        render_claim_based_artifact_markdown(artifact)


@pytest.mark.parametrize(
    ("artifact_type", "audience", "message"),
    [
        ([], "public", "artifact_type"),
        ("resume_claims", {}, "audience"),
    ],
)
def test_pure_public_apis_reject_non_string_artifact_type_and_audience(
    artifact_type: object, audience: object, message: str
) -> None:
    _, claims = _store()
    with pytest.raises(ValueError, match=message):
        build_artifact_from_claim_nodes(
            [claims[0]],
            artifact_type=artifact_type,  # type: ignore[arg-type]
            audience=audience,  # type: ignore[arg-type]
            created_at=NOW,
        )
    item = build_artifact_from_claim_nodes(
        [claims[0]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )["items"][0]
    with pytest.raises(ValueError, match=message):
        claim_based_artifact(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            audience=audience,  # type: ignore[arg-type]
            created_at=NOW,
            items=[item],
        )
    with pytest.raises(ValueError, match=message):
        claim_based_artifact_id(
            artifact_type,  # type: ignore[arg-type]
            audience,  # type: ignore[arg-type]
            [claims[0]["id"]],
        )


def test_warnings_are_structured_ordered_and_do_not_copy_candidate_warning_text() -> None:
    store, claims = _store()
    selected = [
        next(claim for claim in claims if claim["properties"]["claim_type"] == "metric_observed"),
        next(claim for claim in claims if claim["properties"]["claim_type"] == "work_performed"),
    ]

    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claim["id"] for claim in selected],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )

    assert artifact["warnings"] == sorted(
        {"claim_has_candidate_warnings", "contains_metric_observation", "mixed_claim_types"}
    )
    assert "metric_is_observation_not_impact" not in json.dumps(artifact)
    assert "Observed latency metric: 300 ms." in [item["text"] for item in artifact["items"]]


def test_validation_recalculates_warnings_for_metric_single_candidate_and_mixed_claims() -> None:
    store, claims = _store()
    metric = next(claim for claim in claims if claim["properties"]["claim_type"] == "metric_observed")
    work = next(claim for claim in claims if claim["properties"]["claim_type"] == "work_performed")

    single = build_artifact_from_career_claims(
        store,
        claim_ids=[metric["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    assert single["warnings"] == sorted(
        {"claim_has_candidate_warnings", "contains_metric_observation", "single_claim_artifact"}
    )
    for changed_warnings in ([], ["contains_metric_observation"], [*single["warnings"], "mixed_claim_types"]):
        changed = copy.deepcopy(single)
        changed["warnings"] = changed_warnings
        with pytest.raises(ValueError, match="warnings"):
            validate_claim_based_artifact(changed)
        with pytest.raises(ValueError, match="warnings"):
            render_claim_based_artifact_markdown(changed)

    mixed = build_artifact_from_career_claims(
        store,
        claim_ids=[metric["id"], work["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    assert mixed["warnings"] == sorted(
        {"claim_has_candidate_warnings", "contains_metric_observation", "mixed_claim_types"}
    )


def test_claim_based_artifact_id_validates_claim_refs_without_changing_order_independence() -> None:
    first = claim_based_artifact_id("resume_claims", "public", ["claim:b", "claim:a"])
    second = claim_based_artifact_id("resume_claims", "public", ("claim:a", "claim:b"))

    assert first == second
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", "claim:a")
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", [])
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", ["claim:a", "claim:a"])
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", ["claim:a", ""])
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", 123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="claim_refs"):
        claim_based_artifact_id("resume_claims", "public", object())  # type: ignore[arg-type]


def test_pure_api_validates_claims_and_matches_store_api() -> None:
    store, claims = _store()
    selected = claims[:2]

    from_store = build_artifact_from_career_claims(
        store,
        claim_ids=[claim["id"] for claim in selected],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    pure = build_artifact_from_claim_nodes(
        list(reversed(selected)),
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )

    assert pure == from_store
    bad = copy.deepcopy(selected[0])
    bad["id"] = "career_claim:other"
    with pytest.raises(ValueError, match="identity|envelope"):
        build_artifact_from_claim_nodes([bad], artifact_type="resume_claims", audience="public", created_at=NOW)


def test_validation_rejects_unstable_or_mutated_contract() -> None:
    store, claims = _store()
    artifact = build_artifact_from_career_claims(
        store,
        claim_ids=[claims[0]["id"]],
        artifact_type="resume_claims",
        audience="public",
        created_at=NOW,
    )
    changed = copy.deepcopy(artifact)
    changed["id"] = "claim_based_artifact:other"
    with pytest.raises(ValueError, match="identity"):
        validate_claim_based_artifact(changed)

    changed = copy.deepcopy(artifact)
    changed["items"][0]["text"] = ""
    with pytest.raises(ValueError, match="text"):
        render_claim_based_artifact_markdown(changed)


def test_compatibility_legacy_pipeline_review_and_artifacts_stay_separate() -> None:
    store, claims = _store()
    assert validate_persisted_career_claim(claims[0]) is claims[0]

    pipeline_store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")
    assert pipeline_store.nodes_by_type("CareerClaim") == []
    assert pipeline_store.nodes_by_type("ClaimBasedArtifact") == []
    assert pipeline_store.nodes_by_type("ProfessionalArtifact")
