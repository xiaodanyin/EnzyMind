export const isBlastPending = record => record?.tool === 'blast' && ['submitting', 'queued', 'paused'].includes(record.status);
export const isRunningResult = record => isBlastPending(record) || (record?.tool === 'structure' && record.status === 'running');
export const resultStatusLabel = status => ({running:'Predicting structure',completed:'Completed',failed:'Failed',submitting:'Submitting',queued:'Queued at NCBI',paused:'Checks paused'}[status] || status);
