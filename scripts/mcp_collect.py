from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from shutil import which
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_intelligence_mvp import validate_source_export_v1

PROJECT = os.environ.get("AZURE_DEVOPS_PROJECT", "Koncili")


def configured_project(env: dict[str, str]) -> str:
    return env.get("AZURE_DEVOPS_PROJECT") or PROJECT


def source_label(project: str) -> str:
    return f"Azure DevOps MCP - {project}"


def source_id(project: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project.lower()).strip("-")
    return f"azure-devops-mcp-{slug or 'project'}"


def load_ps_env(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    if not path.exists():
        return env
    pattern = re.compile(r'^\$env:([A-Z0-9_]+)\s*=\s*"([^"]*)"\s*$')
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            value = match.group(2).replace("$PSScriptRoot", str(path.parent))
            env[match.group(1)] = str(Path(value).resolve()) if "\\" in value else value
    if env.get("AZURE_DEVOPS_EXT_PAT") and not env.get("PERSONAL_ACCESS_TOKEN"):
        env["PERSONAL_ACCESS_TOKEN"] = base64.b64encode(f":{env['AZURE_DEVOPS_EXT_PAT']}".encode("utf-8")).decode("ascii")
    return env


def redact_sensitive(text: object) -> str:
    value = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
    value = re.sub(r'(?i)("?(?:pat|token|authorization|private-token|personal_access_token)"?\s*[:=]\s*)"?[^",\s}]+"?', r'\1"<redacted>"', value)
    value = re.sub(r"(?i)(Bearer|Basic)\s+[A-Za-z0-9+/._~=-]+", r"\1 <redacted>", value)
    return value


def require_env(env: dict[str, str], *names: str) -> None:
    missing = [name for name in names if not env.get(name) or env.get(name) == "replace-me"]
    if missing:
        raise SystemExit("Missing required environment variable(s): " + ", ".join(missing))


class McpClient:
    def __init__(self, command: list[str], env: dict[str, str]) -> None:
        self.next_id = 1
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )

    def close(self) -> None:
        self.process.terminate()

    def request(self, method: str, params: dict | None = None) -> dict:
        request_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        while True:
            message = self._read()
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(redact_sensitive(message["error"]))
                return message["result"]

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def call_tool(self, name: str, arguments: dict) -> object:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            return {"error": redact_sensitive(result["content"][0].get("text", "unknown MCP error"))}
        text = result["content"][0].get("text", "")
        parsed = parse_tool_content_json(text)
        return parsed if parsed is not None else text

    def _send(self, message: dict) -> None:
        body = json.dumps(message).encode("utf-8") + b"\n"
        self.process.stdin.write(body)
        self.process.stdin.flush()

    def _read(self) -> dict:
        timer = threading.Timer(45, self.process.kill)
        timer.start()
        try:
            while True:
                line = self.process.stdout.readline().decode("utf-8", errors="replace")
                if not line:
                    stderr = self.process.stderr.read().decode("utf-8", errors="replace")
                    raise RuntimeError(redact_sensitive(stderr.strip() or "MCP server closed stdout"))
                line = line.strip()
                if not line:
                    continue
                return json.loads(line)
        finally:
            timer.cancel()


def azure_client(env: dict[str, str]) -> McpClient:
    require_env(env, "AZURE_DEVOPS_ORG", "PERSONAL_ACCESS_TOKEN")
    org = env["AZURE_DEVOPS_ORG"]
    npx = which("npx") or which("npx.cmd") or r"C:\Program Files\nodejs\npx.cmd"
    return McpClient(
        [
            npx,
            "-y",
            "-p",
            "@modelcontextprotocol/sdk",
            "-p",
            "@azure-devops/mcp",
            "mcp-server-azuredevops",
            org,
            "--authentication",
            "pat",
        ],
        env,
    )


def gitlab_client(env: dict[str, str]) -> McpClient:
    require_env(env, "GITLAB_PERSONAL_ACCESS_TOKEN")
    npx = which("npx") or which("npx.cmd") or r"C:\Program Files\nodejs\npx.cmd"
    return McpClient([npx, "-y", "@modelcontextprotocol/server-gitlab"], env)


def initialize(client: McpClient) -> None:
    client.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "career-intelligence-agent", "version": "0.1"},
        },
    )
    client.notify("notifications/initialized")


def text_from_identity(value: object) -> str:
    if isinstance(value, dict):
        return value.get("displayName") or value.get("uniqueName") or ""
    return str(value or "")


def parse_tool_content_json(text: str) -> object | None:
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    return None


def identity_matches(value: object, filters: list[str]) -> bool:
    text = text_from_identity(value).lower()
    return any(item.lower() in text for item in filters if item)


WORK_ITEM_FIELDS = [
    "System.Id",
    "System.Title",
    "System.WorkItemType",
    "System.State",
    "System.AreaPath",
    "System.AssignedTo",
    "System.CreatedBy",
    "System.ChangedBy",
    "System.Tags",
    "System.CreatedDate",
    "System.ChangedDate",
    "System.Description",
    "System.History",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
]

DEFAULT_MY_WORK_ITEMS_WIQL = """
SELECT [System.Id]
FROM WorkItems
WHERE
    [System.TeamProject] = @project
    AND
    (
        [System.AssignedTo] = @Me
        OR [System.CreatedBy] = @Me
    )
ORDER BY [System.CreatedDate] ASC
"""


def work_item_record(item: dict, relationships: list[dict] | None = None) -> dict:
    fields = item.get("fields", item)
    work_id = item.get("id") or fields.get("System.Id")
    title = fields.get("System.Title", f"Work item {work_id}")
    changed_at = fields.get("System.ChangedDate") or fields.get("System.CreatedDate") or now()
    description = clean_html(fields.get("System.Description", ""))
    discussion = clean_html(fields.get("System.History", ""))
    acceptance_criteria = clean_html(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""))
    return {
        "source_entity_type": "work_item",
        "external_id": f"ADO-WI-{work_id}",
        "occurred_at": changed_at,
        "privacy_level": "internal",
        "payload": {
            "title": title,
            "state": fields.get("System.State", ""),
            "work_item_type": fields.get("System.WorkItemType", ""),
            "assigned_to": text_from_identity(fields.get("System.AssignedTo")),
            "created_by": text_from_identity(fields.get("System.CreatedBy")),
            "changed_by": text_from_identity(fields.get("System.ChangedBy")),
            "tags": [tag.strip() for tag in fields.get("System.Tags", "").split(";") if tag.strip()],
            "domain": readable_domain(fields.get("System.AreaPath", PROJECT)),
            "description": description,
            "discussion": discussion,
            "acceptance_criteria": acceptance_criteria,
            "relationships": relationships if relationships is not None else work_item_relationships(item),
            "technologies": technologies_from_text(title, fields.get("System.Tags", ""), description, discussion, acceptance_criteria),
        },
    }


def clean_html(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def work_item_relationships(item: dict) -> list[dict]:
    relationships = []
    for relation in item.get("relations", []) or []:
        if relation.get("external_id"):
            relationships.append({"type": relation.get("rel", relation.get("type", "")), "external_id": relation["external_id"]})
            continue
        url = relation.get("url", "")
        match = re.search(r"/workItems/(\d+)$", url)
        if match:
            relationships.append({"type": relation.get("rel", ""), "external_id": f"ADO-WI-{match.group(1)}"})
    return relationships


def work_item_link_map(client: McpClient, work_item_ids: list[int]) -> dict[int, list[dict]]:
    links: dict[int, list[dict]] = {work_id: [] for work_id in work_item_ids}
    for start in range(0, len(work_item_ids), 200):
        ids = work_item_ids[start : start + 200]
        if not ids:
            continue
        wiql = f"""
SELECT [System.Id]
FROM WorkItemLinks
WHERE (
    [Source].[System.TeamProject] = @project
    AND [Source].[System.Id] IN ({",".join(str(work_id) for work_id in ids)})
  )
  OR (
    [Target].[System.TeamProject] = @project
    AND [Target].[System.Id] IN ({",".join(str(work_id) for work_id in ids)})
  )
MODE (MayContain)
"""
        result = client.call_tool("wit_query_by_wiql", {"project": PROJECT, "wiql": wiql, "top": 10000})
        relations = result.get("workItemRelations", result.get("relations", [])) if isinstance(result, dict) else []
        for relation in relations:
            source = relation.get("source") or {}
            target = relation.get("target") or {}
            source_id = source.get("id")
            target_id = target.get("id")
            if source_id in links and target_id and source_id != target_id:
                links[source_id].append({"type": relation.get("rel", ""), "external_id": f"ADO-WI-{target_id}"})
            if target_id in links and source_id and source_id != target_id:
                links[target_id].append({"type": relation.get("rel", ""), "external_id": f"ADO-WI-{source_id}"})
    return links


def pull_request_record(pr: dict) -> dict:
    pr_id = pr.get("pullRequestId") or pr.get("id")
    return {
        "source_entity_type": "pull_request",
        "external_id": f"ADO-PR-{pr_id}",
        "occurred_at": pr.get("creationDate") or pr.get("closedDate") or now(),
        "privacy_level": "internal",
        "payload": {
            "title": pr.get("title", f"Pull request {pr_id}"),
            "status": pr.get("status", ""),
            "repository": pr.get("repository", {}).get("name", ""),
            "domain": PROJECT,
            "technologies": technologies_from_text(pr.get("title", "")),
        },
    }


def commit_record(commit: dict, repository: str) -> dict:
    commit_id = commit.get("commitId", "")
    author = commit.get("author", {})
    return {
        "source_entity_type": "commit",
        "external_id": f"ADO-COMMIT-{commit_id[:12] or stable_id(commit)}",
        "occurred_at": author.get("date") or commit.get("committer", {}).get("date") or now(),
        "privacy_level": "internal",
        "payload": {
            "message": first_line(commit.get("comment", f"Commit {commit_id[:12]}")),
            "repository": repository,
            "domain": PROJECT,
            "technologies": technologies_from_text(commit.get("comment", ""), repository),
        },
    }


def branch_record(branch: dict, repository: str) -> dict:
    name = branch.get("name") or branch.get("refName") or ""
    return {
        "source_entity_type": "branch",
        "external_id": f"ADO-BRANCH-{repository}-{name}",
        "occurred_at": branch.get("date") or branch.get("creator", {}).get("date") or now(),
        "privacy_level": "internal",
        "payload": {
            "title": name.replace("refs/heads/", ""),
            "repository": repository,
            "domain": PROJECT,
            "technologies": technologies_from_text(name, repository),
        },
    }


def first_line(value: str) -> str:
    return str(value or "").splitlines()[0][:240]


def readable_domain(value: str) -> str:
    leaf = str(value or PROJECT).split("\\")[-1]
    leaf = re.sub(r"^\d+-", "", leaf)
    return leaf.replace("_", " ").strip().lower() or PROJECT


def technologies_from_text(*values: str) -> list[str]:
    text = " ".join(str(value or "") for value in values).lower()
    known = {
        "java": "Java",
        "spring": "Spring Boot",
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
    return sorted({label for needle, label in known.items() if needle in text})


def stable_id(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_azure(client: McpClient, output_path: Path, work_items_top: int, commit_author: str, branch_filter: str, wiql_file: str | None) -> dict:
    captured_at = now()
    records = []

    if wiql_file:
        wiql = Path(wiql_file).read_text(encoding="utf-8")
    else:
        wiql = DEFAULT_MY_WORK_ITEMS_WIQL
    work_items = client.call_tool("wit_query_by_wiql", {"project": PROJECT, "wiql": wiql, "top": work_items_top})
    raw_items = work_items.get("workItems", work_items.get("results", [])) if isinstance(work_items, dict) else []
    work_item_ids = [item["id"] for item in raw_items]
    if work_item_ids:
        links = work_item_link_map(client, work_item_ids)
        for start in range(0, len(work_item_ids), 200):
            details = client.call_tool(
                "wit_get_work_items_batch_by_ids",
                {
                    "project": PROJECT,
                    "ids": work_item_ids[start : start + 200],
                    "fields": WORK_ITEM_FIELDS,
                },
            )
            for item in details if isinstance(details, list) else []:
                fields = item.get("fields", item)
                work_id = item.get("id") or fields.get("System.Id")
                records.append(work_item_record(item, links.get(work_id, [])))
    if not records and not wiql_file:
        work_items = client.call_tool("wit_my_work_items", {"project": PROJECT, "type": "myactivity", "top": work_items_top, "includeCompleted": True})
        work_item_ids = [item["id"] for item in work_items.get("results", [])] if isinstance(work_items, dict) else []
        links = work_item_link_map(client, work_item_ids)
        for start in range(0, len(work_item_ids), 200):
            details = client.call_tool(
                "wit_get_work_items_batch_by_ids",
                {
                    "project": PROJECT,
                    "ids": work_item_ids[start : start + 200],
                    "fields": WORK_ITEM_FIELDS,
                },
            )
            for item in details if isinstance(details, list) else []:
                fields = item.get("fields", item)
                work_id = item.get("id") or fields.get("System.Id")
                records.append(work_item_record(item, links.get(work_id, [])))

    repos = client.call_tool("repo_list_repos_by_project", {"project": PROJECT, "top": 20})
    repo_list = repos if isinstance(repos, list) else []
    for repo in repo_list:
        branches = client.call_tool("repo_list_branches_by_repo", {"repositoryId": repo["id"], "top": 100, "filterContains": branch_filter})
        if isinstance(branches, list):
            records.extend(branch_record(branch, repo["name"]) for branch in branches)
        prs = client.call_tool(
            "repo_list_pull_requests_by_repo_or_project",
            {"project": PROJECT, "repositoryId": repo["id"], "top": 20, "status": "All", "created_by_me": True},
        )
        if isinstance(prs, list):
            records.extend(pull_request_record(pr) for pr in prs)
        for author_key in ("author", "committer"):
            commits = client.call_tool(
                "repo_search_commits",
                {"project": PROJECT, "repository": repo["id"], "top": 100, "includeWorkItems": True, author_key: commit_author},
            )
            if isinstance(commits, list):
                records.extend(commit_record(commit, repo["name"]) for commit in commits)

    export = {
        "format": "source_export_v1",
        "captured_at": captured_at,
        "engineer": {
            "id": "engineer-1",
            "display_name": "Rodolpho Toppan",
            "primary_email_hash": "configured-locally",
        },
        "source": {
            "id": source_id(PROJECT),
            "type": "azure_devops_mcp",
            "name": source_label(PROJECT),
            "visibility": "private",
        },
        "records": dedupe_records(records),
    }
    validate_source_export_v1(export)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"output": str(output_path), "records": len(export["records"])}


def merge_into_career_export(source_path: Path, target_path: Path) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    validate_source_export_v1(source)
    if target_path.exists():
        target = json.loads(target_path.read_text(encoding="utf-8"))
        validate_source_export_v1(target)
    else:
        target = {**source, "records": []}
    records = {(record["source_entity_type"], record["external_id"]): record for record in target["records"]}
    for record in source["records"]:
        record = {**record, "source": source["source"]}
        records[(record["source_entity_type"], record["external_id"])] = record
    target["records"] = sorted(records.values(), key=record_key)
    target["captured_at"] = now()
    validate_source_export_v1(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(target, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"output": str(target_path), "records": len(target["records"])}


def dedupe_records(records: list[dict]) -> list[dict]:
    deduped = {}
    for record in records:
        deduped[(record["source_entity_type"], record["external_id"])] = record
    return sorted(deduped.values(), key=record_key)


def record_key(record: dict) -> tuple[str, str]:
    return (str(record.get("source_entity_type", "")), str(record.get("external_id", "")))


def commit_identities(commits: object) -> list[dict]:
    if not isinstance(commits, list):
        return []
    identities = []
    for commit in commits:
        identities.append(
            {
                "author": commit.get("author", {}).get("name", ""),
                "authorEmail": commit.get("author", {}).get("email", ""),
                "committer": commit.get("committer", {}).get("name", ""),
                "committerEmail": commit.get("committer", {}).get("email", ""),
            }
        )
    return identities


def main() -> int:
    global PROJECT
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["list-tools", "list-gitlab-tools", "describe-gitlab-tools", "describe-tools", "call-tool", "inspect-small", "inspect-code", "inspect-identity", "inspect-workitems-wiql", "collect-azure"])
    parser.add_argument("tool", nargs="?")
    parser.add_argument("tool_args", nargs="?", default="{}")
    parser.add_argument("--work-items-top", type=int, default=10000)
    parser.add_argument("--commit-author", default="rodolpho.toppan@db1.com.br")
    parser.add_argument("--branch-filter", default="rodolpho")
    parser.add_argument("--wiql-file")
    args = parser.parse_args()

    env = load_ps_env(ROOT / ".codex" / "env.local.ps1")
    PROJECT = configured_project(env)
    client = gitlab_client(env) if args.command in {"list-gitlab-tools", "describe-gitlab-tools"} else azure_client(env)
    try:
        initialize(client)
        if args.command == "list-tools":
            tools = client.request("tools/list")["tools"]
            for tool in tools:
                print(tool["name"])
        if args.command == "list-gitlab-tools":
            tools = client.request("tools/list")["tools"]
            for tool in tools:
                print(tool["name"])
        if args.command == "describe-gitlab-tools":
            print(json.dumps(client.request("tools/list")["tools"], indent=2))
        if args.command == "describe-tools":
            wanted = {
                "wit_my_work_items",
                "wit_query_by_wiql",
                "wit_get_work_items_batch_by_ids",
                "core_get_identity_ids",
                "repo_list_repos_by_project",
                "repo_search_commits",
                "repo_list_my_branches_by_repo",
                "repo_list_branches_by_repo",
                "repo_list_pull_requests_by_repo_or_project",
                "repo_list_pull_request_threads",
                "repo_list_pull_request_thread_comments",
            }
            tools = [tool for tool in client.request("tools/list")["tools"] if tool["name"] in wanted]
            print(json.dumps(tools, indent=2))
        if args.command == "call-tool":
            result = client.request(
                "tools/call",
                {"name": args.tool, "arguments": json.loads(args.tool_args)},
            )
            print(json.dumps(result, indent=2))
        if args.command == "inspect-small":
            calls = [
                ("wit_my_work_items", {"project": PROJECT, "type": "myactivity", "top": 5, "includeCompleted": True}),
                ("repo_list_repos_by_project", {"project": PROJECT, "top": 5}),
                ("repo_list_pull_requests_by_repo_or_project", {"project": PROJECT, "top": 5, "status": "All", "created_by_me": True}),
            ]
            output = {}
            for name, arguments in calls:
                output[name] = client.request("tools/call", {"name": name, "arguments": arguments})
            print(json.dumps(output, indent=2))
        if args.command == "inspect-code":
            repos = client.call_tool("repo_list_repos_by_project", {"project": PROJECT, "top": 1})
            repo = repos[0]
            output = {
                "repo": repo["name"],
                "branches": client.call_tool("repo_list_branches_by_repo", {"repositoryId": repo["id"], "top": 5, "filterContains": args.branch_filter}),
                "commits_author": client.call_tool("repo_search_commits", {"project": PROJECT, "repository": repo["id"], "top": 5, "author": args.commit_author}),
                "commits_committer": client.call_tool("repo_search_commits", {"project": PROJECT, "repository": repo["id"], "top": 5, "committer": args.commit_author}),
                "recent_commit_identities": commit_identities(client.call_tool("repo_search_commits", {"project": PROJECT, "repository": repo["id"], "top": 20})),
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        if args.command == "inspect-identity":
            print(json.dumps(client.call_tool("core_get_identity_ids", {"searchFilter": args.commit_author}), indent=2, ensure_ascii=False))
        if args.command == "inspect-workitems-wiql":
            identity = args.commit_author
            wiql = """
SELECT [System.Id]
FROM WorkItems
WHERE [System.TeamProject] = @project
  AND (
    [System.AssignedTo] = '{identity}'
    OR [System.CreatedBy] = '{identity}'
    OR [System.ChangedBy] = '{identity}'
  )
ORDER BY [System.ChangedDate] DESC
""".format(identity=identity.replace("'", "''"))
            result = client.call_tool("wit_query_by_wiql", {"project": PROJECT, "wiql": wiql, "top": args.work_items_top})
            items = result.get("workItems", result.get("results", [])) if isinstance(result, dict) else []
            print(json.dumps({"count": len(items), "sample": items[:5]}, indent=2, ensure_ascii=False))
        if args.command == "collect-azure":
            azure_result = collect_azure(client, ROOT / "data" / "azure_devops_mcp_export.json", args.work_items_top, args.commit_author, args.branch_filter, args.wiql_file)
            merged = merge_into_career_export(ROOT / "data" / "azure_devops_mcp_export.json", ROOT / "data" / "career_source_export.json")
            print(json.dumps({"azure": azure_result, "career": merged}, indent=2))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
