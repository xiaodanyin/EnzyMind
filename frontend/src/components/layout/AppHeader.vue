<template>
  <header @keydown.esc="closeMobileMenu" class="app-header" :class="{ 'scrolled': isScrolled, 'transparent': isHomePage && !isScrolled }">
    <div class="header-container container">
      <router-link to="/" class="logo">
        <div class="logo-glow"></div>
        <img src="@/assets/enzymind_logo_icon_v3.png" alt="EnzyMind" class="logo-icon" />
        <span class="logo-text">EnzyMind</span>
      </router-link>

      <button class="mobile-menu-btn" @click="toggleMobileMenu" :aria-expanded="mobileMenuOpen" aria-controls="main-navigation" aria-label="Toggle menu">
        <span class="hamburger" :class="{ 'active': mobileMenuOpen }"></span>
      </button>

      <nav id="main-navigation" aria-label="Main navigation" class="nav-menu" :class="{ 'open': mobileMenuOpen }">
        <router-link to="/" class="nav-link" @click="closeMobileMenu">
          Home
        </router-link>
        
        <router-link to="/agent" class="nav-link" @click="closeMobileMenu">
          Workspace
        </router-link>
        <router-link to="/results" class="nav-link" @click="closeMobileMenu">Results</router-link>
        
        <div class="nav-dropdown" :class="{ 'is-open': openDropdown === 'prediction' }" @focusout="closeDropdownOnExit">
          <button class="nav-link dropdown-trigger" @click="openDropdown = openDropdown === 'prediction' ? '' : 'prediction'" :aria-expanded="openDropdown === 'prediction'" aria-controls="prediction-menu">
            Prediction
            <svg class="dropdown-arrow" viewBox="0 0 24 24" width="16" height="16">
              <path fill="currentColor" d="M7 10l5 5 5-5z"/>
            </svg>
          </button>
          <div id="prediction-menu" class="dropdown-menu">
            <router-link to="/predict/enzyme" @click="closeMobileMenu">
              <span class="menu-icon">🔍</span>
              Enzyme Recognition
            </router-link>
            <router-link to="/predict/ec" @click="closeMobileMenu">
              <span class="menu-icon">🏷️</span>
              EC Number Prediction
            </router-link>
            <router-link to="/predict/recommendation" @click="closeMobileMenu">
              <span class="menu-icon">💡</span>
              Enzyme Recommendation
            </router-link>
            <router-link to="/predict/substrate" @click="closeMobileMenu">
              <span class="menu-icon">⚛️</span>
              Substrate Determination
            </router-link>
            <router-link to="/predict/kcat" @click="closeMobileMenu">
              <span class="menu-icon">⚡</span>
              Kcat Prediction
            </router-link>
            <router-link to="/predict/km" @click="closeMobileMenu">
              <span class="menu-icon">🎚️</span>
              Km Prediction
            </router-link>
            <router-link to="/predict/activesite" @click="closeMobileMenu">
              <span class="menu-icon">🎯</span>
              Active Site Annotation
            </router-link>
          </div>
        </div>

        <div class="nav-dropdown" :class="{ 'is-open': openDropdown === 'utility' }" @focusout="closeDropdownOnExit">
          <button class="nav-link dropdown-trigger" @click="openDropdown = openDropdown === 'utility' ? '' : 'utility'" :aria-expanded="openDropdown === 'utility'" aria-controls="utility-menu">
            Utility
            <svg class="dropdown-arrow" viewBox="0 0 24 24" width="16" height="16">
              <path fill="currentColor" d="M7 10l5 5 5-5z"/>
            </svg>
          </button>
          <div id="utility-menu" class="dropdown-menu">
            <router-link to="/utility/enzyme-info" @click="closeMobileMenu">
              <span class="menu-icon">📖</span>
              Enzyme Information
            </router-link>
            <router-link to="/utility/parameters" @click="closeMobileMenu">
              <span class="menu-icon">📊</span>
              Sequence Parameters
            </router-link>
            <router-link to="/utility/structure" @click="closeMobileMenu">
              <span class="menu-icon">🧊</span>
              Structure Prediction
            </router-link>
            <router-link to="/utility/alignment" @click="closeMobileMenu">
              <span class="menu-icon">🔗</span>
              Sequence Alignment
            </router-link>
          </div>
        </div>

        <router-link to="/help" class="nav-link" @click="closeMobileMenu">
          Help
        </router-link>
      </nav>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const openDropdown = ref('')
const closeDropdownOnExit = event => {if (!event.currentTarget.contains(event.relatedTarget)) openDropdown.value = ''}
const mobileMenuOpen = ref(false)
const isScrolled = ref(false)

const isHomePage = computed(() => route.path === '/')

const handleScroll = () => {
  isScrolled.value = window.scrollY > 50
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

const closeMobileMenu = () => {
  openDropdown.value = ''
  mobileMenuOpen.value = false
}
</script>

<style lang="scss" scoped>
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--navbar-height);
  background: var(--color-navbar);
  z-index: 1000;
  transition: all var(--transition-normal);
  
  &.scrolled {
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
  }

  // Transparent home-page header blends into the hero background
  &.transparent {
    background: transparent;
    box-shadow: none;
  }
}

.header-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  position: relative;
  
  .logo-glow {
    position: absolute;
    width: 60px;
    height: 60px;
    background: radial-gradient(circle, rgba(37, 99, 235, 0.4) 0%, transparent 70%);
    border-radius: 50%;
    left: -5px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
    transition: opacity var(--transition-normal);
  }
  
  &:hover .logo-glow {
    opacity: 1;
  }
  
  .logo-icon {
    height: 48px;
    width: auto;
    position: relative;
    z-index: 1;
    transition: transform var(--transition-normal);
  }
  
  &:hover .logo-icon {
    transform: scale(1.05);
  }
  
  &:hover .logo-text {
    background-position: 100% 50%;
  }
  
  .logo-text {
    font-family: "Concert One", sans-serif;
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(
      90deg,
      #60a5fa 0%,
      #a78bfa 25%,
      #f472b6 50%,
      #a78bfa 75%,
      #60a5fa 100%
    );
    background-size: 200% 100%;
    background-position: 0% 50%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    position: relative;
    z-index: 1;
    letter-spacing: 0.03em;
    transition: background-position 0.5s ease;
    animation: gradient-shift 4s ease infinite;
  }
  
  @keyframes gradient-shift {
    0%, 100% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
  }
}

.nav-menu {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.nav-link {
  font-family: "Concert One", sans-serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  background: none;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  
  .nav-icon {
    font-size: 1rem;
    opacity: 0.8;
    transition: transform var(--transition-fast);
  }
  
  &:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
    
    .nav-icon {
      transform: scale(1.1);
    }
  }
  
  &.router-link-active {
    color: #fff;
    background: rgba(37, 99, 235, 0.3);
  }
}

.nav-dropdown {
  position: relative;
  
  .dropdown-trigger {
    padding: 8px 12px;
  }
  
  .dropdown-arrow {
    transition: transform var(--transition-fast);
    opacity: 0.7;
  }
  
  .dropdown-menu {
    position: absolute;
    top: calc(100% + 12px);
    left: 50%;
    transform: translateX(-50%) translateY(10px);
    min-width: 260px;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: var(--radius-xl);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15), 0 8px 25px rgba(0, 0, 0, 0.1);
    padding: var(--spacing-md);
    opacity: 0;
    visibility: hidden;
    transition: all var(--transition-fast);
    
    // Small triangle at the top
    &::before {
      content: '';
      position: absolute;
      top: -8px;
      left: 50%;
      transform: translateX(-50%);
      border: 8px solid transparent;
      border-bottom-color: rgba(255, 255, 255, 0.98);
      border-top: none;
    }
    
    a {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      padding: 14px 18px;
      color: var(--color-text);
      font-family: "Concert One", sans-serif;
      font-size: 1rem;
      font-weight: 700;
      border-radius: var(--radius-lg);
      transition: all var(--transition-fast);
      white-space: nowrap;
      margin-bottom: 4px;
      
      &:last-child {
        margin-bottom: 0;
      }
      
      .menu-icon {
        font-size: 1.25rem;
        flex-shrink: 0;
        transition: transform var(--transition-fast);
      }
      
      &:hover {
        background: linear-gradient(135deg, var(--color-primary-light) 0%, rgba(37, 99, 235, 0.08) 100%);
        color: var(--color-primary);
        transform: translateX(4px);
        
        .menu-icon {
          transform: scale(1.15);
        }
      }
      
      &.router-link-active {
        background: var(--color-primary-light);
        color: var(--color-primary);
        font-weight: 600;
      }
    }
  }
  
  &.is-open {
    .dropdown-menu {
      opacity: 1;
      visibility: visible;
      transform: translateX(-50%) translateY(0);
    }
    
    .dropdown-arrow {
      transform: rotate(180deg);
    }
  }
}

.mobile-menu-btn {
  display: none;
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
  
  .hamburger {
    display: block;
    width: 24px;
    height: 2px;
    background: #fff;
    position: relative;
    transition: background var(--transition-fast);
    border-radius: 2px;
    
    &::before,
    &::after {
      content: '';
      position: absolute;
      left: 0;
      width: 100%;
      height: 2px;
      background: #fff;
      border-radius: 2px;
      transition: transform var(--transition-normal);
    }
    
    &::before {
      top: -8px;
    }
    
    &::after {
      bottom: -8px;
    }
    
    &.active {
      background: transparent;
      
      &::before {
        transform: rotate(45deg) translate(5px, 6px);
      }
      
      &::after {
        transform: rotate(-45deg) translate(5px, -6px);
      }
    }
  }
}

@media (max-width: 1024px) {
  .mobile-menu-btn {
    display: block;
  }
  
  .nav-menu {
    position: fixed;
    top: var(--navbar-height);
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    flex-direction: column;
    align-items: stretch;
    padding: var(--spacing-xl);
    gap: var(--spacing-sm);
    transform: translateX(100%);
    transition: transform var(--transition-normal);
    overflow-y: auto;
    
    &.open {
      transform: translateX(0);
    }
  }
  
  .nav-link {
    width: 100%;
    padding: 14px 16px;
    font-size: 1.1rem;
    justify-content: flex-start;
  }
  
  .nav-dropdown {
    width: 100%;
    
    .dropdown-trigger {
      width: 100%;
      justify-content: flex-start;
    }
    
    .dropdown-arrow {
      margin-left: auto;
    }
    
    .dropdown-menu {
      position: static;
      opacity: 1;
      visibility: visible;
      transform: none !important;
      left: 0;
      right: 0;
      box-shadow: none;
      background: rgba(255, 255, 255, 0.05);
      border: none;
      border-radius: var(--radius-lg);
      margin-top: var(--spacing-xs);
      padding: var(--spacing-xs);
      min-width: 100%;
      
      // Hide the small triangle
      &::before {
        display: none;
      }
      
      a {
        color: rgba(255, 255, 255, 0.9);
        padding: 12px 16px;
        transform: none !important;
        
        &:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
          transform: none !important;
        }
        
        .menu-icon {
          transform: none !important;
        }
      }
    }
  }
}
</style>
