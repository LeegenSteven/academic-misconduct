# R2EXP25 三条待核补证

日期：2026-11-12｜范围：R2EXP25 第 04、12、19 点｜累计口径保持 22 确认＋3 待核

## 一、结论

1. 第 04 点：被引 Bellenguez 2022 纳入 UK Biobank 数据，正文无“排除 UK Biobank 估计遗传力”的表述；引用句的方法归属不成立，个人复核意见为按限定范围判 NOT_ACCURATE，待双方确认。
2. 第 12 点：Bellenguez Table 1 确有 CR1 位点 rs679515；全文无 C1s。引用可限定为“CR1 为 AD 风险位点”并判 ACCURATE，C1s 与补体激活诱导表述超出 [19]，整句仍待核。
3. 第 19 点：InterPro 2022 只说明 Pfam 属成员库、Pfam 网站功能迁入 InterPro，未直述“Pfam ID 链接到 UniProt 记录”；维持待核，缺当时页面或代码。
4. 三条均不改变 22 确认＋3 待核的总数；04 的改判建议、12 的限定范围均需李云确认后登记，不由单方改写。

## 二、逐条核查

### 第 04 点

- 施引：PMC9155614（braincomms fcac125），段 21，引用标记“2022”，目标 fcac125-B21。
- 施引句：For Wightman et al. (2021) and Bellenguez et al. (2022) studies, the heritability was estimated using summary statistics, excluding UK Biobank data.
- 被引原文：p57 用 LDSC v1.0.1 与 baselineLD 计算 LD score regression intercept；p55 将 EADB 与 UKBB proxy-AD 做 meta 分析；p316 列出 UKBB 诊断例 2,447、proxy 46,828、对照 338,440。
- 检索结果：SNP-based heritability 0 命中；excluding UK Biobank 0 命中；heritability 仅两处一般性表述。
- 判断：引用句把“用 summary statistics 估计遗传力并排除 UKB”归给 Bellenguez，与其实际做法相反（UKBB 被纳入）。最多只能承担“该研究提供 GWAS 数据来源”。

### 第 12 点

- 施引：PMC10889136（ijms25042272），段 3，引用标记 19，目标 B19。
- 施引句：Among the genetic risks for developing AD are polymorphisms for complement proteins, CR1 (Complement Receptor 1) or C1s (Complement protein 1s), which are inducers of complement activation [19,20].
- 被引原文：Table 1 的 CR1 行 rs679515，位置 1:207577223，MAF 0.188，OR 1.13（1.11–1.15），P=7.2×10^-46；C1s 全文 0 命中；无“inducers of complement activation”表述。
- 判断：CR1 部分成立；C1s 与“inducers”属于 [20] 或施引作者概括，不能记在 [19]。限定范围为 CR1 位点时可判 ACCURATE，整句维持待核。

### 第 19 点

- 施引：PMC10790787（Toxinome，mbio.01911-23），段 14，引用标记 45，目标 B45。
- 施引句：Pfam ID is an active link to the record on the UniProt website (45).
- 被引原文：p2 列 13 个成员库，含 Pfam；p34 说明 Pfam 网站退役、关键功能迁入 InterPro；p51 说明 InterPro 将在未来提供 Pfam 网站访问。全文无该链接关系的直接表述。
- 判断：[45] 只能支持 Pfam 属 InterPro 成员库与网站功能迁移；具体跳转关系需 Toxinome 当时页面、代码或截图。

## 三、对累计口径的影响

| 点位 | 当前状态 | 本次意见 | 累计口径 |
| --- | --- | --- | --- |
| 04 | 待核 | 建议限定范围 NOT_ACCURATE，待确认 | 不改总数 |
| 12 | 待核 | CR1 部分可判 ACCURATE，C1s 待 [20] | 不改总数 |
| 19 | 待核 | 维持待核，补页面或代码 | 不改总数 |

22 确认（20 ACC＋2 NA）＋3 待核的口径不变；确认后按点位逐条登记，不并入 25 条分母。

## 四、请求事项

1. 第 04 点：提供 Bellenguez Supplementary Note 中遗传力估计段落，或确认按“方法归属不成立”改判 NOT_ACCURATE。
2. 第 12 点：提供 [20] 全文，核对 C1s 与“inducers of complement activation”表述及 [19,20] 份额。
3. 第 19 点：提供 Toxinome 网站当时页面、前端代码或截图，证明 Pfam ID 的跳转目标。

## 五、边界

- 不修改冻结原文、既有标签和累计口径；改判建议须双方确认后登记。
- 不以缺词直接判错；本说明区分“原文相反”“超出范围”“缺页面证据”三种情形。
- 三条分别登记，不与本周 25 条或 15 条 gold 追索合并分母。

## 六、校验值

- 三条引用句、被引定位、检索命中数均已回填；04 的 excluding UK Biobank 命中 0、12 的 C1s 命中 0、19 的链接表述命中 0。
- 文件校验值见交付回执。
