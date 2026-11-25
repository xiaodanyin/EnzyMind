import { ref, onMounted, onBeforeUnmount } from 'vue';
export const RETENTION_DAYS = 90;
export const WARNING_DAYS = 7;
export const RETENTION_SECONDS = RETENTION_DAYS * 86400;
const clock = ref(Date.now() / 1000);
let users = 0, timer;
export function useRetentionClock() {
  onMounted(() => {
    clock.value = Date.now() / 1000;
    if (++users === 1) timer = setInterval(() => { clock.value = Date.now() / 1000; }, 60000);
  });
  onBeforeUnmount(() => { if (--users === 0) clearInterval(timer); });
  return clock;
}
export function resultExpiry(record) {
  if (record?.local_only) return null;
  return Number.isFinite(record?.expires_at) ? record.expires_at :
    Number.isFinite(record?.created) ? record.created + RETENTION_SECONDS : null;
}
export function expiryState(expiresAt, now = Date.now() / 1000) {
  if (!Number.isFinite(expiresAt)) return { dated: false, urgent: false, expired: false };
  const remaining = expiresAt - now;
  return { dated: true, urgent: remaining <= WARNING_DAYS * 86400, expired: remaining <= 0,
    days: Math.max(0, Math.ceil(remaining / 86400)) };
}
export function expiryDate(value, short = false) {
  return new Date(value * 1000).toLocaleString('en-US', short ?
    { year: 'numeric', month: 'short', day: 'numeric' } :
    { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' });
}
