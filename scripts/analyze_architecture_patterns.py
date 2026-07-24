"""
Analyze architecture patterns from evidence data.
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict


def extract_architecture_patterns(text: str) -> dict:
    """Extract architecture-related patterns from text."""
    if not text:
        return {}

    patterns = {
        'event_driven': [
            r'\bevent[os]?\b',
            r'\bmessag(e|ing|em)\b',
            r'\bqueue\b',
            r'\bfila\b',
            r'\basync\b',
            r'\bass[íi]ncrono\b',
        ],

        'message_queue': [
            r'\brabbitmq\b',
            r'\bactivemq\b',
            r'\bartemis\b',
            r'\bkafka\b',
        ],

        'distributed': [
            r'\bdistribui[dç][ao]\b',
            r'\bdistributed\b',
            r'\bscal(e|ability|ar)\b',
        ],

        'caching': [
            r'\bcache\b',
            r'\bredis\b',
            r'\bin-memory\b',
        ],

        'rest_api': [
            r'\brest\b',
            r'\bapi\b',
            r'\bendpoint\b',
        ],
    }

    text_lower = text.lower()
    found = defaultdict(int)

    for category, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                found[category] += len(matches)

    return dict(found)


data_path = Path(__file__).parent.parent / 'data' / 'azure_devops_mcp_export.json'
data = json.loads(data_path.read_text(encoding='utf-8'))
work_items = [r for r in data['records'] if r.get('source_entity_type') == 'work_item']

print("=" * 80)
print("ARCHITECTURE PATTERN DETECTION ANALYSIS")
print("=" * 80)
print()

all_patterns = defaultdict(int)
pattern_items = defaultdict(list)

for wi in work_items:
    title = wi['payload'].get('title', '')
    desc = wi['payload'].get('description', '')
    text = f"{title} {desc}"

    patterns = extract_architecture_patterns(text)

    for pattern, count in patterns.items():
        all_patterns[pattern] += count
        if wi not in pattern_items[pattern]:
            pattern_items[pattern].append(wi)

print("🏗️  ARCHITECTURE PATTERNS FOUND")
print()
for pattern, count in sorted(all_patterns.items(), key=lambda x: x[1], reverse=True):
    wi_count = len(pattern_items[pattern])
    pct = wi_count / len(work_items) * 100 if work_items else 0
    print(f"   {pattern:20s}: {count:4d} mentions in {wi_count:3d} work items ({pct:5.1f}%)")
print()

print("📊 TOP PATTERNS BY WORK ITEM COUNT")
print()
for pattern, items in sorted(pattern_items.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"   {pattern:20s}: {len(items):3d} work items")
    if items:
        example = items[0]['payload'].get('title', '')[:80]
        print(f"      Example: {example}...")
print()

