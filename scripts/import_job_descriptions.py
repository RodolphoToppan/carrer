from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from career_intelligence_mvp import validate_source_export_v1
from mcp_collect import technologies_from_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def title_from_text(path: Path, text: str) -> str:
    for line in text.splitlines():
        value = line.strip(" #\t")
        if value:
            return value[:120]
    return path.stem.replace("_", " ").replace("-", " ").title()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "job-description"


def iter_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in {".txt", ".md"} else []
    return sorted(item for item in path.iterdir() if item.suffix.lower() in {".txt", ".md"})


def file_to_record(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Empty job description: {path}")
    title = title_from_text(path, text)
    return {
        "source_entity_type": "job_description",
        "external_id": f"JD-{slug(path.stem)}",
        "occurred_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "privacy_level": "artifact_safe",
        "payload": {
            "title": title,
            "description": text,
            "domain": "job market requirements",
            "technologies": technologies_from_text(title, text),
        },
    }


def convert(input_path: Path, output_path: Path) -> dict:
    files = iter_input_files(input_path)
    if not files:
        raise ValueError(f"No .txt or .md job descriptions found in {input_path}")
    export = {
        "format": "source_export_v1",
        "captured_at": now(),
        "engineer": {
            "id": "engineer-1",
            "display_name": "Rodolpho Toppan",
            "primary_email_hash": "configured-locally",
        },
        "source": {
            "id": "job-descriptions-local",
            "type": "job_descriptions",
            "name": "Local Job Descriptions",
            "visibility": "artifact_safe",
        },
        "records": [file_to_record(path) for path in files],
    }
    validate_source_export_v1(export)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"output": str(output_path), "records": len(export["records"])}


if __name__ == "__main__":
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "job_descriptions_source_export.json"
    print(json.dumps(convert(input_path, output_path), indent=2, ensure_ascii=False))
