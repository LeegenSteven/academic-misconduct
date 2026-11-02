"""提取10条理由收紧条目的原始claim、候选证据、v5理由和李云问题，生成DeepSeek审核文件"""
import json, re, csv

PAYLOAD = r"C:\Users\Administrator\AppData\Local\Temp\ly_45cases_20261020\45条全量初审_20261020\miss45_payload.jsonl"
V5_CSV = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v5_20261021.csv"
OUT = r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\10条理由收紧_DeepSeek审核材料_20261021.md"

TARGETS = ["48", "186", "235", "257", "466", "490", "502", "544", "580", "600"]

# 李云指出的问题
LIYUN_ISSUES = {
    "48": "原句说研究/应用成为热点，不等于临床疗效已证实，理由不应增加疗效前提。",
    "186": "原句没有'all'，可以讨论特定人群外推是否构成重要歪曲，不能先添加'所有'再判错。",
    "235": "Zachary的22%明确属于另一引文，当前Flanagan不负责覆盖这个数字；其地理描述另议。",
    "257": "正负行为同时变化不自动反驳综合饮食分数改善；全文总体分数句与原候选覆盖分别保留。",
    "466": "旧claim包含重复拼接和postmo截短，已在旧标注及冻结输入中存在；原XML目标更接近repair/immune通路比较。不能将旧片段恢复后悄悄作为原模型输入，也不能仅围绕'必须死后验证'片段判真实引用失实。",
    "490": "原目标只承担体内外实验句。不得把numerous experiments直接变成'多个独立论文'；也不能仅凭体内外各一项便自动通过。需区分实验数量与独立论文数量，不直接新增严格/宽松阈值。",
    "502": "The antiviral efficacy承接RDV；原候选D01说的是IFN-I，不能拿IFN-I替代RDV。全文有RDV小鼠结果。原XML引用6为恒河猴RDV研究、7为小鼠研究，组内不同文献可承担不同模型，不能因目标7没做恒河猴就否定整组。",
    "544": "原句没有'all'。候选研究特定黑人HIV样本，负面疫情影响与较低ART依从性有关；单次邻近月份数据不直接证明前后下降。不能改写成'所有HIV患者均下降'再判错。",
    "580": "目标标记紧接diet，不应要求此目标同时证明后面的心理健康内容。原句in children不是字面all children；是否省略肥胖小样本构成重要过度概括仍需裁决。",
    "600": "全文有41名肥胖儿童家长报告的运动时长减少2.30h/周及屏幕时长增加4.85h/日；不能说完全没有数值资料。但这是家长报告非客观活动测量，screen time不等于全部sedentary time；群体外推仍待裁决。",
}

# 读取v5
v5 = {}
with open(V5_CSV, "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        v5[r["claim_id"]] = r

# 读取payload
payload = {}
with open(PAYLOAD, "r", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        cid = str(rec.get("claim_id", ""))
        if cid in TARGETS:
            inp = rec.get("original_model_input", {})
            if isinstance(inp, str):
                inp = json.loads(inp)
            up = inp.get("user_prompt", "")
            m = re.search(r"引用论断：(.+?)(?:\n候选证据：|\n\n候选证据：|$)", up, re.DOTALL)
            claim = m.group(1).strip() if m else "?"
            cands = inp.get("candidate_evidence", [])
            payload[cid] = {"claim": claim, "candidates": cands}

# 生成MD
lines = []
lines.append("# 10条理由收紧审核材料（供DeepSeek同步审核）")
lines.append("")
lines.append("日期：2026-10-21")
lines.append("")
lines.append("## 背景")
lines.append("")
lines.append("45条Mbio退化案例复核v5已生成（42 NOT_ACCURATE / 3 ACCURATE）。李云接收核对后指出以下10条的理由存在范围/量词/引用归属问题，需要收紧。")
lines.append("")
lines.append("请逐条审核：")
lines.append("1. 陈明进v5当前理由是否准确（是否有范围误读、量词强化、引用归属错误）")
lines.append("2. 按李云指出的问题，理由应如何修改")
lines.append("3. 标签是否需要变更（维持NOT_ACCURATE / 改为暂缓 / 改ACCURATE）")
lines.append("")
lines.append("注意：候选证据是原模型输入中实际存在的证据；全文补核证据未进入原模型输入，不能用于支持原模型判断，但可用于诊断引用忠实性。")
lines.append("")
lines.append("---")
lines.append("")

for cid in TARGETS:
    p = payload.get(cid, {})
    v = v5.get(cid, {})
    lines.append(f"## claim {cid}")
    lines.append("")
    lines.append("**陈明进v5标签：** " + v.get("chen_label", "?"))
    lines.append("")
    lines.append("**claim原文：**")
    lines.append("")
    lines.append("> " + p.get("claim", "?"))
    lines.append("")
    lines.append("**候选证据（原模型输入）：**")
    lines.append("")
    for c in p.get("candidates", []):
        eid = c.get("evidence_id", "?")
        text = c.get("text", "")
        lines.append(f"- {eid}: {text}")
    lines.append("")
    lines.append("**陈明进v5理由：**")
    lines.append("")
    lines.append(v.get("chen_reason", "?"))
    lines.append("")
    lines.append("**陈明进v5归因：** " + v.get("chen_attribution_basis", "?"))
    lines.append("")
    lines.append("**李云指出的问题：**")
    lines.append("")
    lines.append(LIYUN_ISSUES.get(cid, "?"))
    lines.append("")
    lines.append("**请审核：**")
    lines.append("")
    lines.append("1. v5理由是否存在范围误读或量词强化？")
    lines.append("2. 按李云问题，理由应如何修改？")
    lines.append("3. 标签是否需要变更？")
    lines.append("")
    lines.append("---")
    lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"已生成: {OUT}")
print(f"包含10条: {', '.join(TARGETS)}")
import os
print(f"文件大小: {os.path.getsize(OUT)} bytes")
