# -*- coding: utf-8 -*-
"""查看有疑问条目的被引全文关键内容"""
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

def search_in_text(text, keywords, context=200):
    """在文本中搜索关键词，返回上下文"""
    results = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text, re.IGNORECASE):
            start = max(0, m.start() - context)
            end = min(len(text), m.end() + context)
            results.append(f"[{kw}] ...{text[start:end]}...")
            if len(results) >= 3:
                break
    return results

BASE = r"C:\Users\Administrator\AppData\Local\Temp\r2exp25_20261022"

# 有疑问的条目
queries = {
    "R2EXP-PMC-04": {
        "pmc": "PMC9005347",
        "keywords": ["UK Biobank", "heritability", "summary statistics", "excluding"]
    },
    "R2EXP-PMC-06": {
        "pmc": "PMC10396962",
        "keywords": ["continual pre-training", "pre-training", "Med-PaLM"]
    },
    "R2EXP-PMC-08": {
        "pmc": "PMC7614055",
        "keywords": ["0.72", "hazard ratio", "kidney disease progression", "cardiovascular death"]
    },
    "R2EXP-PMC-12": {
        "pmc": "PMC9005347",
        "keywords": ["CR1", "C1s", "complement", "genetic risk"]
    },
    "R2EXP-PMC-19": {
        "pmc": "PMC9825450",
        "keywords": ["Pfam", "UniProt", "link", "active link"]
    },
    "R2EXP-PMC-24": {
        "pmc": "PMC10048148",
        "keywords": ["clinical vignette", "simulated clinical", "oncology", "education"]
    },
    "R2EXP-PMC-27": {
        "pmc": "PMC10048148",
        "keywords": ["genuine understanding", "understanding", "limitation", "hallucination"]
    },
    "R2EXP-PMC-28": {
        "pmc": "PMC9005347",
        "keywords": ["111,326", "677,663", "two-stage", "clinically diagnosed"]
    },
}

for sid, q in queries.items():
    print(f"\n{'='*80}")
    print(f"【{sid}】被引: {q['pmc']}")
    try:
        with open(f"{BASE}/fulltext/{q['pmc']}.html", "r", encoding="utf-8") as f:
            text = html_to_text(f.read())
        results = search_in_text(text, q["keywords"])
        if results:
            for r in results[:3]:
                print(r)
                print()
        else:
            print("未找到关键词，打印摘要部分:")
            # 找摘要
            abs_match = re.search(r'(?:Abstract|ABSTRACT)[\s:]+(.{200,600}?)(?:Introduction|INTRODUCTION|Background|BACKGROUND)', text)
            if abs_match:
                print(abs_match.group(1)[:500])
            else:
                print(text[:500])
    except Exception as e:
        print(f"读取失败: {e}")
