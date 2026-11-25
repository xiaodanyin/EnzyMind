<template>
  <div class="page-container container">
    <div class="page-header">
      <div class="header-decoration">
        <div class="deco-line"></div>
        <div class="deco-dot"></div>
        <div class="deco-line"></div>
      </div>
      <h1 class="page-title">{{ title }}</h1>
      <p class="page-description" v-if="description">{{ description }}</p>
      <GuideButton class="page-guide-inline" />
    </div>
    <slot name="overview"></slot>
    <div class="page-content" :class="{ 'allow-overflow': allowOverflow }">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import GuideButton from '@/components/common/GuideButton.vue';
defineProps({
  title: {
    type: String,
    required: true
  },
  description: {
    type: String,
    default: ''
  },
  allowOverflow: {
    type: Boolean,
    default: false
  }
})
</script>

<style lang="scss" scoped>
.page-guide-inline { margin-top: 14px; }
.page-container {
  padding-block: var(--spacing-xl);
  animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.page-header {
  text-align: center;
  margin-bottom: var(--spacing-2xl);
}

.header-decoration {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.deco-line {
  width: 60px;
  height: 3px;
  background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  border-radius: 2px;
}

.deco-dot {
  width: 10px;
  height: 10px;
  background: var(--color-primary-gradient);
  border-radius: 50%;
  box-shadow: 0 0 15px rgba(37, 99, 235, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 15px rgba(37, 99, 235, 0.5);
  }
  50% {
    transform: scale(1.2);
    box-shadow: 0 0 25px rgba(37, 99, 235, 0.7);
  }
}

.page-title {
  font-size: 2.75rem;
  font-weight: 800;
  margin-bottom: var(--spacing-md);
  letter-spacing: -0.03em;
  background: var(--color-primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-description {
  font-size: 1.15rem;
  color: var(--color-text-secondary);
  max-width: 700px;
  margin: 0 auto;
  line-height: 1.8;
}

.page-content {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-xl);
  padding: var(--spacing-2xl);
  position: relative;
  overflow: hidden;
  
  // Subtle gradient overlay
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 50%);
    pointer-events: none;
  }
  
  // Decorative corner accent
  &::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 200px;
    height: 200px;
    background: radial-gradient(circle at top right, rgba(37, 99, 235, 0.08) 0%, transparent 70%);
    pointer-events: none;
  }
}

.page-content.allow-overflow {
  overflow: visible;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

@media (max-width: 768px) {
  .page-container {
    padding-block: var(--spacing-lg);
  }
  
  .page-title {
    font-size: 2rem;
  }
  
  .page-content {
    padding: var(--spacing-lg);
    border-radius: var(--radius-xl);
  }
  
  .deco-line {
    width: 40px;
  }
}
</style>
