<template>
  <span v-if="state.dated" class="expiry-badge" :class="{ urgent: state.urgent }" :title="`Automatic deletion: ${expiryDate(expiresAt)}`">
    {{ state.expired ? 'Due for deletion' : state.urgent ? `Deletes in ${state.days} ${state.days === 1 ? 'day' : 'days'}` : 'Deletes' }} · <time :datetime="new Date(expiresAt * 1000).toISOString()">{{ expiryDate(expiresAt, true) }}</time>
  </span>
</template>
<script setup>
import { computed } from 'vue';
import { useRetentionClock, expiryState, expiryDate } from '@/utils/retention';
const props=defineProps({expiresAt:{type:Number,default:null}}), now=useRetentionClock();
const state=computed(()=>expiryState(props.expiresAt,now.value));
</script>
<style scoped>
.expiry-badge{display:inline-block;font-size:11px;line-height:1.6;color:var(--color-text-secondary);font-weight:400;letter-spacing:normal;text-transform:none;overflow-wrap:anywhere;}.urgent{color:#805313;background:#fff1d3;border-radius:4px;padding:2px 6px;}
</style>
