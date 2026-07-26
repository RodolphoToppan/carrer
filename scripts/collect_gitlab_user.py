from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "data" / "career_source_export.json"
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import validate_source_export_v1

TECHNOLOGY_KEYWORDS = {
    "java": "Java",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "rabbitmq": "RabbitMQ",
    "active mq": "ActiveMQ Artemis",
    "activemq": "ActiveMQ Artemis",
    "artemis": "ActiveMQ Artemis",
    "redis": "Redis",
    "oracle": "Oracle",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "docker": "Docker",
    "rest": "REST APIs",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def technologies_from_text(*values: str) -> list[str]:
    text = " ".join(str(value or "") for value in values).lower()
    return sorted({label for needle, label in TECHNOLOGY_KEYWORDS.items() if needle in text})


def ps_env(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("$env:") and "=" in line:
            key, value = line.split("=", 1)
            key = key.removeprefix("$env:").strip()
            value = value.strip().strip('"').replace("$PSScriptRoot", str(path.parent))
            env[key] = str(Path(value).resolve()) if "\\" in value else value
    return env


def require_env(env: dict[str, str], *names: str) -> None:
    missing = [name for name in names if not env.get(name) or env.get(name) == "replace-me"]
    if missing:
        raise SystemExit("Missing required environment variable(s): " + ", ".join(missing))


def redact_sensitive(text: object) -> str:
    value = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
    value = re.sub(
        r'(?i)("?(?:token|private-token|personal_access_token)"?\s*[:=]\s*)"?[^",\s}]+"?', r'\1"<redacted>"', value
    )
    value = re.sub(r"(?i)(Bearer|Basic)\s+[A-Za-z0-9+/._~=-]+", r"\1 <redacted>", value)
    return value


def new_export(user: dict) -> dict:
    username = user.get("username") or user.get("id") or "user"
    return {
        "format": "source_export_v1",
        "captured_at": now(),
        "engineer": {
            "id": "engineer-1",
            "display_name": user.get("name") or username,
            "primary_email_hash": "configured-locally",
        },
        "source": {
            "id": f"gitlab-user-{username}",
            "type": "gitlab_user_api",
            "name": "GitLab User API",
            "visibility": "private",
        },
        "records": [],
    }


def load_or_create_export(path: Path, user: dict) -> dict:
    if path.exists():
        export = json.loads(path.read_text(encoding="utf-8"))
    else:
        export = new_export(user)
    validate_source_export_v1(export)
    return export


class GitLab:
    def __init__(self, env: dict[str, str]) -> None:
        self.base = env["GITLAB_API_URL"].rstrip("/")
        self.token = env["GITLAB_PERSONAL_ACCESS_TOKEN"]
        cert = env.get("NODE_EXTRA_CA_CERTS")
        self.context = ssl.create_default_context(cafile=cert) if cert else None

    def get(self, path: str, params: dict | None = None) -> object:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base}{path}" + (f"?{query}" if query else "")
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": self.token})
        try:
            with urllib.request.urlopen(req, context=self.context, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError(
                    f"GitLab authentication failed ({exc.code}). Check GITLAB_PERSONAL_ACCESS_TOKEN."
                ) from exc
            raise RuntimeError(f"GitLab API request failed ({exc.code}) for {path}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitLab API request failed for {path}: {redact_sensitive(exc.reason)}") from exc

    def paged(self, path: str, params: dict | None = None, max_pages: int = 20) -> list[dict]:
        items = []
        for page in range(1, max_pages + 1):
            batch = self.get(path, {**(params or {}), "per_page": 100, "page": page})
            if not batch:
                break
            items.extend(batch)
        return items


def merge_records(export: dict, new_records: list[dict], source: dict | None = None) -> dict:
    validate_source_export_v1(export)
    records = {(r["source_entity_type"], r["external_id"]): r for r in export["records"]}
    for record in new_records:
        if source:
            record = {**record, "source": source}
        records[(record["source_entity_type"], record["external_id"])] = record
    export["records"] = sorted(records.values(), key=record_key)
    export["captured_at"] = now()
    validate_source_export_v1(export)
    return export


def write_export(path: Path, export: dict) -> None:
    validate_source_export_v1(export)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")


def record_key(record: dict) -> tuple[str, str]:
    return (str(record.get("source_entity_type", "")), str(record.get("external_id", "")))


def mr_record(mr: dict) -> dict:
    title = mr.get("title", "")
    source_branch = mr.get("source_branch", "")
    target_branch = mr.get("target_branch", "")
    return {
        "source_entity_type": "merge_request",
        "external_id": f"GL-MR-{mr['id']}",
        "occurred_at": mr.get("merged_at") or mr.get("updated_at") or mr.get("created_at") or now(),
        "privacy_level": "internal",
        "payload": {
            "title": title,
            "state": mr.get("state", ""),
            "repository": str(mr.get("project_id", "")),
            "source_branch": source_branch,
            "target_branch": target_branch,
            "domain": "gitlab merge request",
            "technologies": technologies_from_text(title, source_branch, target_branch),
        },
    }


def push_records(event: dict) -> list[dict]:
    push = event.get("push_data") or {}
    project_id = event.get("project_id", "")
    ref = push.get("ref", "")
    created_at = event.get("created_at") or now()
    records = []
    if push.get("commit_to"):
        commit_title = push.get("commit_title", "")
        records.append(
            {
                "source_entity_type": "commit",
                "external_id": f"GL-COMMIT-{project_id}-{push['commit_to']}",
                "occurred_at": created_at,
                "privacy_level": "internal",
                "payload": {
                    "message": commit_title,
                    "repository": str(project_id),
                    "branch": ref,
                    "domain": "gitlab commit",
                    "technologies": technologies_from_text(commit_title, ref),
                },
            }
        )
    if ref:
        records.append(
            {
                "source_entity_type": "branch",
                "external_id": f"GL-BRANCH-{project_id}-{ref}",
                "occurred_at": created_at,
                "privacy_level": "internal",
                "payload": {
                    "title": ref,
                    "repository": str(project_id),
                    "domain": "gitlab branch",
                    "technologies": technologies_from_text(ref),
                },
            }
        )
    return records


def main() -> int:
    env = ps_env(ROOT / ".codex" / "env.local.ps1")
    require_env(env, "GITLAB_API_URL", "GITLAB_PERSONAL_ACCESS_TOKEN")
    gitlab = GitLab(env)
    user = gitlab.get("/user")
    mrs = gitlab.paged("/merge_requests", {"scope": "all", "author_id": user["id"]})
    events = gitlab.paged("/events", {"action": "pushed"})

    records = [mr_record(mr) for mr in mrs]
    for event in events:
        records.extend(push_records(event))

    gitlab_source = new_export(user)["source"]
    export = load_or_create_export(EXPORT_PATH, user)
    export = merge_records(export, records, gitlab_source)
    write_export(EXPORT_PATH, export)
    print(
        json.dumps(
            {"output": str(EXPORT_PATH), "gitlab_records": len(records), "total_records": len(export["records"])},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
