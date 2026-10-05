# PMC natural v3 双人对照与来源复核说明

日期：2026-10-05

## 回传完整性

- 陈明进回传原件已按原始字节保留：`pmc_oa_v3_10_candidates_chen_blind_annotation_return_raw_2026-10-05_gb18030.csv`
- 编码：GB18030
- SHA-256：`0BDCD570F7DB28D79B427F02E6E4E733E3B4F789AF6181F662FE987BCB346887`
- 记录数：10
- `candidate_id` 唯一：是
- 10 条 `annotator_1_evidence_status` 均已填写为“已定位”
- 与发送的 10 条盲标候选 ID 集合一致：是

## 当前对照结果

- 标签一致：5/10
- 标签分歧：5/10（PMC-OA-V3-02、03、04、07、08）
- 最终裁决：尚未填写
- 双方原始标签和理由：均保留，未覆盖

## 需要共同回看的来源核查

1. **PMC-OA-V3-02**：PMC10765876 正文可定位到 p=5、8、52，涉及 healthy periapical tissue、biocompatible 和 non-toxic。师兄只按摘要判断“未涉及 periapical tissues tolerance”，李云侧按整体语境判为 ACCURATE。该条需要按项目的“完整 claim 是否由该引用支持”口径共同决定。
2. **PMC-OA-V3-03**：PMC4868912 p=39 明确说根管封闭剂 adhesion 的定义，并指出该连接涉及 mechanical interlocking forces rather than molecular attraction。这个原文直接影响“molecular attraction”表述，师兄的 NOT_ACCURATE 有明确全文依据；李云侧初标需复核。
3. **PMC-OA-V3-04**：PMC4841349 p=19、28 讨论 AH-Plus 的 mixed/cohesive failure 和 Endosequence 的 failure mode，但施引段使用了“Sealer Plus BC”名称。需要核对产品名称和整段 claim 是否构成部分支持。
4. **PMC-OA-V3-07**：PMC13193722 p=7、8 支持质谱蛋白质组学的灵敏度/通量和 D/L-2HG 的生物手性效应，但“简单快速探索”是否由该具体引用直接支持，需要按多引用句的分段口径裁决。
5. **PMC-OA-V3-08**：PMC9708575 p=13、19、21、23、24、35 讨论 PNN 降解/重塑与 associative、spatial、social、auditory 等记忆或学习变化。师兄仅据摘要认为证据不足，需改按全文定位复核；李云侧 ACCURATE 有较强全文依据。

## 数据质量备注

- **PMC-OA-V3-10** 的陈明进理由与 **PMC-OA-V3-09** 理由完全相同，内容描述 HA 与胶质激活，和 PMC10464498 的脑衰老/胶质炎症主题不一致。该条标签暂不改写；共同裁决时应先让陈明进补正理由或确认原意。
- 以上来源核查只用于准备共同裁决，不替代双方共同裁决；在共同裁决完成前，不写入 `adjudicated_label`，不计入最终合格样本。
