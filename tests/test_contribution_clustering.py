from __future__ import annotations

import copy
import json

import pytest

from carrer.contributions import (
    cluster_evidence,
    clustering,
    contribution_candidate,
    contribution_candidate_id,
    find_contribution_candidates,
)
from carrer.domain.models import evidence_node
from carrer.storage.json_graph_storage import JsonGraphStorage

CAPTURED_AT = "2026-01-01T00:00:00+00:00"


def _evidence(
    entity_type: str,
    entity_id: str,
    *,
    title: str | None = None,
    message: str | None = None,
    source_id: str = "src",
    occurred_at: str | None = "2026-01-01T00:00:00Z",
    privacy_level: str = "artifact_safe",
    metadata: dict | None = None,
) -> dict:
    payload = dict(metadata or {})

    if title is not None:
        payload["title"] = title

    if message is not None:
        payload["message"] = message

    evidence_type = {
        "work_item": "WORK_ITEM_EXISTS",
        "commit": "COMMIT_EXISTS",
        "pull_request": "MERGE_REQUEST_EXISTS",
        "merge_request": "MERGE_REQUEST_EXISTS",
        "review_comment": "REVIEW_COMMENT_CREATED",
        "documentation": "DOCUMENTATION_EXISTS",
        "branch": "BRANCH_EXISTS",
    }[entity_type]

    return evidence_node(
        source_id=source_id,
        source_entity_type=entity_type,
        source_entity_id=entity_id,
        evidence_type=evidence_type,
        captured_at=CAPTURED_AT,
        occurred_at=occurred_at,
        privacy_level=privacy_level,
        metadata=payload,
    )


def _edge(left: dict, right: dict) -> dict:
    return {
        "id": f"edge:{left['id']}:{right['id']}",
        "edge_type": "EVIDENCE_RELATED_TO_EVIDENCE",
        "from_node_id": left["id"],
        "to_node_id": right["id"],
        "created_at": CAPTURED_AT,
        "properties": {},
    }


def test_explicit_edge_forms_candidate_and_missing_edge_endpoint_is_ignored() -> None:
    work = _evidence("work_item", "WI-1", title="Retry API")
    commit = _evidence("commit", "abc", message="Implement retry")

    candidates = cluster_evidence(
        [work, commit],
        [
            _edge(work, commit),
            {**_edge(work, commit), "to_node_id": "missing"},
        ],
    )

    assert len(candidates) == 1
    assert candidates[0]["evidence_refs"] == sorted([work["id"], commit["id"]])
    assert candidates[0]["confidence"] == "high"
    assert candidates[0]["reasons"] == [
        "connected_component",
        "explicit_evidence_relationship",
    ]


def test_explicit_component_is_transitive_and_edge_direction_does_not_change_identity() -> None:
    work = _evidence("work_item", "WI-1", title="Retry API")
    commit = _evidence("commit", "abc")
    mr = _evidence("merge_request", "MR-1", title="Retry merge")

    forward = cluster_evidence(
        [work, commit, mr],
        [_edge(work, commit), _edge(commit, mr)],
    )
    backward = cluster_evidence(
        [mr, commit, work],
        [_edge(commit, work), _edge(mr, commit)],
    )

    assert len(forward) == 1
    assert forward == backward
    assert forward[0]["evidence_refs"] == sorted([work["id"], commit["id"], mr["id"]])


def test_two_independent_components_stay_separate_and_sorted() -> None:
    first = _evidence("work_item", "WI-1", title="First")
    first_commit = _evidence("commit", "c1")
    second = _evidence("merge_request", "MR-1", title="Second")
    second_commit = _evidence("commit", "c2")

    candidates = cluster_evidence(
        [second_commit, first_commit, second, first],
        [
            _edge(first, first_commit),
            _edge(second, second_commit),
        ],
    )

    assert len(candidates) == 2
    assert candidates == sorted(candidates, key=lambda item: item["id"])
    assert {tuple(item["evidence_refs"]) for item in candidates} == {
        tuple(sorted([first["id"], first_commit["id"]])),
        tuple(sorted([second["id"], second_commit["id"]])),
    }


def test_shared_structural_ids_group_but_same_title_does_not() -> None:
    first = _evidence("work_item", "WI-1", title="Same")
    updated = _evidence("work_item", "WI-1", title="Changed")
    unrelated = _evidence("work_item", "WI-2", title="Same")

    candidates = cluster_evidence([unrelated, updated, first], [])

    grouped = [item for item in candidates if item["evidence_refs"] == sorted([first["id"], updated["id"]])]

    assert len(grouped) == 1
    assert grouped[0]["confidence"] == "medium"
    assert "shared_structural_entity_id" in grouped[0]["reasons"]
    assert any(item["evidence_refs"] == [unrelated["id"]] for item in candidates)


def test_branch_groups_only_with_compatible_source_and_repository() -> None:
    commit = _evidence(
        "commit",
        "c1",
        metadata={
            "branch": "feature/a",
            "repository": "repo-a",
        },
    )
    mr = _evidence(
        "merge_request",
        "MR-1",
        title="Feature A",
        metadata={
            "source_branch": "feature/a",
            "repository": "repo-a",
        },
    )
    other_repo = _evidence(
        "merge_request",
        "MR-2",
        title="Feature A elsewhere",
        metadata={
            "source_branch": "feature/a",
            "repository": "repo-b",
        },
    )

    candidates = cluster_evidence([other_repo, mr, commit], [])

    assert any(item["evidence_refs"] == sorted([commit["id"], mr["id"]]) for item in candidates)
    assert any(item["evidence_refs"] == [other_repo["id"]] for item in candidates)


def test_same_branch_without_repository_or_project_does_not_group() -> None:
    commit = _evidence(
        "commit",
        "c1",
        metadata={"branch": "feature/a"},
    )
    mr = _evidence(
        "merge_request",
        "MR-1",
        title="Feature A",
        metadata={"source_branch": "feature/a"},
    )

    candidates = cluster_evidence([mr, commit], [])

    assert len(candidates) == 1
    assert candidates[0]["evidence_refs"] == [mr["id"]]
    assert candidates[0]["reasons"] == ["isolated_allowed_entity_type"]


def test_same_repository_without_branch_or_relation_does_not_group() -> None:
    first = _evidence(
        "work_item",
        "WI-1",
        title="A",
        metadata={"repository": "repo"},
    )
    second = _evidence(
        "merge_request",
        "MR-1",
        title="B",
        metadata={"repository": "repo"},
    )

    candidates = cluster_evidence([first, second], [])

    assert {tuple(item["evidence_refs"]) for item in candidates} == {
        (first["id"],),
        (second["id"],),
    }


@pytest.mark.parametrize(
    ("entity_type", "expected"),
    [
        ("work_item", True),
        ("merge_request", True),
        ("documentation", True),
        ("commit", False),
        ("review_comment", False),
        ("branch", False),
    ],
)
def test_isolated_evidence_rules(
    entity_type: str,
    expected: bool,
) -> None:
    node = _evidence(
        entity_type,
        "one",
        title="Title",
        message="Message",
    )

    assert bool(cluster_evidence([node], [])) is expected


def test_candidate_identity_uses_only_type_and_canonical_support() -> None:
    first = _evidence("work_item", "WI-1", title="First")
    second = _evidence("commit", "c1")

    first_id = contribution_candidate_id(
        "work_item_delivery",
        [second["id"], first["id"], first["id"]],
    )
    second_id = contribution_candidate_id(
        "work_item_delivery",
        [first["id"], second["id"]],
    )

    assert first_id == second_id
    assert first_id != contribution_candidate_id(
        "work_item_delivery",
        [first["id"]],
    )


def test_title_changes_do_not_change_candidate_id() -> None:
    first = _evidence("work_item", "WI-1", title="First")
    changed = _evidence("work_item", "WI-1", title="Changed")

    candidates = cluster_evidence([first, changed], [])

    assert candidates[0]["id"] == contribution_candidate_id(
        "work_item_delivery",
        [first["id"], changed["id"]],
    )


def test_confidence_rules_are_explainable() -> None:
    work = _evidence("work_item", "WI-1", title="Retry")
    commit = _evidence("commit", "c1")
    duplicate_work = _evidence(
        "work_item",
        "WI-1",
        title="Retry updated",
    )

    explicit = cluster_evidence(
        [work, commit],
        [_edge(work, commit)],
    )[0]
    structural = cluster_evidence(
        [work, duplicate_work],
        [],
    )[0]
    isolated = cluster_evidence([work], [])[0]

    assert explicit["confidence"] == "high"
    assert structural["confidence"] == "medium"
    assert isolated["confidence"] == "low"

    assert explicit["reasons"] == [
        "connected_component",
        "explicit_evidence_relationship",
    ]
    assert "shared_structural_entity_id" in structural["reasons"]
    assert isolated["reasons"] == ["isolated_allowed_entity_type"]


def test_dates_are_derived_from_occurred_at_only_and_input_order_independent() -> None:
    early = _evidence(
        "work_item",
        "WI-1",
        title="Date",
        occurred_at="2026-01-01T00:00:00Z",
    )
    late = _evidence(
        "commit",
        "c1",
        occurred_at="2026-01-03T00:00:00Z",
    )
    missing = _evidence(
        "commit",
        "c2",
        occurred_at=None,
    )

    candidate = cluster_evidence(
        [late, missing, early],
        [_edge(early, late), _edge(late, missing)],
    )[0]
    one_date = cluster_evidence([early], [])[0]
    no_dates = cluster_evidence(
        [
            _evidence(
                "work_item",
                "WI-2",
                title="No date",
                occurred_at=None,
            )
        ],
        [],
    )[0]

    assert candidate["started_at"] == "2026-01-01T00:00:00Z"
    assert candidate["ended_at"] == "2026-01-03T00:00:00Z"
    assert one_date["started_at"] == one_date["ended_at"] == "2026-01-01T00:00:00Z"
    assert no_dates["started_at"] is None
    assert no_dates["ended_at"] is None


def test_dates_compare_timezone_offsets_and_preserve_original_strings() -> None:
    early = _evidence(
        "work_item",
        "WI-1",
        title="Date",
        occurred_at="2026-01-01T10:00:00+02:00",
    )
    late = _evidence(
        "commit",
        "c1",
        occurred_at="2026-01-01T07:30:00-03:00",
    )

    candidate = cluster_evidence(
        [late, early],
        [_edge(early, late)],
    )[0]

    assert candidate["started_at"] == "2026-01-01T10:00:00+02:00"
    assert candidate["ended_at"] == "2026-01-01T07:30:00-03:00"


def test_invalid_occurred_at_fails_predictably() -> None:
    node = _evidence(
        "work_item",
        "WI-1",
        title="Bad date",
        occurred_at="not-a-date",
    )

    with pytest.raises(
        ValueError,
        match="occurred_at must be an ISO8601 string",
    ):
        cluster_evidence([node], [])


def test_occurred_at_without_timezone_fails_predictably() -> None:
    node = _evidence(
        "work_item",
        "WI-1",
        title="Missing timezone",
        occurred_at="2026-01-01T10:00:00",
    )

    with pytest.raises(
        ValueError,
        match="occurred_at must include a timezone",
    ):
        cluster_evidence([node], [])


def test_candidate_date_validation_uses_timezone_offsets() -> None:
    with pytest.raises(
        ValueError,
        match="started_at must be before or equal to ended_at",
    ):
        contribution_candidate(
            candidate_type="work_item_delivery",
            title="Bad range",
            evidence_refs=["evidence:a"],
            started_at="2026-01-01T07:30:00-03:00",
            ended_at="2026-01-01T10:00:00+02:00",
        )

    with pytest.raises(
        ValueError,
        match="started_at must be an ISO8601 string",
    ):
        contribution_candidate(
            candidate_type="work_item_delivery",
            title="Bad ISO",
            evidence_refs=["evidence:a"],
            started_at="not-a-date",
        )


def test_candidate_rejects_timestamp_without_timezone() -> None:
    with pytest.raises(
        ValueError,
        match="started_at must include a timezone",
    ):
        contribution_candidate(
            candidate_type="work_item_delivery",
            title="Missing timezone",
            evidence_refs=["evidence:a"],
            started_at="2026-01-01T10:00:00",
        )

    with pytest.raises(
        ValueError,
        match="ended_at must include a timezone",
    ):
        contribution_candidate(
            candidate_type="work_item_delivery",
            title="Missing timezone",
            evidence_refs=["evidence:a"],
            ended_at="2026-01-01T10:00:00",
        )


def test_privacy_is_most_restrictive_and_evidence_is_not_mutated() -> None:
    public = _evidence(
        "work_item",
        "WI-1",
        title="Privacy",
        privacy_level="artifact_safe",
    )
    internal = _evidence(
        "commit",
        "c1",
        privacy_level="internal",
    )
    private = _evidence(
        "merge_request",
        "MR-1",
        title="Private",
        privacy_level="private",
    )
    original = copy.deepcopy([public, internal, private])

    candidate = cluster_evidence(
        [private, public, internal],
        [_edge(public, internal), _edge(internal, private)],
    )[0]

    assert candidate["privacy_level"] == "private"
    assert [public, internal, private] == original


def test_invalid_privacy_level_fails_predictably() -> None:
    node = _evidence(
        "work_item",
        "WI-1",
        title="Bad",
    )
    node["properties"]["privacy_level"] = "public"

    with pytest.raises(
        ValueError,
        match="Invalid privacy level",
    ):
        cluster_evidence([node], [])


def test_title_priority_and_candidate_type_are_structural() -> None:
    work = _evidence(
        "work_item",
        "WI-1",
        title="Work title",
    )
    mr = _evidence(
        "merge_request",
        "MR-1",
        title="MR title",
    )
    docs = _evidence(
        "documentation",
        "D-1",
        title="Docs title",
    )

    assert cluster_evidence([mr], [])[0]["title"] == "MR title"
    assert cluster_evidence([docs], [])[0]["candidate_type"] == "documentation"

    candidate = cluster_evidence(
        [mr, work, docs],
        [_edge(mr, work), _edge(mr, docs)],
    )[0]

    assert candidate["title"] == "Work title"
    assert candidate["candidate_type"] == "work_item_delivery"


def test_deterministic_json_lists_and_no_input_mutation() -> None:
    work = _evidence(
        "work_item",
        "WI-1",
        title="Work",
    )
    mr = _evidence(
        "merge_request",
        "MR-1",
        title="MR",
    )
    nodes = [work, mr]
    edges = [_edge(work, mr)]

    before_nodes = copy.deepcopy(nodes)
    before_edges = copy.deepcopy(edges)

    first = cluster_evidence(nodes, edges)
    second = cluster_evidence(
        list(reversed(nodes)),
        list(reversed(edges)),
    )

    assert json.dumps(
        first,
        sort_keys=True,
    ) == json.dumps(
        second,
        sort_keys=True,
    )
    assert first[0]["evidence_refs"] == sorted(first[0]["evidence_refs"])
    assert first[0]["reasons"] == sorted(first[0]["reasons"])
    assert first[0]["signals"] == sorted(first[0]["signals"])
    assert nodes == before_nodes
    assert edges == before_edges


def test_find_candidates_reads_store_without_persisting_contributions_or_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JsonGraphStorage()
    work = _evidence(
        "work_item",
        "WI-1",
        title="Store",
    )
    commit = _evidence(
        "commit",
        "c1",
    )

    store.create_node(work)
    store.create_node(commit)
    store.create_edge(
        "EVIDENCE_RELATED_TO_EVIDENCE",
        work["id"],
        commit["id"],
    )

    audit_count = len(store.audit_records)

    def fail_create_contribution(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise AssertionError("create_contribution must not be called")

    monkeypatch.setattr(
        clustering,
        "contribution_candidate",
        clustering.contribution_candidate,
    )
    monkeypatch.setattr(
        "carrer.contributions.service.create_contribution",
        fail_create_contribution,
    )

    candidates = find_contribution_candidates(store)

    assert len(candidates) == 1
    assert store.nodes_by_type("Contribution") == []
    assert len(store.audit_records) == audit_count


def test_pipeline_legacy_remains_without_candidate_side_effects() -> None:
    from career_intelligence_mvp import run_pipeline

    store, _ = run_pipeline("tests/fixtures/characterization_source_export.json")

    assert store.nodes_by_type("Contribution") == []
    assert all(node["node_type"] != "ContributionCandidate" for node in store.nodes.values())
