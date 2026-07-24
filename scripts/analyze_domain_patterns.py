import json
from pathlib import Path
from collections import Counter

# Load Azure DevOps export
data_path = Path(__file__).parent.parent / "data" / "azure_devops_mcp_export.json"
data = json.loads(data_path.read_text(encoding="utf-8"))

work_items = [r for r in data['records'] if r.get('source_entity_type', r.get('type')) == 'work_item']

print(f"=== Analyzing {len(work_items)} Work Items ===\n")

# Extract title patterns
title_patterns = []
for wi in work_items:
    title = wi['payload'].get('title', '')
    # Extract patterns in brackets like [PEDIDOS], [API], etc
    import re
    brackets = re.findall(r'\[([^\]]+)\]', title)
    title_patterns.extend(brackets)

print("=== Most Common Title Patterns (in brackets) ===")
pattern_counter = Counter(title_patterns)
for pattern, count in pattern_counter.most_common(20):
    print(f"  [{pattern}]: {count} occurrences")

# Extract keywords from titles (after cleaning brackets)
print("\n=== Most Common Keywords in Titles ===")
all_words = []
for wi in work_items:
    title = wi['payload'].get('title', '')
    # Remove brackets content
    title_clean = re.sub(r'\[([^\]]+)\]', '', title)
    # Split and lowercase
    words = [w.lower().strip() for w in title_clean.split() if len(w) > 3]
    all_words.extend(words)

word_counter = Counter(all_words)
# Filter out common words
stopwords = {'para', 'para', 'pela', 'pelo', 'com', 'dos', 'das', 'que', 'são', 'foi', 'ser', 'está', 'como', 'uma', 'mais'}
for word, count in word_counter.most_common(30):
    if word not in stopwords and count >= 5:
        print(f"  {word}: {count} times")

# Analyze domain field
print("\n=== Current Domain Values ===")
domains = [wi['payload'].get('domain', 'missing') for wi in work_items]
domain_counter = Counter(domains)
for domain, count in domain_counter.most_common(10):
    print(f"  {domain}: {count} work items")

# Identify business processes from titles
print("\n=== Business Process Keywords ===")
business_keywords = {
    'pedidos': 0, 'orders': 0,
    'vendas': 0, 'sales': 0,
    'conciliacao': 0, 'conciliação': 0, 'reconciliation': 0,
    'baixas': 0, 'settlement': 0,
    'frete': 0, 'shipping': 0, 'logistica': 0,
    'estoque': 0, 'inventory': 0,
    'importacao': 0, 'importação': 0, 'import': 0,
    'integracao': 0, 'integração': 0, 'integration': 0,
    'api': 0, 'endpoint': 0,
    'webhook': 0,
    'expansao': 0, 'expansão': 0,
    'onboarding': 0,
    'migracao': 0, 'migração': 0, 'migration': 0,
}

for wi in work_items:
    title = wi['payload'].get('title', '').lower()
    desc = wi['payload'].get('description', '').lower()
    text = title + ' ' + desc

    for keyword in business_keywords:
        if keyword in text:
            business_keywords[keyword] += 1

print("Business process mentions:")
for keyword, count in sorted(business_keywords.items(), key=lambda x: x[1], reverse=True):
    if count > 0:
        print(f"  {keyword}: {count} mentions")

