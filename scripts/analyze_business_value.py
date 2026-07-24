"""
Analyze business value patterns from evidence data.
"""

import json
import re
from pathlib import Path
from collections import defaultdict


def extract_business_value_indicators(text: str) -> dict:
    """Extract business value indicators from text."""
    if not text:
        return {}

    patterns = {
        'customer_satisfaction': [
            r'\bcliente\b',
            r'\bcustomer\b',
            r'\bsatisfa[çc][ãa]o\b',
            r'\busu[áa]rio\b',
            r'\buser\b',
        ],

        'error_reduction': [
            r'\berro\b',
            r'\berror\b',
            r'\bbug\b',
            r'\bfalha\b',
            r'\bfailure\b',
            r'\bcorri[çg]\b',
            r'\bfix\b',
        ],

        'performance_improvement': [
            r'\bperformance\b',
            r'\bdesempenho\b',
            r'\botimi[zs]a[çc][ãa]o\b',
            r'\bmelhoria\b',
            r'\bimprovement\b',
        ],

        'time_efficiency': [
            r'\btempo\b',
            r'\btime\b',
            r'\bprazo\b',
            r'\br[áa]pido\b',
            r'\bfast\b',
            r'\bagilidade\b',
        ],

        'cost_reduction': [
            r'\bcusto\b',
            r'\bcost\b',
            r'\beconomia\b',
            r'\bredu[çc][ãa]o\b',
        ],

        'automation': [
            r'\bautoma[çc][ãa]o\b',
            r'\bautomation\b',
            r'\bautomatizar\b',
        ],

        'scalability': [
            r'\bescal(a|ar|abilidade)\b',
            r'\bscal(e|ability)\b',
            r'\bvolume\b',
            r'\bcapacidade\b',
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
print("BUSINESS VALUE EXTRACTION ANALYSIS")
print("=" * 80)
print()

all_values = defaultdict(int)
value_items = defaultdict(list)

for wi in work_items:
    title = wi['payload'].get('title', '')
    desc = wi['payload'].get('description', '')
    text = f"{title} {desc}"

    values = extract_business_value_indicators(text)

    for value_type, count in values.items():
        all_values[value_type] += count
        if wi not in value_items[value_type]:
            value_items[value_type].append(wi)

print("💰 BUSINESS VALUE INDICATORS FOUND")
print()
for value_type, count in sorted(all_values.items(), key=lambda x: x[1], reverse=True):
    wi_count = len(value_items[value_type])
    pct = wi_count / len(work_items) * 100 if work_items else 0
    print(f"   {value_type:30s}: {count:4d} mentions in {wi_count:3d} work items ({pct:5.1f}%)")
print()

