<template>
  <div class="home-page">
    <!-- Hero Section with Particles -->
    <div class="hero">
      <!-- Background Image -->
      <div class="hero-background">
        <img :src="heroImage" alt="EnzyMind Hero" class="hero-bg-image" />
      </div>
      <!-- Overlay Effects -->
      <div class="hero-overlay"></div>
      <div class="hero-particles">
        <div class="particle" v-for="i in 20" :key="i" :style="getParticleStyle(i)"></div>
      </div>
      <div class="hero-gradient"></div>
      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-icon">🧬</span>
          <span class="badge-text">AI-Powered Enzyme Informatics</span>
        </div>
        <h1 class="hero-title">
          Welcome to <span class="highlight">EnzyMind</span>
        </h1>
        <p class="hero-slogan">
          Empowering enzyme research with intelligent agents: analyze, predict, and optimize with EnzyMind.
        </p>
        <div class="hero-buttons">
          <router-link to="/predict/enzyme" class="cta-button primary">
            <span>Get Started</span>
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path fill="currentColor" d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z"/>
            </svg>
          </router-link>
          <router-link to="/help" class="cta-button secondary">
            <span>Learn More</span>
          </router-link>
        </div>
        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-number">18+</span>
            <span class="stat-label">AI Models</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-number">7</span>
            <span class="stat-label">Prediction Tools</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-number">4</span>
            <span class="stat-label">Utility Tools</span>
          </div>
        </div>
      </div>
      <div class="scroll-indicator">
        <div class="mouse">
          <div class="wheel"></div>
        </div>
        <span>Scroll to explore</span>
      </div>
    </div>

    <!-- Features Section -->
    <section class="features-section">
      <div class="section-container">
        <div class="section-header">
          <span class="section-badge">Features</span>
          <h2 class="section-title">Platform Capabilities</h2>
          <p class="section-desc">Comprehensive tools for enzyme analysis and prediction</p>
        </div>
        <div class="features-grid">
          <div 
            class="feature-card" 
            v-for="(feature, index) in features" 
            :key="feature.title"
            :style="{ animationDelay: `${index * 0.1}s` }"
          >
            <div class="feature-icon-wrapper">
              <div class="feature-icon">{{ feature.icon }}</div>
              <div class="feature-glow"></div>
            </div>
            <h3 class="feature-title">{{ feature.title }}</h3>
            <p class="feature-desc">{{ feature.description }}</p>
            <div class="feature-link">
              <router-link :to="feature.link">
                Explore →
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Quick Start Section -->
    <section class="quickstart-section">
      <div class="section-container">
        <div class="section-header">
          <span class="section-badge">Quick Access</span>
          <h2 class="section-title">Start Your Analysis</h2>
          <p class="section-desc">Jump directly to any tool</p>
        </div>
        <div class="quickstart-grid">
          <router-link 
            v-for="(item, index) in quickStartItems" 
            :key="item.path" 
            :to="item.path"
            class="quickstart-card"
            :style="{ animationDelay: `${index * 0.05}s` }"
          >
            <span class="quickstart-icon">{{ item.icon }}</span>
            <span class="quickstart-text">{{ item.title }}</span>
            <span class="quickstart-arrow">→</span>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Tech Stack Section -->
    <section class="tech-section">
      <div class="section-container">
        <div class="tech-content">
          <div class="tech-text">
            <span class="section-badge">Technology</span>
            <h2 class="section-title">Powered by Cutting-Edge AI</h2>
            <p class="tech-desc">
              EnzyMind leverages state-of-the-art machine learning models including 
              ESM, ProtTrans, and custom deep learning architectures trained on 
              millions of enzyme sequences and structures.
            </p>
            <div class="tech-tags">
              <span class="tech-tag">ESMFold</span>
              <span class="tech-tag">LangChain</span>
              <span class="tech-tag">FastAPI</span>
              <span class="tech-tag">Vue 3</span>
              <span class="tech-tag">PyTorch</span>
            </div>
          </div>
          <div class="tech-visual">
            <div class="protein-helix">
              <!-- Alpha helix backbone -->
              <div class="helix-backbone">
                <div class="amino-acid" v-for="i in 16" :key="i" :style="{ animationDelay: `${i * 0.12}s` }">
                  <span class="residue"></span>
                  <span class="side-chain" :class="`chain-type-${(i % 4) + 1}`"></span>
                </div>
              </div>
              <!-- Helix ribbon effect -->
              <svg class="helix-ribbon" viewBox="0 0 100 300" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="ribbonGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.8" />
                    <stop offset="50%" style="stop-color:#8b5cf6;stop-opacity:0.9" />
                    <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0.8" />
                  </linearGradient>
                </defs>
                <path class="ribbon-path" d="M50,10 Q80,40 50,70 Q20,100 50,130 Q80,160 50,190 Q20,220 50,250 Q80,280 50,290" 
                      stroke="url(#ribbonGradient)" stroke-width="8" fill="none" stroke-linecap="round"/>
              </svg>
              <!-- Floating particles -->
              <div class="helix-particle" v-for="j in 6" :key="'p'+j" :style="getHelixParticleStyle(j)"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import heroImage from '@/assets/enzyme_ai_dark_v3.png'

const features = [
  {
    icon: '🧪',
    title: 'Enzyme Recognition',
    description: 'Identify whether a protein sequence is an enzyme using advanced ML models.',
    link: '/predict/enzyme'
  },
  {
    icon: '🏷️',
    title: 'EC Number Prediction',
    description: 'Predict enzyme commission numbers for accurate functional classification.',
    link: '/predict/ec'
  },
  {
    icon: '📊',
    title: 'Kinetic Parameters',
    description: 'Predict kcat and Km values for enzyme-substrate pairs with high accuracy.',
    link: '/predict/kcat'
  },
  {
    icon: '🎯',
    title: 'Active Site Prediction',
    description: 'Identify catalytic residues and functional sites in enzyme sequences.',
    link: '/predict/activesite'
  },
  {
    icon: '🔬',
    title: 'Structure Prediction',
    description: 'Generate 3D protein structures using ESMFold technology.',
    link: '/utility/structure'
  },
  {
    icon: '📋',
    title: 'Comprehensive Analysis',
    description: 'Access complete enzyme information from UniProt and other databases.',
    link: '/utility/enzyme-info'
  }
]

const quickStartItems = [
  { icon: '🧪', title: 'Enzyme Recognition', path: '/predict/enzyme' },
  { icon: '🏷️', title: 'EC Prediction', path: '/predict/ec' },
  { icon: '💡', title: 'Enzyme Recommendation', path: '/predict/recommendation' },
  { icon: '🧫', title: 'Substrate Prediction', path: '/predict/substrate' },
  { icon: '📈', title: 'Kcat Prediction', path: '/predict/kcat' },
  { icon: '📉', title: 'Km Prediction', path: '/predict/km' },
  { icon: '🎯', title: 'Active Sites', path: '/predict/activesite' },
  { icon: '📋', title: 'Enzyme Info', path: '/utility/enzyme-info' },
]

const getParticleStyle = (i) => {
  const size = Math.random() * 4 + 2
  return {
    width: `${size}px`,
    height: `${size}px`,
    left: `${Math.random() * 100}%`,
    top: `${Math.random() * 100}%`,
    animationDelay: `${Math.random() * 5}s`,
    animationDuration: `${Math.random() * 10 + 10}s`
  }
}

const getHelixParticleStyle = (i) => {
  return {
    width: `${4 + Math.random() * 4}px`,
    height: `${4 + Math.random() * 4}px`,
    left: `${20 + Math.random() * 60}%`,
    top: `${10 + i * 14}%`,
    animationDelay: `${i * 0.5}s`
  }
}
</script>

<style lang="scss" scoped>
.home-page {
  min-height: 100vh;
  overflow-x: hidden;
}

// ========== Hero Section ==========
.hero {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #fff;
  background: #0a0f1a;
  overflow: hidden;
}

.hero-background {
  position: absolute;
  inset: 0;
  z-index: 0;
  
  .hero-bg-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    opacity: 0.85;
  }
}

.hero-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(
    135deg,
    rgba(15, 23, 42, 0.7) 0%,
    rgba(30, 41, 59, 0.5) 50%,
    rgba(15, 23, 42, 0.7) 100%
  );
  pointer-events: none;
}

.hero-particles {
  position: absolute;
  inset: 0;
  overflow: hidden;
  z-index: 2;
  pointer-events: none;
  
  .particle {
    position: absolute;
    background: rgba(59, 130, 246, 0.5);
    border-radius: 50%;
    animation: float linear infinite;
    
    &:nth-child(odd) {
      background: rgba(139, 92, 246, 0.5);
    }
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateY(-100vh) translateX(50px);
    opacity: 0;
  }
}

.hero-gradient {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  background: 
    radial-gradient(ellipse at 20% 20%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, rgba(16, 185, 129, 0.08) 0%, transparent 60%);
}

.hero-content {
  position: relative;
  z-index: 10;
  max-width: 800px;
  padding: 0 var(--spacing-lg);
  animation: fadeInUp 1s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(40px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  margin-bottom: var(--spacing-xl);
  backdrop-filter: blur(10px);
  
  .badge-icon {
    font-size: 1.2rem;
  }
  
  .badge-text {
    font-size: 0.9rem;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
  }
}

.hero-title {
  font-size: 4rem;
  font-weight: 800;
  margin-bottom: var(--spacing-lg);
  line-height: 1.1;
  letter-spacing: -0.03em;
  
  .highlight {
    background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #34d399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    background-size: 200% auto;
    animation: gradient-shift 4s ease infinite;
  }
}

@keyframes gradient-shift {
  0%, 100% {
    background-position: 0% center;
  }
  50% {
    background-position: 100% center;
  }
}

.hero-slogan {
  font-size: 1.35rem;
  font-weight: 400;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.8);
  margin-bottom: var(--spacing-2xl);
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.hero-buttons {
  display: flex;
  gap: var(--spacing-md);
  justify-content: center;
  margin-bottom: var(--spacing-2xl);
}

.cta-button {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 16px 36px;
  font-size: 1.1rem;
  font-weight: 600;
  border-radius: var(--radius-full);
  text-decoration: none;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
  
  &.primary {
    background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
    color: #fff;
    box-shadow: 0 10px 40px rgba(37, 99, 235, 0.4);
    
    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 15px 50px rgba(37, 99, 235, 0.5);
      
      svg {
        transform: translateX(4px);
      }
    }
  }
  
  &.secondary {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.3);
    backdrop-filter: blur(10px);
    
    &:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-3px);
    }
  }
  
  svg {
    transition: transform var(--transition-fast);
  }
}

.hero-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xl);
  padding: var(--spacing-lg) var(--spacing-2xl);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-2xl);
  backdrop-filter: blur(10px);
}

.stat-item {
  text-align: center;
  
  .stat-number {
    display: block;
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .stat-label {
    font-size: 0.9rem;
    color: rgba(255, 255, 255, 0.6);
  }
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
}

.scroll-indicator {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm);
  color: rgba(255, 255, 255, 0.5);
  font-size: 0.85rem;
  animation: bounce 2s infinite;
  
  .mouse {
    width: 24px;
    height: 38px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-radius: 12px;
    position: relative;
    
    .wheel {
      width: 4px;
      height: 8px;
      background: rgba(255, 255, 255, 0.6);
      border-radius: 2px;
      position: absolute;
      top: 8px;
      left: 50%;
      transform: translateX(-50%);
      animation: scroll 1.5s infinite;
    }
  }
}

@keyframes bounce {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(10px); }
}

@keyframes scroll {
  0% { opacity: 1; transform: translateX(-50%) translateY(0); }
  100% { opacity: 0; transform: translateX(-50%) translateY(12px); }
}

// ========== Section Styles ==========
.section-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--spacing-lg);
}

.section-header {
  text-align: center;
  margin-bottom: var(--spacing-3xl);
}

.section-badge {
  display: inline-block;
  padding: 6px 16px;
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: var(--radius-full);
  margin-bottom: var(--spacing-md);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.section-title {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--color-text);
  margin-bottom: var(--spacing-md);
  letter-spacing: -0.02em;
}

.section-desc {
  font-size: 1.15rem;
  color: var(--color-text-secondary);
  max-width: 600px;
  margin: 0 auto;
}

// ========== Features Section ==========
.features-section {
  padding: var(--spacing-3xl) 0;
  background: var(--color-surface);
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--color-border), transparent);
  }
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--spacing-xl);
}

.feature-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
  text-align: center;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
  animation: fadeInUp 0.6s ease-out backwards;
  
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(37, 99, 235, 0.05) 0%, transparent 50%);
    opacity: 0;
    transition: opacity var(--transition-normal);
  }
  
  &:hover {
    transform: translateY(-8px);
    box-shadow: var(--shadow-xl), 0 0 50px rgba(37, 99, 235, 0.1);
    border-color: rgba(37, 99, 235, 0.3);
    
    &::before {
      opacity: 1;
    }
    
    .feature-icon {
      transform: scale(1.1) rotate(5deg);
    }
    
    .feature-glow {
      opacity: 0.6;
    }
    
    .feature-link a {
      color: var(--color-primary);
    }
  }
}

.feature-icon-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: var(--spacing-lg);
}

.feature-icon {
  font-size: 3.5rem;
  display: block;
  transition: transform var(--transition-normal);
}

.feature-glow {
  position: absolute;
  inset: -20px;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.2) 0%, transparent 70%);
  opacity: 0;
  transition: opacity var(--transition-normal);
  border-radius: 50%;
}

.feature-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--spacing-sm);
}

.feature-desc {
  font-size: 0.95rem;
  color: var(--color-text-secondary);
  line-height: 1.7;
  margin-bottom: var(--spacing-md);
}

.feature-link {
  a {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-text-muted);
    transition: color var(--transition-fast);
  }
}

// ========== Quick Start Section ==========
.quickstart-section {
  padding: var(--spacing-3xl) 0;
  background: linear-gradient(135deg, #f8fafc 0%, #e0f2fe 50%, #f0fdf4 100%);
}

.quickstart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing-md);
}

.quickstart-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  text-decoration: none;
  transition: all var(--transition-normal);
  animation: fadeInUp 0.5s ease-out backwards;
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: var(--color-primary-gradient);
    transform: scaleY(0);
    transition: transform var(--transition-normal);
  }
  
  &:hover {
    transform: translateY(-4px) translateX(4px);
    box-shadow: var(--shadow-lg);
    border-color: var(--color-primary);
    
    &::before {
      transform: scaleY(1);
    }
    
    .quickstart-text {
      color: var(--color-primary);
    }
    
    .quickstart-arrow {
      transform: translateX(4px);
      opacity: 1;
    }
  }
}

.quickstart-icon {
  font-size: 2rem;
  flex-shrink: 0;
}

.quickstart-text {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text);
  transition: color var(--transition-fast);
  flex: 1;
}

.quickstart-arrow {
  font-size: 1.2rem;
  color: var(--color-primary);
  opacity: 0;
  transition: all var(--transition-fast);
}

// ========== Tech Section ==========
.tech-section {
  padding: var(--spacing-3xl) 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #fff;
}

.tech-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-3xl);
  align-items: center;
}

.tech-text {
  .section-badge {
    background: rgba(37, 99, 235, 0.2);
    color: #60a5fa;
  }
  
  .section-title {
    color: #fff;
  }
}

.tech-desc {
  font-size: 1.1rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.8;
  margin-bottom: var(--spacing-xl);
}

.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.tech-tag {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-full);
  font-size: 0.9rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.tech-visual {
  display: flex;
  justify-content: center;
  align-items: center;
}

// ========== Protein Alpha-Helix Animation ==========
.protein-helix {
  width: 200px;
  height: 300px;
  position: relative;
  perspective: 800px;
}

.helix-backbone {
  position: absolute;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  animation: helix-spin 12s linear infinite;
}

@keyframes helix-spin {
  from {
    transform: rotateY(0deg);
  }
  to {
    transform: rotateY(360deg);
  }
}

.amino-acid {
  position: absolute;
  left: 50%;
  display: flex;
  align-items: center;
  transform-style: preserve-3d;
  
  @for $i from 1 through 16 {
    &:nth-child(#{$i}) {
      top: #{($i - 1) * 18}px;
      transform: translateX(-50%) rotateY(#{($i - 1) * 100}deg) translateZ(35px);
    }
  }
}

.residue {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.6),
              inset 0 -2px 4px rgba(0, 0, 0, 0.2);
  animation: residue-pulse 2s ease-in-out infinite;
}

@keyframes residue-pulse {
  0%, 100% {
    transform: scale(1);
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.6);
  }
  50% {
    transform: scale(1.1);
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.8);
  }
}

.side-chain {
  position: absolute;
  left: 14px;
  width: 20px;
  height: 4px;
  border-radius: 2px;
  transform-origin: left center;
  animation: chain-wave 3s ease-in-out infinite;
  
  &.chain-type-1 {
    background: linear-gradient(90deg, #8b5cf6, #a78bfa);
    box-shadow: 0 0 8px rgba(139, 92, 246, 0.5);
  }
  
  &.chain-type-2 {
    background: linear-gradient(90deg, #10b981, #34d399);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
    width: 28px;
  }
  
  &.chain-type-3 {
    background: linear-gradient(90deg, #f59e0b, #fbbf24);
    box-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
    width: 16px;
  }
  
  &.chain-type-4 {
    background: linear-gradient(90deg, #ec4899, #f472b6);
    box-shadow: 0 0 8px rgba(236, 72, 153, 0.5);
    width: 24px;
  }
}

@keyframes chain-wave {
  0%, 100% {
    transform: rotateZ(0deg);
  }
  50% {
    transform: rotateZ(15deg);
  }
}

.helix-ribbon {
  position: absolute;
  width: 100%;
  height: 100%;
  pointer-events: none;
  opacity: 0.4;
}

.ribbon-path {
  stroke-dasharray: 400;
  stroke-dashoffset: 400;
  animation: ribbon-draw 4s ease-in-out infinite;
}

@keyframes ribbon-draw {
  0% {
    stroke-dashoffset: 400;
  }
  50% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: -400;
  }
}

.helix-particle {
  position: absolute;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.8), transparent);
  animation: particle-float 4s ease-in-out infinite;
  pointer-events: none;
}

@keyframes particle-float {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translateY(-20px) scale(1.2);
    opacity: 1;
  }
}

// ========== Responsive ==========
@media (max-width: 1024px) {
  .tech-content {
    grid-template-columns: 1fr;
    text-align: center;
  }
  
  .tech-tags {
    justify-content: center;
  }
  
  .tech-visual {
    order: -1;
  }
}

@media (max-width: 768px) {
  // Hero 区域移动端适配 - 添加顶部 padding 避免导航栏遮挡
  .hero {
    padding-top: var(--navbar-height);
    min-height: 100vh;
    min-height: 100dvh; // 使用动态视口高度，解决移动端浏览器地址栏问题
  }
  
  .hero-content {
    padding: var(--spacing-md);
    padding-top: var(--spacing-lg);
  }
  
  .hero-badge {
    padding: 8px 16px;
    font-size: 0.8rem;
    
    .badge-icon {
      font-size: 1rem;
    }
  }
  
  .hero-title {
    font-size: 2.2rem;
    line-height: 1.2;
  }
  
  .hero-slogan {
    font-size: 1rem;
    padding: 0 var(--spacing-sm);
  }
  
  .hero-buttons {
    flex-direction: column;
    gap: var(--spacing-sm);
    
    .cta-button {
      width: 100%;
      justify-content: center;
      padding: 14px 24px;
    }
  }
  
  .hero-stats {
    flex-direction: column;
    gap: var(--spacing-md);
    padding: var(--spacing-lg);
    margin-top: var(--spacing-lg);
  }
  
  .stat-divider {
    width: 40px;
    height: 1px;
  }
  
  .section-title {
    font-size: 2rem;
  }
  
  .features-grid {
    grid-template-columns: 1fr;
  }
  
  .quickstart-grid {
    grid-template-columns: 1fr;
  }
  
  .scroll-indicator {
    display: none;
  }
}

@media (max-width: 480px) {
  .hero {
    padding-top: calc(var(--navbar-height) + 10px);
  }
  
  .hero-content {
    padding: var(--spacing-sm);
  }
  
  .hero-badge {
    padding: 6px 12px;
    font-size: 0.75rem;
    
    .badge-icon {
      font-size: 0.9rem;
    }
    
    .badge-text {
      font-size: 0.7rem;
    }
  }
  
  .hero-title {
    font-size: 1.8rem;
  }
  
  .hero-slogan {
    font-size: 0.9rem;
  }
  
  .hero-buttons {
    .cta-button {
      padding: 12px 20px;
      font-size: 0.95rem;
    }
  }
  
  .hero-stats {
    padding: var(--spacing-md);
    
    .stat-number {
      font-size: 2rem;
    }
    
    .stat-label {
      font-size: 0.8rem;
    }
  }
  
  .section-container {
    padding: 0 var(--spacing-sm);
  }
  
  .section-title {
    font-size: 1.6rem;
  }
  
  .section-desc {
    font-size: 0.9rem;
  }
}
</style>
