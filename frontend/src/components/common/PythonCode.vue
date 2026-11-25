<template>
  <div class="python-code">
    <div class="code-toolbar">
      <span><span class="language-dot" aria-hidden="true"></span>Python <span class="line-count">{{ lines.length }} lines</span></span>
      <button type="button" @click="copy">{{ copied ? 'Copied' : 'Copy code' }}</button>
      <span class="sr-only" role="status">{{ copied ? 'Code copied to clipboard.' : '' }}</span>
    </div>
    <pre tabindex="0" aria-label="Python source code"><code><span v-for="(line, i) in lines" :key="i" class="code-line"><span class="line-number" aria-hidden="true">{{ i + 1 }}</span><span class="line-content"><span v-for="(token, j) in line" :key="j" :class="token.types">{{ token.text }}</span>{{ line.length ? '' : '\n' }}</span></span></code></pre>
    <p v-if="copyError" role="alert">Could not copy. Select the code and copy it manually.</p>
  </div>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import Prism from 'prismjs/components/prism-core.js';
import 'prismjs/components/prism-python.js';
import { copyToClipboard } from '@/utils/clipboard';

const props = defineProps({ code: { type: String, default: '' } });
const copied = ref(false), copyError = ref(false);
let timer;
// Render Prism tokens as Vue text, never as HTML supplied by an execution.
const lines = computed(() => {
  const output = [[]];
  function append(value, types = []) {
    if (Array.isArray(value)) return value.forEach(item => append(item, types));
    if (typeof value !== 'string') return append(value.content, [...types, value.type, ...[].concat(value.alias || [])]);
    value.split('\n').forEach((text, i) => {
      if (i) output.push([]);
      if (text) output.at(-1).push({ text, types });
    });
  }
  append(Prism.tokenize(props.code.replace(/\r\n?/g, '\n'), Prism.languages.python));
  return output;
});
watch(() => props.code, () => { copied.value = false; copyError.value = false; clearTimeout(timer); });
onBeforeUnmount(() => clearTimeout(timer));
async function copy() {
  clearTimeout(timer);
  copied.value = await copyToClipboard(props.code);
  copyError.value = !copied.value;
  if (copied.value) timer = setTimeout(() => { copied.value = false; }, 2000);
}
</script>

<style scoped>
.python-code{overflow:hidden;border-radius:0 0 12px 12px;background:#132033;color:#e2e8f0;}
.code-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 18px;background:#1b2b42;border-bottom:1px solid #2c3c53;font:12px var(--font-mono);color:#d0dbea;}
.code-toolbar>span:first-child{display:flex;align-items:center;gap:9px;}.language-dot{width:7px;height:7px;border-radius:50%;background:#7dd3fc;}.line-count{color:#a8b8cb;margin-left:8px;}
button{font:inherit;color:#e2e8f0;border:1px solid #506077;border-radius:6px;padding:6px 10px;background:transparent;cursor:pointer;}button:hover{background:#2c3c53;}button:focus-visible,pre:focus-visible{outline:2px solid #7dd3fc;outline-offset:-2px;}
pre{margin:0;padding:16px 0;max-height:480px;overflow:auto;tab-size:4;font:12px/1.8 var(--font-mono);white-space:pre;}code{display:block;min-width:max-content;font:inherit;}.code-line{display:flex;min-height:1.8em;}.code-line:hover{background:#ffffff06;}.line-number{position:sticky;left:0;flex:0 0 4.5em;padding:0 16px;text-align:right;user-select:none;color:#91a3ba;background:#132033;border-right:1px solid #2c3c53;}.line-content{padding:0 20px;}.comment{color:#9cabbf;font-style:italic;}.keyword,.boolean{color:#c4b5fd;}.string,.triple-quoted-string{color:#a7e3bb;}.number{color:#f6c785;}.function,.class-name{color:#7dd3fc;}.builtin,.decorator{color:#f3d68e;}.operator{color:#a5dce8;}.punctuation{color:#becadb;}
p{margin:0;padding:10px 18px;color:#fecaca;font-size:12px;}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;}
@media(max-width:600px){.code-toolbar{padding:10px 12px;}pre{font-size:11px;}.line-number{flex-basis:3.5em;padding:0 10px;}.line-content{padding:0 12px;}}
</style>
