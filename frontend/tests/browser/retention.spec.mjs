import {test,expect} from './fixtures.mjs';

const day=86400;
const sid='77777777-7777-4777-8777-777777777777';
const rid='88888888-8888-4888-8888-888888888888';
const tid='99999999-9999-4999-8999-999999999999';
async function downloadedJSON(download){
 const chunks=[];
 for await(const chunk of await download.createReadStream())chunks.push(chunk);
 return JSON.parse(Buffer.concat(chunks).toString());
}

test('results show exact expiry, seven-day warning and a complete JSON download',async({page})=>{
 const now=Math.floor(Date.now()/1000);
 await page.clock.setFixedTime(now*1000);
 const record={id:rid,tool:'kcat',title:'Retention fixture',status:'completed',evidence_type:'Prediction',created:now-87*day,expires_at:now+3*day,retention_days:90,inputs:{query:'P00761',smiles:'CCO'},payload:{kcat:2.3,unit:'s^-1',full_evidence:Array.from({length:250},(_,i)=>i)}};
 const later={...record,id:tid,title:'Recent result',created:now,expires_at:now+90*day};
 await page.route('**/enzymind/api/workspace/results**',async route=>{
  const list=new URL(route.request().url()).pathname.endsWith('/results');
  const {payload,...metadata}=record;
  return route.fulfill({json:list?{results:[metadata,later]}:record});
 });
 await page.goto('/enzymind/results');
 await expect(page.locator('.retention-notice')).toContainText('90 days of creation');
 await expect(page.locator('.result-library-item').first().locator('.expiry-badge')).not.toHaveClass(/urgent/);
 const card=page.getByRole('link',{name:/Retention fixture/});
 await expect(card.locator('.expiry-badge')).toHaveClass(/urgent/);
 await expect(card.locator('.expiry-badge')).toContainText('Deletes in 3 days');
 await card.click();
 await expect(page.locator('.retention-notice')).toHaveClass(/urgent/);
 await expect(page.locator('.retention-notice time')).toHaveAttribute('datetime',new Date(record.expires_at*1000).toISOString());
 const saving=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download full result JSON'}).click();
 const data=await downloadedJSON(await saving);
 expect(data.payload).toEqual(record.payload);
 expect(data.inputs).toEqual(record.inputs);
 expect(data.expires_at).toBe(record.expires_at);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/retention-result-mobile.png',animations:'disabled'});
});

test('an expired result link explains the retention period',async({page})=>{
 await page.route('**/enzymind/api/workspace/results/**',route=>route.fulfill({status:404,json:{detail:'Result not found in this workspace. It may have been automatically deleted after the 90-day retention period.'}}));
 await page.goto(`/enzymind/results/${rid}`);
 await expect(page.getByRole('alert')).toContainText('90-day retention period');
 await expect(page.getByRole('button',{name:'Download full result JSON'})).toHaveCount(0);
});

test('Agent exposes message expiry, memory reset and conversation export on mobile',async({page})=>{
 const now=Math.floor(Date.now()/1000);
 await page.clock.setFixedTime(now*1000);
 const session={id:sid,title:'Retention regression',created:now-100*day,updated:now,summary:'',summarized_count:0,memory_revision:2,retention_reset_at:now};
 const turn={id:tid,session_id:sid,created:now-89*day,expires_at:now+day,status:'completed',message:'Remaining recent question',output:'Remaining recent answer',references:[],events:[]};
 await page.route('**/enzymind/api/workspace/**',route=>{
  const path=new URL(route.request().url()).pathname;
  return route.fulfill({json:path.endsWith('/sessions')?{sessions:[session]}:path.endsWith('/results')?{results:[]}:{...session,turns:[turn],results:[]}});
 });
 await page.goto('/enzymind/agent');
 await page.getByRole('button',{name:/Retention regression/}).click();
 await expect(page.locator('.workspace-retention')).toContainText('90 days');
 await expect(page.locator('.user-turn .expiry-badge')).toContainText('Deletes in 1 day');
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();
 await expect(page.locator('.memory-panel')).toContainText('memory is rebuilt from the remaining messages');
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();
 const saving=page.waitForEvent('download');
 await page.getByRole('button',{name:'Download conversation',exact:true}).click();
 const data=await downloadedJSON(await saving);
 expect(data.turns.map(t=>t.id)).toEqual([tid]);
 expect(data.turns[0].expires_at).toBe(turn.expires_at);
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('link',{name:'Download saved results'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Send question'})).toBeVisible();
 const composer=await page.locator('textarea').boundingBox();
 expect(composer.height).toBeGreaterThan(40);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/retention-agent-mobile.png',animations:'disabled'});
 await page.getByRole('button',{name:'Dismiss retention notice'}).click();
 await expect(page.locator('.workspace-retention.retention-collapsed')).toBeVisible();
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();
 await expect(page.locator('.memory-panel')).toBeVisible();
 await page.getByRole('button',{name:'Close conversation memory'}).click();
 await page.getByRole('button',{name:'Open page guide'}).click();
 await expect(page.getByRole('dialog')).toBeVisible();
 await page.getByRole('button',{name:'Skip guide'}).click();
 await page.screenshot({path:'/tmp/enzymind-browser-artifacts/compact-agent-mobile.png',animations:'disabled'});
});
