import { test, expect } from './fixtures.mjs';

// UI labels stay English even when the browser and saved metadata are Chinese.
test.use({ locale: 'zh-CN', timezoneId: 'UTC' });
const id = '11111111-1111-4111-8111-111111111111';
const sid = '22222222-2222-4222-8222-222222222222';
const created = Date.UTC(2027, 1, 7, 13, 5) / 1000;
const record = {
  id, tool: 'python', title: 'Python analysis', status: 'completed',
  evidence_type: '代码计算结果', created, inputs: { code: 'result = 6' },
  payload: { success: true, execution_status: 'completed', result: 6 },
};
const records = [
  record,
  { ...record, id: '33333333-3333-4333-8333-333333333333', evidence_type: 'Code calculation result' },
  { ...record, id: '44444444-4444-4444-8444-444444444444', tool: 'recognize', title: 'Enzyme recognition', evidence_type: 'Prediction' },
];
const session = { id: sid, title: 'English UI regression', created, updated: created };

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(created * 1000);
  await page.route('**/api/workspace/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/results/' + id)) return route.fulfill({ json: record });
    if (path.endsWith('/results')) return route.fulfill({ json: { results: records } });
    if (path.endsWith('/sessions')) return route.fulfill({ json: { sessions: [session] } });
    if (path.endsWith('/sessions/' + sid)) return route.fulfill({ json: {
      ...session, results: records, turns: [{
        id, session_id: sid, created, status: 'completed', message: 'Run a calculation.',
        output: 'The result is 6.', references: [], events: [],
      }],
    } });
    if (path.endsWith('/usage')) return route.fulfill({ json: { limit: 10, remaining: 10 } });
    return route.fulfill({ json: {} });
  });
});

test('Agent result details translate evidence metadata but preserve the exported record', async ({ page }) => {
  await page.goto('/enzymind/agent?reference=' + id);
  const details = page.getByRole('complementary', { name: 'Results inspector' });
  await expect(details.getByRole('heading', { name: 'Result details', exact: true })).toBeVisible();
  await expect(details.locator('.research-result-header .eyebrow')).toHaveText('Code calculation result / python');
  await expect(details.locator('.result-meta')).toContainText('2/7/2027, 1:05:00 PM');
  await details.getByText('Input & provenance', { exact: true }).click();
  await expect(details.locator('.result-details dd').first()).toHaveText('Code calculation result');
  await expect(details).not.toContainText('代码计算结果');

  const saving = page.waitForEvent('download');
  await details.getByRole('button', { name: 'Export JSON', exact: true }).click();
  const chunks = [];
  for await (const chunk of await (await saving).createReadStream()) chunks.push(chunk);
  expect(JSON.parse(Buffer.concat(chunks).toString())).toEqual(record);
});

test('English evidence labels are consistent across results, filters and the Agent library', async ({ page }) => {
  await page.goto('/enzymind/results');
  await expect(page.locator('.result-library-item')).toHaveCount(3);
  const evidence = page.getByRole('combobox', { name: /^Evidence/ });
  await expect(evidence.locator('option')).toHaveText(['All evidence', 'Code calculation result', 'Prediction']);
  await evidence.selectOption({ label: 'Code calculation result' });
  await expect(page.locator('.result-library-item')).toHaveCount(2);
  await expect(page.locator('.result-library-item .eyebrow')).toHaveText(['Code calculation result', 'Code calculation result']);
  await expect(page.locator('.result-library-item > div > time').first()).toHaveText('2/7/2027');

  await page.goto('/enzymind/agent');
  const conversation = page.getByRole('button', { name: /English UI regression/ });
  await expect(conversation.locator('small')).toHaveText('Feb 7');
  await conversation.click();
  await expect(page.locator('.user-turn .message-byline > time')).toHaveText('01:05 PM');
  await page.getByRole('button', { name: /Saved results/ }).click();
  await expect(page.locator('.library-card .eyebrow')).toHaveText(['Code calculation result', 'Code calculation result', 'Prediction']);
});
