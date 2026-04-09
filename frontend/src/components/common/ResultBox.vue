<template>
  <Transition name="result-slide">
    <div class="result-box" :class="[status, { 'show': show }]" v-show="show">
      <div class="result-glow"></div>
      <div class="result-header">
        <div class="status-badge" :class="status">
          <span class="status-icon">{{ statusIcon }}</span>
        </div>
        <h3 class="result-title">{{ title }}</h3>
      </div>
      <div class="result-content">
        <slot></slot>
      </div>
      <div class="result-actions" v-if="showCopy">
        <button 
          class="copy-btn" 
          :class="{ 'copied': isCopied }"
          @click="copyResult"
        >
          <Transition name="icon-swap" mode="out-in">
            <svg v-if="!isCopied" key="copy" viewBox="0 0 24 24" width="18" height="18">
              <path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
            <svg v-else key="check" viewBox="0 0 24 24" width="18" height="18">
              <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          </Transition>
          <span class="btn-text">{{ isCopied ? 'Copied!' : 'Copy Result' }}</span>
          <span class="ripple-container">
            <span class="ripple" v-for="ripple in ripples" :key="ripple.id" :style="ripple.style"></span>
          </span>
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: 'Result'
  },
  status: {
    type: String,
    default: 'info',
    validator: (value) => ['success', 'error', 'warning', 'info', 'loading'].includes(value)
  },
  showCopy: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['copy'])

const isCopied = ref(false)
const ripples = ref([])
let rippleId = 0

const statusIcon = computed(() => {
  const icons = {
    success: '✓',
    error: '✕',
    warning: '!',
    info: 'i',
    loading: '◌'
  }
  return icons[props.status] || icons.info
})

const createRipple = (event) => {
  const button = event.currentTarget
  const rect = button.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height)
  const x = event.clientX - rect.left - size / 2
  const y = event.clientY - rect.top - size / 2
  
  const ripple = {
    id: rippleId++,
    style: {
      width: `${size}px`,
      height: `${size}px`,
      left: `${x}px`,
      top: `${y}px`
    }
  }
  
  ripples.value.push(ripple)
  
  setTimeout(() => {
    ripples.value = ripples.value.filter(r => r.id !== ripple.id)
  }, 600)
}

const copyResult = (event) => {
  createRipple(event)
  emit('copy')
  isCopied.value = true
  
  setTimeout(() => {
    isCopied.value = false
  }, 2000)
}
</script>

<style lang="scss" scoped>
.result-box {
  margin-top: var(--spacing-xl);
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--spacing-xl);
  position: relative;
  overflow: hidden;
  border: 1px solid var(--glass-border);
  
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%);
    pointer-events: none;
  }
  
  // Status border indicator
  &::after {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    border-radius: 4px 0 0 4px;
    transition: all var(--transition-normal);
  }
  
  &.success::after {
    background: linear-gradient(180deg, #059669, #10b981);
    box-shadow: 0 0 20px rgba(5, 150, 105, 0.4);
  }
  
  &.error::after {
    background: linear-gradient(180deg, #dc2626, #ef4444);
    box-shadow: 0 0 20px rgba(220, 38, 38, 0.4);
  }
  
  &.warning::after {
    background: linear-gradient(180deg, #d97706, #f59e0b);
    box-shadow: 0 0 20px rgba(217, 119, 6, 0.4);
  }
  
  &.info::after {
    background: linear-gradient(180deg, #2563eb, #3b82f6);
    box-shadow: 0 0 20px rgba(37, 99, 235, 0.4);
  }
  
  &.loading::after {
    background: linear-gradient(180deg, #64748b, #94a3b8);
    animation: pulse 1.5s infinite;
  }
}

// Ambient glow effect
.result-glow {
  position: absolute;
  top: -50%;
  right: -50%;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.08) 0%, transparent 70%);
  pointer-events: none;
  
  .success & {
    background: radial-gradient(circle, rgba(5, 150, 105, 0.08) 0%, transparent 70%);
  }
  
  .error & {
    background: radial-gradient(circle, rgba(220, 38, 38, 0.08) 0%, transparent 70%);
  }
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
}

.status-badge {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.1rem;
  color: white;
  flex-shrink: 0;
  
  &.success {
    background: linear-gradient(135deg, #059669, #10b981);
    box-shadow: 0 4px 15px rgba(5, 150, 105, 0.4);
  }
  
  &.error {
    background: linear-gradient(135deg, #dc2626, #ef4444);
    box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4);
  }
  
  &.warning {
    background: linear-gradient(135deg, #d97706, #f59e0b);
    box-shadow: 0 4px 15px rgba(217, 119, 6, 0.4);
  }
  
  &.info {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
  }
  
  &.loading {
    background: linear-gradient(135deg, #64748b, #94a3b8);
    animation: pulse 1.5s infinite;
  }
}

.status-icon {
  animation: scaleIn 0.3s ease-out;
}

@keyframes scaleIn {
  from {
    transform: scale(0);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.result-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.result-content {
  font-size: 1.05rem;
  line-height: 1.7;
  color: var(--color-text);
  position: relative;
  z-index: 1;
}

.result-actions {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-border-light);
}

// ✨ Enhanced Copy Button with Ripple Effect
.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: var(--color-surface);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all var(--transition-normal);
  
  svg {
    transition: all var(--transition-fast);
  }
  
  &:hover {
    background: var(--color-primary-light);
    border-color: var(--color-primary);
    color: var(--color-primary);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    
    svg {
      transform: scale(1.1);
    }
  }
  
  &:active {
    transform: translateY(0);
  }
  
  // Copied state
  &.copied {
    background: linear-gradient(135deg, #059669, #10b981);
    border-color: transparent;
    color: white;
    box-shadow: var(--shadow-success);
    
    &:hover {
      background: linear-gradient(135deg, #047857, #059669);
    }
  }
}

// Ripple Container
.ripple-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  border-radius: inherit;
}

.ripple {
  position: absolute;
  border-radius: 50%;
  background: rgba(37, 99, 235, 0.3);
  transform: scale(0);
  animation: ripple-effect 0.6s ease-out forwards;
  
  .copied & {
    background: rgba(255, 255, 255, 0.4);
  }
}

@keyframes ripple-effect {
  to {
    transform: scale(2.5);
    opacity: 0;
  }
}

// Icon swap transition
.icon-swap-enter-active,
.icon-swap-leave-active {
  transition: all 0.2s ease;
}

.icon-swap-enter-from {
  opacity: 0;
  transform: scale(0.5) rotate(-90deg);
}

.icon-swap-leave-to {
  opacity: 0;
  transform: scale(0.5) rotate(90deg);
}

// Result slide transition
.result-slide-enter-active {
  animation: slideUp 0.5s ease-out;
}

.result-slide-leave-active {
  animation: slideUp 0.3s ease-in reverse;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@media (max-width: 768px) {
  .result-box {
    padding: var(--spacing-lg);
  }
  
  .copy-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
