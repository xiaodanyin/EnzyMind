import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const root = new URL("../", import.meta.url);
const workflow = JSON.parse(
  readFileSync(new URL("enzymind_workspace_v2.json", root)),
);
const run = (name, input, states = {}) =>
  new Function(
    "$input",
    "$",
    "$runIndex",
    ["context", "compress"].includes(name) ? workflow.nodes.find(n=>n.name===(name === "context" ? "Evaluate context" : "Apply memory")).parameters.jsCode : readFileSync(new URL(`code/${name}.js`, root), "utf8"),
  )({ first: () => ({ json: input }) }, (name) => ({
    first: () => ({ json: states[name] }),
  }), 0)[0].json;
test('Python arguments preserve source and references and surface admission errors', () => {
  const node = workflow.nodes.find(n => n.name === 'Python Analysis');
  const expression = node.parameters.jsonBody.slice(3, -2).trim();
  const code = "value = results[data['source']]['km']\nresult = {'value': value}\n";
  const id = 'f91b1792-6707-46d7-97c6-77e8c1a33f36';
  const evaluate = inputs => new Function('$fromAI', `return (${expression});`)(
    (key, _description, type) => {
      assert.equal(type, key === 'code' ? 'string' : 'json');
      return key === 'code' ? code : inputs;
    },
  );
  assert.deepEqual(evaluate({data: {source: id}, result_ids: [id], file_ids: [], network: 'host'}),
    {code, data: {source: id}, result_ids: [id], file_ids: []});
  assert.deepEqual(evaluate({data: {}, result_ids: [], file_ids: []}),
    {code, data: {}, result_ids: [], file_ids: []});
  const refs = Array.from({length: 12}, (_, i) =>
    `f91b1792-6707-46d7-97c6-${String(i).padStart(12, '0')}`);
  assert.deepEqual(evaluate({data: {}, result_ids: refs, file_ids: []}).result_ids, refs);
  assert.match(node.parameters.toolDescription, /up to 12 exact saved result UUIDs/);
  assert.deepEqual(node.parameters.options.response.response,
    {neverError: true, responseFormat: 'json'});
});
test("workflow graph connects every tool and both memory branches", () => {
  const names = workflow.nodes.map((n) => n.name);
  assert.equal(new Set(names).size, names.length);
  for (const [name, ports] of Object.entries(workflow.connections)) {
    assert.ok(names.includes(name));
    for (const branches of Object.values(ports))
      for (const branch of branches)
        for (const edge of branch) assert.ok(names.includes(edge.node));
  }
  const tools = workflow.nodes.filter((n) =>
    n.type.endsWith(".httpRequestTool"),
  );
  assert.equal(tools.length, 27);
  const python = tools.find(n => n.name === 'Python Analysis');
  assert.match(python.parameters.url, /\/tools\/python/);
  assert.equal(python.parameters.options.timeout, 100000);
  assert.ok(!python.retryOnFail);
  assert.match(python.parameters.toolDescription, /result_ids/);
  for (const tool of tools) {
    assert.match(tool.parameters.url, /\/api\/workspace\/tools\//);
    assert.equal(
      tool.parameters.headerParameters.parameters[0].name,
      "X-Enzymind-Turn",
    );
    assert.equal(
      workflow.connections[tool.name].ai_tool[0][0].node,
      "Research Agent",
    );
  }
  assert.equal(workflow.connections["Compress memory?"].main.length, 2);
  assert.ok(!workflow.nodes.some((n) => /memoryBuffer/.test(n.type)));
  assert.ok(!workflow.nodes.some((n) => n.credentials));
});
test("small context skips compression and malformed capability is rejected", () => {
  const body = {
    message: "hello",
    history: [],
    summary: "",
    summarized_count: 0,
  };
  assert.equal(
    run("context", { body, headers: { "x-enzymind-turn": "a".repeat(48) } })
      .needs_compression,
    false,
  );
  assert.throws(() => run("context", { body, headers: {} }), /capability/);
});
test("compression preserves three recent exchanges and updates memory position", () => {
  const history = Array.from({ length: 14 }, (_, i) => ({
    role: i % 2 ? "assistant" : "user",
    content: `${i}:` + "x".repeat(3000),
  }));
  const state = run("context", {
    body: {
      message: "followup " + "x".repeat(270000),
      history,
      summary: "previous",
      summarized_count: 2,
    },
    headers: { "x-enzymind-turn": "a".repeat(48) },
  });
  assert.equal(state.needs_compression, true);
  assert.equal(state.compress_count, 8);
  const compressed = run(
    "compress",
    { text: "Accurate summary" },
    { "Prepare memory summary": state },
  );
  assert.equal(compressed.summarized_count, 10);
  assert.deepEqual(compressed.history, history.slice(8));
  const response = run(
    "response",
    { output: "Answer with citation" },
    { "Research context": compressed },
  );
  assert.deepEqual(response, {
    output: "Answer with citation",
    summary: "Accurate summary",
    summarized_count: 10,
    memory_revision: undefined,
    compression_count: 1,
    context_tokens: compressed.context_tokens,
    billing_mode: 'free',
  });
});

test('both reasoning and memory select the requested billing model without fallback',()=>{
  for(const target of ['Research Agent','Summarize older turns'])
    assert.ok(workflow.connections['Select billing model'].ai_languageModel[0].some(edge=>edge.node===target));
  assert.equal(workflow.connections['User DeepSeek relay'].ai_languageModel[0][0].index,1);
  assert.equal(workflow.connections['Research language model'].ai_languageModel[0][0].index,0);
  const selector=workflow.nodes.find(n=>n.name==='Select billing model');
  assert.equal(selector.parameters.rules.rule[0].modelIndex,2);
  assert.match(selector.parameters.rules.rule[0].conditions.conditions[0].leftValue,/billing_mode === 'byok'/);
  assert.throws(()=>run('context',{body:{billing_mode:'byok'},headers:{'x-enzymind-turn':'a'.repeat(48)}}),/temporary model capability/);
  assert.equal(workflow.settings.saveManualExecutions,false);
});

test('provider failures never expose raw credentials or use the free model',()=>{
  for(const code of [401,402,429]){
    const result=run('failure',{error:{statusCode:code,message:'sk-SECRET-TEST-ONLY'}},{'Workspace Webhook':{body:{billing_mode:'byok'}}});
    assert.match(result.error,/DeepSeek/);assert.ok(!JSON.stringify(result).includes('SECRET'));
  }
});
test("invalid compression state and empty answers do not silently overwrite memory", () => {
  assert.throws(
    () => run("compress", { text: "" }, { "Prepare memory summary": {} }),
    /memory compression state/,
  );
  assert.throws(
    () => run("response", { output: "" }, { "Research context": {} }),
    /did not return/,
  );
});

const contextState = body => run('context', {body, headers:{'x-enzymind-turn':'a'.repeat(48)}});
const bodyAtTokens = (count, extra = {}) => {
  const body = {message:'', history:[], summary:'', summarized_count:0, ...extra};
  const base = contextState(body).context_tokens;
  assert.ok(count >= base);
  body.message = 'x'.repeat((count - base) * 3);
  assert.equal(contextState(body).context_tokens, count);
  return body;
};

test('100,000-token boundary applies to full context including history, evidence and fixed instructions',()=>{
  for (const withHistory of [false,true]) {
    const history=withHistory ? [{role:'user',content:'Keep the original constraints.'},{role:'assistant',content:'Saved scientific evidence.'}] : [];
    const evidence=[{id:'saved-result',data:{sequence:'ACDE'.repeat(2000)}}];
    for (const count of [99999,100000,100001]) {
      const body=bodyAtTokens(count,{history,evidence});
      const state=contextState(body);
      assert.equal(state.needs_compression,withHistory && count>100000);
      assert.equal(state.context_warning,!withHistory && count>100000);
      assert.equal(state.message,body.message);
      assert.deepEqual(state.evidence,evidence);
      assert.deepEqual(state.history,history);
      assert.equal(state.summarized_count,0);
    }
  }
});
test('the old 10k and 12k budgets no longer compress history or warn',()=>{
  const history=[{role:'user',content:'Question'},{role:'assistant',content:'Evidence'}];
  for (const count of [12001,48000,99999]) {
    const body=bodyAtTokens(count,{history});
    const state=contextState(body);
    assert.equal(state.needs_compression,false);
    assert.equal(state.context_warning,false);
    assert.deepEqual(state.history,history);
    assert.equal(state.summary,'');
  }
});
test('compression loops until the context fits 100k; summary batches and raw records stay bounded',()=>{
  const history=Array.from({length:80},(_,i)=>({role:i%2?'assistant':'user',content:'研究蛋白质反应'.repeat(150)}));
  let state=contextState({message:'继续',history,summary:'',summarized_count:0}),passes=0;
  while(state.needs_compression){
    const batch=JSON.stringify({summary:state.summary,history:state.history.slice(0,state.compress_count)});
    const size=Math.ceil([...batch].reduce((sum,c)=>sum+(c.codePointAt(0)<128?1:6),0)/3);
    assert.ok(size<=10000);
    state=run('compress',{text:'Keep the research goal and verify exact values in saved results.'},{'Prepare memory summary':state});
    state=run('context',state);passes++;assert.ok(passes<100);
  }
  assert.ok(passes>1);assert.ok(state.context_tokens<=100000);
  assert.equal(state.context_warning,false);assert.equal(history.length,80);
  assert.equal(state.summarized_count+state.history.length,80);
});
test('long first questions and retries preserve intact evidence above the advisory threshold',()=>{
  const body={message:'蛋白质'.repeat(17000),history:[],summary:'',summarized_count:0,
    evidence:[{id:'saved-result',data:{sequence:'ACDE'.repeat(2000)}}]};
  const state=contextState(body);
  assert.ok(state.context_tokens>100000);
  assert.equal(state.context_warning,true);assert.equal(state.needs_compression,false);
  assert.equal(state.message,body.message);assert.deepEqual(state.evidence,body.evidence);
  assert.equal(state.summarized_count,0);
  assert.equal(run('context',{body,headers:{'x-enzymind-turn':'b'.repeat(48)}}).context_warning,true);
});
test('compression retries once and preserves original memory if both summaries are rejected',()=>{
  const history=[{role:'user',content:'Question '.repeat(800)},{role:'assistant',content:'Evidence '.repeat(800)}];
  const state=contextState(bodyAtTokens(101000,{history,summary:'Existing memory',summarized_count:4}));
  assert.equal(state.needs_compression,true);
  for (const text of ['',null,{text:'wrong shape'},'研究'.repeat(900),'x'.repeat(6000)]) {
    const retry=run('compress',{text},{'Prepare memory summary':state});
    assert.equal(retry.retry_summary,true);assert.equal(retry.summary_attempt,1);
    assert.equal(retry.summary,state.summary);assert.deepEqual(retry.history,history);
    assert.equal(retry.summarized_count,4);assert.equal(retry.compression_count,0);
    const accepted=run('compress',{text:'Preserved goal, constraints and evidence references.'},{'Prepare memory summary':retry});
    assert.equal(accepted.summarized_count,6);assert.equal(accepted.summary_attempt,0);
    assert.equal(accepted.compression_count,1);assert.equal(accepted.retry_summary,false);
    assert.equal(run('context',accepted).needs_compression,false);
    assert.equal(run('context',accepted).context_warning,false);
    const deferred=run('compress',{text},{'Prepare memory summary':retry});
    assert.equal(deferred.retry_summary,false);assert.equal(deferred.summary,state.summary);
    assert.deepEqual(deferred.history,history);
    const ready=run('context',deferred);
    assert.equal(ready.needs_compression,false);assert.equal(ready.context_warning,true);
    assert.equal(ready.summarized_count,4);
    assert.equal(run('response',{output:'Answer'},{'Research context':ready}).summary,'Existing memory');
  }
});
test('summary retries use matching attempt indices even across multiple context passes',()=>{
  const source=workflow.nodes.find(n=>n.name==='Apply memory').parameters.jsCode;
  for(const runIndex of [0,1,2,3]){
    const state={history:[{role:'user',content:'question '.repeat(50)},{role:'assistant',content:'answer '.repeat(100)}],
      summary:'prior',compress_count:2,summarized_count:runIndex*2,compression_count:runIndex,context_tokens:101000,summary_attempt:runIndex%2};
    const out=new Function('$input','$','$runIndex',source)({first:()=>({json:{text:'Concise valid memory'}})},name=>({first:(branch,index)=>{
      assert.equal(name,'Prepare memory summary');assert.equal(branch,0);assert.equal(index,runIndex);return {json:state};
    }}),runIndex)[0].json;
    assert.equal(out.summarized_count,runIndex*2+2);
  }
});
test('a new turn resets deferred compression and below-threshold contexts do not warn',()=>{
  const history=[{role:'user',content:'Question'},{role:'assistant',content:'Evidence '.repeat(900)}];
  const body=bodyAtTokens(101000,{history,compression_deferred:true});
  assert.equal(contextState(body).needs_compression,true);
  assert.equal(run('context',{...body,compression_count:0}).needs_compression,false);
  assert.equal(run('context',{...body,compression_count:0}).context_warning,true);
  const smaller=bodyAtTokens(50000,{history,compression_deferred:true});
  assert.equal(contextState(smaller).context_warning,false);
  assert.equal(run('context',{...smaller,compression_count:0}).context_warning,false);
});
test('oversized historical exchanges and exhausted compression passes remain available to the Agent',()=>{
  const body={message:'Follow up',history:[{role:'user',content:'中文'.repeat(26000)},{role:'assistant',content:'Saved answer'}],summary:'',summarized_count:0};
  const state=contextState(body);
  assert.equal(state.needs_compression,false);assert.equal(state.context_warning,true);
  assert.deepEqual(state.history,body.history);
  const eligible=bodyAtTokens(101000,{history:[{role:'user',content:'Question'},{role:'assistant',content:'Evidence'}]});
  assert.equal(contextState(eligible).needs_compression,true);
  const exhausted=run('context',{...eligible,compression_count:100});
  assert.equal(exhausted.needs_compression,false);assert.equal(exhausted.context_warning,true);
  assert.deepEqual(exhausted.history,eligible.history);
});
test('memory validation errors omit internal code line numbers',()=>{
  const result=run('failure',{error:{message:'Invalid workspace request: memory compression state. [line 5]'}},{'Workspace Webhook':{body:{billing_mode:'free'}}});
  assert.equal(result.error,'Invalid workspace request: memory compression state.');
});
test('graph re-evaluates compressed memory and reports progress before tools',()=>{
  assert.equal(workflow.connections['Apply memory'].main[0][0].node,'Retry memory summary?');
  assert.equal(workflow.connections['Retry memory summary?'].main[0][0].node,'Prepare memory summary');
  assert.equal(workflow.connections['Retry memory summary?'].main[1][0].node,'Evaluate context');
  assert.equal(workflow.connections['Evaluate context'].main[0][0].node,'Report memory progress');
});
test('native streaming carries Agent text and a separate final memory envelope',()=>{
  const node=name=>workflow.nodes.find(n=>n.name===name);
  assert.equal(node('Workspace Webhook').parameters.responseMode,'streaming');
  assert.equal(node('Research Agent').parameters.options.enableStreaming,true);
  assert.equal(node('Research Agent').parameters.options.returnIntermediateSteps,false);
  assert.ok(node('Workspace response').typeVersion>=1.5);
  assert.equal(node('Workspace response').parameters.options.enableStreaming,true);
  assert.equal(workflow.connections['Return answer and memory'].main[0][0].node,'Workspace response');
  assert.equal(workflow.connections['Preserve memory on failure'].main[0][0].node,'Workspace response');
});
