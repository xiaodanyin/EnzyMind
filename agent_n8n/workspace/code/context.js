// The gateway owns raw history. This node runs again after each compression pass.
const incoming = $input.first().json;
const initial = incoming.body !== undefined;
if (initial && !/^[A-Za-z0-9_-]{40,128}$/.test(incoming.headers?.['x-enzymind-turn'] || '')) throw new Error('A gateway-issued execution capability is required.');
const state = initial ? {...incoming.body, compression_count:0,summary_attempt:0,retry_summary:false,compression_deferred:false} : {...incoming};
if (state.billing_mode === 'byok' && !/^[a-f0-9]{64}$/.test(state.model_relay_token || '')) throw new Error('Invalid workspace request: missing temporary model capability.');
if (state.billing_mode && !['free','byok'].includes(state.billing_mode)) throw new Error('Invalid workspace request: billing mode.');
if (typeof state.message !== 'string' || !Array.isArray(state.history) || state.history.length % 2 || typeof state.summary !== 'string' || !Number.isInteger(state.summarized_count) || state.summarized_count < 0 || state.summarized_count % 2) throw new Error('Invalid workspace request.');
if (state.history.some((h,i)=>h.role !== (i%2?'assistant':'user') || typeof h.content !== 'string')) throw new Error('History must contain complete user/assistant pairs.');
const tokens = value => Math.ceil([...String(value)].reduce((sum,c)=>sum+(c.codePointAt(0)<128?1:6),0)/3);
// Replaced by the builder using the actual system prompt and tool descriptions.
const reserve = __CONTEXT_RESERVE__;
const contextLimit = __CONTEXT_TOKEN_LIMIT__;
const context = {summary:state.summary,history:state.history,message:state.message,evidence:state.evidence || [],result_index:state.result_index || []};
const estimate = reserve + tokens(JSON.stringify(context));
let compressCount = 0;
if (estimate > contextLimit && state.history.length && !state.compression_deferred && state.compression_count < 100) {
  // First preserve three recent exchanges; if they alone are too large, reduce
  // the window by whole exchanges. Never slice a question, answer or evidence.
  const available = Math.max(2,state.history.length - 6);
  for (let n=2;n<=available;n+=2) {
    const batchSize = tokens(JSON.stringify({summary:state.summary,history:state.history.slice(0,n)}));
    if (batchSize > 10000) break; // Summary-call batch size, not the Agent context threshold.
    compressCount = n;
  }
}
// This estimate is a compression target, not the selected model's context limit.
// Continue with intact input when there is nothing suitable left to summarize.
const contextWarning = !compressCount && estimate > contextLimit;
return [{json:{...state,context_tokens:estimate,context_warning:contextWarning,needs_compression:compressCount>0,compress_count:compressCount,retained_messages:state.history.length-compressCount}}];
