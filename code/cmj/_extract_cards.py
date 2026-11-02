# -*- coding: utf-8 -*-
"""从所有card中提取黄色标记附近的完整上下文"""
import re
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
        self.in_mark = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True
        if tag == 'mark':
            self.in_mark = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False
        if tag == 'mark':
            self.in_mark = False
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)

def html_to_text(html):
    p = TextExtractor()
    p.feed(html)
    return ' '.join(''.join(p.text).split())

BASE = r"C:\Users\Administrator\AppData\Local\Temp\r2exp25_20261022"

import json
with open(f"{BASE}/annotation_units.jsonl", "r", encoding="utf-8") as f:
    units = [json.loads(l) for l in f if l.strip()]

for u in units:
    sid = u["sample_id"]
    card_path = f"{BASE}/cards/{sid}.html"
    with open(card_path, "r", encoding="utf-8") as f:
        card_html = f.read()
    
    # 找原始施引段落部分
    para_match = re.search(r'<h2>原始施引段落</h2>(.*?)<p>XML定位', card_html, re.DOTALL)
    if para_match:
        para_html = para_match.group(1)
        # 去掉HTML标签但保留mark位置信息
        # 先找mark的位置
        mark_match = re.search(r'<mark[^>]*>(.*?)</mark>', para_html)
        if mark_match:
            mark_text = mark_match.group(1)
            # 提取mark前后各200字符
            start = max(0, mark_match.start() - 250)
            end = min(len(para_html), mark_match.end() + 250)
            snippet = para_html[start:end]
            snippet_text = html_to_text(snippet)
            print(f"\n【{sid}】mark内容={html_to_text(mark_text)}")
            print(f"  上下文: ...{snippet_text}...")
        else:
            print(f"\n【{sid}】未找到mark标记")
    else:
        print(f"\n【{sid}】未找到原始施引段落")
