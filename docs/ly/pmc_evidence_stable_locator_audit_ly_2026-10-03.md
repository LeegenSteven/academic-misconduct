# PMC 被引证据稳定定位核查（李云，2026-10-03）

## 结果

已通过 NCBI PMC OA BioC JSON 接口回取候选池涉及的 cited PMCID 共 16 个；20/20 条候选的 cited_evidence 均能在对应被引文献的 ABSTRACT passage 中定位。已将 evidence_locator 更新为 PMCID、BioC passage index（从 0 起）、全局字符 offset 和稳定接口 URL。

其中 18 条可在单个 passage 中直接匹配；PMC-OA-V2-05 和 PMC-OA-V2-16 的证据字段由原始抽取结果拼接/重复了相邻摘要片段，因此分别保留最先的精确段落或列出两个必要 passage，未把拼接文本伪装成单一连续段落。

## 定位口径

- 接口：https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/{PMCID}/unicode
- passage_index：BioC 文档 passages 数组的 0-based 下标。
- offset：BioC 文档中的原始字符起点。
- exact raw/normalized：原始证据文本可直接匹配，或只存在规范化空格/标点差异。
- normalized span：证据字段由多个摘要 passage 拼接，按规范化文本分别定位。

## 明细

|候选|被引 PMCID|passage index|offset|匹配状态|
|---|---|---:|---:|---|
|PMC-OA-V2-01|PMC10715499|2|137|exact raw/normalized|
|PMC-OA-V2-02|PMC10715499|2|137|exact raw/normalized|
|PMC-OA-V2-03|PMC5007409|2|135|exact raw/normalized|
|PMC-OA-V2-04|PMC10850450|1|96|exact raw/normalized|
|PMC-OA-V2-05|PMC11309924|2|88|exact raw/normalized|
|PMC-OA-V2-06|PMC12491465|1|103|exact raw/normalized|
|PMC-OA-V2-07|PMC6709302|3|68|exact raw/normalized|
|PMC-OA-V2-08|PMC6709302|3|68|exact raw/normalized|
|PMC-OA-V2-09|PMC11984007|2|157|exact raw/normalized|
|PMC-OA-V2-10|PMC7696452|1|119|exact raw/normalized|
|PMC-OA-V2-11|PMC8793832|1|54|exact raw/normalized|
|PMC-OA-V2-12|PMC6982324|1|76|exact raw/normalized|
|PMC-OA-V2-13|PMC6982324|1|76|exact raw/normalized|
|PMC-OA-V2-14|PMC12297025|1|113|exact raw/normalized|
|PMC-OA-V2-15|PMC5839013|2|106|exact raw/normalized|
|PMC-OA-V2-16|PMC7777221|1, 12|92, 2572|normalized span|
|PMC-OA-V2-17|PMC9099525|1|120|exact raw/normalized|
|PMC-OA-V2-18|PMC9099525|1|120|exact raw/normalized|
|PMC-OA-V2-19|PMC6837311|1|80|exact raw/normalized|
|PMC-OA-V2-20|PMC11177495|1|85|exact raw/normalized|

## 限制与后续

本轮定位落在被引文献的摘要段落，已经有稳定的 PMCID、passage index、offset 和原文接口地址；尚未补出版物 PDF 页码，也未将摘要定位等同于正文中更细的句号范围。正式入组前应由标注者复核施引句与该摘要/正文证据是否足以支持标签。候选池仍不是正式试标集，双方盲标和裁决完成前不计入正式样本数。
