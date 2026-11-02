"""
脚本：filter_stable_control_groupfix_r1.py
功能：对照候选49条 → 44正式对照 +5盲测样本，SEED=42固定可复现
修复记录：
旧bug根源：concat(ignore_index=True)重置行号，旧脚本使用sample_blind.index旧行号给新总表赋值group，
导致总名单group列4条样本错位；但sample_control、sample_blind子表本身数据正确，未改动抽样。
修复方案：改用OpenAlex_W集合匹配分组，增加三重assert校验，不再依赖DataFrame行号。
输出：
- 任务1_对照样本_稳定总名单_49条_group修正r1.csv
- 任务1_对照样本_正式对照_44条.csv
- 任务1_对照样本_盲测样本_5条.csv
- 任务1_对照样本_剔除记录.csv
"""
import pandas as pd

# 读取候选
df = pd.read_csv("任务1_匹配对照候选.csv", encoding="utf-8-sig")
print(f"原始候选总数：{len(df)}")
print("字段：", df.columns.tolist())

# ========== 准入筛选规则 ==========
# 准入硬条件：
# 1. OpenAlex_W以W开头（可映射）
# 2. 是否撤稿标记=False（对照样本不能是撤稿）
# 3. WID无重复
# 年份不作为剔除条件
mask_mapped = df["OpenAlex_W"].astype(str).str.startswith("W")
mask_not_retracted = df["是否撤稿标记"] == False
mask_unique = ~df["OpenAlex_W"].duplicated(keep="first")

pass_mask = mask_mapped & mask_not_retracted & mask_unique
pool_all = df[pass_mask].copy()
dropped = df[~pass_mask].copy()

print(f"\n准入合格池数量：{len(pool_all)}")
print(f"剔除数量：{len(dropped)}")
if len(dropped) > 0:
    print("剔除明细：")
    print(dropped[["OpenAlex_W","标题","年份","是否撤稿标记"]].to_string(index=False))

# ========== 固定种子随机划分：盲测取5条，剩余全部正式对照【可复现】==========
SEED = 42
sample_blind = pool_all.sample(n=5, random_state=SEED)
sample_control = pool_all.drop(sample_blind.index)

print(f"\n正式对照数量：{len(sample_control)}")
print(f"盲测样本数量：{len(sample_blind)}")
print(f"合计：{len(sample_control)+len(sample_blind)}")

# 合并一份总稳定名单
stable_total = pd.concat([sample_control, sample_blind], ignore_index=True)
stable_total["group"] = "正式对照"
# concat(ignore_index=True) 已重置行号，必须按稳定W号回填分组。
blind_ids = set(sample_blind["OpenAlex_W"])
control_ids = set(sample_control["OpenAlex_W"])
stable_total.loc[stable_total["OpenAlex_W"].isin(blind_ids), "group"] = "盲测样本"
assert not (blind_ids & control_ids)
assert set(stable_total.loc[stable_total["group"] == "盲测样本", "OpenAlex_W"]) == blind_ids
assert set(stable_total.loc[stable_total["group"] == "正式对照", "OpenAlex_W"]) == control_ids

# ========== 落盘输出 ==========
stable_total.to_csv("任务1_对照样本_稳定总名单_49条_group修正r1.csv", index=False, encoding="utf-8-sig")
sample_control.to_csv("任务1_对照样本_正式对照_44条.csv", index=False, encoding="utf-8-sig")
sample_blind.to_csv("任务1_对照样本_盲测样本_5条.csv", index=False, encoding="utf-8-sig")
dropped.to_csv("任务1_对照样本_剔除记录.csv", index=False, encoding="utf-8-sig")

print("\n文件输出完成：")
print("1. 任务1_对照样本_稳定总名单_49条_group修正r1.csv（带group分组标记）")
print("2. 任务1_对照样本_正式对照_44条.csv")
print("3. 任务1_对照样本_盲测样本_5条.csv")
print("4. 任务1_对照样本_剔除记录.csv")
print(f"随机种子 SEED={SEED}，可复现该套划分")
