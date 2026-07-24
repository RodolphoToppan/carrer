#!/usr/bin/env python3
"""Quick check of data structure"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.load(open(ROOT / "data" / "career_source_export.json", encoding='utf-8'))

print(f"Total records: {len(data['records'])}")
print("\nRecord types:")
types = {}
for r in data['records']:
    t = r.get('source_entity_type', r.get('type'))
    types[t] = types.get(t, 0) + 1
for t, count in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {t}: {count}")

print("\nSample work_item payload:")
wi = [r for r in data['records'] if r.get('source_entity_type') == 'work_item'][0]
import pprint
pprint.pprint(wi['payload'])

print("\nSample commit payload:")
commit = [r for r in data['records'] if r.get('source_entity_type') == 'commit'][0]
pprint.pprint(commit['payload'])

