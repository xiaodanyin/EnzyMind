import { ref } from 'vue';

// UI preferences are separate from the private workspace access key.
export const UI_PREFERENCES_KEY = 'enzymind_ui_preferences_v1';
function readPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY) || '{}');
    const strings = value => Array.isArray(value) ? value.filter(v => typeof v === 'string').slice(-100) : [];
    return { seenTours: strings(saved.seenTours), dismissedNotices: strings(saved.dismissedNotices) };
  } catch { return { seenTours: [], dismissedNotices: [] }; }
}
const preferences = ref(readPreferences());
function save() {
  try { localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify(preferences.value)); }
  catch { /* Storage may be disabled; the current tab still remembers choices. */ }
}
export function hasSeenTour(key) { return preferences.value.seenTours.includes(key); }
export function markTourSeen(key) {
  preferences.value.seenTours = [...preferences.value.seenTours.filter(v => v !== key), key].slice(-100);
  save();
}
export function isNoticeDismissed(key) { return preferences.value.dismissedNotices.includes(key); }
export function setNoticeDismissed(key, dismissed) {
  preferences.value.dismissedNotices = preferences.value.dismissedNotices.filter(v => v !== key);
  if (dismissed) preferences.value.dismissedNotices.push(key);
  preferences.value.dismissedNotices = preferences.value.dismissedNotices.slice(-100);
  save();
}

export const GUIDE_EVENT = 'enzymind:open-page-guide';
export function openPageGuide() { window.dispatchEvent(new Event(GUIDE_EVENT)); }
