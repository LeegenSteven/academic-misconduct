# 固定45条错误案例交付版

更新日期：2026-10-25。先看[一页分析](一页分析.md)，逐条看[45条归并主表](miss45_review_归并版.csv)。

**本轮固定45条已逐条完成来源复核与共同处置：43条限定分类（27 ACCURATE、16 NOT_ACCURATE），217/466两条共同确认不作三分类，待裁决0条。** 已收到并归并陈明进对剩余10项的真实同版回复；原35条及原因确认继续沿用。完成的是本45条案例复核，不代表PDF或模型实现验收通过。

## 文件与字段

- `miss45_review_归并版.csv`：固定45案例，当前限定范围与意见在前列；双方首轮`*_original_*`原值和来源保留。
- `已有20条复核及归因补充.csv`：原有20条最终标签和原理由保持原值；与45条仅sarol:test:51重合，共64个不同案例。原预测暴露情况未记载的保持unknown。
- `paired_transitions.csv`：原606条配对表原样保留，未回改统计。
- `证据与归因依据.jsonl`：与主表同序，含原文件哈希、候选来源、补充定位和实际确认出处。
- [陈明进原始回复](45条集中确认回复_20261025.md)与[集中登记](陈明进集中确认登记_20261025.json)：记录本次真实意见、原ID及显式对应。
- `交付核验.json`：当前计数、变动单元格、来源哈希与保护文件核查。PASS仅指列出的检查通过，不是人工未决项已解决。

`frozen_gold/M0_pred/Mbio_pred`为原冻结值；`current_scope_label`仅为限定范围来源复核共同意见，本版空值仅为217/466已共同确认的非分类处置，不映射为IRRELEVANT。`li_original_* / chen_original_*`为实际首轮原值；`*_current_label`来自后续实际确认。摘要为对原件的整理，不是新增人工原话。

`assistant_reason_codes/assistant_SEM_subtypes/assistant_attribution_basis`保留助手归因建议；新增`chen_current_reason_codes/chen_current_SEM_subtypes/chen_reason_confirmation_basis/chen_reason_confirmation_source/chen_reason_source_case_id`登记陈明进本次书面意见及来文主键。李云本次明确回复“全部认可”，233的ATT与新增CTX均已确认；`joint_reason_codes`及`joint_SEM_subtypes`据实际双方意见登记。新增`li_current_reason_codes/li_current_SEM_subtypes/li_reason_confirmation_source`保留李云本次意见与出处，实际确认见[本轮确认原文及范围](李云本轮原因码确认_20261025.json)。两表65行、64个不同案例；原20例来文10处前缀已由陈明进修订，更正后的20条ID、原因码及SEM子类与现有表均一致，原稿保留。CTX等诊断候选覆盖或复核范围，不证明模型内部因果机制；原因内容已确认不等于未决标签已裁决。

120、190按双方真实确认登记限定ACCURATE，陈明进首轮NOT_ACCURATE仍在历史列；两条UNK含义为评分范围差异，不写模型错因未定、不升格SEM。466恢复句ACCURATE只作诊断；原冻结claim已共同确认为损坏、不作三分类。补充全文未写回模型输入，gold、预测和成绩不变。

## 20例来文ID问题

旧稿第三节10条Sarol案例误写为SciCiteVal前缀：1、2、5、16、31、51、61、115、153、402。陈明进[本次修订稿](45条集中确认回复_20261025(1).md)已全部更正为sarol:test:*；机器逐行比较确认其余文本不变，更正后20条ID与现有主键逐条一致，原因码、SEM子类和理由相同。[更正登记](陈明进ID前缀更正登记_20261025.json)保留旧ID→新ID及来源哈希。当前表引用修订原件；旧回复和更正前确认收据保持原样。原20例最终标签、理由、日期、预测暴露信息均未更改。本项已收口，无需重复发送或确认。

## 剩余10项共同确认已完成

[陈明进最新原始回复](剩余10条确认回复_20261025.md)已按字节归档，与[李云实际确认](李云剩余10条处置确认_20261025.json)逐项对应；10条ID、分类/处置及32个证据定位键均匹配。共同理由同时保存判断范围、依据、限制与证据缺口。完整来源及来文行号见[共同处置登记](剩余10条双方共同处置登记_20261025.json)。

| 本次收口ID | 实际共同结果 | 关键限制 |
| --- | --- | --- |
| 48 | ACCURATE | 仅研究关注/探索性治疗，不称临床疗效已确证。 |
| 63 | NOT_ACCURATE | 保留most数量概括，所引来源未给领域分母。 |
| 87 | ACCURATE | 作者may假说与被引实验区分，目标只承担理论背景。 |
| 197 | NOT_ACCURATE | 保留PWID及双终点，PWID特异重症支持存在缺口。 |
| 217 | 不作三分类 | small幅度口径不明确，不以P值或新阈值强判。 |
| 243 | NOT_ACCURATE | 参与者国别分布不能替代领域研究篇数。 |
| 278 | ACCURATE | immunity按抗体反应读数，不推为总体保护增强。 |
| 466 | 不作三分类 | 原冻结claim损坏；恢复句仅诊断，不替换输入或gold。 |
| 469 | ACCURATE | 方法应用谱系可支持，完整参数及补充方法未完全核实。 |
| 506 | NOT_ACCURATE | 指定细胞对象未获所引来源支持，仅核对象与证据层次。 |

`joint_disposition`对全45条明确区分：43条`SCOPED_LABEL`；217为`UNDETERMINABLE_MAGNITUDE`；466为`NON_ADJUDICABLE_FROZEN_CLAIM`。后两条`current_scope_label/li_current_label/chen_current_label`均为空。`chen_current_disposition`记录本次10项实际回文处置；旧35条不新增签核。李云原已确认意见不改，陈明进首轮意见保留在`chen_original_*`；`current_state_source`指向绑定双方来源的共同登记。

既有[10项建议说明](剩余10条_集中处置建议.md)和[证据依据JSON](剩余10条处置依据_20261025.json)保留签核前历史快照，内含当时待确认状态；当前实际结果以上表和主表为准，无需重新发送它们索要确认。

138、236、342、580的[评分范围疑点](gold疑点旁表_仅诊断.jsonl)仅作诊断，同属固定45条，不新增样本、不改gold。242不再归为数值SEM。

`归因与未决项_共同确认单.md`是10月24日已发送的历史确认单，内容及当时计数保留；当前状态以本README和主表为准。原已发送ZIP不覆盖；本轮没有新ZIP、外发消息、GitHub推送或模型运行。
