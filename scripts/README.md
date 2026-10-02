# scripts — 数据获取与复现

因为 `data/` 不进版本控制，任何一份数据都必须能靠这里的脚本重建。

## 约定

每接入一个数据源，写一个 `fetch_<来源>.py`：

```bash
python scripts/fetch_crossref.py        # 抓取 → data/raw/crossref-20261002.json
python scripts/build_processed.py       # raw → interim → processed
```

要求：

1. **幂等**：重复运行结果一致；已有数据时默认跳过，`--force` 才重新抓取
2. **带日期**：输出文件名含抓取日期，不覆盖旧快照
3. **礼貌抓取**：外部 API 加 sleep 和重试，不要把人家的服务打挂
4. **可追溯**：抓完在这份 README 下方登记一条，写明来源、时间、行数

## 环境

```bash
pip install -r requirements.txt
```

待补充：`requirements.txt`。

## 当前入口

```bash
python scripts/fetch_seed42_sources.py --date 2026-10-02
python scripts/validate_seed42_snapshot.py
```

`fetch_seed42_sources.py` 从 SciFact 官方 S3 和 ReferenceErrorDetection 官方 GitHub 下载带日期的本地原始快照，并生成 SHA-256 manifest；它不会把原始文件加入 Git。`validate_seed42_snapshot.py` 检查已提交的 60 条脱敏核查快照的行数、ID 唯一性和裁决字段保护。

## 数据登记

> 每次抓取后追加一条，方便对不上数时回查。

| 日期 | 脚本 | 输出 | 行数 | 备注 |
|------|------|------|------|------|
| | | | | |
| 2026-10-02 | `fetch_seed42_sources.py` | `data/raw/*_2026-10-02.*` | — | 本地重建入口；原始文件按 `.gitignore` 忽略 |
| 2026-10-02 | `validate_seed42_snapshot.py` | `data/processed/seed42_source_audit_ly_v19.csv` | 60 | 李云侧阶段快照，未填最终裁决 |
