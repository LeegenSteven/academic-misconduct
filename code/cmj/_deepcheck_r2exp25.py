# -*- coding: utf-8 -*-
"""深入检查5个有疑问的条目"""
import re
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)

def html_to_text(html):
    p = TextExtractor()
    p.feed(html)
    return ' '.join(''.join(p.text).split())

def search_all(text, keywords, context=300):
    results = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
            start = max(0, m.start() - context)
            end = min(len(text), m.end() + context)
            results.append(f"[{kw}] ...{text[start:end]}...")
    return results

BASE = r"C:\Users\Administrator\AppData\Local\Temp\r2exp25_20261022"

# 04: Bellenguez 2022 - heritability估计是否排除UKBB
print("="*80)
print("【04】Bellenguez 2022 - heritability & UKBB")
with open(f"{BASE}/fulltext/PMC9005347.html", "r", encoding="utf-8") as f:
    text = html_to_text(f.read())
for r in search_all(text, ["liability scale", "SNP-based heritability", "excluded", "without UK", "restricted"]):
    print(r[:500])
    print()

# 06: Singhal 2023 - continual pre-training
print("="*80)
print("【06】Singhal 2023 - continual pre-training")
with open(f"{BASE}/fulltext/PMC10396962.html", "r", encoding="utf-8") as f:
    text = html_to_text(f.read())
for r in search_all(text, ["continual", "continued pre-training", "instruction tuning", "Flan-PaLM", "Med-PaLM"]):
    print(r[:500])
    print()

# 12: Bellenguez 2022 - CR1
print("="*80)
print("【12】Bellenguez 2022 - CR1")
with open(f"{BASE}/fulltext/PMC9005347.html", "r", encoding="utf-8") as f:
    text = html_to_text(f.read())
for r in search_all(text, ["CR1", "complement receptor", "C1s", "C1S"]):
    print(r[:400])
    print()

# 19: InterPro - Pfam UniProt link
print("="*80)
print("【19】InterPro - Pfam UniProt link")
with open(f"{BASE}/fulltext/PMC9825450.html", "r", encoding="utf-8") as f:
    text = html_to_text(f.read())
for r in search_all(text, ["UniProt", "link to", "active link", "redirect"]):
    print(r[:400])
    print()

# 27: ChatGPT review - genuine understanding
print("="*80)
print("【27】ChatGPT review - genuine understanding")
with open(f"{BASE}/fulltext/PMC10048148.html", "r", encoding="utf-8") as f:
    text = html_to_text(f.read())
for r in search_all(text, ["understanding", "comprehension", "reasoning abilit", "lack true"]):
    print(r[:400])
    print()
