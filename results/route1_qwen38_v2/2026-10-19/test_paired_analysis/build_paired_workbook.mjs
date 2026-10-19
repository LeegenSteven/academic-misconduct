import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const dir = path.dirname(fileURLToPath(import.meta.url));
const summary = JSON.parse(await fs.readFile(path.join(dir, "paired_summary.json"), "utf8"));
const paired = (await fs.readFile(path.join(dir, "paired_rows.jsonl"), "utf8"))
  .trim().split(/\r?\n/).map(line => JSON.parse(line));
const cases = (await fs.readFile(path.join(dir, "case_review_packet.jsonl"), "utf8"))
  .trim().split(/\r?\n/).map(line => JSON.parse(line));

const wb = Workbook.create();
const result = wb.worksheets.add("结果");
const details = wb.worksheets.add("逐条配对");
const review = wb.worksheets.add("20例待复核");
for (const sheet of [result, details, review]) sheet.showGridLines = false;

function setHeader(sheet, range) {
  sheet.getRange(range).format.fill = "#17365D";
  sheet.getRange(range).format.font = { name: "Microsoft YaHei", size: 10, bold: true, color: "#FFFFFF" };
  sheet.getRange(range).format.rowHeight = 27;
  sheet.getRange(range).format.wrapText = true;
}
function setBody(sheet, range) {
  sheet.getRange(range).format.font = { name: "Microsoft YaHei", size: 10, color: "#1F2937" };
  sheet.getRange(range).format.rowHeight = 23;
}
function outcome(row, model) {
  const baseline = row.correct.M0;
  const current = row.correct[model];
  if (baseline && current) return "双方正确";
  if (!baseline && current) return "修复";
  if (baseline && !current) return "新增错误";
  return "双方错误";
}

result.getRange("A1:I1").values = [["路线一 v2 Test：配对变化与案例交接", null, null, null, null, null, null, null, null]];
result.getRange("A1:I1").format.fill = "#102A43";
result.getRange("A1:I1").format.font = { name: "Microsoft YaHei", size: 16, bold: true, color: "#FFFFFF" };
result.getRange("A1:I1").format.rowHeight = 36;
result.getRange("A2:I2").values = [["来源：冻结 v2 Test 输入与 gold、5120 run02 六组原始预测；同一条目按 (dataset, claim_id) 连接。", null, null, null, null, null, null, null, null]];
result.getRange("A2:I2").format.font = { name: "Microsoft YaHei", size: 10, color: "#475569" };
result.getRange("A4:F4").values = [["数据集", "模型", "正确", "总数", "Accuracy", "Macro-F1"]];
setHeader(result, "A4:F4");
const metricRows = [];
for (const dataset of ["sciciteval", "sarol"]) {
  const item = summary.datasets[dataset];
  for (const model of ["M0", "Mbio", "Mscv"]) {
    const metric = item.model_metrics[model];
    metricRows.push([dataset, model, metric.correct, item.records, metric.accuracy, metric.macro_f1]);
  }
}
result.getRange("A5:F10").values = metricRows;
setBody(result, "A5:F10");
result.getRange("E5:E10").format.numberFormat = "0.00%";
result.getRange("F5:F10").format.numberFormat = "0.000000";

result.getRange("A13:I13").values = [["数据集", "adapter", "双方正确", "修复", "新增错误", "双方错误", "净正确数", "Accuracy 差/百分点", "Macro-F1 差"]];
setHeader(result, "A13:I13");
const comparisonRows = [];
for (const dataset of ["sciciteval", "sarol"]) {
  for (const adapter of ["Mbio", "Mscv"]) {
    const item = summary.datasets[dataset].comparisons[adapter];
    const count = item.outcome_counts;
    comparisonRows.push([dataset, adapter, count.both_correct, count.repaired_error,
      count.new_error, count.both_wrong, item.net_correct_change,
      item.accuracy.delta_percentage_points, item.macro_f1.delta]);
  }
}
result.getRange("A14:I17").values = comparisonRows;
setBody(result, "A14:I17");
result.getRange("H14:H17").format.numberFormat = "+0.00;-0.00;0.00";
result.getRange("I14:I17").format.numberFormat = "+0.000000;-0.000000;0.000000";
result.getRange("A20:I20").values = [["解读与限制", null, null, null, null, null, null, null, null]];
setHeader(result, "A20:I20");
const caveats = [
  "修复/新增错误仅相对于冻结 gold；20 个案例的双人独立证据复核尚未完成。",
  "SciCiteVal：Mscv 本域提升，Mbio 跨域下降；Sarol：Mbio 本域提升，Mscv 跨域提升。",
  "Sarol M0 的 1 条 INVALID 仍按错误计入原分母；不得删例或重选 checkpoint。",
  "SciCiteVal 给定段落，Sarol 使用检索十句；绝对分数不用于比较领域难度。",
  "20 个案例是诊断抽样，不能用于估计总体错误率；真实双 PDF 流程另行验收。",
];
result.getRange("A21:A25").values = caveats.map(x => [x]);
setBody(result, "A21:A25");
result.getRange("A1:A25").format.columnWidth = 55;
result.getRange("B1:B25").format.columnWidth = 16;
result.getRange("C1:G25").format.columnWidth = 15;
result.getRange("H1:I25").format.columnWidth = 23;
result.freezePanes.freezeRows(4);

const detailHeader = ["数据集", "claim_id", "gold", "M0", "Mbio", "Mscv", "M0正确", "Mbio正确", "Mscv正确", "Mbio对M0", "Mscv对M0", "M0无效原因", "Mbio无效原因", "Mscv无效原因"];
details.getRange("A1:N1").values = [detailHeader];
setHeader(details, "A1:N1");
const detailRows = paired.map(row => [row.dataset, row.claim_id, row.gold,
  row.predictions.M0, row.predictions.Mbio, row.predictions.Mscv,
  row.correct.M0, row.correct.Mbio, row.correct.Mscv,
  outcome(row, "Mbio"), outcome(row, "Mscv"),
  row.invalid_reason.M0 ?? "", row.invalid_reason.Mbio ?? "", row.invalid_reason.Mscv ?? ""]);
details.getRangeByIndexes(1, 0, detailRows.length, detailHeader.length).values = detailRows;
setBody(details, `A2:N${paired.length + 1}`);
details.getRange(`A1:B${paired.length + 1}`).format.columnWidth = 15;
details.getRange(`C1:I${paired.length + 1}`).format.columnWidth = 19;
details.getRange(`J1:N${paired.length + 1}`).format.columnWidth = 20;
details.freezePanes.freezeRows(1);

const caseHeader = ["案例", "gold", "M0", "Mbio", "Mscv", "对错模式 M0/Mbio/Mscv", "精确标注证据命中", "复核焦点", "Codex 来源初筛（非独立签核）", "需 gold 裁决", "李云独立判断", "陈明进独立判断", "共同裁决"];
review.getRange("A1:M1").values = [["仅在两位复核者分别提交盲复核表后查看；此表含冻结 gold 和模型预测。", null, null, null, null, null, null, null, null, null, null, null, null]];
review.getRange("A1:M1").format.fill = "#8A4B08";
review.getRange("A1:M1").format.font = { name: "Microsoft YaHei", size: 11, bold: true, color: "#FFFFFF" };
review.getRange("A1:M1").format.rowHeight = 28;
review.getRange("A3:M3").values = [caseHeader];
setHeader(review, "A3:M3");
const caseRows = cases.map(row => [row.case_id, row.gold,
  row.predictions.M0, row.predictions.Mbio, row.predictions.Mscv,
  [...row.correctness_pattern_M0_Mbio_Mscv].map(char => char === "1" ? "对" : "错").join(" / "),
  ({not_applicable_given_passage: "不适用/无精确标注", annotated_evidence_in_candidates: "命中", annotated_evidence_not_in_candidates: "未命中精确句"})[row.annotated_evidence_coverage.status],
  row.codex_source_triage.review_focus, row.codex_source_triage.source_check_note,
  row.codex_source_triage.requires_gold_adjudication ? "是" : "否", "待填写", "待填写", "待填写"]);
review.getRange("A4:M23").values = caseRows;
setBody(review, "A4:M23");
review.getRange("A4:M23").format.rowHeight = 80;
review.getRange("A4:M23").format.wrapText = true;
review.getRange("A1:A23").format.columnWidth = 26;
review.getRange("B1:E23").format.columnWidth = 18;
review.getRange("F1:G23").format.columnWidth = 24;
review.getRange("H1:H23").format.columnWidth = 28;
review.getRange("I1:I23").format.columnWidth = 86;
review.getRange("J1:M23").format.columnWidth = 22;
review.freezePanes.freezeRows(3);

wb.recalculate();
for (const [sheet, range] of [["结果", "A4:I17"], ["逐条配对", "A1:N4"], ["20例待复核", "A1:J6"]]) {
  const inspected = await wb.inspect({ kind: "table", range: `${sheet}!${range}`, include: "values", tableMaxRows: 15, tableMaxCols: 14, maxChars: 5000 });
  console.log(sheet, inspected.ndjson);
}
const errors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 20 }, maxChars: 1500 });
console.log("formula_errors", errors.ndjson);
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(dir, "路线一Test配对变化与20案例_20261019.xlsx"));
for (const [sheet, range, name] of [["结果", "A1:I25", "summary_preview.png"], ["20例待复核", "A1:J6", "cases_preview.png"]]) {
  const blob = await wb.render({ sheetName: sheet, range, scale: 1.5, format: "png" });
  await fs.writeFile(path.join(dir, name), new Uint8Array(await blob.arrayBuffer()));
}
console.log("workbook_saved=true");
