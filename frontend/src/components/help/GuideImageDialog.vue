<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="help-image-dialog"
      aria-labelledby="help-image-title"
      aria-describedby="help-image-instructions"
      @cancel.prevent="emit('close')"
      @click="onBackdropClick"
      @keydown="keepFocusInside"
    >
      <div class="image-dialog-content">
        <header class="image-dialog-header">
          <div>
            <span class="dialog-eyebrow">TOOL GUIDE</span>
            <h2 id="help-image-title">{{ guide.title }}</h2>
          </div>
          <button ref="closeButton" type="button" class="dialog-close" aria-label="Close full guide" @click="emit('close')">×</button>
        </header>
        <div class="image-dialog-toolbar">
          <div class="zoom-controls" role="group" aria-label="Image zoom">
            <button type="button" aria-label="Zoom out" :disabled="zoom <= 1" @click="setZoom(zoom / 1.5)">−</button>
            <output aria-live="polite" aria-label="Image scale">{{ Math.round(imageWidth / 2200 * 100) }}%</output>
            <button type="button" aria-label="Zoom in" :disabled="zoom >= maxZoom" @click="setZoom(zoom * 1.5)">+</button>
            <button type="button" @click="setZoom(1)">Fit</button>
            <button type="button" @click="setZoom(maxZoom)">100%</button>
          </div>
          <p id="help-image-instructions">Zoom in, then scroll to explore. Esc to close.</p>
        </div>
        <div ref="viewport" class="image-dialog-viewport" tabindex="0" aria-label="Guide image; scroll to explore when zoomed in">
          <div class="image-dialog-stage" :style="{ width: `${imageWidth + 32}px`, height: `${imageWidth * 1550 / 2200 + 32}px` }">
            <img :src="guide.image" :alt="guide.imageAlt || `${guide.title}: input, workflow and result guide`" :style="{ width: `${imageWidth}px` }" width="2200" height="1550" draggable="false" />
          </div>
        </div>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({ guide: { type: Object, required: true }, returnFocus: Object })
const emit = defineEmits(['close'])
const dialog = ref(null)
const closeButton = ref(null)
const viewport = ref(null)
const fitWidth = ref(800)
const zoom = ref(1)
const maxZoom = computed(() => 2200 / fitWidth.value)
const imageWidth = computed(() => fitWidth.value * zoom.value)
let observer
let previousOverflow

async function setZoom(value) {
  const el = viewport.value
  const centerX = (el.scrollLeft + el.clientWidth / 2) / el.scrollWidth
  const centerY = (el.scrollTop + el.clientHeight / 2) / el.scrollHeight
  zoom.value = Math.min(maxZoom.value, Math.max(1, value))
  await nextTick()
  el.scrollLeft = centerX * el.scrollWidth - el.clientWidth / 2
  el.scrollTop = centerY * el.scrollHeight - el.clientHeight / 2
}

function onBackdropClick(event) {
  if (event.target !== dialog.value) return
  const box = dialog.value.getBoundingClientRect()
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) emit('close')
}

function keepFocusInside(event) {
  if (event.key !== 'Tab') return
  const controls = [...dialog.value.querySelectorAll('button:not(:disabled), [tabindex="0"]')]
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(() => {
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  dialog.value.showModal()
  closeButton.value.focus({ preventScroll: true })
  observer = new ResizeObserver(() => {
    const el = viewport.value
    fitWidth.value = Math.max(1, Math.min(2200, el.clientWidth - 32, (el.clientHeight - 32) * 2200 / 1550))
    zoom.value = Math.min(zoom.value, maxZoom.value)
  })
  observer.observe(viewport.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  dialog.value?.close()
  document.body.style.overflow = previousOverflow ?? ''
  if (props.returnFocus?.isConnected) props.returnFocus.focus({ preventScroll: true })
})
</script>

<style scoped>
.help-image-dialog { width: min(1440px, calc(100vw - 40px)); max-width: none; height: min(1050px, calc(100dvh - 40px)); max-height: none; padding: 0; margin: auto; border: 1px solid #d7e1f2; border-radius: 18px; background: #fff; color: #203653; box-shadow: 0 24px 100px #101d4a55; overflow: hidden; }
.help-image-dialog::backdrop { background: #101c38b8; backdrop-filter: blur(4px); }
.image-dialog-content { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.image-dialog-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 22px 12px; }
.dialog-eyebrow { font-size: 10px; color: #6c7c97; letter-spacing: .13em; font-weight: 700; }
.image-dialog-header h2 { margin: 4px 0 0; font-size: 22px; line-height: 1.3; }
.dialog-close { flex-shrink: 0; width: 40px; height: 40px; border: 1px solid #dde4f0; border-radius: 10px; background: #f6f8fc; font: 26px var(--font-family); color: #536780; cursor: pointer; }
.image-dialog-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; padding: 0 22px 14px; }
.zoom-controls { display: flex; align-items: center; gap: 5px; }
.zoom-controls button { min-width: 40px; min-height: 36px; padding: 6px 10px; border: 1px solid #dbe4f2; border-radius: 7px; background: #fff; color: #395a9b; font: 600 13px var(--font-family); cursor: pointer; }
.zoom-controls button:disabled { opacity: .35; cursor: default; }
.zoom-controls output { min-width: 48px; text-align: center; font-size: 12px; font-variant-numeric: tabular-nums; color: #677b96; }
.image-dialog-toolbar p { margin: 0; font-size: 12px; color: #70809a; }
.image-dialog-viewport { flex: 1; min-height: 0; overflow: auto; overscroll-behavior: contain; background: #eaf0f9; border-top: 1px solid #dce4f1; }
.image-dialog-stage { display: grid; place-items: center; min-width: 100%; min-height: 100%; padding: 16px; }
.image-dialog-stage img { display: block; height: auto; max-width: none; border-radius: 4px; box-shadow: 0 3px 16px #27436a14; }
button:focus-visible, .image-dialog-viewport:focus-visible { outline: 3px solid #729cf3; outline-offset: -3px; }
@media (max-width: 600px) { .help-image-dialog { width: calc(100vw - 16px); height: calc(100dvh - 16px); border-radius: 12px; } .image-dialog-header { padding: 13px 14px 10px; } .image-dialog-header h2 { font-size: 18px; } .image-dialog-toolbar { padding: 0 14px 12px; } }
@media (prefers-reduced-motion: no-preference) { .help-image-dialog[open] { animation: image-dialog-in .18s ease-out; } @keyframes image-dialog-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } } }
</style>
