// Anchor each attempt, not each context pass: a summary retry does not run
// Evaluate context again. Explicit run indices also avoid reading pass zero.
const state = $('Prepare memory summary').first(0, $runIndex).json;
if (!Array.isArray(state.history) || !Number.isInteger(state.compress_count) ||
    state.compress_count < 2 || state.compress_count % 2 || state.compress_count > state.history.length ||
    !Number.isInteger(state.context_tokens) || state.context_tokens < 0 ||
    !Number.isInteger(state.summary_attempt) || ![0, 1].includes(state.summary_attempt)) {
  throw new Error('Invalid workspace request: memory compression state. The original conversation is preserved.');
}
const text = $input.first().json.text;
const summary = typeof text === 'string' ? text.trim() : '';
const tokens = value => Math.ceil([...value].reduce((n,c)=>n+(c.codePointAt(0)<128?1:6),0)/3);
const size = tokens(summary);
const previousSize = tokens(JSON.stringify({summary:state.summary,history:state.history.slice(0,state.compress_count)}));
const issue = !summary ? 'empty' : size > 1600 ? 'too_long' : size >= previousSize ? 'not_shorter' : '';
if (!issue) {
  return [{json:{...state,summary,summarized_count:state.summarized_count+state.compress_count,
    history:state.history.slice(state.compress_count),compression_count:state.compression_count+1,
    summary_attempt:0,retry_summary:false,summary_issue:'',summary_tokens:size,compression_deferred:false}}];
}
// Compression is advisory. Keep every original
// message and the exact persisted summary; never commit an invalid replacement.
if (state.context_tokens <= __CONTEXT_TOKEN_LIMIT__ || state.summary_attempt === 1) {
  return [{json:{...state,retry_summary:false,summary_issue:issue,summary_tokens:size,compression_deferred:true}}];
}
// One corrective generation from the original material, not from a lossy draft.
if (state.summary_attempt === 0) {
  return [{json:{...state,summary_attempt:1,retry_summary:true,summary_issue:issue,summary_tokens:size}}];
}
