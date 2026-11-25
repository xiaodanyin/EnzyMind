const state = $('Research context').first().json;
const output = $input.first().json.output;
if (typeof output !== 'string' || !output.trim()) throw new Error('The research agent did not return an answer.');
return [{json:{output,summary:state.summary,summarized_count:state.summarized_count,memory_revision:state.memory_revision,compression_count:state.compression_count,context_tokens:state.context_tokens,billing_mode:state.billing_mode || 'free'}}];
