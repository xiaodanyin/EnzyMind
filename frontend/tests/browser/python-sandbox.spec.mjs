import { test, expect } from './fixtures.mjs';

const id = '11111111-1111-4111-8111-111111111111';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1cAAAAASUVORK5CYII=', 'base64');
const code = '# Scientific calculation\nimport numpy as np\nvalues = np.array([1, 2, 6])\nmessage = "<img src=x onerror=window.injected=true>"\nresult = {"mean": float(values.mean())}';
const files = [
  ['22222222-2222-4222-8222-222222222222', 'table.csv', 'text/csv'],
  ['33333333-3333-4333-8333-333333333333', 'report.txt', 'text/plain'],
  ['44444444-4444-4444-8444-444444444444', 'molecule.png', 'image/png'],
].map(([id, name, mime]) => ({ id, name, mime, size: 120, url: 'https://untrusted.invalid/ignore' }));

async function mockResult(page, { failImage = false, workspace = false, image = png, csv = 'name,value\n"a,b",6\n<script>,=1+1' } = {}) {
  const requests = [], pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  const record = {
    id, tool: 'python', title: 'Python analysis', status: 'completed', evidence_type: '代码计算结果',
    created: Date.now() / 1000, duration: .2, inputs: { code },
    payload: {
      success: true, execution_status: 'completed', duration: .2,
      result: [{ length: 6, gc: 0.5 }], stdout: '<img src=x onerror="window.injected=true">', stderr: '',
      files, image_digest: 'sha256:' + 'a'.repeat(64), versions: { python: '3.12.16', rdkit: '2025.9.3' },
    },
  };
  await page.route('**/api/workspace/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/retention')) return route.fulfill({ json: { retention_days: 90, warning_days: 7 } });
    if (path.endsWith('/sessions')) return route.fulfill({ json: { sessions: [] } });
    if (path.endsWith('/results')) return route.fulfill({ json: { results: [record] } });
    if (path.endsWith('/results/' + id)) return route.fulfill({ json: record });
    if (path.includes('/files/')) {
      expect(route.request().headers()['x-enzymind-client']).toMatch(/^[a-f0-9]{64}$/);
      const file = files.find(f => path.endsWith(f.id));
      requests.push(file.name);
      if (file.mime === 'image/png' && failImage) {
        failImage = false;
        return route.fulfill({ status: 403, json: { detail: 'Preview temporarily unavailable.' } });
      }
      const body = file.mime === 'image/png' ? image
        : file.mime === 'text/csv' ? csv
        : '<script>window.injected=true</script>';
      return route.fulfill({ body, contentType: file.mime });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto(workspace ? '/enzymind/agent' : '/enzymind/results/' + id);
  if (workspace) {
    await page.getByRole('button', { name: /^Results/ }).click();
    await page.locator('.library-card-title').click();
  }
  await expect(page.getByRole('region', { name: 'Python analysis result' })).toBeVisible();
  return { requests, pageErrors };
}

test('Python results open private figures and tables by default, highlight code and keep output inert', async ({ page, context }) => {
  const { requests, pageErrors } = await mockResult(page);
  const figure = page.locator('.python-file').filter({ hasText: 'molecule.png' });
  const table = page.locator('.python-file').filter({ hasText: 'table.csv' });
  const text = page.locator('.python-file').filter({ hasText: 'report.txt' });
  await expect(figure.locator('img')).toBeVisible();
  await expect(table.locator('table')).toBeVisible();
  await expect(table.locator('th[scope="col"]')).toHaveCount(3);
  await expect(table.locator('table')).toContainText('a,b');
  await expect(table.locator('table')).toContainText('<script>');
  await expect(page.locator('.computed-values table')).toBeVisible();
  expect(await figure.locator('img').evaluate(img => img.naturalWidth)).toBe(1);
  expect(requests.sort()).toEqual(['molecule.png', 'table.csv']);
  await expect(text).not.toHaveAttribute('open');

  // Folding is local: reopening uses the authenticated preview already fetched.
  await table.locator('summary').click();
  await expect(table.locator('table')).toBeHidden();
  await table.locator('summary').press('Enter');
  await expect(table.locator('table')).toBeVisible();
  await figure.locator('summary').click();
  await expect(figure.locator('img')).toBeHidden();
  await figure.locator('summary').click();
  await expect(figure.locator('img')).toBeVisible();
  expect(requests).toHaveLength(2);

  await text.locator('summary').click();
  await expect(text.locator('pre')).toContainText('<script>window.injected=true</script>');
  await page.locator('.execution-output > summary').click();
  await expect(page.locator('.execution-output pre')).toContainText('<img src=x');
  await page.locator('.code-panel > summary').click();
  await expect(page.locator('.python-code .keyword').filter({ hasText: 'import' })).toBeVisible();
  await expect(page.locator('.python-code .comment')).toHaveText('# Scientific calculation');
  await expect(page.locator('.python-code .line-number')).toHaveCount(5);
  await expect(page.locator('.python-code .string').filter({ hasText: '<img' })).toBeVisible();
  expect(await page.locator('.python-code .keyword').first().evaluate(el => getComputedStyle(el).color))
    .not.toEqual(await page.locator('.python-code .string').first().evaluate(el => getComputedStyle(el).color));
  expect(await page.locator('.python-code img, .python-code script, .execution-output img').count()).toBe(0);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();

  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: 'Copy code', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Copied', exact: true })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(code);
  const downloaded = page.waitForEvent('download');
  await table.getByRole('button', { name: 'Download table.csv', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe('table.csv');
  expect(requests).toHaveLength(3);
  expect(pageErrors).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: '/tmp/enzymind-python-result-desktop.png', fullPage: true });
});

test('Python previews can retry a failure and download while collapsed', async ({ page }) => {
  const { requests } = await mockResult(page, { failImage: true });
  const figure = page.locator('.python-file').filter({ hasText: 'molecule.png' });
  await expect(figure.getByRole('alert')).toContainText('Preview temporarily unavailable.');
  await expect(page.locator('.csv-preview table')).toBeVisible();
  await figure.getByRole('button', { name: 'Retry preview' }).click();
  await expect(figure.locator('img')).toBeVisible();
  await expect(figure.getByRole('alert')).toHaveCount(0);
  await figure.locator('summary').click();
  const downloaded = page.waitForEvent('download');
  await figure.getByRole('button', { name: 'Download molecule.png' }).click();
  await downloaded;
  await expect(figure).not.toHaveAttribute('open');
  expect(requests.filter(name => name === 'molecule.png')).toHaveLength(2);
});

test('Python result previews and highlighted code fit a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { pageErrors } = await mockResult(page);
  await expect(page.locator('.figure-preview img')).toBeVisible();
  await expect(page.locator('.csv-preview table')).toBeVisible();
  await page.locator('.code-panel > summary').click();
  await expect(page.locator('.python-code .keyword').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: '/tmp/enzymind-python-result-mobile.png', fullPage: true });
  expect(pageErrors).toEqual([]);
});

test('Workspace figures expand above the panel, zoom, trap focus and restore the original preview', async ({ page }) => {
  const { requests, pageErrors } = await mockResult(page, { workspace: true });
  const figure = page.locator('.figure-preview img');
  const trigger = page.getByRole('button', { name: 'Expand molecule.png', exact: true });
  await figure.click();
  const modal = page.getByRole('dialog', { name: 'molecule.png', exact: true });
  await expect(modal).toBeVisible();
  await expect.poll(async () => (await modal.boundingBox()).width).toBeGreaterThan((await page.locator('.result-inspector').boundingBox()).width);
  await expect(modal.getByRole('button', { name: 'Close expanded result' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(modal.locator('.preview-dialog-viewport')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(modal.getByRole('button', { name: 'Close expanded result' })).toBeFocused();
  const img = modal.locator('img');
  await expect(img).toBeVisible();
  const width = (await img.boundingBox()).width;
  await modal.getByRole('button', { name: 'Zoom in', exact: true }).click();
  expect((await img.boundingBox()).width).toBeGreaterThan(width);
  await modal.getByRole('button', { name: 'Fit', exact: true }).click();
  expect((await img.boundingBox()).width).toBeCloseTo(width);
  await page.keyboard.press('Escape');
  await expect(modal).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('');
  await trigger.press('Enter');
  await expect(modal).toBeVisible();
  await page.mouse.click(2, 2);
  await expect(modal).toHaveCount(0);
  expect(requests.sort()).toEqual(['molecule.png', 'table.csv']);
  expect(pageErrors).toEqual([]);
});

test('Workspace expanded CSV is scrollable on mobile, keeps literal cells and closes cleanly on navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const longCell = '<img src=x onerror=window.injected=true> ' + 'Long scientific description '.repeat(20);
  const csv = 'name,value,condition,notes\n' + Array.from({ length: 100 }, (_, i) => `sample ${i},${i / 10},pH 7,${longCell}`).join('\n');
  const { requests, pageErrors } = await mockResult(page, { workspace: true, csv });
  await page.getByRole('button', { name: 'Expand table.csv', exact: true }).click();
  const modal = page.getByRole('dialog', { name: 'table.csv', exact: true });
  await expect(modal).toBeVisible();
  const box = await modal.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.width).toBeLessThanOrEqual(390);
  const viewport = modal.locator('.preview-dialog-viewport');
  expect(await viewport.evaluate(el => el.scrollWidth > el.clientWidth && el.scrollHeight > el.clientHeight)).toBe(true);
  await expect(modal.locator('tbody tr')).toHaveCount(100);
  await expect(modal.locator('tbody tr').first()).toContainText(longCell);
  await expect(modal.locator('img,script')).toHaveCount(0);
  expect(await page.evaluate(() => window.injected)).toBeUndefined();
  await viewport.evaluate(el => { el.scrollTop = el.scrollHeight; el.scrollLeft = el.scrollWidth; });
  await expect(modal.getByRole('button', { name: 'Close expanded result' })).toBeInViewport();
  await modal.getByRole('button', { name: 'Close expanded result' }).click();
  await expect(page.getByRole('button', { name: 'Expand table.csv', exact: true })).toBeFocused();
  await page.locator('.csv-preview td').first().click();
  await expect(modal).toBeVisible();
  // Popstate can unmount an open preview even while the background is inert.
  await page.evaluate(() => { history.pushState({}, '', '/enzymind/help'); dispatchEvent(new PopStateEvent('popstate')); });
  await expect(modal).toHaveCount(0);
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('');
  expect(requests.sort()).toEqual(['molecule.png', 'table.csv']);
  expect(pageErrors).toEqual([]);
});
