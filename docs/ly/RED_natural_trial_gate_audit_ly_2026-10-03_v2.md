# RED seed=42 自然试标准入闸门审计（v2，2026-10-03）

本审计只评估现有 30 条 RED 是否满足进入正式自然引用试标的前置条件，不把通过数量写成正式 20—30 条试标集。正式试标仍需独立盲标和裁决。

- 总记录：30；排除：4；非排除：26
- 双方均有标签且已裁决：26
- 有明确全文/公开全文定位：16
- 仅摘要或入口级定位：10
- 同时满足非排除、双人标签、裁决、natural、全文定位的候选：16

## 闸门规则

记录必须同时满足：非 excluded；natural；双方标签和裁决字段齐全；被引原文有全文或公开全文定位。仅摘要、出版社入口或元数据不算全文闸门通过。

## 逐条结果

| citation_id | 证据层级 | 双方标签/裁决 | 闸门 | 说明 |
|---|---|---|---|---|
| RED:1 | 全文或公开全文定位 | 已齐全 | 通过 | 公开全文渲染页 LookChem（DOI 10.1002/anie.201603204）：摘要及全文引言，HTML 约第 1 页/引言段落说明 ZnO 强烈影响 CO 氢化并可作为 structural and electronic promoter；未直接给出施引句列举的 hydrogen reservoir、direct promot |
| RED:2 | 未能判断定位层级 | 不齐全 | 不通过 | excluded |
| RED:3 | 摘要/入口级定位 | 已齐全 | 不通过 | PubMed 官方摘要（PMID 34936965，DOI 10.1016/j.imbio.2021.152166）；网页行 267–272：研究慢性恰加斯病患者 TNF、sTNFR1/sTNFR2 和心脏病进展。 |
| RED:4 | 全文或公开全文定位 | 已齐全 | 通过 | ResearchGate 作者公开全文（DOI 10.1144/M36.2）；摘要/正文文章页 17–19，网页行 18–23、143–180、239–246：记载 23 个古大陆的分布史、1930 年代的发现阶段及 1982–1997 年可靠古地磁与冰海沉积模型的结论。 |
| RED:5 | 全文或公开全文定位 | 已齐全 | 通过 | arXiv v5 PDF（arXiv:1604.06620；对应 DOI 10.1109/ICPR.2016.7900086），p.1 Abstract 与 Introduction；文件 SHA-256=3FBAE3A78E34A4EDD21664365305F22E83D6568DB82023EF19B47053A3C47F0。 |
| RED:6 | 全文或公开全文定位 | 不齐全 | 不通过 | excluded |
| RED:7 | 摘要/入口级定位 | 已齐全 | 不通过 | Bentham Science 官方摘要页（DOI 10.2174/1574893615666200207094357）；网页行 239–265、482–488：主题为嗜热蛋白预测、蛋白序列特征融合和机器学习。 |
| RED:8 | 全文或公开全文定位 | 已齐全 | 通过 | TechScience 开放 PDF（DOI 10.32604/cmc.2020.013251）；文章第 1 页摘要及引言，全文主题为 IoT/云端深度学习诊断糖尿病视网膜病变。 |
| RED:9 | 摘要/入口级定位 | 已齐全 | 不通过 | ScienceDirect 官方摘要（DOI 10.1016/j.gr.2010.02.011）：South China Datangpo black shales（663–654.5 Ma）形成于 Sturtian 与 Marinoan 冰期之间的 Cryogenian interglacial；摘要重点是铁形态、钼浓度和古氧化还原环境 |
| RED:10 | 全文或公开全文定位 | 不齐全 | 不通过 | excluded |
| RED:11 | 全文或公开全文定位 | 已齐全 | 通过 | W. K. Wootters & W. H. Zurek, Nature 299 (1982) 802–803, DOI 10.1038/299802a0；摘要/第 802 页：说明量子态复制问题，并明确指出量子力学线性阻止复制，结论适用于所有量子系统。公开 PDF：tmp/red11_source_20261002/A_single_q |
| RED:12 | 摘要/入口级定位 | 已齐全 | 不通过 | Experts@Minnesota 文献页（DOI 10.1038/345315a0）；Abstract，网页行 33–45：明确说明 DMD 患者一个糖蛋白浓度显著降低、dystrophin 缺失可能导致相关糖蛋白丢失，但未给出施引句其余完整病理链。 |
| RED:13 | 摘要/入口级定位 | 已齐全 | 不通过 | PubMed 官方摘要（PMID 18200504；DOI 10.1002/eji.200737271）：MS 患者 Tr1 细胞活性和 IL-10R 信号受损；MS 患者分离的 Tr1 细胞比对照产生更少 IL-10，直接支持“Tr1-like、IL-10-producing T cells 减少”的概括。 |
| RED:14 | 全文或公开全文定位 | 已齐全 | 通过 | ResearchGate 作者公开全文（DOI 10.1182/blood-2009-03-209262）；Introduction/WHO guidelines 网页行 137–185、303–333，及 AML 诊断标准网页行 2373–2393：明确介绍修订 WHO 分类和 AML 诊断标准。 |
| RED:15 | 全文或公开全文定位 | 已齐全 | 通过 | PMC8215920 fullTextXML；Abstract（DeepCleave: protease substrate and cleavage-site prediction）。 |
| RED:16 | 摘要/入口级定位 | 已齐全 | 不通过 | ScienceDirect 官方摘要（DOI 10.1016/j.lithos.2014.03.014）：摘要说明 Ongatiti 单一火山系统的 amphibole-dominated crystal mush 位于 mid-lower crust，研究对象为 New Zealand 的一个大型流纹岩系统。 |
| RED:17 | 全文或公开全文定位 | 已齐全 | 通过 | 公开 PDF（Ibis 2015，DOI 10.1111/ibi.12258）第 7、10 页：研究巴尔干—撒哈拉以南非洲的埃及秃鹫迁徙；第 10 页说明幼鸟在越冬区探索多个区域以追踪 resource availability 和未来食物来源，但未直接建立施引句所称北半球繁殖资源与南半球越冬资源的普遍 dynamic link。 |
| RED:18 | 全文或公开全文定位 | 已齐全 | 通过 | PubMed 官方摘要（PMID 34763006；DOI 10.1016/j.jbiotec.2021.11.001）：摘要全文围绕 Pichia pastoris 的密码子使用偏好、密码子优化、蛋白表达、mRNA 稳定性和蛋白结构，未涉及高中翻译课堂、学生行为/认知/情感参与或翻译成绩。 |
| RED:19 | 全文或公开全文定位 | 已齐全 | 通过 | PMC8828813 fullTextXML；Abstract/Results（68Ga-DOTA-TOC 胰腺摄取与血糖相关性）。 |
| RED:20 | 全文或公开全文定位 | 已齐全 | 通过 | White Rose Research Online accepted manuscript（DOI 10.1016/j.clon.2020.08.010）；PDF 第 3 页 Abstract：研究 SABR、射频消融与手术治疗肝转移癌/HCC 的成本效果。公开 PDF：tmp/red20_source_20261002/SABR_co |
| RED:21 | 全文或公开全文定位 | 不齐全 | 不通过 | excluded |
| RED:22 | 摘要/入口级定位 | 已齐全 | 不通过 | ResearchGate/Springer 公开预览摘要（DOI 10.1007/s10853-018-2793-3）：研究 hierarchically porous metal–organic frameworks 的模板法、室温合成、孔结构和甲烷吸附；未给出施引句关于 coordination polymers 一般定义的完整证据。 |
| RED:23 | 全文或公开全文定位 | 已齐全 | 通过 | PMC2852313 fullTextXML；Introduction 第 1 段。 |
| RED:24 | 全文或公开全文定位 | 已齐全 | 通过 | arXiv:1602.06877（被引论文开放镜像）；PDF 第 1 页 Abstract。 |
| RED:25 | 摘要/入口级定位 | 已齐全 | 不通过 | EPA HERO 文献摘要（DOI 10.1016/j.diamond.2008.01.033）：报告 detonation nanodiamond 的酯化功能化、0.3–0.4 mmol g−1 表面负载及在有机溶剂中的分散性；未报告施引句的 electrolyte 中约 530 nm 团聚簇动态光散射结果。 |
| RED:26 | 全文或公开全文定位 | 已齐全 | 通过 | PMC4053721 fullTextXML；Materials and methods > voom variance modeling，以及 Normalization 段。 |
| RED:27 | 摘要/入口级定位 | 已齐全 | 不通过 | OpenAlex 文献摘要（DOI 10.1002/anie.202016233）：研究局域有序石墨化碳正极、双离子电池容量、倍率性能和循环稳定性；与施引句关于破碎种群、等位基因丰富度、遗传漂变和近交衰退无关。 |
| RED:28 | 摘要/入口级定位 | 已齐全 | 不通过 | PubMed 官方摘要（PMID 27825224；DOI 10.1063/1.4966192）：综述机器学习原子间势，明确回顾 ML potentials 的发展、适用性和局限，并讨论势能面表示；与施引句所说能源预测中的 kernels/descriptors 研究背景直接相关。 |
| RED:29 | 全文或公开全文定位 | 已齐全 | 通过 | PMC4634641 fullTextXML；Abstract，以及 Optical erasure of acquired skills 段。 |
| RED:30 | 全文或公开全文定位 | 已齐全 | 通过 | arXiv:1304.0911 开放 PDF；第 8 页（WSe2 Raman spectra 段，文章页 8/23）。 |

## 结论

按上述严格闸门，当前 RED seed=42 可作为“自然试标候选”的记录数为 **16** 条，仍不足 20 条。新增 RED:5 的 arXiv v5 公开预印本后，闸门计数由上一版 15 条增至 16 条；摘要级和入口级记录仍需取得可追溯全文证据，或另从开放来源抽取新的自然引用。不能用现有记录直接凑成 20 条。
