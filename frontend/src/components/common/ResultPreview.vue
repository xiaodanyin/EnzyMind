<template>
  <div class="result-preview">
    <div class="preview-toolbar">
      <button ref="expandButton" type="button" class="expand-preview" :disabled="disabled" :aria-label="`Expand ${title}`" aria-haspopup="dialog" @click="open">
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4M3 3l5 5m9-5-5 5M3 17l5-5m9 5-5-5" /></svg>
        Expand {{ isImage ? 'figure' : 'table' }}
      </button>
    </div>
    <div class="result-preview-surface" :class="{ 'can-expand': !disabled }" @click="openFromContent"><slot /></div>
    <ResultPreviewDialog v-if="opened" :title="title" :image-src="openedImage" :note="note" :return-focus="expandButton" @close="opened = false">
      <slot />
    </ResultPreviewDialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import ResultPreviewDialog from './ResultPreviewDialog.vue';

const props = defineProps({ title: { type: String, default: 'Result table' }, imageSrc: String, imageProvider: Function, note: String, disabled: Boolean, clickToExpand: { type: Boolean, default: true } });
const expandButton = ref(null), opened = ref(false), openedImage = ref('');
const isImage = computed(() => Boolean(props.imageSrc || props.imageProvider));
function open() {
  if (props.disabled) return;
  openedImage.value = props.imageSrc || props.imageProvider?.() || '';
  opened.value = true;
}
function openFromContent(event) {
  // Preserve links, residue selection, and selecting text for copying.
  if (!props.clickToExpand || event.target.closest('a,button,input,select,textarea,summary,[role="button"]') || window.getSelection()?.toString()) return;
  open();
}
watch(() => [props.title, props.imageSrc], () => { opened.value = false; });
</script>

<style scoped>
.result-preview{min-width:0;}.preview-toolbar{display:flex;justify-content:flex-end;padding:7px 10px;background:#f8fafc;border-bottom:1px solid var(--color-border);}.expand-preview{display:inline-flex;align-items:center;gap:6px;padding:6px 9px;border:1px solid #dbe4f2;border-radius:6px;background:white;color:#45628c;font:500 11px var(--font-family);cursor:pointer;}.expand-preview:hover{color:var(--color-primary);background:#eff6ff;border-color:#adc6ef;}.expand-preview:focus-visible{outline:2px solid var(--color-primary);outline-offset:2px;}.expand-preview:disabled{opacity:.4;cursor:default;}.expand-preview svg{width:14px;height:14px;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round;}.can-expand{cursor:zoom-in;}
</style>
