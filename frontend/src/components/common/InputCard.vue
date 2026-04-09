<template>
  <div class="input-card" :class="{ 'wide': wide }">
    <div class="card-header">
      <div class="card-icon">
        <slot name="icon">
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
          </svg>
        </slot>
      </div>
      <h3 class="card-title">{{ title }}</h3>
    </div>
    <p class="card-hint" v-if="hint">
      <svg class="hint-icon" viewBox="0 0 24 24" width="14" height="14">
        <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
      </svg>
      {{ hint }}
    </p>
    <div class="card-content">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  },
  hint: {
    type: String,
    default: ''
  },
  wide: {
    type: Boolean,
    default: false
  }
})
</script>

<style lang="scss" scoped>
.input-card {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
  position: relative;
  overflow: hidden;
  transition: all var(--transition-normal);
  
  // Gradient overlay
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.3) 0%, transparent 60%);
    pointer-events: none;
    opacity: 0;
    transition: opacity var(--transition-normal);
  }
  
  // Animated border on hover
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 2px;
    background: linear-gradient(135deg, var(--color-primary), var(--color-accent-1), var(--color-accent-2));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity: 0;
    transition: opacity var(--transition-normal);
  }
  
  &:hover {
    transform: translateY(-6px);
    box-shadow: var(--shadow-xl), 0 0 40px rgba(37, 99, 235, 0.1);
    
    &::before {
      opacity: 1;
    }
    
    &::after {
      opacity: 0.5;
    }
  }
  
  &:focus-within {
    box-shadow: var(--shadow-xl), 0 0 0 3px rgba(37, 99, 235, 0.1);
    
    &::after {
      opacity: 0.7;
    }
  }
  
  &.wide {
    grid-column: 1 / -1;
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.card-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--color-primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.card-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  background: var(--color-primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-background-alt);
  border-radius: var(--radius-md);
  
  .hint-icon {
    flex-shrink: 0;
    color: var(--color-primary);
  }
}

.card-content {
  position: relative;
  z-index: 1;
}

@media (max-width: 768px) {
  .input-card {
    padding: var(--spacing-lg);
  }
}
</style>
