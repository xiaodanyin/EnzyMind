import test from 'node:test';
import assert from 'node:assert/strict';
import { csvPreview, jsonPreview } from '../src/utils/pythonFiles.js';

test('CSV preview retains escaped quotes, commas, newlines and inert HTML/formulas', () => {
  assert.deepEqual(csvPreview('name,value\r\n"a,b","line1\nline2"\r\n"say ""hi""",<script>\r\n=1+1,2'),
    [['name','value'],['a,b','line1\nline2'],['say "hi"','<script>'],['=1+1','2']]);
});
test('CSV preview bounds rows, columns and cell length', () => {
  const rows = csvPreview(Array.from({length:100}, () => Array(35).fill('x'.repeat(2100)).join(',')).join('\n'), 3, 2);
  assert.equal(rows.length, 3);
  assert.ok(rows.every(row => row.length === 2 && row.every(cell => cell.length <= 2000)));
});
test('JSON preview bounds recursive data without changing the source record', () => {
  const value = Array.from({length:1000}, (_, n) => ({n, text:'x'.repeat(4000)}));
  assert.equal(jsonPreview(value).length, 100);
  assert.equal(jsonPreview(value)[0].text.length, 3000);
  assert.equal(value[0].text.length, 4000);
  let deep=1; for(let i=0;i<100;i++) deep={inner:deep};
  assert.match(JSON.stringify(jsonPreview(deep)), /See full result JSON/);
});
