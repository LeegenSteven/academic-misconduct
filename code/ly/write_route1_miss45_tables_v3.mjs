import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

// Resolve only the configured dependency junction in the writable QA directory.
const [input, qaDirectory] = process.argv.slice(2);
if (!input || !qaDirectory) throw new Error('Usage: node write_route1_miss45_tables_v3.mjs tables.json qa_directory');
const qa = path.resolve(qaDirectory);
await fs.mkdir(qa, { recursive: true });
const require = createRequire(path.join(qa, 'package.json'));
const { Workbook } = await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const spec = JSON.parse(await fs.readFile(input, 'utf8'));
const wb = Workbook.create();
const sheets = [];
function columnName(number) {
  let out = '';
  while (number > 0) { number--; out = String.fromCharCode(65 + number % 26) + out; number = Math.floor(number / 26); }
  return out;
}
const csvValue = value => {
  const s = value == null ? '' : typeof value === 'boolean' ? String(value) : String(value);
  return /[",\r\n]/.test(s) ? '"' + s.replaceAll('"', '""') + '"' : s;
};
for (const table of spec.tables) {
  const sheet = wb.worksheets.add(table.sheet);
  const matrix = [table.columns, ...table.rows];
  const region = sheet.getRangeByIndexes(0, 0, matrix.length, table.columns.length);
  region.values = matrix;
  sheet.showGridLines = false;
  region.format.font = { name: 'Arial', size: 10, color: '#1F2937' };
  region.format.verticalAlignment = 'center';
  region.format.rowHeight = 24;
  region.format.columnWidth = 19;
  sheet.getRangeByIndexes(0, 0, 1, table.columns.length).format = {
    fill: '#203A52', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    rowHeight: 38, wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center',
  };
  sheet.getRange('A:A').format.columnWidth = table.sheet === '45条漏检复核' ? 9 : 24;
  sheet.getRange('B:B').format.columnWidth = table.sheet === '45条漏检复核' ? 25 : 15;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);
  sheet.tables.add(`A1:${columnName(table.columns.length)}${matrix.length}`, true, table.file === 'miss45_review.csv' ? 'Miss45Review' : 'Sarol606Transitions');
  sheets.push({ sheet, table, region, matrix });
}
wb.recalculate();
const findings = [];
for (const { sheet, table, region, matrix } of sheets) {
  const values = region.values;
  if (values.length !== matrix.length) throw new Error('Row count changed');
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < table.columns.length; j++) {
      const a = values[i][j] ?? '';
      const b = matrix[i][j] ?? '';
      if (a !== b) throw new Error(`Value changed at ${table.sheet} R${i+1}C${j+1}`);
    }
  }
  const csv = '\uFEFF' + values.map(row => row.map(csvValue).join(',')).join('\r\n') + '\r\n';
  await fs.writeFile(path.join(spec.output_dir, table.file), csv, 'utf8');
  findings.push({ sheet: table.sheet, dataRows: values.length - 1, columns: table.columns.length });
  const check = await wb.inspect({ kind: 'table', range: `${table.sheet}!A1:H4`, include: 'values,formulas', maxChars: 2500, tableMaxRows: 4, tableMaxCols: 8 });
  await fs.writeFile(path.join(qa, table.file + '.inspection.txt'), check.ndjson ?? String(check), 'utf8');
  const preview = await wb.render({ sheetName: table.sheet, range: 'A1:H9', scale: 1.4, format: 'png' });
  await fs.writeFile(path.join(qa, table.file + '.preview.png'), new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({status: 'csv_written_from_verified_artifact_ranges', tables: findings}));
