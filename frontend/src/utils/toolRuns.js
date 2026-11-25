import { reactive } from 'vue';
import api from '../api/index.js';
import { newRequestId } from './workspace.js';
import { unpackResult } from './resultData.js';

// Requests and drafts outlive route components. Each result belongs to its run.
export const toolRuns = reactive({});
export function toolState(id) {
  if (!toolRuns[id]) toolRuns[id] = { protein: {text:'',method:'auto',selected:'',filename:''}, smiles:'', chemicalMode:'text', maxHits:3, database:'', running:false, started:0, error:'', record:null };
  // Read back through the reactive map; assignment itself returns the raw object.
  return toolRuns[id];
}
export function toolRequest(tool, protein, smiles, options = {}) {
  if (tool.id === 'enzyme-type') return {query:smiles,k:5};
  if (tool.id === 'enzyme-info') return {uniprot_id:protein.query};
  if (tool.id === 'active-sites') return protein.type === 'uniprot' ? {uniprot_id:protein.query} : {aa_sequence:protein.query,...(smiles?{rxn_smiles:smiles}:{})};
  if (tool.molecule === 'molecule') return {enzyme_input_type:protein.type,enzyme_query:protein.query,smiles};
  if (tool.id === 'blast') return {query:protein.query,max_results:options.maxHits,...(options.database ? {database:options.database} : {}),wait_for_result:false};
  if (tool.id === 'parameters') return {query:protein.query};
  return {input_type:protein.type,query:protein.query,...(tool.id==='structure'?{output_name:`enzymind_${Date.now()}`}:{})};
}
export async function runTool(tool, inputs) {
  const state=toolState(tool.id);if(state.running)return;
  state.running=true;state.error='';state.record=null;state.started=Date.now();
  const created=Date.now()/1000;
  try {
    const response=await api.post(tool.endpoint,inputs);
    const {workspace_result: saved,...payload}=response;
    const data=unpackResult(payload);
    const failure=data.error || (data.success===false?'The service could not complete this analysis.':'') || (typeof data.result==='string' && /^\s*(?:\[ERROR\]|❌)/.test(data.result)?data.result:'');
    state.record={...(saved||{id:newRequestId(),tool:tool.id,title:tool.title,created,inputs,status:failure?'failed':data.status || 'completed',evidence_type:tool.analysis?(tool.id==='parameters'?'Calculated properties':tool.id==='blast'?'Sequence alignment':'Database annotation'):'Prediction',local_only:true}),payload,duration:(Date.now()/1000-created)};
    if(failure)state.error=String(failure);
  } catch(e) {state.error=e.message || 'The request could not complete. Your input is preserved. Retry when ready.'; if(e.workspaceResult)state.record=e.workspaceResult;}
  finally {state.running=false;}
}
