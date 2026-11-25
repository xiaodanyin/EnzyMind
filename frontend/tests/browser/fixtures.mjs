import { test as base, expect } from '@playwright/test';
import { GUIDE_KEYS } from '../../src/config/pageGuides.js';

// Existing functional regressions represent returning users. First-visit behavior
// is exercised separately in guidance.spec.mjs with empty browser storage.
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript(keys => {
      const storageKey='enzymind_ui_preferences_v1';
      if(!localStorage.getItem(storageKey))localStorage.setItem(storageKey,JSON.stringify({seenTours:keys,dismissedNotices:[]}));
    }, GUIDE_KEYS);
    await use(page);
  },
});
export { expect };
