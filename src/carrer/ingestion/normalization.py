from __future__ import annotations

from typing import Any


def source_entity_type(record: dict[str, Any]) -> str:
    value = record["source_entity_type"] if "source_entity_type" in record else record["type"]
    return str(value)


def normalize_technology_list(raw_value: object) -> list[str]:
    if not isinstance(raw_value, list):
        return []

    normalized: list[str] = []
    for item in raw_value:
        value = str(item).strip()
        if value and not any(value.lower() == current.lower() for current in normalized):
            normalized.append(value)
    return normalized


def normalize_source_payload(_entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["technologies"] = normalize_technology_list(normalized.get("technologies"))

    # Domain is preserved only when explicitly provided in the source payload.
    current_domain = normalized.get("domain")
    if not isinstance(current_domain, str) or not current_domain.strip():
        normalized.pop("domain", None)

    return normalized


def normalize_source_export(export: dict[str, Any]) -> dict[str, Any]:
    return {
        "captured_at": export["captured_at"],
        "engineer": export["engineer"],
        "source": export["source"],
        "records": [
            {
                "type": source_entity_type(record),
                "external_id": record["external_id"],
                "occurred_at": record["occurred_at"],
                "privacy_level": record.get("privacy_level", record.get("visibility", "artifact_safe")),
                "source": record.get("source", export["source"]),
                "payload": normalize_source_payload(source_entity_type(record), record["payload"]),
            }
            for record in export["records"]
        ],
    }
