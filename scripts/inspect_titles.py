import json
from pathlib import Path

data_path = Path(__file__).parent.parent / "data" / "azure_devops_mcp_export.json"
data = json.loads(data_path.read_text(encoding="utf-8"))

print("=== Work Item Title Samples ===\n")
work_items = [r for r in data["records"] if r.get("source_entity_type", r.get("type")) == "work_item"]
for i, record in enumerate(work_items[:15], 1):
    title = record["payload"].get("title", "N/A")
    print(f"{i}. {title}")

print("\n=== Commit Message Samples ===\n")
commits = [r for r in data["records"] if r.get("source_entity_type", r.get("type")) == "commit"]
for i, record in enumerate(commits[:10], 1):
    msg = record["payload"].get("message", "N/A")
    print(f"{i}. {msg[:100]}")

print("\n=== Technology Keywords Found in Titles ===\n")
tech_keywords = {
    "spring": 0,
    "rabbitmq": 0,
    "activemq": 0,
    "artemis": 0,
    "postgres": 0,
    "postgresql": 0,
    "oracle": 0,
    "docker": 0,
    "kubernetes": 0,
    "k8s": 0,
    "sql": 0,
    "api": 0,
    "rest": 0,
    "grpc": 0,
    "microservice": 0,
    "marketplace": 0,
    "integration": 0,
}

for record in work_items:
    title = record["payload"].get("title", "").lower()
    desc = record["payload"].get("description", "").lower()
    text = title + " " + desc

    for keyword in tech_keywords:
        if keyword in text:
            tech_keywords[keyword] += 1

for keyword, count in sorted(tech_keywords.items(), key=lambda x: x[1], reverse=True):
    if count > 0:
        print(f"  {keyword}: {count} occurrences")
