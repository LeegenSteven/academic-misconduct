# -*- coding: utf-8 -*-
"""检查candidates的实际字段"""
import json

F = r"C:\Users\Administrator\AppData\Local\Temp\ly_5points_20261022\02_离线补充诊断\5点人工复核材料_未填写.jsonl"

with open(F, "r", encoding="utf-8") as f:
    rec = json.loads(f.readline())
    c = rec["candidates"][0]
    print("candidate keys:", list(c.keys()))
    print()
    for k, v in c.items():
        if isinstance(v, str):
            print(f"{k}: {v[:200]}")
        else:
            print(f"{k}: {type(v).__name__} = {str(v)[:100]}")
