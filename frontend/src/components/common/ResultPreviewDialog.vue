<template>
  <Teleport to="body">
    <dialog ref="dialog" class="result-preview-dialog" :style="imageSrc ? { width: `${imageWidth + 34}px` } : undefined" :aria-label="title" @cancel.prevent="emit('close')" @click="backdrop" @keydown="keepFocusInside">
      <div class="preview-dialog-layout">
        <header class="preview-dialog-header">
          <div><span class="preview-eyebrow">{{ imageSrc ? 'RESULT FIGURE' : 'RESULT TABLE' }}</span><h2>{{ title }}</h2></div>
          <button ref="closeButton" type="button" class="preview-close" aria-label="Close expanded result" @click="emit('close')">×</button>
        </header>
        <div class="preview-dialog-toolbar">
          <div v-if="imageSrc" class="preview-zoom" role="group" aria-label="Figure zoom">
            <button type="button" aria-label="Zoom out" :disabled="zoom <= minZoom" @click="setZoom(zoom / 1.5)">−</button>
            <output aria-live="polite" aria-label="Image scale">{{ Math.round(imageWidth / naturalWidth * 100) }}%</output>
            <button type="button" aria-label="Zoom in" :disabled="zoom >= maxZoom" @click="setZoom(zoom * 1.5)">+</button>
            <button type="button" @click="setZoom(1)">Fit</button>
            <button type="button" @click="setZoom(naturalWidth / fitWidth)">100%</button>
          </div>
          <p>{{ imageSrc ? 'Zoom in, then scroll to explore.' : 'Scroll to explore rows and columns.' }} Esc to close.</p>
        </div>
        <div ref="viewport" class="preview-dialog-viewport" :class="{ 'table-viewport': !imageSrc }" tabindex="0" :aria-label="imageSrc ? 'Expanded figure; scroll to explore' : 'Expanded table; scroll to explore'">
          <div v-if="imageSrc" class="preview-image-stage" :style="{ width: `${imageWidth + 32}px`, height: `${imageWidth * naturalHeight / naturalWidth + 32}px` }">
            <img :src="imageSrc" :alt="title" :style="{ width: `${imageWidth}px` }" draggable="false" @load="imageLoaded" @error="imageError = true" />
            <p v-if="imageError" role="alert">This figure could not be displayed. Close this view and retry the preview.</p>
          </div>
          <div v-else class="expanded-result-content"><slot /></div>
        </div>
        <p v-if="note" class="preview-dialog-note">{{ note }}</p>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';

const props = defineProps({ title: { type: String, required: true }, imageSrc: String, note: String, returnFocus: Object });
const emit = defineEmits(['close']);
const dialog = ref(null), closeButton = ref(null), viewport = ref(null);
const naturalWidth = ref(1), naturalHeight = ref(1), fitWidth = ref(1), zoom = ref(1), imageError = ref(false);
const imageWidth = computed(() => fitWidth.value * zoom.value);
const minZoom = computed(() => Math.min(.25, naturalWidth.value / fitWidth.value));
const maxZoom = computed(() => Math.max(8, naturalWidth.value / fitWidth.value));
let observer, previousOverflow;
function fit() {
  const el = dialog.value;
  if (!el) return;
  // Fit against screen bounds, not the content-sized viewport: using the latter
  // would make the image shrink repeatedly as the dialog adapts to its content.
  const bounds = getComputedStyle(el);
  const chromeHeight = [...el.querySelectorAll('.preview-dialog-header,.preview-dialog-toolbar,.preview-dialog-note')]
    .reduce((total, node) => total + node.getBoundingClientRect().height, 0);
  fitWidth.value = Math.max(1, Math.min(
    Math.max(720, naturalWidth.value),
    parseFloat(bounds.maxWidth) - 34,
    (parseFloat(bounds.maxHeight) - chromeHeight - 35) * naturalWidth.value / naturalHeight.value,
  ));
}
function imageLoaded(event) {
  naturalWidth.value = event.target.naturalWidth;
  naturalHeight.value = event.target.naturalHeight;
  fit();
}
async function setZoom(value) {
  const el = viewport.value;
  const x = (el.scrollLeft + el.clientWidth / 2) / el.scrollWidth;
  const y = (el.scrollTop + el.clientHeight / 2) / el.scrollHeight;
  zoom.value = Math.min(maxZoom.value, Math.max(minZoom.value, value));
  await nextTick();
  el.scrollLeft = x * el.scrollWidth - el.clientWidth / 2;
  el.scrollTop = y * el.scrollHeight - el.clientHeight / 2;
}
function backdrop(event) {
  if (event.target !== dialog.value) return;
  const r = dialog.value.getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) emit('close');
}
function keepFocusInside(event) {
  if (event.key !== 'Tab') return;
  const controls = [...dialog.value.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),[tabindex="0"]')].filter(el => el.getClientRects().length);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
onMounted(() => {
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  dialog.value.showModal();
  closeButton.value.focus({ preventScroll: true });
  observer = new ResizeObserver(fit);
  observer.observe(dialog.value);
  window.addEventListener('resize', fit);
});
onBeforeUnmount(() => {
  observer?.disconnect();
  window.removeEventListener('resize', fit);
  dialog.value?.close();
  document.body.style.overflow = previousOverflow ?? '';
  if (props.returnFocus?.isConnected) props.returnFocus.focus({ preventScroll: true });
});
</script>

<style scoped>
.result-preview-dialog{--preview-max-height:min(1100px,calc(100dvh - 48px));width:fit-content;min-width:min(520px,calc(100vw - 48px));height:fit-content;max-width:min(1440px,calc(100vw - 48px));max-height:var(--preview-max-height);inset:0;margin:auto;padding:0;border:1px solid #d7e1f2;border-radius:16px;background:#fff;color:var(--color-text);font-family:var(--font-family);box-shadow:0 24px 100px #101d4a55;overflow:hidden;}.result-preview-dialog::backdrop{background:#101c38b8;backdrop-filter:blur(4px);}.preview-dialog-layout{display:flex;flex-direction:column;max-height:calc(var(--preview-max-height) - 2px);min-height:0;}.preview-dialog-header,.preview-dialog-toolbar,.preview-dialog-note{flex-shrink:0;}.preview-dialog-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 22px 12px;}.preview-dialog-header>div{min-width:0;}.preview-eyebrow{font:10px var(--font-mono);letter-spacing:.12em;color:#71819b;}.preview-dialog-header h2{margin:5px 0 0;font-size:20px;line-height:1.4;overflow-wrap:anywhere;}.preview-close{flex-shrink:0;width:40px;height:40px;border:1px solid #dde4f0;border-radius:9px;background:#f6f8fc;color:#536780;font:26px var(--font-family);cursor:pointer;}.preview-dialog-toolbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding:0 22px 14px;}.preview-dialog-toolbar p{margin:0;font-size:12px;color:#64748b;}.preview-zoom{display:flex;align-items:center;gap:6px;}.preview-zoom button{min-width:36px;min-height:36px;padding:6px 10px;border:1px solid #dbe4f2;border-radius:7px;background:#fff;color:#395a9b;font:600 13px var(--font-family);cursor:pointer;}.preview-zoom button:disabled{opacity:.35;cursor:default;}.preview-zoom output{min-width:48px;text-align:center;font-size:12px;font-variant-numeric:tabular-nums;}.preview-dialog-viewport{display:flex;flex:1 1 auto;min-height:0;min-width:0;overflow:auto;overscroll-behavior:contain;background:#edf2f8;border-top:1px solid #dce4f1;}.preview-image-stage{display:grid;place-items:center;flex:0 0 auto;min-width:100%;margin:auto;padding:16px;}.preview-image-stage img{display:block;max-width:none;height:auto;background:white;border-radius:4px;box-shadow:0 3px 16px #27436a14;}.table-viewport{background:white;}.expanded-result-content{flex:0 0 auto;width:max-content;min-width:100%;margin:auto;padding:16px 20px;color:#334155;font-size:14px;}.expanded-result-content :deep(.data-table-scroll),.expanded-result-content :deep(.csv-preview),.expanded-result-content :deep(.chart-table),.expanded-result-content :deep(.site-table-wrap){max-height:none;overflow:visible;margin:0;}.expanded-result-content :deep(table){border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:14px;line-height:1.6;}.expanded-result-content :deep(th),.expanded-result-content :deep(td){text-align:left;padding:12px 16px;min-width:120px;max-width:560px;border-bottom:1px solid #e2e8f0;white-space:pre-wrap;overflow-wrap:anywhere;vertical-align:top;}.expanded-result-content :deep(thead th){position:sticky;top:0;z-index:1;background:#f1f5f9;color:#475569;font-size:13px;font-weight:600;}.expanded-result-content :deep(tbody tr:nth-child(even)){background:#f8fafc;}.expanded-result-content :deep(.cell-value){max-width:520px;white-space:pre-wrap;overflow:visible;text-overflow:clip;}.expanded-result-content :deep(.row-number){min-width:48px;width:48px;color:#64748b;}.preview-dialog-note{margin:0;padding:10px 22px;background:#f8fafc;border-top:1px solid #dce4f1;color:#64748b;font-size:11px;line-height:1.6;}button:focus-visible,.preview-dialog-viewport:focus-visible{outline:2px solid var(--color-primary);outline-offset:-3px;}
@media(max-width:600px){.result-preview-dialog{--preview-max-height:calc(100dvh - 16px);min-width:min(520px,calc(100vw - 16px));max-width:calc(100vw - 16px);border-radius:12px;}.preview-dialog-header{padding:14px;}.preview-dialog-header h2{font-size:17px;}.preview-dialog-toolbar{padding:0 14px 12px;}.expanded-result-content{padding:12px 10px;}.preview-dialog-note{padding:10px 14px;}}
</style>
