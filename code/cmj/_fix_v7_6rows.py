# -*- coding: utf-8 -*-
import csv

updates = {
    "235": {
        "chen_label": "NOT_ACCURATE",
        "chen_reason": "当前目标Flanagan只承担27.5%这一数字，D05:S01支持27.5%（D01:S01为27.3%）；Zachary的22%属other_cit，不由当前目标承担。27.5%为Flanagan全样本（多国）数值，claim归为美国结果但无美国亚组27.5%的直接支持，具体数值的地域归属错误构成重要范围简化。与250不同：250是方向性结论且有美国亚组方向一致支持，235是具体数值归属错误。经双方共同确认维持NOT_ACCURATE。",
        "chen_attribution_basis": "27.5%为全样本数值非美国亚组，地域归属错误构成重要范围简化；22%属other_cit不由当前目标承担",
        "resolved_label": "NOT_ACCURATE",
        "review_status": "resolved",
    },
    "236": {
        "chen_attribution_basis": "候选为验证问卷+自编题混合（D03: combination of validated questionnaires with minor modifications），claim未排除自编题；may have enhanced为弱推断保留限制",
    },
    "342": {
        "chen_attribution_basis": "雷帕霉素作为药物实例支持can be beneficial可能性主张；保留PDAPP小鼠模型限制，不推广到所有药物，也不视为已证实自噬中介机制",
    },
    "466": {
        "chen_label": "NOT_ACCURATE",
        "chen_reason": "【暂缓】原claim存在重复拼接和postmo截短，不能围绕截断片段判引用失实。经双方确认恢复引用范围为'The comparison of findings between...'对应的第二句，即本研究与Voineagu研究的若干通路重叠（修复和免疫相关过程）。原候选D01（RNA-Seq验证）、D02（模块与疾病相关）支持自闭症转录与功能通路异常。范围确认后再议标签，不把'死后验证'另一句拼进来，也不把异常归因于A100。",
        "chen_attribution_basis": "claim截断/拼接，暂缓三分类；恢复范围为通路比较（修复/免疫），原候选有支持；不围绕截断postmo片段判错",
        "review_status": "pending_two_reviews",
    },
    "490": {
        "chen_reason": "【待核】范围确认：It承接IFN-I treatment（含IFN-I单用及含IFN-I方案，不扩成所有抗MERS治疗），ref14承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，首句双病毒活性另有ref20。全文方法部分有IFNb体外试验、多次动物预防/治疗研究及既往动物研究，支持numerous的定性概括；但动物治疗研究无IFNb单药组，结果不全部阳性。原10候选只提供概述、结果及试验目的，不能可靠合计独立实验数，D03/D04重复不计。标签待双方统一判断口径：若按被引全文判断引用忠实性可给限定性ACCURATE；若按原候选覆盖则numerous支持不足。全文复核意见不直接修改冻结标签或成绩。",
        "chen_attribution_basis": "范围确认：It=IFN-I treatment, ref14=第二句；全文支持numerous定性概括但原候选覆盖不足；不预设独立实验数量；标签待共同确认判断口径",
        "review_status": "pending_two_reviews",
    },
    "580": {
        "chen_label": "ACCURATE",
        "chen_reason": "目标5紧接changes in diet，只承担diet从句，不要求同时证明mental health或BMI因果。原候选D02:S01/D04:S01直接支持肥胖儿童/青少年饮食行为出现不利变化，D07:S01支持每日进餐次数增加（P<0.001）。原句'in children ... have been reported'是报告性表述，未给总体比例或all children主张，核心'儿童中已有饮食变化报告'有直接支持。被引为意大利41名肥胖儿童小样本、家长报告，施引语境为奥地利一般小学生BMI讨论，省略obesity限定可能造成外推印象，但不改变报告性核心。保留样本及家长报告限制。经复核由NOT_ACCURATE改为限定性ACCURATE，待李云确认。",
        "chen_attribution_basis": "目标只承担diet；饮食变化报告有D02/D04/D07直接支持；in children为报告性表述非all children；保留意大利肥胖儿童小样本及家长报告限制",
        "review_status": "pending_two_reviews",
    },
}

paths = [
    r"C:\Users\Administrator\Desktop\miss45_review_陈明进v7_20261022.csv",
    r"C:\Users\Administrator\Documents\academic-misconduct\deliverables\2026-10-20_45条漏检案例复核\miss45_review_陈明进v7_20261022.csv",
]

for path in paths:
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    for row in rows:
        cid = row.get("claim_id", "")
        if cid in updates:
            for k, v in updates[cid].items():
                if k in row:
                    row[k] = v
            print(f"已更新 claim {cid}: label={row['chen_label']}, status={row['review_status']}")
    
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已保存: {path}\n")

# 统计最终分布
with open(paths[0], "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    acc = sum(1 for r in rows if r["chen_label"] == "ACCURATE")
    na = sum(1 for r in rows if r["chen_label"] == "NOT_ACCURATE")
    resolved = sum(1 for r in rows if r["review_status"] == "resolved")
    pending = sum(1 for r in rows if r["review_status"] == "pending_two_reviews")
    print(f"最终分布: ACCURATE={acc}, NOT_ACCURATE={na}, 总计={len(rows)}")
    print(f"已裁决(resolved)={resolved}, 待核(pending)={pending}")
