<template>
  <Transition name="overlay-fade">
    <div class="loading-overlay" v-if="show">
      <div class="loading-backdrop"></div>
      <div class="loading-content">
        <div class="dna-loader">
          <div class="helix">
            <div class="strand strand-1">
              <span v-for="i in 8" :key="'a'+i" class="nucleotide" :style="{ animationDelay: `${i * 0.1}s` }"></span>
            </div>
            <div class="strand strand-2">
              <span v-for="i in 8" :key="'b'+i" class="nucleotide" :style="{ animationDelay: `${i * 0.1 + 0.5}s` }"></span>
            </div>
          </div>
        </div>
        <p class="loading-text">{{ text }}</p>
        <p class="loading-hint" v-if="hint">{{ hint }}</p>
        <div class="progress-bar">
          <div class="progress-fill"></div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  show: {
    type: Boolean,
    default: false
  },
  text: {
    type: String,
    default: 'Processing...'
  },
  hint: {
    type: String,
    default: ''
  }
})
</script>

<style lang="scss" scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.loading-content {
  position: relative;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-2xl);
  padding: var(--spacing-2xl) var(--spacing-3xl);
  text-align: center;
  box-shadow: var(--shadow-2xl);
  min-width: 320px;
  animation: scaleIn 0.3s ease-out;
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

// 🧬 DNA Double Helix Loader
.dna-loader {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--spacing-xl);
  position: relative;
}

.helix {
  width: 100%;
  height: 100%;
  position: relative;
  animation: rotate 3s linear infinite;
}

@keyframes rotate {
  to { transform: rotateY(360deg); }
}

.strand {
  position: absolute;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
}

.strand-2 {
  transform: rotateY(180deg);
}

.nucleotide {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  animation: nucleotide-pulse 1.6s ease-in-out infinite;
  
  .strand-1 & {
    background: linear-gradient(135deg, #2563eb, #3b82f6);
    box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
  }
  
  .strand-2 & {
    background: linear-gradient(135deg, #8b5cf6, #a78bfa);
    box-shadow: 0 0 10px rgba(139, 92, 246, 0.5);
  }
}

@keyframes nucleotide-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(0.6);
    opacity: 0.5;
  }
}

.loading-text {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  background: var(--color-primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.loading-hint {
  font-size: 0.9rem;
  color: var(--color-text-muted);
  margin: var(--spacing-sm) 0 0;
}

// Progress bar animation
.progress-bar {
  margin-top: var(--spacing-lg);
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary-gradient);
  border-radius: 2px;
  animation: progress 2s ease-in-out infinite;
}

@keyframes progress {
  0% {
    width: 0%;
    margin-left: 0%;
  }
  50% {
    width: 60%;
    margin-left: 20%;
  }
  100% {
    width: 0%;
    margin-left: 100%;
  }
}

// Transition
.overlay-fade-enter-active {
  transition: opacity 0.3s ease;
  
  .loading-content {
    animation: scaleIn 0.3s ease-out;
  }
}

.overlay-fade-leave-active {
  transition: opacity 0.2s ease;
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}
</style>
