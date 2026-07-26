from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mcp_collect import technologies_from_text


def now() -> str:
    return datetime.now(UTC).isoformat()


def split_tags(value: str) -> list[str]:
    return [tag.strip() for tag in str(value or "").replace(",", ";").split(";") if tag.strip()]


def first_existing(row: dict, *names: str) -> str:
    for name in names:
        if row.get(name):
            return row[name]
    return ""


def relationships(row: dict) -> list[dict]:
    items = []
    for column, rel_type in (
        ("Parent", "System.LinkTypes.Hierarchy-Reverse"),
        ("Parent ID", "System.LinkTypes.Hierarchy-Reverse"),
    ):
        if row.get(column):
            items.append({"type": rel_type, "external_id": f"ADO-WI-{row[column]}"})
    return items


def occurred_at(row: dict) -> str:
    return row.get("Closed Date") or row.get("Target Date") or row.get("Created Date") or now()


def row_to_record(row: dict) -> dict:
    tags = split_tags(row.get("Tags", ""))
    work_type = row.get("Work Item Type", "")
    description = first_existing(row, "Description", "System.Description")
    discussion = first_existing(row, "Discussion", "History", "System.History")
    acceptance_criteria = first_existing(row, "Acceptance Criteria", "AcceptanceCriteria")
    return {
        "source_entity_type": "work_item",
        "external_id": f"ADO-WI-{row['ID']}",
        "occurred_at": occurred_at(row),
        "privacy_level": "internal",
        "payload": {
            "title": row.get("Title", ""),
            "state": row.get("State", ""),
            "work_item_type": work_type,
            "assigned_to": row.get("Assigned To", ""),
            "created_by": row.get("Created By", ""),
            "tags": tags,
            "target_date": row.get("Target Date", ""),
            "closed_date": row.get("Closed Date", ""),
            "time_spent": row.get("Tempo gasto", ""),
            "description": description,
            "discussion": discussion,
            "acceptance_criteria": acceptance_criteria,
            "relationships": relationships(row),
            "domain": work_type.lower() or "azure boards",
            "technologies": technologies_from_text(
                row.get("Title", ""), " ".join(tags), description, discussion, acceptance_criteria
            ),
        },
    }


def convert(input_path: Path, output_path: Path) -> dict:
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    export = {
        "format": "source_export_v1",
        "captured_at": now(),
        "engineer": {
            "id": "engineer-1",
            "display_name": "Rodolpho Toppan",
            "primary_email_hash": "configured-locally",
        },
        "source": {
            "id": "azure-devops-ui-csv",
            "type": "azure_devops_ui_csv",
            "name": "Azure DevOps UI CSV Export",
            "visibility": "private",
        },
        "records": [row_to_record(row) for row in rows if row.get("ID")],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"output": str(output_path), "records": len(export["records"])}


if __name__ == "__main__":
    input_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\rodolpho.toppan\Desktop\todosmeuscards.csv")
    )
    result = convert(input_path, ROOT / "data" / "career_source_export.json")
    print(json.dumps(result, indent=2, ensure_ascii=False))
