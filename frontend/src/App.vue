<template>
  <div id="app-container" :class="{ 'maintenance-visible': maintenanceVisible }">
    <aside
      v-if="maintenanceVisible"
      class="maintenance-ticker"
      :class="{ 'is-paused': maintenancePaused }"
      aria-label="Enzyme Recommendation maintenance notice"
    >
      <span class="maintenance-label">SERVICE NOTICE</span>
      <div class="maintenance-viewport" tabindex="0" aria-label="Focus to pause the announcement">
        <div class="maintenance-track">
          <span v-for="copy in 2" :key="copy" class="maintenance-message" :aria-hidden="copy === 2 ? 'true' : undefined">
            <strong>Enzyme Recommendation</strong> will be unavailable on
            <time datetime="2026-09-13">September 13, 2026</time> due to data center maintenance.
            Service resumes on <time datetime="2026-09-14">September 14, 2026</time>.
          </span>
        </div>
      </div>
      <button
        class="maintenance-toggle"
        type="button"
        :aria-label="maintenancePaused ? 'Resume announcement scrolling' : 'Pause announcement scrolling'"
        :title="maintenancePaused ? 'Resume scrolling' : 'Pause scrolling'"
        :aria-pressed="maintenancePaused"
        @click="maintenancePaused = !maintenancePaused"
      >
        <span aria-hidden="true">{{ maintenancePaused ? '▶' : 'Ⅱ' }}</span>
      </button>
    </aside>
    <AppHeader />
    <main class="main-content" :class="{ 'no-padding': isHomePage }">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <AppFooter v-if="!isHomePage" />
    <PageGuide />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import PageGuide from '@/components/common/PageGuide.vue'

// Temporary remote-only announcement; expires at midnight on September 14 (China time).
const maintenanceEndsAt = Date.parse('2026-09-14T00:00:00+08:00')
const maintenanceVisible = ref(Date.now() < maintenanceEndsAt)
const maintenancePaused = ref(false)
let maintenanceTimer

onMounted(() => {
  if (maintenanceVisible.value) {
    maintenanceTimer = window.setTimeout(() => {
      maintenanceVisible.value = false
    }, Math.max(0, maintenanceEndsAt - Date.now()))
  }
})

onUnmounted(() => window.clearTimeout(maintenanceTimer))

const route = useRoute()
const isHomePage = computed(() => route.path === '/')
</script>

<style lang="scss">
#app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  padding-top: var(--navbar-height, 72px);
  
  &.no-padding {
    padding-top: 0;
  }
}

// Page transition
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// Temporary global notice: reserve space above the fixed navigation.
#app-container.maintenance-visible {
  --maintenance-height: 36px;

  > .app-header {
    top: var(--maintenance-height);
  }

  > .main-content {
    padding-top: calc(var(--navbar-height, 72px) + var(--maintenance-height));

    &.no-padding {
      padding-top: var(--maintenance-height);
    }
  }
}

.maintenance-ticker {
  position: fixed;
  inset: 0 0 auto;
  z-index: 1100;
  display: flex;
  align-items: center;
  height: var(--maintenance-height);
  overflow: hidden;
  background: var(--color-warning-light, #fffbeb);
  color: #78350f;
  border-bottom: 1px solid #fcd34d;
  font-size: 0.85rem;
  line-height: 1.4;

  &:hover .maintenance-track,
  &:focus-within .maintenance-track,
  &.is-paused .maintenance-track {
    animation-play-state: paused;
  }
}

.maintenance-label {
  flex-shrink: 0;
  padding: 0 14px;
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  border-right: 1px solid #fcd34d;
}

.maintenance-viewport {
  flex: 1;
  min-width: 0;
  overflow: hidden;

  &:focus-visible {
    outline: 2px solid #b45309;
    outline-offset: -2px;
  }
}

.maintenance-track {
  display: flex;
  width: max-content;
  animation: maintenance-scroll 38s linear infinite;
}

.maintenance-message {
  flex-shrink: 0;
  padding: 0 36px 0 14px;
  white-space: nowrap;

  strong, time {
    font-weight: 700;
  }
}

.maintenance-toggle {
  align-self: stretch;
  flex-shrink: 0;
  width: 40px;
  border: 0;
  border-left: 1px solid #fcd34d;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 700;
  cursor: pointer;

  &:hover, &:focus-visible {
    background: #fef3c7;
  }

  &:focus-visible {
    outline: 2px solid #b45309;
    outline-offset: -3px;
  }
}

@keyframes maintenance-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

@media (max-width: 1024px) {
  #app-container.maintenance-visible .app-header .nav-menu {
    position: absolute;
    top: 100%;
    bottom: auto;
    height: calc(100vh - var(--navbar-height) - var(--maintenance-height));
    height: calc(100dvh - var(--navbar-height) - var(--maintenance-height));
  }
}

@media (max-width: 480px) {
  .maintenance-label {
    padding: 0 8px;
    font-size: 0.6rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .maintenance-track {
    animation: none;
  }

  .maintenance-viewport {
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .maintenance-message[aria-hidden='true'] {
    display: none;
  }
}
</style>
