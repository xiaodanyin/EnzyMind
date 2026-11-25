<template>
  <section class="selected-tool-guide" :aria-labelledby="`guide-title-${guide.id}`">
    <div class="selected-guide-heading">
      <div><component :is="headingTag" :id="`guide-title-${guide.id}`" class="guide-title">{{ guide.title }}</component><p>{{ guide.description }}</p></div>
      <router-link class="open-tool" :to="guide.path" :aria-label="`Open ${guide.title}`">{{ guide.openLabel || 'Open tool' }} <span aria-hidden="true">↗</span></router-link>
    </div>
    <p class="sr-only" role="status">Showing {{ guide.title }} guide.</p>
    <ol class="guide-steps" :class="{ 'four-steps': guide.steps.length === 4 }">
      <li v-for="(step, index) in guide.steps" :key="index">
        <span class="step-number" aria-hidden="true">0{{ index + 1 }}</span>
        <div><h5>{{ step.title }}</h5><p>{{ step.text }}</p></div>
      </li>
    </ol>
    <figure class="guide-figure">
      <button type="button" class="guide-preview" :class="{ loaded: imageState === 'ready' }" :disabled="imageState === 'error'" :aria-label="`View full ${guide.title} guide`" @click="openImage">
        <img :key="guide.id" :src="guide.image" :data-guide-id="guide.id" :alt="guide.imageAlt || `${guide.title}: screenshots showing the input, workflow and results`" width="2200" height="1550" loading="lazy" decoding="async" @load="imageLoaded" @error="imageFailed" />
        <span v-if="imageState === 'loading'" class="image-placeholder" role="status">Loading guide…</span>
        <span v-else-if="imageState === 'error'" class="image-placeholder" role="status">{{ guide.imageUnavailable || 'Image unavailable. Open the tool and select “Guide” for a walkthrough.' }}</span>
        <span v-else class="expand-image" aria-hidden="true">⤢ Expand</span>
      </button>
      <figcaption>
        <span>{{ guide.caption || 'Example walkthrough · your results may differ.' }}</span>
        <button type="button" :disabled="imageState === 'error'" @click="openImage">View full guide <span aria-hidden="true">↗</span></button>
      </figcaption>
    </figure>
    <GuideImageDialog v-if="imageOpen" :guide="guide" :return-focus="imageOpener" @close="imageOpen = false" />
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import GuideImageDialog from './GuideImageDialog.vue'

const props = defineProps({
  guide: { type: Object, required: true },
  headingTag: { type: String, default: 'h4' },
})
const imageState = ref('loading')
const imageOpen = ref(false)
const imageOpener = ref(null)

watch(() => props.guide.id, () => { imageState.value = 'loading' })
function imageLoaded(event) { if (event.target.dataset.guideId === props.guide.id) imageState.value = 'ready' }
function imageFailed(event) { if (event.target.dataset.guideId === props.guide.id) imageState.value = 'error' }
function openImage(event) { imageOpener.value = event.currentTarget; imageOpen.value = true }
</script>

<style scoped>
.selected-tool-guide { border-top: 1px solid #e3eaf5; padding: 24px; background: linear-gradient(160deg, #f8fbff, #fff 60%); }
.selected-guide-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.guide-title { font-size: 22px; margin: 0 0 8px; line-height: 1.3; letter-spacing: -.025em; }
.selected-guide-heading p { font-size: 13px; line-height: 1.7; color: var(--guide-muted); margin: 0; max-width: 600px; }
.open-tool { flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; gap: 10px; padding: 10px 14px; border-radius: 8px; background: #3f64d1; border: 1px solid #3f64d1; color: white; font-size: 12px; font-weight: 600; text-decoration: none; }
.guide-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; list-style: none; padding: 0; margin: 24px 0; }
.guide-steps.four-steps { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.guide-steps li { display: flex; align-items: flex-start; gap: 9px; min-width: 0; }
.step-number { font: 600 10px var(--font-mono); color: #697fbe; padding-top: 3px; }
.guide-steps h5 { font-size: 12px; line-height: 1.5; margin: 0 0 6px; color: #344f75; }
.guide-steps p { font-size: 12px; line-height: 1.75; margin: 0; color: var(--guide-muted); }
.guide-figure { margin: 0; }
.guide-preview { display: block; position: relative; width: 100%; aspect-ratio: 2200 / 1550; padding: 0; background: #eef3fb; border: 1px solid #dce5f3; border-radius: 10px; overflow: hidden; cursor: zoom-in; }
.guide-preview img { display: block; width: 100%; height: auto; opacity: 0; }
.guide-preview.loaded img { opacity: 1; }
.guide-preview:disabled { cursor: default; }
.image-placeholder { position: absolute; inset: 0; display: grid; place-content: center; padding: 24px; color: #7889a2; font: 13px var(--font-family); line-height: 1.7; }
.expand-image { position: absolute; top: 10px; right: 10px; border: 1px solid #d4dff2; border-radius: 7px; padding: 6px 9px; background: #ffffffed; color: #4564a4; font: 11px var(--font-family); }
.guide-figure figcaption { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-top: 10px; }
.guide-figure figcaption > span { font-size: 11px; color: #7a89a0; line-height: 1.6; }
.guide-figure figcaption button { flex-shrink: 0; background: none; border: 0; padding: 7px 0 7px 7px; color: #4166bf; font: 600 12px var(--font-family); cursor: pointer; }

.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
button:focus-visible, a:focus-visible { outline: 3px solid #7b9fe8; outline-offset: 3px; }
@media (hover: hover) { .open-tool:hover { background: #3055ba; } .guide-preview:hover { border-color: #8ba9df; } }
@media (max-width: 1000px) { .guide-steps.four-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) { .guide-steps, .guide-steps.four-steps { grid-template-columns: 1fr; gap: 15px; } .guide-steps h5 { margin-bottom: 3px; } .selected-tool-guide { padding: 20px; } }
@media (max-width: 500px) { .selected-guide-heading { flex-direction: column; gap: 13px; } .guide-title { font-size: 20px; } .guide-figure figcaption { flex-wrap: wrap; gap: 3px; } .guide-figure figcaption button { padding-left: 0; } }
@media (prefers-reduced-motion: no-preference) { .guide-preview img { transition: opacity .18s ease-out; } .open-tool { transition: background-color .18s, border-color .18s, color .18s; } }
</style>
