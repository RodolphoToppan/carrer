"""Deterministic ContributionCandidate clustering over evidence."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from carrer.contributions.candidates import contribution_candidate, parse_iso8601
from carrer.domain.privacy import derive_privacy
from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage

EVIDENCE_RELATED_TO_EVIDENCE = "EVIDENCE_RELATED_TO_EVIDENCE"

_ISOLATED_CANDIDATE_TYPES = {
    "work_item": "work_item_delivery",
    "pull_request": "change_delivery",
    "merge_request": "change_delivery",
    "documentation": "documentation",
}
_STRUCTURAL_ENTITY_TYPES = frozenset({"work_item", "pull_request", "merge_request", "documentation"})
_TITLE_FIELDS = ("title", "name", "summary", "message")


def find_contribution_candidates(store: GraphStore) -> list[dict[str, Any]]:
    return cluster_evidence(store.nodes_by_type("EvidenceNode"), store.edges)


def cluster_evidence(
    evidence_nodes: list[dict[str, Any]],
    evidence_edges: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    nodes = sorted(evidence_nodes, key=lambda node: node["id"])
    parent = {node["id"]: node["id"] for node in nodes}
    reasons_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(left: str, right: str, reason: str) -> None:
        if left not in parent or right not in parent or left == right:
            return
        ordered_pair = sorted((left, right))
        pair = (ordered_pair[0], ordered_pair[1])
        reasons_by_pair[pair].add(reason)
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            winner, loser = sorted((left_root, right_root))
            parent[loser] = winner

    for edge in sorted(
        evidence_edges or [], key=lambda item: (item.get("from_node_id", ""), item.get("to_node_id", ""))
    ):
        if edge.get("edge_type") == EVIDENCE_RELATED_TO_EVIDENCE:
            union(str(edge.get("from_node_id", "")), str(edge.get("to_node_id", "")), "explicit_evidence_relationship")

    for reason, groups in _structural_groups(nodes).items():
        for refs in groups.values():
            ordered = sorted(refs)
            for index, left in enumerate(ordered):
                for right in ordered[index + 1 :]:
                    union(left, right, reason)

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        components[find(node["id"])].append(node)

    candidates = [
        candidate
        for component in components.values()
        for candidate in [_candidate_from_component(sorted(component, key=lambda node: node["id"]), reasons_by_pair)]
        if candidate is not None
    ]
    return sorted(candidates, key=lambda item: item["id"])


def _structural_groups(nodes: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    groups: dict[str, dict[str, list[str]]] = {
        "shared_structural_entity_id": defaultdict(list),
        "shared_branch": defaultdict(list),
    }
    for node in nodes:
        props = node["properties"]
        metadata = props.get("metadata", {})
        entity_type = props.get("source_entity_type")
        entity_id = props.get("source_entity_id")
        source = props.get("source_id", "")
        if entity_type in _STRUCTURAL_ENTITY_TYPES and entity_id:
            groups["shared_structural_entity_id"][f"{source}:{entity_type}:{entity_id}"].append(node["id"])

        branch = _branch_value(props, metadata)
        if branch and (metadata.get("repository") or metadata.get("project")):
            repo = metadata.get("repository") or metadata.get("project") or ""
            groups["shared_branch"][f"{source}:{repo}:{branch}"].append(node["id"])
    return groups


def _candidate_from_component(
    component: list[dict[str, Any]],
    reasons_by_pair: dict[tuple[str, str], set[str]],
) -> dict[str, Any] | None:
    evidence_refs = [node["id"] for node in component]
    component_reasons = _component_reasons(evidence_refs, reasons_by_pair)
    if len(component) == 1 and not _is_allowed_isolated(component[0]):
        return None
    if len(component) > 1 and not component_reasons:
        return None

    types = sorted({str(node["properties"].get("source_entity_type", "")) for node in component})
    reasons = (
        ["isolated_allowed_entity_type"] if len(component) == 1 else sorted(component_reasons | {"connected_component"})
    )
    candidate_type = _candidate_type(types)
    return contribution_candidate(
        candidate_type=candidate_type,
        title=_title(component, candidate_type),
        evidence_refs=evidence_refs,
        source_refs=[
            f"source:{node['properties']['source_id']}" for node in component if node["properties"].get("source_id")
        ],
        confidence=_confidence(types, component_reasons, len(component)),
        privacy_level=derive_privacy(node["properties"].get("privacy_level") for node in component),
        started_at=_boundary_date(component, min),
        ended_at=_boundary_date(component, max),
        signals=types,
        reasons=reasons,
        metadata={"evidence_count": len(component), "source_entity_types": types},
    )


def _component_reasons(evidence_refs: list[str], reasons_by_pair: dict[tuple[str, str], set[str]]) -> set[str]:
    refs = set(evidence_refs)
    return {
        reason for pair, reasons in reasons_by_pair.items() if pair[0] in refs and pair[1] in refs for reason in reasons
    }


def _branch_value(props: dict[str, Any], metadata: dict[str, Any]) -> str:
    if props.get("source_entity_type") == "branch":
        return str(props.get("source_entity_id", "")).strip()
    for key in ("branch", "source_branch"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_allowed_isolated(node: dict[str, Any]) -> bool:
    return node["properties"].get("source_entity_type") in _ISOLATED_CANDIDATE_TYPES


def _candidate_type(types: list[str]) -> str:
    if "work_item" in types:
        return "work_item_delivery"
    if "pull_request" in types or "merge_request" in types:
        return "change_delivery"
    if types == ["documentation"]:
        return "documentation"
    if "review_comment" in types:
        return "review_activity"
    return "unknown_work_unit"


def _confidence(types: list[str], reasons: set[str], count: int) -> str:
    if "explicit_evidence_relationship" in reasons and count > 1 and len(types) > 1:
        return "high"
    if reasons & {"shared_structural_entity_id", "shared_branch"}:
        return "medium"
    return "low"


def _title(component: list[dict[str, Any]], candidate_type: str) -> str:
    for wanted_type in ("work_item", "pull_request", "merge_request", "documentation", "commit"):
        for node in component:
            props = node["properties"]
            if props.get("source_entity_type") == wanted_type:
                metadata = props.get("metadata", {})
                for field in _TITLE_FIELDS:
                    value = metadata.get(field)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
    return candidate_type.replace("_", " ")


def _boundary_date(component: list[dict[str, Any]], pick: Any) -> str | None:
    dates = [
        (parse_iso8601(date, "occurred_at"), date)
        for node in component
        for date in [node["properties"].get("occurred_at")]
        if isinstance(date, str) and date.strip()
    ]
    return pick(dates, key=lambda item: item[0])[1] if dates else None
