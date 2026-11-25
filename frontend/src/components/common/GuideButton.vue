<template>
  <button v-if="guide" type="button" class="page-guide-trigger" aria-label="Open page guide" title="Replay this page's guide" @click="openPageGuide"><span aria-hidden="true">?</span> <span class="guide-button-label">Guide</span></button>
</template>
<script setup>
import { openPageGuide } from '@/utils/uiPreferences';
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { pageGuide } from '@/config/pageGuides';
const route = useRoute();
const guide = computed(() => pageGuide(route));
</script>
<style scoped>
.page-guide-trigger{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--color-border);background:var(--color-surface);color:var(--color-primary);font:600 12px var(--font-family);padding:7px 11px;border-radius:20px;cursor:pointer;white-space:nowrap;min-height:32px;}
.page-guide-trigger>span:first-child{display:inline-grid;place-items:center;border:1px solid currentColor;border-radius:50%;width:16px;height:16px;font-size:11px;}.page-guide-trigger:hover{background:var(--color-primary-light);border-color:var(--color-primary);}.page-guide-trigger:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px;}
</style>
