import { ref, watch, onBeforeUnmount } from 'vue';
import { workspaceFetch, postWorkspace } from './workspace.js';
import { isRunningResult } from './blastStatus.js';

// Poll saved local state only. The server owns NCBI polling and rate limits.
export function useLiveBlast(source, updated) {
  const record = ref(source()), error = ref(''), checking = ref(false);
  let timer, generation = 0, stopped = false;
  function schedule() {
    clearTimeout(timer);
    if (!stopped && !record.value.local_only && isRunningResult(record.value) && record.value.status !== 'paused')
      timer = setTimeout(() => fetchRecord(false), 5000);
  }
  async function fetchRecord(manual) {
    const current = generation, id = record.value.id;
    if (manual) checking.value = true;
    try {
      const next = await (manual ? postWorkspace(`/results/${id}/refresh`) : workspaceFetch(`/results/${id}`));
      if (stopped || current !== generation) return;
      record.value = next; error.value = ''; updated(next);
    } catch (e) {
      if (!stopped && current === generation) error.value = e.message;
    } finally {
      if (!stopped && current === generation) { checking.value = false; schedule(); }
    }
  }
  watch(source, value => { generation++; record.value = value; error.value = ''; checking.value = false; schedule(); }, {immediate:true});
  onBeforeUnmount(() => { stopped = true; generation++; clearTimeout(timer); });
  return {record, pollError:error, checking, refresh:()=>fetchRecord(true)};
}
