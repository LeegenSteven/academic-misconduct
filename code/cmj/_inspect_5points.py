# -*- coding: utf-8 -*-
"""检查5点材料的JSON结构"""
import json

F = r"C:\Users\Administrator\AppData\Local\Temp\ly_5points_20261022\02_离线补充诊断\5点人工复核材料_未填写.jsonl"

with open(F, "r", encoding="utf-8") as f:
    rec = json.loads(f.readline())
    print("顶层keys:", list(rec.keys()))
    print()
    for k, v in rec.items():
        if isinstance(v, str):
            print(f"{k}: {v[:200]}")
        elif isinstance(v, list):
            print(f"{k}: list[{len(v)}], first={str(v[0])[:200] if v else 'empty'}")
        elif isinstance(v, dict):
            print(f"{k}: dict keys={list(v.keys())[:10]}")
        else:
            print(f"{k}: {v}")
