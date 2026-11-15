# R2EXP25 四条待核本地证据复核（2026-11-09）

本记录复用现有 R2EXP25 正文包，对成员1列出的 04、12、19、27 四条待核项做一次集中证据核对。它只形成李云个人复核建议，不回填 `joint_*`，不修改原始 CSV、gold 或模型结果。

## 04：继续待核，偏数据来源范围

- 施引目标范围是 `excluding UK Biobank data` 与“使用 summary statistics 估计遗传力”的关系。
- 被引 PMC9005347 的 p2 明确写 EADB GWAS 与 UK Biobank proxy-AD GWAS 做 meta-analysis；p48 明确 stage I 样本包含 UKBB，并列出 2,447 个 diagnosed cases、46,828 个 proxy cases 和 338,440 个 controls。
- 当前正文没有直接给出施引句所需的“用 summary statistics 估计 heritability 且排除 UKBB”方法归属。现有证据能支持数据来源和 UKBB 被纳入研究范围，不能单独决定该句是否把排除 UKBB 归因给 Bellenguez 研究。
- 处理：继续待核，暂不填标签。

## 12：继续待核，缺 reference 20 全文

- 施引 PMC10889136 的目标引用标记 `[19]` 落在 CR1/C1s 及 complement activation 的成组句末。
- 当前被引 PMC9005347 可用于核对 reference 19 的 CR1 关联，但本地材料没有 reference 20 对应全文，因此无法确认 C1s 与“inducers of complement activation”这一分句是否由 [20] 承担。
- 处理：继续待核，等待 reference 20 全文或可定位段落。

## 19：继续待核，缺当时网站跳转证据

- 施引 PMC10790787 的目标标记 `[45]` 落在“Pfam ID is an active link to the record on the UniProt website”句末。
- 被引 PMC9825450 p2 支持 Pfam 是 InterPro 的成员数据库，p4、p16、p34、p53支持 InterPro 与 Pfam 网站功能、网页访问和数据资源关系。
- 当前正文没有直接记录 Toxinome 网站当时的 Pfam ID 到 UniProt 跳转关系。InterPro/Pfam 资源背景不能替代该具体网站功能的版本证据。
- 处理：继续待核，等待当时网站页面、代码或截图。

## 27：建议按限定句登记个人 ACCURATE，待确认

- 施引 PMC11579624 的目标引用标记 `[92]` 只落在第一句“absence of genuine understanding”之后。后续“lack true comprehension or reasoning abilities”使用的是另一个引用 `[93]`，不归给 [92]。
- 被引 PMC10048148 p49 明确写当前 LLM（包括 ChatGPT）无法理解生物系统的复杂性，该能力是医疗决策和研究所需的重要概念。
- 因此，按当前引用范围，[92] 对“缺乏真正理解”这一限定主张有直接支持。该意见不外推到后一句 reasoning claim。
- 个人建议：`ACCURATE`，范围限定为 `[92]` 所承担的第一句。尚未登记为共同结论，等待李云确认后再写入个人意见记录。

## 来源文件哈希

- `PMC9005347.html` SHA256 `540f8c30f2dc7008e2982c80384c99861723a23e80dc4c9331f100e9631abb57`
- `PMC9825450.html` SHA256 `87d0ba59e5494258cc8073b87f08d4d5702c20480e9f18817995b8d99e14f799`
- `PMC10048148.html` SHA256 `941cfa3c879242180913238df234f5d85c89537033c35f331945de02301e2712`

本轮没有新增模型运行、分数或共同裁决。R2EXP25 仍按 21 条共同确认、4 条待核维护。

## 2026-11-13 陈明进三条待核补证回传

陈明进回传的三条补证材料已解压核对。范围为 R2EXP25 第04、12、19点，三条均不改原始累计口径。第04点建议按“方法归属不成立”限定为个人 `NOT_ACCURATE`，等待双方确认；第12点仅在“CR1 为 AD 风险位点”限定范围内个人建议 `ACCURATE`，C1s 与 complement activation 仍需 reference 20，整句继续待核；第19点继续待核，缺 Toxinome 当时页面、代码或截图证明 Pfam ID 的跳转目标。

本回传不修改原始 CSV、gold、模型输出、Test、score 或 joint 字段。由于第27点已由双方登记共同 `ACCURATE`，R2EXP25 当前口径更新为 **22 条共同确认、04/12/19 三条共同待核**。第04的改判建议和第12的限定范围意见仍是个人意见，未代填共同字段。

回传包：`11.9-11.15/R2EXP25三条待核补证_20261112/`；压缩包 SHA256 `124f3252772edae2a2b4a2b0c465b7d48121cba4d7f30f730d136a5a24929068`；Markdown SHA256 `5a465c07182fa5470bf43855a6374beabb6410efd855814eb6b63ab31f42cd70`；Excel SHA256 `0e7898d274eca803d16b6e9182043f4c6d162530546b9c19511a469ad239cec8`。

## 2026-11-13 李云个人意见确认

李云已明确确认：

- 第04点：按“Bellenguez 方法归属不成立、但具体范围以当前补证为限”登记个人 `NOT_ACCURATE`；是否形成共同结论仍待双方确认。
- 第12点：按“CR1 为 AD 风险位点”限定范围登记个人 `ACCURATE`；C1s 与 `inducers of complement activation` 不归入 [19]，整句继续待核。
- 第19点：继续待核，等待 Toxinome 当时网页、代码或截图证明 Pfam ID 的跳转目标。

本次确认不改变 R2EXP25 的累计口径：22 条共同确认、04/12/19 三条共同待核。未回填新的 `joint_*`，未修改原始 CSV、gold、模型输出、Test 成绩或 score。

## 2026-11-14 陈明进登记回复

陈明进已回复确认按以下方式登记：第04点为李云个人限定范围 `NOT_ACCURATE`，第12点为李云个人限定范围 `ACCURATE`，整句继续待核，第19点继续待核；三条只登记个人意见，不写入 `joint`。R2EXP25 继续保持 22 条共同确认、04/12/19 三条共同待核，`joint`、gold、Test 和 score 不变。
