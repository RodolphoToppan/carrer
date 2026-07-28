from __future__ import annotations

import re

from carrer.storage.json_graph_storage import JsonGraphStorage

GraphStore = JsonGraphStorage


def artifact_claim_rows(artifact: dict) -> list[dict]:
    props = artifact.get("properties", {})
    if props.get("artifact_type") == "Skill Matrix":
        return list(props.get("rows", []))
    sections = props.get("sections", {})
    if props.get("artifact_type") == "STAR Stories":
        return list(sections.get("stories", []))
    if props.get("artifact_type") == "Interview Answers":
        return list(sections.get("answers", []))
    if props.get("artifact_type") == "Cover Letter":
        return list(sections.get("claims", []))
    if props.get("artifact_type") == "Career Timeline":
        return list(sections.get("milestones", []))
    if props.get("artifact_type") == "Gap Analysis":
        return list(sections.get("strengths", [])) + list(sections.get("weak_evidence", []))
    return list(sections.get("highlights", []))


UNSUPPORTED_METRIC_PATTERN = re.compile(
    r"(\d+(\.\d+)?\s*%|\$\s*\d+|\bby\s+\d+|\b\d+(\.\d+)?x\s+(faster|slower|more|less))", re.IGNORECASE
)
PRIVATE_DETAIL_PATTERN = re.compile(r"(https?://\S+|\b[A-Z]{2,}-[A-Z]*\d+\b)")


def artifact_claim_text(row: dict) -> str:
    return " ".join(
        str(value)
        for key, value in row.items()
        if key not in {"evidence_refs", "observation_refs", "knowledge_id", "evidence_context"}
        and isinstance(value, str)
    )


def validate_artifact(artifact: dict, store: GraphStore) -> list[dict]:
    warnings = []
    for index, row in enumerate(artifact_claim_rows(artifact)):
        knowledge_id = row.get("knowledge_id")
        observation_refs = row.get("observation_refs", [])
        evidence_refs = row.get("evidence_refs", [])
        statement = row.get("statement", "")
        claim_text = artifact_claim_text(row)

        if "unsupported metric" not in claim_text.lower() and UNSUPPORTED_METRIC_PATTERN.search(claim_text):
            warnings.append(
                {
                    "code": "possible_unsupported_metric",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if PRIVATE_DETAIL_PATTERN.search(claim_text):
            warnings.append(
                {
                    "code": "possible_private_source_detail",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if not knowledge_id:
            warnings.append({"code": "missing_knowledge_ref", "claim_index": index, "statement": statement})
            continue
        if not observation_refs:
            warnings.append(
                {
                    "code": "missing_observation_refs",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        if not evidence_refs:
            warnings.append(
                {
                    "code": "missing_evidence_refs",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
        missing_observation_refs = [ref for ref in observation_refs if ref not in store.nodes]
        if missing_observation_refs:
            warnings.append(
                {
                    "code": "observation_ref_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "missing_refs": missing_observation_refs,
                    "statement": statement,
                }
            )
        missing_evidence_refs = [ref for ref in evidence_refs if ref not in store.nodes]
        if missing_evidence_refs:
            warnings.append(
                {
                    "code": "evidence_ref_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "missing_refs": missing_evidence_refs,
                    "statement": statement,
                }
            )
        wrong_observation_ref_types = [
            ref
            for ref in observation_refs
            if ref in store.nodes and store.nodes[ref].get("node_type") != "ObservationNode"
        ]
        if wrong_observation_ref_types:
            warnings.append(
                {
                    "code": "observation_ref_wrong_type",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": wrong_observation_ref_types,
                    "statement": statement,
                }
            )
        wrong_evidence_ref_types = [
            ref for ref in evidence_refs if ref in store.nodes and store.nodes[ref].get("node_type") != "EvidenceNode"
        ]
        if wrong_evidence_ref_types:
            warnings.append(
                {
                    "code": "evidence_ref_wrong_type",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": wrong_evidence_ref_types,
                    "statement": statement,
                }
            )
        context = row.get("evidence_context", {})
        if context and context.get("evidence_count") != len(evidence_refs):
            warnings.append(
                {
                    "code": "evidence_context_count_mismatch",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "evidence_count": context.get("evidence_count"),
                    "evidence_refs": len(evidence_refs),
                    "statement": statement,
                }
            )

        if str(knowledge_id).startswith("cluster:"):
            continue

        knowledge = store.nodes.get(knowledge_id)
        if not knowledge:
            warnings.append(
                {
                    "code": "knowledge_not_found",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "statement": statement,
                }
            )
            continue

        props = knowledge["properties"]
        if props.get("status") != "accepted":
            warnings.append(
                {
                    "code": "knowledge_not_accepted",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "status": props.get("status"),
                    "statement": statement,
                }
            )
        if props.get("privacy_level") != "artifact_safe":
            warnings.append(
                {
                    "code": "knowledge_not_artifact_safe",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "privacy_level": props.get("privacy_level"),
                    "statement": statement,
                }
            )
        observation_refs_not_in_knowledge = [
            ref for ref in observation_refs if ref not in props.get("observation_refs", [])
        ]
        if observation_refs_not_in_knowledge:
            warnings.append(
                {
                    "code": "observation_ref_not_in_knowledge",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": observation_refs_not_in_knowledge,
                    "statement": statement,
                }
            )
        evidence_refs_not_in_knowledge = [ref for ref in evidence_refs if ref not in props.get("evidence_refs", [])]
        if evidence_refs_not_in_knowledge:
            warnings.append(
                {
                    "code": "evidence_ref_not_in_knowledge",
                    "claim_index": index,
                    "knowledge_id": knowledge_id,
                    "refs": evidence_refs_not_in_knowledge,
                    "statement": statement,
                }
            )
    return warnings


def warning_severity(code: str) -> str:
    return "review" if code in {"possible_unsupported_metric", "evidence_context_count_mismatch"} else "blocker"


def warning_summary(warnings: list[dict]) -> str:
    blockers = sum(1 for warning in warnings if warning_severity(warning.get("code", "unknown")) == "blocker")
    reviews = len(warnings) - blockers
    blocker_label = "blocker" if blockers == 1 else "blockers"
    review_label = "review" if reviews == 1 else "reviews"
    return f"{len(warnings)} ({blockers} {blocker_label}, {reviews} {review_label})"


def artifact_validation_markdown(artifact: dict, warnings: list[dict]) -> str:
    title = artifact.get("properties", {}).get("artifact_type", "Artifact")
    status = "REVIEW" if warnings else "PASS"
    readiness = (
        "Ready for human export review." if status == "PASS" else "Resolve validation warnings before export review."
    )
    lines = [
        f"# {title} Validation",
        "",
        f"- status: {status}",
        f"- warnings: {warning_summary(warnings)}",
        f"- readiness: {readiness}",
        "",
    ]
    for warning in warnings:
        code = warning.get("code", "unknown")
        statement = warning.get("statement", "")
        knowledge_id = warning.get("knowledge_id", "")
        details = ", ".join(
            f"{key}={value}" for key, value in warning.items() if key not in {"code", "statement", "knowledge_id"}
        )
        suffix = f" ({details})" if details else ""
        knowledge_part = f" [{knowledge_id}]" if knowledge_id else ""
        lines.append(f"- {warning_severity(code)}: {code}{knowledge_part}: {statement}{suffix}")
    if not warnings:
        lines.append("- No validation warnings.")
    return "\n".join(lines)
