#!/usr/bin/env python3
"""Quick inspection script for career_source_export.json"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
export_path = ROOT / "data" / "career_source_export.json"

if not export_path.exists():
    print(f"File not found: {export_path}")
    exit(1)

with open(export_path, encoding="utf-8") as f:
    data = json.load(f)

print(f"Format: {data.get('format')}")
print(f"Captured at: {data.get('captured_at')}")
print(f"Source type: {data.get('source', {}).get('type')}")
print(f"Source name: {data.get('source', {}).get('name')}")
print(f"Total records: {len(data.get('records', []))}")

# Count record types
record_types = {}
for record in data.get("records", []):
    rtype = record.get("type", record.get("source_entity_type", "unknown"))
    record_types[rtype] = record_types.get(rtype, 0) + 1

print("\nRecord types:")
for rtype, count in sorted(record_types.items()):
    print(f"  {rtype}: {count}")

# Show first record sample
if data.get("records"):
    print("\nFirst record sample:")
    first = data["records"][0]
    print(f"  Type: {first.get('type', first.get('source_entity_type'))}")
    print(f"  External ID: {first.get('external_id')}")
    print(f"  Privacy level: {first.get('privacy_level', first.get('visibility', 'N/A'))}")
    if "payload" in first:
        payload = first["payload"]
        print(f"  Payload keys: {list(payload.keys())[:5]}...")
