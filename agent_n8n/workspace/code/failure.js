// Do not return service URLs, credentials or raw provider error objects.
const error = $input.first().json.error;
const message = (typeof error === 'string' ? error : error?.message || '').replace(/\s*\[line \d+\]\s*$/, '');
const known = ['context budget','compression budget','Memory compression could not','compression limit','Invalid workspace request','complete user/assistant pairs'];
const safe = known.some(part=>message.includes(part)) ? message : 'The Agent could not complete this turn. The original conversation and saved tool results are preserved. Check the workflow service before trying again.';
const ownKey = $('Workspace Webhook').first(0,0).json.body?.billing_mode === 'byok';
let errorMessage = safe;
if (ownKey) {
  const status = Number(error?.statusCode || error?.httpCode || error?.status || 0);
  if (status === 401 || /401|authorization failed|authentication failed|invalid api key/i.test(message)) errorMessage = 'DeepSeek could not authenticate your key. Choose Forget and enter a valid key.';
  else if (status === 402 || /402|insufficient.*balance/i.test(message)) errorMessage = 'Your DeepSeek account has insufficient API balance. Check your balance and retry.';
  else if (status === 429 || /429|rate limit/i.test(message)) errorMessage = 'Your DeepSeek account reached its rate limit. Wait and retry.';
  else errorMessage = 'The Agent could not complete this turn using your DeepSeek key. The original conversation and saved results are preserved.';
}
return [{json:{error:errorMessage}}];
