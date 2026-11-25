<template>
  <Teleport to="body">
    <dialog ref="dialog" class="deepseek-dialog" aria-labelledby="deepseek-title" @close="$emit('close')" @click="backdrop">
      <form @submit.prevent="submit">
        <header><span class="eyebrow">CONTINUE YOUR RESEARCH</span><button type="button" aria-label="Close API key dialog" @click="dialog.close()">×</button></header>
        <h2 id="deepseek-title">Continue with your DeepSeek key</h2>
        <p>EnzyMind includes {{ limit }} free conversation turns per workspace each day. Further turns can use your own DeepSeek account.</p>
        <ol>
          <li><a href="https://platform.deepseek.com/" target="_blank" rel="noopener noreferrer">Sign in to DeepSeek ↗</a></li>
          <li><a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer">Create an API key ↗</a> and check your API balance.</li>
        </ol>
        <label for="deepseek-api-key">DeepSeek API key</label>
        <input id="deepseek-api-key" ref="input" v-model="key" type="password" autocomplete="off" autocapitalize="off" :spellcheck="false" maxlength="256" placeholder="sk-…" aria-describedby="deepseek-privacy" required />
        <p id="deepseek-privacy" class="key-privacy">Your key is kept only in page memory and active requests. Refreshing or leaving clears it from this page; an active turn may finish. It is not saved in browser storage, our database or n8n. Conversation context is sent to DeepSeek, which bills your account.</p>
        <p v-if="error" class="key-error" role="alert">{{ error }}</p>
        <footer><button type="button" @click="dialog.close()">Cancel</button><button type="submit" class="key-submit">Use this key</button></footer>
      </form>
    </dialog>
  </Teleport>
</template>
<script setup>
import {ref,onMounted,onBeforeUnmount} from 'vue';
defineProps({limit:{type:Number,default:10}});
const emit=defineEmits(['close','use-key']);
const dialog=ref(null),input=ref(null),key=ref(''),error=ref('');
function submit(){const value=key.value.trim();if(!/^[A-Za-z0-9_-]{20,256}$/.test(value)){error.value='Enter a valid DeepSeek API key.';return;}emit('use-key',value);key.value='';}
function backdrop(event){if(event.target!==dialog.value)return;const r=dialog.value.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.value.close();}
onMounted(()=>{dialog.value.showModal();input.value.focus();});
onBeforeUnmount(()=>{key.value='';dialog.value?.close();});
</script>
<style scoped>
.deepseek-dialog{width:min(520px,calc(100vw - 32px));max-height:calc(100dvh - 40px);overflow:auto;margin:auto;padding:28px;border:1px solid var(--color-border);border-radius:var(--radius-xl,20px);background:var(--color-background,#fff);color:var(--color-text,#172039);box-shadow:var(--shadow-xl);font-family:var(--font-family);}
.deepseek-dialog::backdrop{background:rgba(12,23,48,.55);backdrop-filter:blur(5px);}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;}header button{border:0;background:none;font-size:26px;color:inherit;cursor:pointer;}.eyebrow{font-size:10px;font-weight:700;letter-spacing:.13em;color:var(--color-primary);}
h2{font-size:24px;line-height:1.25;margin:18px 0 12px;}p,li{font-size:13px;line-height:1.7;color:var(--color-text-secondary);}ol{padding-left:20px;margin:16px 0 22px;}a{color:var(--color-primary);}label{display:block;font-weight:600;font-size:12px;margin-bottom:8px;}input{box-sizing:border-box;width:100%;padding:12px 14px;border:1px solid var(--color-border);border-radius:10px;background:var(--color-background-alt);color:inherit;font:inherit;}input:focus{outline:2px solid var(--color-primary);outline-offset:2px;}.key-privacy{font-size:11px;margin-top:14px;}.key-error{color:var(--color-danger,#b42318);}footer{display:flex;justify-content:flex-end;gap:10px;margin-top:24px;}footer button{padding:10px 16px;border-radius:9px;border:1px solid var(--color-border);background:transparent;color:inherit;cursor:pointer;font:inherit;font-size:12px;}.key-submit{background:var(--color-primary)!important;color:white!important;border-color:transparent!important;}
</style>
