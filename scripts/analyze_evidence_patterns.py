#!/usr/bin/env python3
"""Analyze evidence patterns to identify scale, impact, and business value signals"""
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

def analyze_patterns():
    export_path = ROOT / "data" / "career_source_export.json"
    data = json.load(open(export_path, encoding='utf-8'))

    # Patterns to detect
    scale_patterns = []
    technology_patterns = []
    action_patterns = []
    business_patterns = []

    print("=== ANALYZING EVIDENCE PATTERNS ===\n")

    # Sample first 50 work items
    work_items = [r for r in data['records'] if r.get('type') == 'work_item'][:50]

    print(f"Total work items sampled: {len(work_items)}\n")

    # Extract common patterns
    for record in work_items:
        payload = record.get('payload', {})
        title = payload.get('title', '').lower()
        description = str(payload.get('description', '')).lower()
        tags = payload.get('tags', [])

        # Look for scale indicators
        scale_words = ['million', 'thousand', 'volume', 'scale', 'high', 'performance', 'optimize']
        if any(word in title or word in description for word in scale_words):
            scale_patterns.append(title[:100])

        # Look for action verbs
        action_verbs = ['implement', 'refactor', 'optimize', 'create', 'develop', 'fix', 'improve', 'migrate']
        for verb in action_verbs:
            if verb in title:
                action_patterns.append(f"{verb}: {title[:80]}")

        # Look for business/product references
        business_words = ['product', 'marketplace', 'order', 'integration', 'customer', 'business']
        if any(word in title or word in description for word in business_words):
            business_patterns.append(title[:100])

    print("=== SCALE/PERFORMANCE PATTERNS ===")
    for pattern in scale_patterns[:5]:
        print(f"  - {pattern}")
    print(f"  Total: {len(scale_patterns)}")

    print("\n=== ACTION VERB PATTERNS ===")
    action_counter = Counter(action_patterns)
    for pattern, count in action_counter.most_common(10):
        print(f"  - {pattern}")

    print("\n=== BUSINESS VALUE PATTERNS ===")
    for pattern in business_patterns[:10]:
        print(f"  - {pattern}")
    print(f"  Total: {len(business_patterns)}")

    # Analyze domain distribution
    print("\n=== DOMAIN DISTRIBUTION ===")
    domains = []
    for record in data['records']:
        payload = record.get('payload', {})
        domain = payload.get('domain', '')
        if domain:
            domains.append(domain)

    domain_counter = Counter(domains)
    for domain, count in domain_counter.most_common(10):
        print(f"  {count:4d}x {domain}")

    # Sample some titles for context
    print("\n=== SAMPLE WORK ITEM TITLES ===")
    for i, record in enumerate(work_items[:15]):
        payload = record.get('payload', {})
        title = payload.get('title', 'N/A')
        print(f"{i+1:2d}. {title[:100]}")

if __name__ == "__main__":
    analyze_patterns()

