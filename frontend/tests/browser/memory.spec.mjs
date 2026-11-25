import {test,expect} from './fixtures.mjs';
const sid='11111111-1111-4111-8111-111111111111';
const tid='22222222-2222-4222-8222-222222222222';
test('a failed long question can be reused with its evidence and continue under an advisory notice', async ({page}) => {
  const resultId = '44444444-4444-4444-8444-444444444444';
  const session = {id:sid, title:'Long question retry', summary:'', summarized_count:0, memory_revision:0};
  const message = '请保留全部研究条件。'.repeat(6000) + '\n\nAttached FASTA file: original.fasta\n\n>original\nACDEFG';
  const failed = {id:tid, session_id:sid, request_id:'previous-request', status:'failed', message,
    error:'The current question and attached evidence exceed the context budget.',
    references:[resultId], events:[], created:Date.now()/1000};
  const warning = 'Long context. Analysis is continuing with your full question and attached evidence. Processing may take longer.';
  const result = {id:resultId, tool:'sequence', title:'Reference enzyme sequence', inputs:{query:'P00330'}, status:'completed'};
  let submitted = null;
  let completed = false;
  let posts = 0;
  const next = () => ({...failed, id:'33333333-3333-4333-8333-333333333333', error:null,
    status:completed?'completed':'running', output:completed?'Analysis completed using the attached evidence.':'',
    events:[{kind:'memory',data:{state:'ready',context_tokens:132000,warning,label:'Memory ready for analysis'}}]});
  await page.route('**/enzymind/api/workspace/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/usage')) return route.fulfill({json:{limit:10,used:0,remaining:10}});
    if (path.endsWith('/events')) return route.fulfill({status:503,body:''});
    if (route.request().method()==='POST' && path.endsWith('/turns')) {
      posts++;
      submitted = route.request().postDataJSON();
      return route.fulfill({json:next()});
    }
    if (path.endsWith('/sessions')) return route.fulfill({json:{sessions:[session]}});
    if (path.endsWith('/results')) return route.fulfill({json:{results:[result]}});
    return route.fulfill({json:{...session,turns:submitted?[failed,next()]:[failed],results:[result]}});
  });
  await page.goto('/enzymind/agent');
  await page.getByRole('button',{name:/Long question retry/}).click();
  // An unrelated pending upload must not be appended to the saved question.
  await page.locator('input[type=file][accept*=".fasta"]').setInputFiles({
    name:'other.fasta',mimeType:'text/plain',buffer:Buffer.from('>other\nMKKLL')
  });
  await page.getByRole('button',{name:'Use this question again'}).click();
  await expect(page.locator('textarea')).toHaveValue(message);
  await expect(page.locator('.composer-attachments')).toContainText('Reference enzyme sequence');
  await expect(page.locator('.composer-attachments')).not.toContainText('other.fasta');
  await page.getByRole('button',{name:'Send question'}).click();
  await expect(page.locator('.context-notice')).toHaveText(warning);
  expect(submitted.message).toBe(message);
  expect(submitted.references).toEqual([resultId]);
  expect(submitted.request_id).not.toBe(failed.request_id);
  completed = true;
  await expect(page.locator('.agent-markdown').last()).toContainText('Analysis completed');
  await page.reload();
  await expect(page.locator('.context-notice')).toHaveText(warning);
  expect(posts).toBe(1);
});

test('Agent restores saved memory, shows compression, and refreshes without replay',async({page})=>{
 let posts=0,running=false,complete=false;
 const session={id:sid,title:'Memory regression conversation',created:1700000000,updated:1700000000,summary:'Study P00761; verify exact values in saved results.',summarized_count:2,memory_revision:1,compression_count:1,context_tokens:7000};
 const old={id:tid,session_id:sid,status:'completed',message:'What is our research objective?',output:'Study P00761.',references:[],events:[],created:1700000000};
 await page.route('**/enzymind/api/workspace/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  if(route.request().method()==='POST'&&path.endsWith('/turns')){posts++;running=true;return route.fulfill({json:{...old,id:'33333333-3333-4333-8333-333333333333',status:'running',message:route.request().postDataJSON().message,output:'',events:[{kind:'memory',data:{state:'compressing',label:'Compressing older conversation; original turns remain saved'}}]}});}
  if(path.endsWith('/sessions'))return route.fulfill({json:{sessions:[session]}});
  if(path.endsWith('/results'))return route.fulfill({json:{results:[]}});
  const next={...old,id:'33333333-3333-4333-8333-333333333333',message:'Continue our research',status:complete?'completed':'running',output:complete?'We are studying P00761; prior evidence remains saved.':'',events:[{kind:'memory',data:{state:complete?'saved':'compressing',label:complete?'Answer and memory saved':'Compressing older conversation; original turns remain saved'}}]};
  return route.fulfill({json:{...session,summary:complete?'Updated research memory: P00761.':session.summary,memory_revision:complete?2:1,turns:running?[old,next]:[old],results:[]}});
 });
 await page.goto('/enzymind/agent');await page.getByRole('button',{name:/Memory regression conversation/}).click();
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();await page.getByText(/Read saved summary/).click();await expect(page.locator('.memory-summary')).toContainText('Study P00761');
 await page.locator('textarea').fill('Continue our research');await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.locator('.memory-panel-heading')).toContainText('Compressing');
 await page.reload();await page.getByRole('button',{name:'Conversation memory',exact:true}).click();await expect(page.locator('.memory-panel-heading')).toContainText('Compressing');expect(posts).toBe(1);
 complete=true;await expect(page.locator('.memory-panel')).toContainText('revision 2');await page.getByText(/Read saved summary/).click();await expect(page.locator('.memory-summary')).toContainText('Updated research memory');
 expect(posts).toBe(1);await page.screenshot({path:'/tmp/enzymind-browser-artifacts/agent-memory.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Examples',exact:true}).click();
 await expect(page.locator('.example-grid>button').first()).toBeVisible();
 await expect(page.locator('.memory-panel')).toHaveCount(0);
 const action=await page.getByRole('button',{name:'Examples',exact:true}).boundingBox();
 const notice=await page.locator('.workspace-retention').boundingBox();expect(action.y+action.height).toBeLessThanOrEqual(notice.y);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 expect(posts).toBe(1);
});
