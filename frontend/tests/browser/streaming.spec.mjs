import { test, expect } from './fixtures.mjs';
import { createServer } from 'node:http';
const sid='44444444-4444-4444-8444-444444444444',tid='55555555-5555-4555-8555-555555555555';
let server,origin,connections,state,posts,streamOpens;
const wire=(event,data)=>`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const broadcast=(event,data)=>{for(const res of connections)res.write(wire(event,data));};
test.beforeAll(async()=>{
 server=createServer((req,res)=>{
  res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Headers','Content-Type, X-Enzymind-Client, Accept');
  if(req.method==='OPTIONS'){res.writeHead(204);res.end();return;}
  res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache','X-Accel-Buffering':'no'});
  connections.add(res);streamOpens++;
  res.write(wire('snapshot',{turn:state,results:[]}));
  if(!['running','queued'].includes(state.status)){res.end(wire('done',{turn:state}));}
  req.on('close',()=>connections.delete(res));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin=`http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async()=>{for(const res of connections)res.destroy();await new Promise(resolve=>server.close(resolve));});
test.beforeEach(async({page})=>{
 connections=new Set();posts=0;streamOpens=0;
 state={id:tid,session_id:sid,status:'running',message:'Stream this answer',output:'',partial_output:'',references:[],events:[],created:1700000000};
 await page.route('**/enzymind/api/workspace/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  if(path.endsWith('/stream'))return route.continue({url:origin+path});
  if(route.request().method()==='POST'&&path.endsWith('/turns')){posts++;return route.fulfill({json:state});}
  if(path.endsWith('/cancel')){state.status='cancelled';state.error='Stopped by you.';broadcast('done',{turn:state});return route.fulfill({json:state});}
  const session={id:sid,title:'Streaming regression',created:1700000000,updated:1700000000,summary:'',summarized_count:0,memory_revision:state.status==='completed'?1:0};
  if(path.endsWith('/sessions'))return route.fulfill({json:route.request().method()==='POST'?session:{sessions:[session]}});
  if(path.endsWith('/results'))return route.fulfill({json:{results:[]}});
  return route.fulfill({json:{...session,turns:posts?[state]:[],results:[]}});
 });
 await page.goto('/enzymind/agent');
 await page.locator('textarea').fill(state.message);await page.getByRole('button',{name:'Send question'}).click();
 await expect.poll(()=>connections.size).toBe(1);
});
test.afterEach(()=>{for(const res of connections)res.destroy();});

test('placeholder citations stay unlinked while streaming and after restoring history', async ({page}) => {
 state.partial_output='See [Catalytic reactions](https://example.invalid/), [annotation](https://source.invalid/) and [UniProt](https://www.uniprot.org/uniprotkb/P00698).';
 broadcast('delta',{text:state.partial_output});
 const answer=page.locator('.agent-markdown');
 await expect(answer).toContainText('Catalytic reactions');
 await expect(answer.locator('a')).toHaveCount(1);
 await expect(answer.locator('a')).toHaveAttribute('href','https://www.uniprot.org/uniprotkb/P00698');
 state.status='completed';state.output=state.partial_output;state.partial_output='';broadcast('done',{turn:state});
 await page.reload();
 await expect(answer).toContainText('annotation');
 await expect(answer.locator('a')).toHaveCount(1);
 expect(posts).toBe(1);
});

test('actual stream renders before completion, reconnects and refreshes without another POST',async({page})=>{
 state.partial_output='First paragraph. ';broadcast('delta',{text:state.partial_output});
 await expect(page.locator('.agent-markdown')).toContainText('First paragraph.');
 await expect(page.locator('.live-label')).toHaveText('Streaming');
 expect(state.status).toBe('running');expect(posts).toBe(1);
 // Deliberately split a multibyte character between network writes.
 const text='酶学研究🧬';state.partial_output+=text;const bytes=Buffer.from(wire('delta',{text}));const split=bytes.indexOf(Buffer.from('酶'))+1;
 for(const res of connections){res.write(bytes.subarray(0,split));res.write(bytes.subarray(split));}
 await expect(page.locator('.agent-markdown')).toContainText(text);
 for(const res of connections)res.destroy();
 await expect.poll(()=>streamOpens).toBeGreaterThan(1);
 await expect(page.locator('.agent-markdown')).toHaveText(state.partial_output);
 expect(posts).toBe(1);
 await page.reload();await expect.poll(()=>streamOpens).toBeGreaterThan(2);
 await expect(page.locator('.agent-markdown')).toHaveText(state.partial_output);expect(posts).toBe(1);
 state.status='completed';state.output='Final **verified** answer.';state.partial_output='';broadcast('done',{turn:state});
 await expect(page.locator('.agent-markdown strong')).toHaveText('verified');await expect(page.locator('.live-label')).toHaveCount(0);
 await page.getByRole('button',{name:'Conversation memory',exact:true}).click();await expect(page.locator('.memory-panel')).toContainText('Original exchanges');
 expect(posts).toBe(1);
});

for(const ending of ['cancelled','failed'])test(`${ending} generation retains partial text without treating it as a final answer`,async({page})=>{
 state.partial_output='Partial research response';broadcast('delta',{text:state.partial_output});
 await expect(page.locator('.agent-markdown')).toContainText(state.partial_output);
 if(ending==='cancelled')await page.getByRole('button',{name:'Stop analysis'}).click();
 else{state.status='failed';state.error='Upstream stream ended before completion.';broadcast('done',{turn:state});}
 await expect(page.locator('.partial-notice')).toContainText('not added to conversation memory');
 await expect(page.locator('.turn-error')).toBeVisible();await expect(page.locator('.agent-markdown')).toHaveText(state.partial_output);
 await expect(page.getByRole('button',{name:'Send question'})).toBeVisible();expect(posts).toBe(1);
});
