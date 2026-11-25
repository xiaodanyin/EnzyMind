<template>
  <footer class="app-footer">
    <div class="footer-gradient"></div>
    <div class="footer-container container">
      <div class="footer-content">
        <div class="footer-brand">
          <span class="brand-icon">🧬</span>
          <span class="brand-text">EnzyMind</span>
        </div>
        <p class="footer-copyright">© {{ currentYear }} EnzyMind. All rights reserved.</p>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'

const currentYear = computed(() => new Date().getFullYear())
</script>

<style lang="scss" scoped>
.app-footer {
  position: relative;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #fff;
  padding: var(--spacing-xl) 0;
  margin-top: auto;
  overflow: hidden;
}

.footer-gradient {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, 
    transparent, 
    rgba(59, 130, 246, 0.5), 
    rgba(139, 92, 246, 0.5), 
    transparent
  );
}

.footer-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  text-align: center;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  
  .brand-icon {
    font-size: 1.5rem;
  }
  
  .brand-text {
    font-size: 1.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.footer-copyright {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 400;
}

@media (max-width: 768px) {
  .footer-content {
    text-align: center;
  }
}
</style>
