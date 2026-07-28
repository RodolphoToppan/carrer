from __future__ import annotations

from typing import Any

from carrer.domain.enums import PRIVACY_LEVELS, SOURCE_ENTITY_TYPES


def validate_source_export_v1(export: dict[str, Any]) -> None:
    """Validate the canonical source export contract used by ingestion."""
    errors: list[str] = []
    required_top_level = ("captured_at", "engineer", "source", "records")
    for key in required_top_level:
        if key not in export:
            errors.append(f"missing top-level field: {key}")

    engineer = export.get("engineer")
    if not isinstance(engineer, dict):
        errors.append("engineer must be an object")
    else:
        for key in ("id", "display_name", "primary_email_hash"):
            if key not in engineer:
                errors.append(f"missing engineer field: {key}")

    source = export.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for key in ("id", "type", "name", "visibility"):
            if key not in source:
                errors.append(f"missing source field: {key}")

    records = export.get("records")
    if not isinstance(records, list):
        errors.append("records must be a list")
        records = []

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue

        has_type = "source_entity_type" in record or "type" in record
        if not has_type:
            errors.append(f"records[{index}] missing field: source_entity_type")

        for key in ("external_id", "occurred_at", "payload"):
            if key not in record:
                errors.append(f"records[{index}] missing field: {key}")

        source_entity_type = record.get("source_entity_type", record.get("type"))
        if source_entity_type and source_entity_type not in SOURCE_ENTITY_TYPES:
            errors.append(f"records[{index}] has unsupported source_entity_type: {source_entity_type}")

        privacy_level = record.get("privacy_level", record.get("visibility", "artifact_safe"))
        if privacy_level not in PRIVACY_LEVELS:
            errors.append(f"records[{index}] has unsupported privacy_level: {privacy_level}")

        payload = record.get("payload")
        if payload is not None and not isinstance(payload, dict):
            errors.append(f"records[{index}].payload must be an object")

    if errors:
        raise ValueError("Invalid source_export_v1: " + "; ".join(errors))
