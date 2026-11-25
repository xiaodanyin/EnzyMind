<template>
  <div v-if="dismissed" class="retention-collapsed" :class="{ urgent: state.urgent }">
    <button type="button" aria-label="Show retention details" @click="setNoticeDismissed(key, false)"><span aria-hidden="true">◷</span> {{ state.dated ? `Deletes ${expiryDate(expiresAt, true)}` : '90-day retention' }} <span class="retention-more">Details</span></button>
  </div>
  <aside v-else class="retention-notice" :class="{ urgent: state.urgent, compact }" aria-label="90-day data retention">
    <button type="button" class="retention-dismiss" aria-label="Dismiss retention notice" title="Hide this reminder" @click="setNoticeDismissed(key, true)">×</button>
    <span class="retention-symbol" aria-hidden="true">90d</span>
    <div class="retention-copy">
      <strong v-if="state.dated">{{ state.expired ? 'Retention period ended — download now if still available' : state.urgent ? `Deletes in ${state.days} ${state.days === 1 ? 'day' : 'days'} — download your result` : 'Download your result before it expires' }}</strong>
      <strong v-else>Results and conversation messages are automatically deleted after 90 days</strong>
      <p v-if="state.dated">Deletion date: <time :datetime="new Date(expiresAt * 1000).toISOString()">{{ expiryDate(expiresAt) }}</time>. Save the full result JSON and any figures or structures you need.</p>
      <p v-else>Download results and export conversations within 90 days of creation. Viewing records, continuing a conversation, or saving a link or access file does not extend their retention.</p>
      <small v-if="!compact">Cleanup runs hourly. Records used by active analyses are temporarily protected.</small>
    </div>
    <div v-if="$slots.default" class="retention-actions"><slot /></div>
  </aside>
</template>
<script setup>
import { computed } from 'vue';
import { useRetentionClock, expiryState, expiryDate } from '@/utils/retention';
import { isNoticeDismissed, setNoticeDismissed } from '@/utils/uiPreferences';
const props = defineProps({ expiresAt: { type: Number, default: null }, compact: Boolean, noticeKey: { type: String, default: '' } });
const now = useRetentionClock();
const state = computed(() => expiryState(props.expiresAt, now.value));
const key = computed(() => props.noticeKey || (state.value.dated ? `retention-result:${props.expiresAt}` : 'retention-policy'));
const dismissed = computed(() => isNoticeDismissed(key.value));
</script>
<style scoped>
.retention-notice{display:flex;align-items:flex-start;gap:12px;margin:16px 0;padding:16px;border:1px solid #cad9f5;border-radius:10px;background:#f2f6ff;color:var(--color-text);font-size:12px;line-height:1.65;min-width:0;flex-shrink:0;flex-wrap:wrap;}
.retention-symbol{font:700 12px var(--font-mono);padding:5px 6px;border-radius:6px;background:#e0eaff;color:var(--color-primary);flex-shrink:0;}
.retention-copy{flex:1 1 220px;min-width:0;overflow-wrap:anywhere;}.retention-copy strong{font-size:13px;}.retention-copy p{margin:4px 0;}.retention-copy small{color:var(--color-text-secondary);font-size:11px;}.retention-copy time{font-weight:600;}
.retention-actions{display:flex;gap:8px;flex-wrap:wrap;align-self:center;}.retention-actions :slotted(button),.retention-actions :slotted(a){font:600 12px var(--font-family);line-height:1.5;border:1px solid var(--color-primary);border-radius:6px;padding:8px 10px;background:white;color:var(--color-primary);text-decoration:none;cursor:pointer;}
.urgent{border-color:#dbaf61;background:#fff8e9;}.urgent .retention-symbol{background:#ffedc7;color:#805313;}.compact{padding:11px 14px;}.compact .retention-copy strong{font-size:12px;}
@media(max-width:600px){.retention-actions{width:100%;}.retention-actions :slotted(button){flex:1;}}
.retention-notice{position:relative;padding-right:42px;}.retention-notice.compact{padding-right:42px;}
.retention-dismiss{position:absolute;right:6px;top:6px;display:grid;place-items:center;width:30px;height:30px;border:0;border-radius:6px;background:transparent;color:var(--color-text-secondary);font:22px var(--font-family);cursor:pointer;}.retention-dismiss:hover{background:rgba(37,99,235,.08);}.retention-dismiss:focus-visible,.retention-collapsed button:focus-visible{outline:2px solid var(--color-primary);outline-offset:2px;}
.retention-collapsed{margin:8px 0;flex-shrink:0;line-height:1.4;}.retention-collapsed button{display:inline-flex;align-items:center;gap:6px;padding:3px 0;border:0;background:transparent;font:11px var(--font-family);color:var(--color-text-secondary);cursor:pointer;flex-wrap:wrap;}.retention-collapsed.urgent{background:none;}.retention-collapsed.urgent button{color:#805313;}.retention-more{color:var(--color-primary);text-decoration:underline;text-underline-offset:3px;}
</style>
