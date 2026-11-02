# -*- coding: utf-8 -*-
"""提取25条的引用分句和被引论文关键信息"""
import json
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

def extract_sentences_with_marker(context, marker):
    """从上下文中提取包含marker的句子"""
    # 按句号分割
    sentences = re.split(r'(?<=[.!?])\s+', context)
    result = []
    for s in sentences:
        if marker in s or f'[{marker}]' in s or f'<sup>{marker}</sup>' in s:
            result.append(s.strip())
    return result

BASE = r"C:\Users\Administrator\AppData\Local\Temp\r2exp25_20261022"

with open(f"{BASE}/annotation_units.jsonl", "r", encoding="utf-8") as f:
    units = [json.loads(l) for l in f if l.strip()]

for u in units:
    sid = u["sample_id"]
    marker = u.get("target_marker_text", "")
    ctx = u.get("citing_context", "")
    cited_pmc = u.get("cited_reading_path", "").split("/")[-1].replace(".html", "")
    
    print(f"\n{'='*80}")
    print(f"【{sid}】marker={marker}")
    print(f"施引: {u['citing_title'][:60]}")
    print(f"被引: {u['cited_title'][:60]} ({cited_pmc})")
    
    # 提取包含marker的句子
    sents = extract_sentences_with_marker(ctx, marker)
    if sents:
        print(f"引用分句: {sents[0][:300]}")
    else:
        # 尝试从card中提取
        card_path = f"{BASE}/cards/{sid}.html"
        try:
            with open(card_path, "r", encoding="utf-8") as f:
                card_html = f.read()
            # 找mark标记附近的文本
            mark_match = re.search(r'<mark[^>]*>.*?</mark>', card_html)
            if mark_match:
                # 提取mark前后的句子
                start = max(0, mark_match.start() - 300)
                end = min(len(card_html), mark_match.end() + 300)
                snippet = card_html[start:end]
                snippet_text = html_to_text(snippet)
                print(f"引用附近(从card): {snippet_text[:300]}")
        except:
            pass
        print(f"上下文: {ctx[:300]}")
    
    # 读取被引全文标题和摘要
    try:
        with open(f"{BASE}/fulltext/{cited_pmc}.html", "r", encoding="utf-8") as f:
            cited_html = f.read()
        cited_text = html_to_text(cited_html)
        # 找摘要
        abstract_match = re.search(r'(?:Abstract|ABSTRACT)[\s:]+(.{200,800}?)(?:\n\s*(?:Introduction|INTRODUCTION|Background|BACKGROUND|Methods|METHODS|Results|RESULTS))', cited_text, re.DOTALL)
        if abstract_match:
            print(f"被引摘要: {abstract_match.group(1)[:400]}")
        else:
            print(f"被引开头: {cited_text[:400]}")
    except Exception as e:
        print(f"被引全文读取失败: {e}")
