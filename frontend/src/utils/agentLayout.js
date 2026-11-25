import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue';

export const AGENT_LAYOUT_KEY = 'enzymind_agent_layout_v1';
const HANDLE = 8, CHAT_MIN = 360, LEFT_MIN = 190, RIGHT_MIN = 320;
const clamp = (value, min, max) => Math.min(Math.max(value, min), Math.max(min, max));

export function fitAgentColumns(width, open, preferred = {}) {
  const right = open ? clamp(preferred.right ?? width * .42, RIGHT_MIN, width - LEFT_MIN - CHAT_MIN - 2 * HANDLE) : 0;
  const left = clamp(preferred.left ?? (open ? 220 : 250), LEFT_MIN, Math.min(400, width - right - CHAT_MIN - (open ? 2 : 1) * HANDLE));
  return { left, right, leftMax: Math.min(400, width - right - CHAT_MIN - (open ? 2 : 1) * HANDLE), rightMax: width - left - CHAT_MIN - 2 * HANDLE };
}

export function useAgentLayout(element, inspectorOpen) {
  const width = ref(0), viewport = ref(0), preferred = ref({}), dragging = ref('');
  const wide = computed(() => viewport.value > 1200);
  const desktop = computed(() => viewport.value > 760);
  const columns = computed(() => fitAgentColumns(width.value, inspectorOpen.value && wide.value, preferred.value));
  const style = computed(() => ({ '--sidebar-width': `${columns.value.left}px`, '--inspector-width': `${columns.value.right}px` }));
  let observer, active;
  function persist() { try { localStorage.setItem(AGENT_LAYOUT_KEY, JSON.stringify(preferred.value)); } catch {} }
  function setWidth(side, value) {
    const bounds = columns.value;
    preferred.value = { ...preferred.value, [side]: clamp(value, side === 'left' ? LEFT_MIN : RIGHT_MIN, bounds[`${side}Max`]) };
  }
  function finish() {
    if (!active) return;
    active.target.removeEventListener('pointermove', move);
    active.target.removeEventListener('pointerup', finish);
    active.target.removeEventListener('pointercancel', finish);
    active.target.removeEventListener('lostpointercapture', finish);
    if (active.target.hasPointerCapture(active.id)) active.target.releasePointerCapture(active.id);
    document.body.style.cursor = active.cursor;
    document.body.style.userSelect = active.userSelect;
    active = null;
    dragging.value = '';
    persist();
  }
  function move(event) {
    if (!active || event.pointerId !== active.id) return;
    setWidth(active.side, active.start + (event.clientX - active.x) * (active.side === 'left' ? 1 : -1));
  }
  function start(side, event) {
    if (event.button !== 0 || !desktop.value || (side === 'right' && !wide.value)) return;
    finish();
    event.preventDefault();
    event.currentTarget.focus();
    active = { side, id: event.pointerId, target: event.currentTarget, x: event.clientX, start: columns.value[side], cursor: document.body.style.cursor, userSelect: document.body.style.userSelect };
    active.target.setPointerCapture(active.id);
    active.target.addEventListener('pointermove', move);
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) active.target.addEventListener(type, finish);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    dragging.value = side;
  }
  function key(side, event) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const delta = (event.key === 'ArrowRight' ? 16 : -16) * (side === 'left' ? 1 : -1);
    setWidth(side, event.key === 'Home' ? 0 : event.key === 'End' ? columns.value[`${side}Max`] : columns.value[side] + delta);
    persist();
  }
  function reset(side) { const next = { ...preferred.value }; delete next[side]; preferred.value = next; persist(); }
  function measure() {
    finish();
    viewport.value = window.innerWidth;
    width.value = element.value?.clientWidth || 0;
  }
  onMounted(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(AGENT_LAYOUT_KEY) || '{}');
      preferred.value = Object.fromEntries(['left', 'right'].filter(key => Number.isFinite(saved?.[key])).map(key => [key, saved[key]]));
    } catch {}
    measure();
    observer = new ResizeObserver(measure);
    observer.observe(element.value);
    window.addEventListener('resize', measure);
    window.addEventListener('blur', finish);
  });
  watch(inspectorOpen, finish);
  onBeforeUnmount(() => { finish(); observer?.disconnect(); window.removeEventListener('resize', measure); window.removeEventListener('blur', finish); });
  return { columns, style, dragging, start, key, reset };
}
