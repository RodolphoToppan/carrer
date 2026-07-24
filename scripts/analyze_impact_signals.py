import json
import re
from pathlib import Path
from collections import Counter

# Load Azure DevOps export
data_path = Path(__file__).parent.parent / "data" / "azure_devops_mcp_export.json"
data = json.loads(data_path.read_text(encoding="utf-8"))

work_items = [r for r in data['records'] if r.get('source_entity_type', r.get('type')) == 'work_item']

print("=" * 80)
print("IMPACT SIGNAL DETECTION ANALYSIS")
print("=" * 80)
print()

# Scale indicators
scale_patterns = {
    'numbers': r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(million|thousand|milhão|mil|bilhão|billion|M|K|B)\b',
    'percentages': r'\b(\d+(?:\.\d+)?)\s*%',
    'counts': r'\b(\d+)\s*(pedidos?|orders?|vendas?|sales?|users?|usuários?|clientes?|customers?)',
    'volume': r'\b(high|large|massive|alto|grande|massivo)\s+(volume|scale|escala)',
    'performance': r'\b(performance|desempenho|otimização|optimization|melhoria|improvement)',
}

print("🔍 SCALE INDICATORS FOUND")
print()

for pattern_name, pattern in scale_patterns.items():
    matches = []
    for wi in work_items:
        title = wi['payload'].get('title', '')
        desc = wi['payload'].get('description', '')
        text = title + ' ' + desc

        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            matches.extend(found)

    if matches:
        print(f"{pattern_name.upper()}:")
        if pattern_name == 'numbers':
            # Show unique scale mentions
            unique = list(set([f"{m[0]} {m[1]}" for m in matches[:10]]))
            for u in unique[:5]:
                print(f"  - {u}")
        elif pattern_name == 'percentages':
            unique = list(set([f"{m}%" for m in matches[:10]]))
            for u in unique[:5]:
                print(f"  - {u}")
        elif pattern_name == 'counts':
            unique = list(set([f"{m[0]} {m[1]}" for m in matches[:10]]))
            for u in unique[:5]:
                print(f"  - {u}")
        else:
            print(f"  - {len(matches)} mentions found")
        print()

# Business value indicators
print("💰 BUSINESS VALUE INDICATORS")
print()

value_keywords = {
    'revenue': ['receita', 'revenue', 'faturamento', 'sales'],
    'cost': ['custo', 'cost', 'economia', 'savings', 'redução', 'reduction'],
    'efficiency': ['eficiência', 'efficiency', 'automação', 'automation', 'produtividade', 'productivity'],
    'quality': ['qualidade', 'quality', 'erro', 'error', 'bug', 'falha', 'failure'],
    'time': ['tempo', 'time', 'prazo', 'deadline', 'rápido', 'fast', 'agilidade', 'agility'],
    'customer': ['cliente', 'customer', 'user', 'usuário', 'satisfação', 'satisfaction'],
}

for category, keywords in value_keywords.items():
    count = 0
    examples = []
    for wi in work_items:
        title = wi['payload'].get('title', '').lower()
        desc = wi['payload'].get('description', '').lower()
        text = title + ' ' + desc

        for keyword in keywords:
            if keyword in text:
                count += 1
                if len(examples) < 3 and title:
                    examples.append(wi['payload'].get('title', '')[:60])
                break

    if count > 0:
        print(f"{category.upper()}: {count} mentions")
        for ex in examples:
            print(f"  - {ex}...")
        print()

# Technical achievements
print("🏆 TECHNICAL ACHIEVEMENT PATTERNS")
print()

achievement_patterns = {
    'implemented': r'\b(implement|implementar|criar|create|desenvolver|develop|construir|build)\b',
    'improved': r'\b(improve|melhorar|otimizar|optimize|aprimorar|enhance)\b',
    'fixed': r'\b(fix|corrigir|resolver|solve|solucionar)\b',
    'migrated': r'\b(migrar|migrate|atualizar|update|upgrade)\b',
    'integrated': r'\b(integrar|integrate|conectar|connect)\b',
}

for achievement, pattern in achievement_patterns.items():
    count = sum(1 for wi in work_items if re.search(pattern, wi['payload'].get('title', ''), re.IGNORECASE))
    if count > 0:
        print(f"{achievement.upper()}: {count} work items")

print()
print("=" * 80)
print("IMPACT SIGNAL EXTRACTION OPPORTUNITIES")
print("=" * 80)
print()

print("1. ORDER VOLUME SIGNALS")
print("   - Pattern: 'X pedidos', 'X orders'")
print("   - Context: Marketplace operations")
print()

print("2. PERFORMANCE IMPROVEMENTS")
print("   - Pattern: 'otimização', 'performance', 'melhoria'")
print("   - Context: System efficiency")
print()

print("3. INTEGRATION ACHIEVEMENTS")
print("   - Pattern: 'integração', 'conectar', 'API'")
print("   - Context: System connectivity")
print()

print("4. BUSINESS PROCESS AUTOMATION")
print("   - Pattern: 'automação', 'automatizar'")
print("   - Context: Efficiency gains")
print()

