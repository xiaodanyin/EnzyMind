import {test,expect} from '@playwright/test';
import {TOOLS} from '../../src/config/tools.js';
import {GUIDE_KEYS} from '../../src/config/pageGuides.js';
const storageKey='enzymind_ui_preferences_v1';
const rid='88888888-8888-4888-8888-888888888888';
const record={id:rid,tool:'kcat',title:'Guide fixture',status:'completed',evidence_type:'Prediction',created:Date.now()/1000-87*86400,inputs:{query:'P00761'},payload:{kcat:1.2,unit:'s^-1'}};
async function mockWorkspace(page){
 await page.route('**/enzymind/api/workspace/**',route=>{
  const path=new URL(route.request().url()).pathname;
  return route.fulfill({json:path.endsWith('/sessions')?{sessions:[]}:path.endsWith('/results')?{results:[record]}:record});
 });
}
async function returning(page){await page.addInitScript(keys=>{if(!localStorage.getItem('enzymind_ui_preferences_v1'))localStorage.setItem('enzymind_ui_preferences_v1',JSON.stringify({seenTours:keys,dismissedNotices:[]}));},GUIDE_KEYS);}

test('first visit tours simulate expansion without changing inputs or submitting jobs',async({page})=>{
 const posts=[],errors=[];page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/enzymind/predict/km');
 const dialog=page.getByRole('dialog',{name:'Start with your protein'});
 await expect(dialog).toBeVisible();
 await expect(page.locator('.method-details')).not.toHaveAttribute('open');
 expect(await page.locator('#app-container').evaluate(el=>el.inert)).toBe(true);
 await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview','protein');
 await expect(page.locator('#page-guide-title')).toHaveText('Start with your protein');
 await page.getByRole('button',{name:'Next',exact:false}).click();
 await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview','ketcher');
 await expect.poll(async()=>(await page.locator('.preview-expansion').boundingBox()).height).toBeGreaterThan(80);
 await expect(page.locator('iframe')).toHaveCount(0);
 await expect(page.locator('#protein-query')).toHaveValue('');
 await expect(page.locator('#chemical-smiles')).toHaveValue('');
 await page.getByRole('button',{name:'Replay preview'}).click();
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/guide-ketcher-desktop.png',animations:'disabled'});
 await page.getByRole('button',{name:'Next',exact:false}).click();
 await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview','run');
 await page.getByRole('button',{name:'Next',exact:false}).click();
 await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview','result');
 await page.getByRole('button',{name:'Finish guide'}).click();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 expect(await page.locator('#app-container').evaluate(el=>el.inert)).toBe(false);
 expect(posts).toEqual([]);expect(errors).toEqual([]);
 await page.reload();await expect(page.locator('.tool-form')).toBeVisible();
 await page.waitForTimeout(1000);await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.locator('#protein-query').fill('P00761');
 await page.getByRole('button',{name:'Open page guide'}).click();
 await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
 await expect(page.locator('#protein-query')).toHaveValue('P00761');
 await expect(page.getByRole('button',{name:'Open page guide'})).toBeFocused();
});

for(const tool of TOOLS)test(`${tool.title}: first-use guide covers the available inputs and result`,async({page})=>{
 await page.goto(`/enzymind${tool.path}`);
 const dialog=page.getByRole('dialog');await expect(dialog).toHaveAttribute('data-guide-key',`model:${tool.id}`);
 const steps=await page.locator('.guide-progress button').count();expect(steps).toBeGreaterThanOrEqual(3);
 await expect(page.getByRole('button',{name:/Understand the method/})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Download method diagram as SVG'})).toHaveCount(0);
 await page.getByRole('button',{name:/Go to step \d+: Submit:/}).click();
 await expect(dialog).toContainText(tool.action);
 await expect(page.locator('.guide-preview')).not.toContainText('Stop');
 if(tool.molecule){await page.getByRole('button',{name:/Go to step \d+: (Draw or paste your molecule|Describe your reaction)/}).click();await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview',tool.molecule==='molecule'?'ketcher':'reaction');}
 await page.locator('.guide-progress button').last().click();
 await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview',['structure','active-sites'].includes(tool.id)?'structure':'result');
 await page.getByRole('button',{name:'Close page guide'}).click();
 await expect(page.locator('.tool-form')).toBeVisible();
});

test('Agent and result guides focus on inputs and saved output, with details remembered by page type',async({page})=>{
 await mockWorkspace(page);
 for(const [path,key] of [['/agent','agent'],['/results','results'],[`/results/${rid}`,'result-detail']]){
  await page.goto(`/enzymind${path}`);await expect(page.getByRole('dialog')).toHaveAttribute('data-guide-key',key);
  if(key==='agent'){
   await page.getByRole('button',{name:/Go to step \d+: Open results or ask a follow-up/}).click();
   await expect(page.locator('.guide-preview')).toHaveAttribute('data-preview','library');
   await expect(page.locator('.result-inspector')).toHaveCount(0);
   await page.screenshot({path:'/tmp/enzymind-browser-artifacts/guide-agent-results.png',animations:'disabled'});
  }
  await page.getByRole('button',{name:'Skip guide'}).click();
 }
 await page.goto('/enzymind/results/99999999-9999-4999-8999-999999999999');
 await expect(page.locator('.research-result')).toBeVisible();await page.waitForTimeout(1000);
 await expect(page.getByRole('dialog')).toHaveCount(0);
});

for(const path of ['/', '/help'])test(`${path}: first visit has no guide or replay control`,async({page})=>{
 await page.goto(`/enzymind${path}`);
 await expect(page.locator(path==='/'?'.hero-buttons':'.help-layout')).toBeVisible();
 await page.waitForTimeout(1000);
 await expect(page.getByRole('dialog')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Open page guide'})).toHaveCount(0);
 expect(await page.locator('#app-container').evaluate(el=>el.inert)).toBe(false);
 if(path==='/')await expect(page.locator('.directory-tool')).toHaveCount(TOOLS.length);
});

test('dismissed notices stay compact after refresh and navigation; dates and exports remain available',async({page})=>{
 await returning(page);await mockWorkspace(page);
 await page.goto('/enzymind/predict/enzyme');
 const initial=(await page.locator('.retention-notice').boundingBox()).height;
 await page.getByRole('button',{name:'Dismiss retention notice'}).click();
 await expect(page.locator('.retention-notice')).toHaveCount(0);
 expect((await page.locator('.retention-collapsed').boundingBox()).height).toBeLessThan(initial/2);
 await page.reload();await expect(page.getByRole('button',{name:'Show retention details'})).toBeVisible();
 await page.goto('/enzymind/agent');await expect(page.locator('.workspace-retention.retention-collapsed')).toBeVisible();
 await page.goto(`/enzymind/results/${rid}`);
 await page.getByRole('button',{name:'Dismiss retention notice'}).click();
 await expect(page.locator('.retention-collapsed')).toContainText('Deletes');
 await expect(page.locator('.retention-collapsed')).toHaveClass(/urgent/);
 const saving=page.waitForEvent('download');await page.getByRole('button',{name:'Export JSON',exact:true}).click();expect((await saving).suggestedFilename()).toMatch(/\.json$/);
 await page.reload();await expect(page.locator('.retention-notice')).toHaveCount(0);
 await page.getByRole('button',{name:'Show retention details'}).click();await expect(page.locator('.retention-notice')).toBeVisible();
});

test('mobile guide fits the screen, traps focus and respects reduced motion',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/enzymind/predict/recommendation');await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:/Go to step \d+: Describe your reaction/}).click();
 const box=await page.getByRole('dialog').boundingBox();expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(391);expect(box.y+box.height).toBeLessThanOrEqual(845);
 const target=await page.locator('.guide-spotlight').boundingBox();expect(target.y+target.height).toBeLessThan(box.y);
 expect(await page.locator('.preview-expansion').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
 for(let i=0;i<16;i++){await page.keyboard.press('Tab');expect(await page.evaluate(()=>Boolean(document.activeElement.closest('[role="dialog"]')))).toBe(true);}
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/guide-mobile.png',animations:'disabled'});
 await page.keyboard.press('Escape');expect(await page.locator('#app-container').evaluate(el=>el.inert)).toBe(false);
 await page.getByRole('button',{name:'Dismiss retention notice'}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});

test('storage restrictions do not break first-use guidance or dismissal',async({page})=>{
 await page.addInitScript(()=>{Storage.prototype.getItem=function(){throw new Error('Storage disabled');};Storage.prototype.setItem=function(){throw new Error('Storage disabled');};});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/enzymind/predict/enzyme');await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'Skip guide'}).click();await page.getByRole('button',{name:'Dismiss retention notice'}).click();
 await expect(page.locator('.retention-collapsed')).toBeVisible();await page.getByRole('button',{name:'Open page guide'}).click();await expect(page.getByRole('dialog')).toBeVisible();expect(errors).toEqual([]);
});

test('browser Back closes an active guide and restores the previous page controls',async({page})=>{
 await page.goto('/enzymind/predict/enzyme');await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'Skip guide'}).click();
 await page.getByRole('button',{name:'Prediction',exact:true}).click();
 await page.locator('#prediction-menu').getByRole('link',{name:/EC Number Prediction/}).click();
 await expect(page.getByRole('dialog')).toHaveAttribute('data-guide-key','model:ec');
 await page.goBack();await expect(page.locator('.tool-form')).toBeVisible();
 await expect(page.getByRole('dialog')).toHaveCount(0);
 expect(await page.locator('#app-container').evaluate(el=>el.inert)).toBe(false);
 await page.locator('#protein-query').fill('P00761');await expect(page.locator('#protein-query')).toHaveValue('P00761');
});
