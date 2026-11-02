# -*- coding: utf-8 -*-
"""完整替换md中490的两处理由"""
import re

MD = r"C:\Users\Administrator\Desktop\45条三方对比与分歧裁决_陈明进_v7_20261022.md"

with open(MD, "r", encoding="utf-8") as f:
    content = f.read()

new_reason = (
    "- **理由**：【待核】目标14只承担第二句'It has been investigated in numerous experiments both in vitro and in vivo'，"
    "不承担首句'IFN-I对MERS-CoV/SARS-CoV有活性'（首句引other_cit），也不要求单药或结果全部阳性。"
    "原候选有in vitro相关提及（D01:S02含IFNb体外抗MERS-CoV活性评估、D07:S01含RDV与IFNb体外抗病毒活性比较）"
    "和in vivo相关提及（D03:D04重复概述句、D04:S02 MIRACLE试验），"
    "但概述句、结果句及试验目的句不足以直接合计为确定数量的独立实验；"
    "D03:S01与D04:S01文本完全一致为重复句不计两项；"
    "'numerous experiments'是否充分支持需共同确认，本轮不预设确定计数。"
    "待确认点：claim中'It'指代IFN-I单药还是泛抗MERS-CoV治疗；"
    "若限定IFN-I单药，D03/D04（RDV相关）和D04:S02（组合疗法）是否计入需共同裁决。"
    "不要求多个独立论文，也不要求单药或全部阳性。"
)

# 匹配所有以"- **理由**：【待核】目标14只承担第二句"开头的行（490出现两次）
# 用正则匹配从开头到行尾
pattern = r"- \*\*理由\*\*：【待核】目标14只承担第二句.*?(?=\n|$)"
matches = re.findall(pattern, content, re.DOTALL)
print(f"找到 {len(matches)} 处490理由")

# 替换所有匹配
content_new = re.sub(pattern, new_reason, content, flags=re.DOTALL)

with open(MD, "w", encoding="utf-8") as f:
    f.write(content_new)

# 验证
with open(MD, "r", encoding="utf-8") as f:
    c = f.read()
print(f"含 RDV+IFNb: {'RDV+IFNb' in c}")
print(f"含 合计4项: {'合计4项' in c}")
print(f"含 in vitro 2项: {'in vitro 2项' in c}")
print(f"含 不预设确定计数: {'不预设确定计数' in c}")
print(f"含 其余38条: {'其余38条' in c}")
print(f"含 其余37条: {'其余37条' in c}")
