<template>
  <div class="agent-page">
    <!-- Centered Hero Section with Auto-collapse -->
    <div class="agent-hero" :class="{ 'hero-collapsed': heroCollapsed }" @click="heroCollapsed && expandHero()">
      <div class="hero-container">
        <div class="hero-content">
          <span class="hero-icon">🤖</span>
          <h1 class="hero-title"><span class="highlight">EnzyMind</span> Agent</h1>
          <p class="hero-desc" v-show="!heroCollapsed">AI-powered enzyme research assistant with comprehensive analysis capabilities</p>
          <div class="hero-badges" v-show="!heroCollapsed">
            <span class="badge">🛠️ 16 Tools</span>
            <span class="badge">⚡ Real-time</span>
            <span class="badge">🧠 DeepSeek</span>
            <span class="badge">🔬 Multi-task</span>
          </div>
          <!-- Expand hint when collapsed -->
          <span class="expand-hint" v-show="heroCollapsed">Click to expand</span>
        </div>
        <!-- Collapse/Expand button -->
        <button class="hero-toggle-btn" @click.stop="toggleHero" :title="heroCollapsed ? 'Expand' : 'Collapse'">
          <svg v-if="!heroCollapsed" viewBox="0 0 24 24" width="16" height="16">
            <path fill="currentColor" d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" width="16" height="16">
            <path fill="currentColor" d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Chat Section -->
    <section class="chat-section" :class="{ 'chat-maximized': isMaximized }">
      <div class="section-container" :class="{ 'maximized': isMaximized }">
        <div class="chat-container" 
             ref="chatContainer"
             :style="chatContainerStyle"
             :class="{ 'maximized': isMaximized }">
          <!-- Chat Header with Controls -->
          <div class="chat-header">
            <div class="chat-title">
              <span class="chat-icon">🧠</span>
              <span>EnzyMind Chat</span>
              <span class="session-badge" title="New session on each refresh">Session: {{ userId.slice(0, 8) }}...</span>
            </div>
            <div class="chat-controls">
              <button class="control-btn" @click="clearHistory" title="Clear chat history">
                <svg viewBox="0 0 24 24" width="16" height="16">
                  <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
              <button class="control-btn" @click="toggleMaximize" :title="isMaximized ? 'Exit fullscreen' : 'Maximize'">
                <svg v-if="!isMaximized" viewBox="0 0 24 24" width="16" height="16">
                  <path fill="currentColor" d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" width="16" height="16">
                  <path fill="currentColor" d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                </svg>
              </button>
            </div>
          </div>
          <!-- Chat Messages -->
          <div class="chat-messages" ref="messagesContainer">
            <!-- Welcome Message -->
            <div v-if="messages.length === 0" class="welcome-message">
              <div class="welcome-icon">🧬</div>
              <h3>Welcome to EnzyMind Agent!</h3>
              <p>I'm your AI-powered enzyme research assistant. Ask me anything about:</p>
              <div class="suggestions">
                <button class="suggestion-btn" @click="sendSuggestion('What is P00761 and what does it do?')">
                  🔍 What is P00761?
                </button>
                <button class="suggestion-btn" @click="sendSuggestion('Predict the EC number for UniProt ID P12345')">
                  🏷️ Predict EC number
                </button>
                <button class="suggestion-btn" @click="sendSuggestion('Is P06865 an enzyme? If so, predict its active sites.')">
                  🎯 Predict active sites
                </button>
                <button class="suggestion-btn" @click="sendSuggestion('What are the kinetic parameters of P00698?')">
                  ⚡ Query kinetics
                </button>
              </div>
            </div>

            <!-- Message List -->
            <template v-for="(msg, idx) in messages" :key="idx">
              <!-- Session divider between old and new messages -->
              <div v-if="idx === historyMessageCount && historyMessageCount > 0" class="session-divider">
                <span class="divider-line"></span>
                <span class="divider-label">📜 Above: Previous Session (not sent as context)</span>
                <span class="divider-line"></span>
              </div>
              <div 
                class="message" 
                :class="[msg.role, { 'history-message': msg.isHistory }]"
              >
                <div class="message-avatar">
                  <span v-if="msg.role === 'user'">👤</span>
                  <span v-else>🤖</span>
                </div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="message-sender">{{ msg.role === 'user' ? 'You' : 'EnzyMind' }}</span>
                    <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                    <span v-if="msg.isHistory" class="history-badge">history</span>
                  </div>
                  <!-- Segmented Content Display -->
                  <template v-if="msg.segments && msg.segments.length > 0">
                    <template v-for="(segment, segIdx) in msg.segments" :key="segIdx">
                      <!-- Text Segment -->
                      <div v-if="segment.type === 'text' && segment.content" 
                         class="message-body segment-text" 
                         v-html="renderMarkdownText(segment.content)">
                    </div>
                    <!-- Tool Call Segment -->
                    <div v-else-if="segment.type === 'tool'" class="tool-call-segment">
                      <span class="tool-call-inline"
                            :class="{ 'tool-running': segment.status === 'running', 'tool-completed': segment.status === 'completed' }">
                        <span class="tool-icon">⚙</span>
                        <span class="tool-name">{{ segment.name }}</span>
                        <span v-if="segment.status === 'running'" class="tool-status running">
                          <span class="tool-spinner"></span>
                        </span>
                        <span v-else class="tool-status completed">
                          ✓
                          <span v-if="segment.endTime && segment.startTime" class="tool-duration">
                            {{ ((segment.endTime - segment.startTime) / 1000).toFixed(1) }}s
                          </span>
                        </span>
                      </span>
                    </div>
                  </template>
                </template>
                <!-- Fallback for old message format -->
                <div v-else-if="msg.content" class="message-body" v-html="renderMarkdown(msg)"></div>
              </div>
            </div>
            </template>

            <!-- Loading Indicator -->
            <div v-if="showTyping" class="message assistant loading">
              <div class="message-avatar">🤖</div>
              <div class="message-content">
                <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Input -->
          <div class="chat-input-container">
            <!-- File attachment display -->
            <div v-if="selectedFile" class="file-attachment">
              <div class="file-info">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ selectedFile.name }}</span>
                <span class="file-size">({{ formatFileSize(selectedFile.size) }})</span>
              </div>
              <button class="file-remove" @click="removeFile" title="Remove file">
                <svg viewBox="0 0 24 24" width="16" height="16">
                  <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            </div>
            <div class="input-wrapper">
              <!-- File upload button -->
              <input
                type="file"
                ref="fileInput"
                @change="handleFileSelect"
                accept=".fasta,.fa,.fna,.ffn,.faa,.frn"
                style="display: none"
              />
              <button 
                class="attach-btn" 
                @click="triggerFileInput"
                :disabled="loading"
                title="Attach FASTA file"
              >
                <svg viewBox="0 0 24 24" width="20" height="20">
                  <path fill="currentColor" d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/>
                </svg>
              </button>
              <textarea
                v-model="inputMessage"
                ref="inputTextarea"
                placeholder="Ask me anything about enzymes..."
                @keydown.enter.exact.prevent="sendMessage"
                @input="autoResize"
                rows="1"
                :disabled="loading"
              ></textarea>
              <button 
                class="send-btn" 
                @click="sendMessage" 
                :disabled="!inputMessage.trim() || loading"
              >
                <svg v-if="!loading" viewBox="0 0 24 24" width="20" height="20">
                  <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
                <div v-else class="btn-loading"></div>
              </button>
            </div>
            <p class="input-hint">Press Enter to send • Shift+Enter for new line • 📎 Attach FASTA file</p>
          </div>
          <!-- Resize Handle -->
          <div v-if="!isMaximized" 
               class="resize-handle" 
               @mousedown="startResize"
               title="Drag to resize">
          </div>
        </div>

        <!-- Features Sidebar -->
        <div class="features-sidebar">
          <h3 class="sidebar-title">🛠️ Available Tools</h3>
          
          <!-- Recognition & Classification -->
          <div class="tool-category">
            <h5 class="category-title">🔮 Recognition & Classification</h5>
            <div class="tool-list">
              <router-link to="/predict/enzyme" class="tool-item tool-link">
                <span class="tool-icon">🔍</span>
                <div class="tool-info">
                  <h4>Enzyme Recognition</h4>
                  <p>Identify if a protein is an enzyme using UniProt ID or amino acid sequence</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <router-link to="/predict/ec" class="tool-item tool-link">
                <span class="tool-icon">🏷️</span>
                <div class="tool-info">
                  <h4>EC Number Prediction</h4>
                  <p>Predict Enzyme Commission classification for proteins</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <router-link to="/predict/recommendation" class="tool-item tool-link">
                <span class="tool-icon">💡</span>
                <div class="tool-info">
                  <h4>Enzyme Recommendation</h4>
                  <p>Recommend enzyme types (EC) capable of catalyzing specific reactions</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
            </div>
          </div>

          <!-- Kinetics Prediction -->
          <div class="tool-category">
            <h5 class="category-title">⚗️ Kinetics Prediction</h5>
            <div class="tool-list">
              <router-link to="/predict/substrate" class="tool-item tool-link">
                <span class="tool-icon">⚛️</span>
                <div class="tool-info">
                  <h4>Substrate Prediction</h4>
                  <p>Predict if a small molecule (SMILES) can be a substrate for a specific enzyme</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <router-link to="/predict/kcat" class="tool-item tool-link">
                <span class="tool-icon">⚡</span>
                <div class="tool-info">
                  <h4>Kcat Prediction</h4>
                  <p>Predict catalytic constant (kcat) for enzyme-substrate pairs</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <router-link to="/predict/km" class="tool-item tool-link">
                <span class="tool-icon">🎚️</span>
                <div class="tool-info">
                  <h4>Km Prediction</h4>
                  <p>Predict Michaelis constant (Km) for enzyme-substrate interactions</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
            </div>
          </div>

          <!-- Active Sites & Structure -->
          <div class="tool-category">
            <h5 class="category-title">🧪 Active Sites & Features</h5>
            <div class="tool-list">
              <router-link to="/predict/activesite" class="tool-item tool-link">
                <span class="tool-icon">🎯</span>
                <div class="tool-info">
                  <h4>Active Site Prediction</h4>
                  <p>Predict active sites and binding residues using EasIFA with confidence scores</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <div class="tool-item">
                <span class="tool-icon">📍</span>
                <div class="tool-info">
                  <h4>Functional Features</h4>
                  <p>Retrieve functional sites (Active, Binding, Metal binding) from UniProt</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Database Queries -->
          <div class="tool-category">
            <h5 class="category-title">📚 Database Queries</h5>
            <div class="tool-list">
              <router-link to="/utility/enzyme-info" class="tool-item tool-link">
                <span class="tool-icon">📖</span>
                <div class="tool-info">
                  <h4>Enzyme Information</h4>
                  <p>Get comprehensive enzyme info including sequence, kinetics, sites, and reactions</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <div class="tool-item">
                <span class="tool-icon">📈</span>
                <div class="tool-info">
                  <h4>Kinetics Query</h4>
                  <p>Retrieve known experimental kinetic parameters (Km, Vmax, kcat) from BRENDA</p>
                </div>
              </div>
              <div class="tool-item">
                <span class="tool-icon">⚙️</span>
                <div class="tool-info">
                  <h4>Function Query</h4>
                  <p>Get functional annotations, protein names, organism and gene information</p>
                </div>
              </div>
              <div class="tool-item">
                <span class="tool-icon">🧫</span>
                <div class="tool-info">
                  <h4>Catalytic Activity</h4>
                  <p>Retrieve known catalytic activities and chemical reaction descriptions</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Utility Tools -->
          <div class="tool-category">
            <h5 class="category-title">🛠️ Utility Tools</h5>
            <div class="tool-list">
              <router-link to="/utility/alignment" class="tool-item tool-link">
                <span class="tool-icon">🔗</span>
                <div class="tool-info">
                  <h4>Sequence Alignment</h4>
                  <p>Find similar protein sequences and homologs using BLAST</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <router-link to="/utility/parameters" class="tool-item tool-link">
                <span class="tool-icon">📊</span>
                <div class="tool-info">
                  <h4>Sequence Parameters</h4>
                  <p>Compute physicochemical parameters (MW, pI, Instability Index)</p>
                </div>
                <span class="tool-arrow">→</span>
              </router-link>
              <div class="tool-item">
                <span class="tool-icon">📋</span>
                <div class="tool-info">
                  <h4>Sequence Info</h4>
                  <p>Retrieve amino acid sequence, length, and molecular weight</p>
                </div>
              </div>
            </div>
          </div>

          <div class="tech-stack">
            <h4 class="stack-title">Powered By</h4>
            <div class="stack-items">
              <span class="stack-item">🦜 n8n</span>
              <span class="stack-item">🧠 DeepSeek</span>
              <span class="stack-item">⚡ FastAPI</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { marked } from 'marked'

// n8n Webhook configuration - 通过 Gateway 转发
const N8N_WEBHOOK_URL = '/enzymind/api/agent/chat'

const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const showTyping = ref(false)
const messagesContainer = ref(null)
const inputTextarea = ref(null)
const fileInput = ref(null)
const selectedFile = ref(null)
const userId = ref('')
const chatContainer = ref(null)
const isMaximized = ref(false)
const chatHeight = ref(null)  // null means use default (same as sidebar)
const isResizing = ref(false)
const historyMessageCount = ref(0)  // Number of messages loaded from history
const heroCollapsed = ref(false)  // Hero section collapse state
let heroAutoCollapseTimer = null  // Timer for auto-collapse

// Toggle hero collapse state
const toggleHero = () => {
  heroCollapsed.value = !heroCollapsed.value
  // Clear auto-collapse timer if user manually toggles
  if (heroAutoCollapseTimer) {
    clearTimeout(heroAutoCollapseTimer)
    heroAutoCollapseTimer = null
  }
}

// Expand hero (used when clicking collapsed hero)
const expandHero = () => {
  heroCollapsed.value = false
  // Reset auto-collapse timer
  if (heroAutoCollapseTimer) {
    clearTimeout(heroAutoCollapseTimer)
  }
  heroAutoCollapseTimer = setTimeout(() => {
    heroCollapsed.value = true
  }, 10000)
}

// LocalStorage key for chat history
const CHAT_HISTORY_KEY = 'enzymind_chat_history'

// Computed style for chat container
const chatContainerStyle = computed(() => {
  if (isMaximized.value) return {}
  // If chatHeight is set (user resized), use it; otherwise use auto (CSS will handle)
  if (chatHeight.value !== null) {
    return {
      height: `${chatHeight.value}px`,
      minHeight: '300px',
      maxHeight: 'calc(100vh - 250px)'
    }
  }
  // Default: match sidebar height via CSS
  return {}
})

// Save messages to localStorage
const saveToLocalStorage = () => {
  try {
    const historyData = messages.value.map(msg => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp instanceof Date ? msg.timestamp.toISOString() : msg.timestamp,
      segments: msg.segments
    }))
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(historyData))
  } catch (e) {
    console.warn('Failed to save chat history:', e)
  }
}

// Load messages from localStorage
const loadFromLocalStorage = () => {
  try {
    const saved = localStorage.getItem(CHAT_HISTORY_KEY)
    if (saved) {
      const historyData = JSON.parse(saved)
      messages.value = historyData.map(msg => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
        isHistory: true  // Mark as history message
      }))
      historyMessageCount.value = messages.value.length
    }
  } catch (e) {
    console.warn('Failed to load chat history:', e)
  }
}

// Clear chat history
const clearHistory = () => {
  if (confirm('Clear all chat history? This cannot be undone.')) {
    messages.value = []
    historyMessageCount.value = 0
    localStorage.removeItem(CHAT_HISTORY_KEY)
  }
}

// Toggle maximize
const toggleMaximize = () => {
  isMaximized.value = !isMaximized.value
  nextTick(() => scrollToBottom())
}

// Resize functionality
const startResize = (e) => {
  e.preventDefault()
  e.stopPropagation()
  
  isResizing.value = true
  const startY = e.clientY
  // Get current actual height from element if chatHeight is null
  const startHeight = chatHeight.value ?? chatContainer.value?.offsetHeight ?? 500
  let rafId = null
  
  const onMouseMove = (moveEvent) => {
    moveEvent.preventDefault()
    if (rafId) return  // Throttle with RAF
    
    rafId = requestAnimationFrame(() => {
      const deltaY = moveEvent.clientY - startY
      const newHeight = Math.max(300, Math.min(startHeight + deltaY, window.innerHeight - 250))
      chatHeight.value = newHeight
      rafId = null
    })
  }
  
  const onMouseUp = (upEvent) => {
    upEvent.preventDefault()
    isResizing.value = false
    if (rafId) {
      cancelAnimationFrame(rafId)
    }
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    // Save height preference
    try {
      localStorage.setItem('enzymind_chat_height', String(chatHeight.value))
    } catch (e) {}
  }
  
  // Prevent text selection and set cursor globally during resize
  document.body.style.cursor = 'ns-resize'
  document.body.style.userSelect = 'none'
  
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

// Generate unique session ID
const generateUserId = () => {
  // Use crypto.randomUUID if available, otherwise fallback to timestamp + random
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `user-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
}

// Initialize userId on component mount
onMounted(() => {
  // Generate new userId for each session (refresh)
  userId.value = generateUserId()
  console.log('New session userId:', userId.value)
  
  // Load chat history from localStorage (but don't send to backend)
  loadFromLocalStorage()
  
  // Load saved height preference (null = use default)
  try {
    const savedHeight = localStorage.getItem('enzymind_chat_height')
    if (savedHeight) {
      chatHeight.value = parseInt(savedHeight, 10)
    }
  } catch (e) {}
  
  // Auto-collapse hero after 10 seconds
  heroAutoCollapseTimer = setTimeout(() => {
    heroCollapsed.value = true
  }, 10000)
  
  // Scroll to bottom after loading history
  nextTick(() => scrollToBottom())
})

// Watch messages and save to localStorage
watch(messages, () => {
  saveToLocalStorage()
}, { deep: true })

// Format timestamp
const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const markdownCache = new WeakMap()

// Render markdown content (cache per message to avoid re-parsing unchanged content)
const renderMarkdown = (message) => {
  const content = typeof message === 'string' ? message : message?.content
  if (!content) return ''

  if (message && typeof message === 'object') {
    const cached = markdownCache.get(message)
    if (cached && cached.content === content) {
      return cached.html
    }
    const html = marked(content, {
      breaks: true,
      gfm: true
    })
    markdownCache.set(message, { content, html })
    return html
  }

  return marked(content, {
    breaks: true,
    gfm: true
  })
}

// Render markdown from plain text string
const renderMarkdownText = (text) => {
  if (!text) return ''
  // Pre-process: format [Used tools: ...] blocks
  const processedText = formatToolUsageBlocks(text)
  return marked(processedText, {
    breaks: true,
    gfm: true
  })
}

// Format [Used tools: Tool: xxx, Input: {}, Result: [...]] blocks
const formatToolUsageBlocks = (text) => {
  if (!text) return text
  
  // Match [Used tools: ...] pattern
  const toolBlockRegex = /\[Used tools:\s*Tool:\s*([^,]+),\s*Input:\s*(\{[^}]*\}),\s*Result:\s*(\[[\s\S]*?\])\]/g
  
  return text.replace(toolBlockRegex, (match, toolName, input, resultStr) => {
    try {
      // Parse the result JSON
      const results = JSON.parse(resultStr)
      
      // Format output
      let formattedOutput = `\n\n<div class="tool-result-block">\n`
      formattedOutput += `<div class="tool-result-header">⚙️ <strong>${toolName.trim()}</strong></div>\n`
      
      if (results && results.length > 0) {
        const result = results[0]
        if (result.result) {
          // The result contains markdown-like content, render it
          formattedOutput += `<div class="tool-result-content">\n\n${result.result}\n\n</div>\n`
        } else if (result.error) {
          formattedOutput += `<div class="tool-result-error">❌ Error: ${result.error}</div>\n`
        } else {
          // Generic JSON display
          formattedOutput += `<div class="tool-result-content"><pre>${JSON.stringify(result, null, 2)}</pre></div>\n`
        }
      }
      
      formattedOutput += `</div>\n\n`
      return formattedOutput
    } catch (e) {
      // If parsing fails, return original with basic formatting
      return `\n\n> **⚙️ Tool Used:** ${toolName.trim()}\n\n`
    }
  })
}

// Auto-resize textarea
const autoResize = () => {
  const textarea = inputTextarea.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
  }
}

// Scroll to bottom of messages
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Send suggestion
const sendSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

// File handling functions
const triggerFileInput = () => {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    // Validate file type
    const validExtensions = ['.fasta', '.fa', '.fna', '.ffn', '.faa', '.frn']
    const fileName = file.name.toLowerCase()
    const isValid = validExtensions.some(ext => fileName.endsWith(ext))
    
    if (!isValid) {
      alert('Please select a valid FASTA file (.fasta, .fa, .fna, .ffn, .faa, .frn)')
      return
    }
    
    selectedFile.value = file
  }
}

const removeFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Parse n8n streaming response and extract text content
const parseN8nStreamChunk = (jsonStr) => {
  try {
    const data = JSON.parse(jsonStr)
    // Return structured data for different message types
    if (data.type === 'begin') {
      return { type: 'begin', metadata: data.metadata }
    }
    if (data.type === 'end') {
      return { type: 'end', metadata: data.metadata }
    }
    // n8n streaming format: {"type":"item","content":"actual content"}
    if (data.type === 'item' && typeof data.content === 'string') {
      return { type: 'content', content: data.content }
    }
    // Also handle other possible formats
    if (data.type === 'text' && data.text) {
      return { type: 'content', content: data.text }
    }
    if (data.type === 'message' && data.message) {
      return { type: 'content', content: data.message }
    }
    // Handle delta content format
    if (data.type === 'delta' && data.delta?.content) {
      return { type: 'content', content: data.delta.content }
    }
    return null
  } catch {
    // Not valid JSON, might be plain text
    return null
  }
}

// Send message to n8n webhook
const sendMessage = async () => {
  const message = inputMessage.value.trim()
  if (!message || loading.value) return

  // Build user message content (include file info if attached)
  let userMessageContent = message
  if (selectedFile.value) {
    userMessageContent = `${message}\n\n📎 **Attached file:** ${selectedFile.value.name}`
  }

  // Add user message
  messages.value.push({
    role: 'user',
    content: userMessageContent,
    timestamp: new Date()
  })
  
  // Store file reference before clearing
  const fileToSend = selectedFile.value
  
  inputMessage.value = ''
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  if (inputTextarea.value) {
    inputTextarea.value.style.height = 'auto'
  }
  
  loading.value = true
  showTyping.value = true
  await scrollToBottom()

  // 在 try 外部声明，以便 catch 块可以访问
  let messageIndex = -1

  try {
    let response
    
    if (fileToSend) {
      // Use FormData for file upload (multipart/form-data)
      const formData = new FormData()
      formData.append('message', message)
      formData.append('userID', userId.value)
      formData.append('data', fileToSend)
      
      response = await fetch(N8N_WEBHOOK_URL, {
        method: 'POST',
        body: formData
        // Note: Don't set Content-Type header, browser will set it with boundary
      })
    } else {
      // Use JSON for text-only messages
      response = await fetch(N8N_WEBHOOK_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: message,
          userID: userId.value
        })
      })
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    // 收到响应后关闭 typing indicator，准备显示助手消息
    showTyping.value = false
    
    const assistantMessage = {
      role: 'assistant',
      content: '',  // 保留用于兼容性
      timestamp: new Date(),
      segments: [{ type: 'text', content: '' }],  // 分段显示内容
      isCallingTool: false  // 是否正在调用工具
    }
    messages.value.push(assistantMessage)
    // 获取数组中的响应式引用
    messageIndex = messages.value.length - 1

    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    let hasContent = false
    let buffer = ''  // Buffer for incomplete lines
    let toolCallCount = 0  // 工具调用计数

    // 获取当前文本段落（最后一个 text 类型的段落）
    const getCurrentTextSegment = () => {
      const segments = messages.value[messageIndex].segments
      const lastSegment = segments[segments.length - 1]
      if (lastSegment && lastSegment.type === 'text') {
        return lastSegment
      }
      // 如果最后一个不是 text，创建新的 text 段落
      const newTextSegment = { type: 'text', content: '' }
      segments.push(newTextSegment)
      return newTextSegment
    }

    const updateContent = (text) => {
      if (!text) return
      hasContent = true
      // 向当前文本段落追加内容
      const textSegment = getCurrentTextSegment()
      textSegment.content += text
      // 同时更新 content 用于兼容性
      messages.value[messageIndex].content += text
      // 强制响应式更新
      messages.value = [...messages.value]
    }

    // 显示正在调用工具
    const showToolCalling = () => {
      toolCallCount++
      messages.value[messageIndex].isCallingTool = true
      // 添加工具调用段落
      messages.value[messageIndex].segments.push({
        type: 'tool',
        id: toolCallCount,
        name: `Tool #${toolCallCount}`,
        status: 'running',
        startTime: Date.now()
      })
      // 强制响应式更新
      messages.value = [...messages.value]
      scrollToBottom()
    }

    // 工具调用完成
    const hideToolCalling = () => {
      messages.value[messageIndex].isCallingTool = false
      // 找到最后一个运行中的工具段落并标记为完成
      const segments = messages.value[messageIndex].segments
      for (let i = segments.length - 1; i >= 0; i--) {
        if (segments[i].type === 'tool' && segments[i].status === 'running') {
          segments[i].status = 'completed'
          segments[i].endTime = Date.now()
          break
        }
      }
      // 添加新的文本段落用于后续内容
      segments.push({ type: 'text', content: '' })
      // 强制响应式更新
      messages.value = [...messages.value]
    }

    if (reader) {
      try {
        let lastEventWasEnd = false
        let isFirstBegin = true  // 标记是否是第一个 begin
        
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          
          const chunkText = decoder.decode(value, { stream: true })
          if (!chunkText) continue
          
          buffer += chunkText
          
          // n8n sends NDJSON (newline-delimited JSON)
          // Split by newlines and process complete lines
          const lines = buffer.split('\n')
          // Keep the last potentially incomplete line in buffer
          buffer = lines.pop() || ''
          
          for (const line of lines) {
            const trimmedLine = line.trim()
            if (!trimmedLine) continue
            
            try {
              const parsed = parseN8nStreamChunk(trimmedLine)
              if (!parsed) continue
              
              if (parsed.type === 'begin') {
                if (isFirstBegin) {
                  // 第一个 begin，忽略
                  isFirstBegin = false
                } else if (lastEventWasEnd) {
                  // end 后的 begin，说明工具调用完成
                  hideToolCalling()
                }
                lastEventWasEnd = false
              } else if (parsed.type === 'end') {
                // 检测到 end，显示正在调用工具
                showToolCalling()
                lastEventWasEnd = true
              } else if (parsed.type === 'content' && parsed.content) {
                updateContent(parsed.content)
                lastEventWasEnd = false
              }
            } catch (parseError) {
              console.warn('Error parsing stream line:', parseError, trimmedLine)
              // 继续处理下一行，不中断整个流
            }
          }
          
          // Scroll after processing each chunk
          scrollToBottom()
        }
      } catch (streamError) {
        console.error('Stream reading error:', streamError)
        // 流读取错误时，保留已接收的内容，不抛出异常
      } finally {
        try {
          reader.releaseLock()
        } catch (e) {
          console.warn('Error releasing reader lock:', e)
        }
      }
      
      // Handle any remaining bytes (即使流中断也尝试处理)
      try {
        const remaining = decoder.decode()
        if (remaining) {
          buffer += remaining
        }
        
        // Process any remaining line in buffer
        if (buffer.trim()) {
          const parsed = parseN8nStreamChunk(buffer.trim())
          if (parsed?.type === 'content' && parsed.content) {
            updateContent(parsed.content)
          }
        }
      } catch (e) {
        console.warn('Error processing remaining buffer:', e)
      }
      
      // 确保所有工具调用段落都标记为完成
      messages.value[messageIndex].isCallingTool = false
      const segments = messages.value[messageIndex].segments
      if (segments) {
        segments.forEach(segment => {
          if (segment.type === 'tool' && segment.status === 'running') {
            segment.status = 'completed'
            segment.endTime = Date.now()
          }
        })
        // 移除末尾的空文本段落
        while (segments.length > 0 && 
               segments[segments.length - 1].type === 'text' && 
               !segments[segments.length - 1].content?.trim()) {
          segments.pop()
        }
        // 强制响应式更新
        messages.value = [...messages.value]
      }
      
      // Final scroll
      scrollToBottom()
    } else {
      // Fallback: read entire response as text
      const data = await response.text()
      showTyping.value = false
      // Try to parse as JSON first
      const parsed = parseN8nStreamChunk(data)
      const content = parsed?.type === 'content' ? parsed.content : data
      messages.value[messageIndex].content = content
      messages.value[messageIndex].segments = [{ type: 'text', content: content }]
      await scrollToBottom()
    }

    if (!messages.value[messageIndex].content) {
      const errorContent = 'I apologize, but I could not generate a response. Please try again.'
      messages.value[messageIndex].content = errorContent
      messages.value[messageIndex].segments = [{ type: 'text', content: errorContent }]
    }
  } catch (error) {
    console.error('Error sending message:', error)
    // 检查是否已经有助手消息（可能在流式传输中途失败）
    if (messageIndex >= 0 && messages.value[messageIndex]?.role === 'assistant') {
      // 已有部分内容，追加错误信息
      const existingContent = messages.value[messageIndex].content || ''
      const errorSuffix = existingContent 
        ? `\n\n⚠️ **连接中断**: ${error.message}` 
        : `❌ **Error**: ${error.message}`
      
      // 确保所有工具调用都标记为完成
      const segments = messages.value[messageIndex].segments
      if (segments) {
        segments.forEach(segment => {
          if (segment.type === 'tool' && segment.status === 'running') {
            segment.status = 'completed'
            segment.endTime = Date.now()
          }
        })
        // 如果有内容，追加错误到最后一个文本段落
        if (existingContent) {
          const lastTextSegment = segments.filter(s => s.type === 'text').pop()
          if (lastTextSegment) {
            lastTextSegment.content += errorSuffix
          } else {
            segments.push({ type: 'text', content: errorSuffix })
          }
        } else {
          messages.value[messageIndex].segments = [{ type: 'text', content: errorSuffix }]
        }
      }
      messages.value[messageIndex].content += errorSuffix
      messages.value[messageIndex].isCallingTool = false
      // 强制响应式更新
      messages.value = [...messages.value]
    } else {
      // 没有助手消息，创建新的错误消息
      const errorContent = `❌ **Error**: Unable to connect to the EnzyMind Agent service.\n\nPlease ensure:\n- The n8n service is running on \`localhost:5678\`\n- The EnzyMind workflow is active\n\nError details: ${error.message}`
      messages.value.push({
        role: 'assistant',
        content: errorContent,
        segments: [{ type: 'text', content: errorContent }],
        timestamp: new Date()
      })
    }
  } finally {
    loading.value = false
    showTyping.value = false
    await scrollToBottom()
  }
}

onMounted(() => {
  // Focus on input
  if (inputTextarea.value) {
    inputTextarea.value.focus()
  }
})
</script>

<style lang="scss" scoped>
// ===== Color Variables for Chat =====
$chat-bg: #f8fafc;
$chat-surface: #ffffff;
$chat-border: #e2e8f0;
$chat-text: #1e293b;
$chat-text-secondary: #64748b;
$chat-text-muted: #94a3b8;

// User message - light blue background with dark text for better readability
$user-bubble-bg: #e0f2fe;
$user-bubble-border: #7dd3fc;
$user-bubble-text: #0c4a6e;

$assistant-bubble-bg: #ffffff;
$assistant-bubble-border: #e2e8f0;
$assistant-bubble-text: #1e293b;

$code-bg: #1e293b;
$code-text: #e2e8f0;
$inline-code-bg: #f1f5f9;
$inline-code-text: #0f172a;

$primary-color: #3b82f6;
$primary-light: rgba(59, 130, 246, 0.1);
$accent-color: #8b5cf6;

.agent-page { 
  min-height: 100vh; 
  background: $chat-bg;
}

.agent-hero {
  position: relative; 
  padding-top: var(--navbar-height);
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  
  // Collapsed state - only show title
  &.hero-collapsed {
    cursor: pointer;
    
    .hero-container {
      padding: 3px var(--spacing-lg) 20px;
    }
    
    .hero-content {
      flex-direction: row;
      gap: 10px;
    }
    
    .hero-title {
      font-size: 2.0rem;
    }
    
    &:hover {
      background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
      
      .expand-hint {
        opacity: 1;
      }
    }
  }
}

.hero-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px var(--spacing-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: padding 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  transition: gap 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-icon {
  font-size: 3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  background: rgba(139, 92, 246, 0.2);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 20px;
  animation: pulse 2s ease-in-out infinite;
  margin-bottom: 8px;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-collapsed .hero-icon {
  font-size: 1.5rem;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  margin-bottom: 0;
  animation: none;
}

// Hero toggle button
.hero-toggle-btn {
  position: absolute;
  right: var(--spacing-lg);
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.7);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
  }
}

// Expand hint text
.expand-hint {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  opacity: 0;
  transition: opacity 0.2s ease;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

.hero-title {
  font-size: 2rem;
  font-weight: 800;
  color: #fff;
  margin: 0;
  line-height: 1.2;
  transition: font-size 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  
  .highlight {
    background: linear-gradient(135deg, #a78bfa 0%, #60a5fa 50%, #34d399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.hero-desc {
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.7);
  margin: 0;
  max-width: 500px;
}

.hero-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.25);
    transform: translateY(-1px);
  }
}

// ===== Chat Section =====
.chat-section { 
  padding: var(--spacing-xl) 0 var(--spacing-3xl);
  background: $chat-bg;
  transition: all 0.3s ease;
  
  &.chat-maximized {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 1000;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.section-container {
  max-width: 1400px; 
  margin: 0 auto; 
  padding: 0 var(--spacing-lg);
  display: grid; 
  grid-template-columns: 1fr 320px; 
  gap: var(--spacing-xl);
  align-items: stretch;
  
  &.maximized {
    max-width: 100%;
    width: 100%;
    height: 100%;
    padding: 0;
    display: flex;
    
    .features-sidebar {
      display: none;
    }
  }
}

.chat-container {
  background: $chat-surface;
  border: 1px solid $chat-border;
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  // Default height: same as sidebar
  height: calc(100vh - 350px);
  min-height: 500px;
  
  &.maximized {
    width: 100%;
    height: 100%;
    max-width: 100%;
    max-height: 100%;
    border-radius: 0;
    border: none;
  }
}

// ===== Chat Header =====
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-bottom: 1px solid $chat-border;
  flex-shrink: 0;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 0.9rem;
  color: $chat-text;
  
  .chat-icon {
    font-size: 1.1rem;
  }
  
  .session-badge {
    font-size: 0.7rem;
    font-weight: 400;
    color: $chat-text-muted;
    background: rgba(0, 0, 0, 0.05);
    padding: 2px 8px;
    border-radius: 10px;
    font-family: ui-monospace, SFMono-Regular, monospace;
  }
}

.chat-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: $chat-text-secondary;
  transition: all 0.2s ease;
  
  &:hover {
    background: rgba(0, 0, 0, 0.06);
    color: $chat-text;
  }
}

// ===== Resize Handle =====
.resize-handle {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 8px;
  cursor: ns-resize;
  background: linear-gradient(to bottom, transparent, rgba(0, 0, 0, 0.03));
  
  &::after {
    content: '';
    position: absolute;
    left: 50%;
    bottom: 3px;
    transform: translateX(-50%);
    width: 40px;
    height: 3px;
    background: $chat-border;
    border-radius: 2px;
    transition: background 0.2s ease;
  }
  
  &:hover::after {
    background: $chat-text-muted;
  }
}

// ===== Chat Messages =====
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: $chat-bg;
  
  // Custom scrollbar
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: $chat-border;
    border-radius: 3px;
    &:hover {
      background: $chat-text-muted;
    }
  }
}

.welcome-message {
  text-align: center; 
  padding: 40px 20px;
  
  .welcome-icon { 
    font-size: 4rem; 
    margin-bottom: 20px; 
    animation: bounce 2s infinite; 
  }
  
  h3 { 
    font-size: 1.5rem; 
    font-weight: 700; 
    color: $chat-text; 
    margin-bottom: 12px; 
  }
  
  p { 
    color: $chat-text-secondary; 
    margin-bottom: 28px;
    font-size: 1rem;
  }
}

@keyframes bounce { 
  0%, 100% { transform: translateY(0); } 
  50% { transform: translateY(-10px); } 
}

.suggestions {
  display: flex; 
  flex-wrap: wrap; 
  gap: 10px; 
  justify-content: center;
}

.suggestion-btn {
  padding: 12px 20px;
  background: $chat-surface;
  border: 1px solid $chat-border;
  border-radius: 12px;
  font-size: 0.9rem;
  color: $chat-text;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: $primary-light;
    border-color: $primary-color;
    color: $primary-color;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
  }
}

// ===== Message Styles =====
.message {
  display: flex;
  gap: 12px;
  max-width: 80%;
  animation: messageIn 0.3s ease-out;
  position: relative;
  
  &.user {
    flex-direction: row-reverse;
    margin-left: auto;
  }
  
  &.assistant {
    margin-right: auto;
  }
  
  // History message styling
  &.history-message {
    opacity: 0.7;
    
    .message-content {
      position: relative;
      
      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: repeating-linear-gradient(
          -45deg,
          transparent,
          transparent 10px,
          rgba(148, 163, 184, 0.03) 10px,
          rgba(148, 163, 184, 0.03) 20px
        );
        pointer-events: none;
        border-radius: inherit;
      }
    }
    
    &:hover {
      opacity: 0.85;
    }
  }
}

// Session divider between old and new messages
.session-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0 16px;
  padding: 0 20px;
  width: 100%;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, transparent, #f59e0b, transparent);
}

.divider-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: 1px solid #f59e0b;
  border-radius: 12px;
  font-size: 0.7rem;
  color: #92400e;
  font-weight: 500;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.2);
}

// History badge in message header
.history-badge {
  font-size: 0.6rem;
  padding: 1px 5px;
  background: rgba(148, 163, 184, 0.2);
  color: $chat-text-muted;
  border-radius: 4px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
  
  .user & {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  }
  
  .assistant & {
    background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
  }
}

.message-content {
  border-radius: 16px;
  padding: 14px 18px;
  max-width: 100%;
  
  .user & {
    background: $user-bubble-bg;
    border: 1px solid $user-bubble-border;
    color: $user-bubble-text;
    border-bottom-right-radius: 4px;
  }
  
  .assistant & {
    background: $assistant-bubble-bg;
    border: 1px solid $assistant-bubble-border;
    color: $assistant-bubble-text;
    border-bottom-left-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  
  .user & {
    border-bottom-color: rgba(12, 74, 110, 0.15);
  }
  
  .message-sender {
    font-weight: 600;
    font-size: 0.85rem;
  }
  
  .message-time {
    font-size: 0.75rem;
    color: $chat-text-muted;
    margin-left: auto;
    
    .user & {
      color: rgba(12, 74, 110, 0.6);
    }
  }
}

// ===== Segment Display =====
.segment-text {
  // 文本段落样式，与 message-body 保持一致
  &:not(:last-child) {
    margin-bottom: 8px;
  }
}

.tool-call-segment {
  margin: 6px 0;
  line-height: 1.4;
}

// ===== Tool Calls Display (Inline Style) =====
.tool-call-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace;
  transition: all 0.2s ease;
  
  &.tool-running {
    background: rgba(139, 92, 246, 0.1);
    color: #7c3aed;
  }
  
  &.tool-completed {
    background: rgba(34, 197, 94, 0.08);
    color: #16a34a;
  }
}

.tool-icon {
  font-size: 0.7rem;
  opacity: 0.7;
}

.tool-name {
  font-weight: 500;
}

.tool-status {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.7rem;
  opacity: 0.8;
}

.tool-duration {
  font-weight: 400;
  opacity: 0.7;
}

.tool-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(139, 92, 246, 0.25);
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

// ===== Tool Result Block (from [Used tools: ...] format) =====
.message-body :deep(.tool-result-block) {
  margin: 16px 0;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.06) 0%, rgba(59, 130, 246, 0.04) 100%);
  border: 1px solid rgba(139, 92, 246, 0.15);
  border-radius: 8px;
  border-left: 3px solid $primary-color;
}

.message-body :deep(.tool-result-header) {
  font-size: 0.8rem;
  color: $primary-color;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.1);
}

.message-body :deep(.tool-result-content) {
  font-size: 0.9rem;
  
  h2, h3, h4 {
    color: $chat-text;
    margin-top: 12px;
    margin-bottom: 8px;
    &:first-child {
      margin-top: 0;
    }
  }
  
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 0.85rem;
    
    th, td {
      padding: 6px 10px;
      border: 1px solid rgba(139, 92, 246, 0.15);
      text-align: left;
    }
    
    th {
      background: rgba(139, 92, 246, 0.08);
      font-weight: 600;
    }
    
    tr:nth-child(even) td {
      background: rgba(139, 92, 246, 0.03);
    }
  }
  
  pre {
    background: rgba(0, 0, 0, 0.03);
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.8rem;
  }
}

.message-body :deep(.tool-result-error) {
  color: #dc2626;
  font-size: 0.85rem;
  padding: 8px;
  background: rgba(220, 38, 38, 0.08);
  border-radius: 4px;
}

// ===== Markdown Rendering Styles =====
.message-body {
  font-size: 0.95rem;
  line-height: 1.7;
  color: inherit;
  
  // Paragraphs
  :deep(p) {
    margin: 0 0 12px;
    &:last-child {
      margin-bottom: 0;
    }
  }
  
  // Headings
  :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
    margin: 20px 0 12px;
    font-weight: 700;
    line-height: 1.3;
    color: $chat-text;
    
    &:first-child {
      margin-top: 0;
    }
  }
  
  :deep(h1) { font-size: 1.4rem; }
  :deep(h2) { font-size: 1.25rem; }
  :deep(h3) { font-size: 1.1rem; }
  :deep(h4) { font-size: 1rem; }
  
  // Lists
  :deep(ul), :deep(ol) {
    margin: 12px 0;
    padding-left: 24px;
    
    li {
      margin: 6px 0;
      line-height: 1.6;
      
      &::marker {
        color: $primary-color;
      }
    }
  }
  
  :deep(ul) {
    list-style-type: disc;
    
    ul {
      list-style-type: circle;
      margin: 4px 0;
    }
  }
  
  :deep(ol) {
    list-style-type: decimal;
  }
  
  // Inline code
  :deep(code) {
    background: $inline-code-bg;
    color: $inline-code-text;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.88em;
    font-family: 'SF Mono', 'Fira Code', 'Monaco', 'Consolas', monospace;
    font-weight: 500;
    border: 1px solid #e2e8f0;
  }
  
  .user & :deep(code) {
    background: rgba(12, 74, 110, 0.12);
    color: #0c4a6e;
    border-color: rgba(12, 74, 110, 0.2);
  }
  
  // Code blocks
  :deep(pre) {
    background: $code-bg;
    color: $code-text;
    padding: 16px 20px;
    border-radius: 12px;
    overflow-x: auto;
    margin: 16px 0;
    font-size: 0.88rem;
    line-height: 1.6;
    border: 1px solid #334155;
    
    code {
      background: transparent;
      color: inherit;
      padding: 0;
      border: none;
      font-size: inherit;
      border-radius: 0;
    }
    
    // Syntax highlighting enhancement
    &::-webkit-scrollbar {
      height: 6px;
    }
    &::-webkit-scrollbar-track {
      background: #334155;
      border-radius: 3px;
    }
    &::-webkit-scrollbar-thumb {
      background: #475569;
      border-radius: 3px;
    }
  }
  
  // Tables
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.9rem;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid $chat-border;
    
    th, td {
      padding: 12px 16px;
      text-align: left;
      border-bottom: 1px solid $chat-border;
    }
    
    th {
      background: #f1f5f9;
      font-weight: 600;
      color: $chat-text;
      text-transform: uppercase;
      font-size: 0.8rem;
      letter-spacing: 0.03em;
    }
    
    td {
      background: $chat-surface;
    }
    
    tr:last-child td {
      border-bottom: none;
    }
    
    tr:hover td {
      background: #f8fafc;
    }
  }
  
  // Blockquotes
  :deep(blockquote) {
    margin: 16px 0;
    padding: 12px 20px;
    border-left: 4px solid $primary-color;
    background: $primary-light;
    border-radius: 0 8px 8px 0;
    color: $chat-text-secondary;
    font-style: italic;
    
    p {
      margin: 0;
    }
  }
  
  // Links
  :deep(a) {
    color: $primary-color;
    text-decoration: none;
    font-weight: 500;
    border-bottom: 1px solid transparent;
    transition: all 0.2s ease;
    
    &:hover {
      border-bottom-color: $primary-color;
    }
  }
  
  .user & :deep(a) {
    color: #0369a1;
    
    &:hover {
      border-bottom-color: #0369a1;
    }
  }
  
  // Strong and emphasis
  :deep(strong) {
    font-weight: 700;
    color: inherit;
  }
  
  :deep(em) {
    font-style: italic;
  }
  
  // Horizontal rule
  :deep(hr) {
    border: none;
    height: 1px;
    background: $chat-border;
    margin: 20px 0;
  }
  
  // Images
  :deep(img) {
    max-width: 100%;
    border-radius: 8px;
    margin: 12px 0;
  }
}

// ===== Loading Indicator =====
.loading .message-content {
  padding: 18px;
}

.typing-indicator {
  display: flex;
  gap: 5px;
  align-items: center;
  
  span {
    width: 8px;
    height: 8px;
    background: $accent-color;
    border-radius: 50%;
    animation: typing 1.4s infinite ease-in-out;
    
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

// ===== Chat Input =====
.chat-input-container {
  padding: 20px;
  border-top: 1px solid $chat-border;
  background: $chat-surface;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: $chat-bg;
  border: 2px solid $chat-border;
  border-radius: 16px;
  padding: 8px 12px;
  transition: all 0.2s ease;
  
  &:focus-within {
    border-color: $primary-color;
    box-shadow: 0 0 0 4px $primary-light;
  }
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 1rem;
  resize: none;
  max-height: 150px;
  line-height: 1.5;
  padding: 10px 4px;
  font-family: inherit;
  color: $chat-text;
  
  &::placeholder {
    color: $chat-text-muted;
  }
  
  &:disabled {
    opacity: 0.6;
  }
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  
  &:hover:not(:disabled) {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
  }
  
  &:disabled {
    background: #cbd5e1;
    opacity: 0.7;
    cursor: not-allowed;
  }
}

// ===== Attach Button =====
.attach-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: transparent;
  border: 1px solid $chat-border;
  color: $chat-text-secondary;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  
  &:hover:not(:disabled) {
    background: $primary-light;
    border-color: $primary-color;
    color: $primary-color;
    transform: scale(1.05);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

// ===== File Attachment Display =====
.file-attachment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  margin-bottom: 12px;
  animation: slideIn 0.2s ease-out;
  
  .file-info {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
    
    .file-icon {
      font-size: 1.2rem;
      flex-shrink: 0;
    }
    
    .file-name {
      font-size: 0.9rem;
      font-weight: 600;
      color: $chat-text;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .file-size {
      font-size: 0.8rem;
      color: $chat-text-secondary;
      flex-shrink: 0;
    }
  }
  
  .file-remove {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: $chat-text-muted;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
    margin-left: 8px;
    
    &:hover {
      background: rgba(239, 68, 68, 0.1);
      color: #ef4444;
    }
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.btn-loading {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.input-hint {
  font-size: 0.75rem;
  color: $chat-text-muted;
  text-align: center;
  margin-top: 10px;
}

// ===== Features Sidebar =====
.features-sidebar {
  background: $chat-surface;
  border: 1px solid $chat-border;
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  height: calc(100vh - 350px);
  min-height: 500px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: $chat-text;
  margin-bottom: 16px;
}

.tool-category {
  margin-bottom: 20px;
  
  &:last-of-type {
    margin-bottom: 0;
  }
}

.category-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: $primary-color;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.2);
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: $chat-bg;
  border: 1px solid $chat-border;
  border-radius: 10px;
  transition: all 0.2s ease;
  text-decoration: none;
  
  &:hover {
    border-color: $primary-color;
    transform: translateX(4px);
    background: $primary-light;
  }
  
  .tool-icon {
    font-size: 1.1rem;
    flex-shrink: 0;
    margin-top: 2px;
  }
  
  .tool-info {
    flex: 1;
    
    h4 {
      font-size: 0.85rem;
      font-weight: 600;
      color: $chat-text;
      margin: 0 0 2px;
    }
    
    p {
      font-size: 0.75rem;
      color: $chat-text-secondary;
      margin: 0;
      line-height: 1.4;
    }
  }
  
  .tool-arrow {
    font-size: 0.9rem;
    color: $chat-text-muted;
    opacity: 0;
    transition: all 0.2s ease;
    margin-left: auto;
    align-self: center;
  }
  
  &.tool-link {
    cursor: pointer;
    
    &:hover {
      .tool-arrow {
        opacity: 1;
        color: $primary-color;
        transform: translateX(3px);
      }
      
      .tool-info h4 {
        color: $primary-color;
      }
    }
  }
}

.tech-stack {
  margin-top: auto;
  padding-top: 20px;
  border-top: 1px solid $chat-border;
  
  .stack-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: $chat-text-muted;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .stack-items {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .stack-item {
    font-size: 0.85rem;
    padding: 6px 14px;
    background: $chat-bg;
    border: 1px solid $chat-border;
    border-radius: 20px;
    color: $chat-text-secondary;
    transition: all 0.2s ease;
    
    &:hover {
      background: $primary-light;
      border-color: $primary-color;
      color: $primary-color;
    }
  }
}

// ===== Responsive =====
@media (max-width: 1200px) {
  .section-container {
    grid-template-columns: 1fr 280px;
    gap: 20px;
  }
  
  .features-sidebar {
    padding: 20px;
  }
  
  .tool-item {
    padding: 8px 10px;
    
    .tool-info {
      h4 {
        font-size: 0.8rem;
      }
      p {
        font-size: 0.7rem;
      }
    }
  }
}

@media (max-width: 1024px) {
  .section-container {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  // 工具列表在移动端作为可折叠的底部面板
  .features-sidebar {
    display: block;
    height: auto;
    min-height: auto;
    max-height: none;
    order: 1; // 放在聊天框下方
    padding: 16px;
    
    // 紧凑的水平滚动工具列表
    .tool-category {
      margin-bottom: 12px;
      
      &:last-of-type {
        margin-bottom: 0;
      }
    }
    
    .tool-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    
    .tool-item {
      flex: 0 0 auto;
      padding: 6px 12px;
      
      .tool-info p {
        display: none; // 隐藏描述，只显示标题
      }
    }
  }
  
  .sidebar-title {
    margin-bottom: 12px;
    font-size: 1rem;
  }
  
  .category-title {
    font-size: 0.8rem;
    margin-bottom: 8px;
  }
  
  .tech-stack {
    display: none; // 移动端隐藏技术栈
  }
  
  // 聊天容器占据主要空间
  .chat-container {
    height: calc(100vh - 280px);
    min-height: 450px;
    order: 0; // 确保在工具列表之前
  }
  
  .hero-badges {
    gap: 8px;
  }
  
  .badge {
    padding: 5px 10px;
    font-size: 0.8rem;
  }
}

@media (max-width: 768px) {
  .agent-hero {
    padding-top: calc(var(--navbar-height) - 10px);
  }
  
  .hero-container {
    padding: 16px var(--spacing-md);
  }
  
  .hero-icon {
    width: 52px;
    height: 52px;
    font-size: 2rem;
    border-radius: 14px;
    margin-bottom: 4px;
  }
  
  .hero-title {
    font-size: 1.4rem;
  }
  
  .hero-desc {
    font-size: 0.85rem;
    padding: 0 10px;
  }
  
  .hero-badges {
    gap: 6px;
    flex-wrap: wrap;
    justify-content: center;
  }
  
  .badge {
    padding: 4px 10px;
    font-size: 0.75rem;
  }
  
  .chat-section {
    padding: var(--spacing-md) 0 var(--spacing-lg);
  }
  
  .section-container {
    padding: 0 var(--spacing-md);
  }
  
  // 工具列表更紧凑
  .features-sidebar {
    padding: 14px;
    border-radius: 14px;
    
    .tool-item {
      padding: 5px 10px;
      border-radius: 8px;
      
      .tool-icon {
        font-size: 0.95rem;
      }
      
      .tool-info h4 {
        font-size: 0.75rem;
      }
      
      .tool-arrow {
        display: none;
      }
    }
  }
  
  .sidebar-title {
    font-size: 0.95rem;
  }
  
  .category-title {
    font-size: 0.75rem;
    padding-bottom: 6px;
  }
  
  // 聊天区域保持为主焦点
  .chat-container {
    height: calc(100vh - 260px);
    min-height: 400px;
    border-radius: 16px;
  }
  
  .welcome-message {
    padding: 24px 16px;
    
    .welcome-icon {
      font-size: 2.5rem;
    }
    
    h3 {
      font-size: 1.1rem;
    }
    
    p {
      font-size: 0.85rem;
    }
  }
  
  .suggestions {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .suggestion-btn {
    text-align: left;
    padding: 10px 14px;
    font-size: 0.85rem;
  }
  
  .message {
    max-width: 92%;
  }
  
  .chat-messages {
    padding: 14px;
  }
  
  .message-content {
    padding: 10px 12px;
    font-size: 0.9rem;
  }
  
  .chat-input-container {
    padding: 12px;
  }
  
  .input-wrapper {
    padding: 8px 10px;
    border-radius: 20px;
    
    textarea {
      font-size: 0.9rem;
    }
  }
  
  .input-hint {
    font-size: 0.7rem;
  }
}

@media (max-width: 480px) {
  .hero-container {
    padding: 12px var(--spacing-sm);
  }
  
  .hero-icon {
    width: 44px;
    height: 44px;
    font-size: 1.6rem;
    border-radius: 12px;
  }
  
  .hero-title {
    font-size: 1.2rem;
  }
  
  .hero-desc {
    font-size: 0.8rem;
  }
  
  .hero-badges {
    gap: 4px;
  }
  
  .badge {
    padding: 3px 8px;
    font-size: 0.7rem;
  }
  
  .section-container {
    padding: 0 var(--spacing-sm);
  }
  
  // 超小屏幕：只显示可跳转的工具，更紧凑
  .features-sidebar {
    padding: 12px;
    border-radius: 12px;
    
    // 隐藏无链接的工具项
    .tool-item:not(.tool-link) {
      display: none;
    }
    
    .tool-item {
      padding: 4px 8px;
      
      .tool-icon {
        font-size: 0.85rem;
      }
      
      .tool-info h4 {
        font-size: 0.7rem;
      }
    }
  }
  
  .sidebar-title {
    font-size: 0.9rem;
    margin-bottom: 10px;
  }
  
  .category-title {
    font-size: 0.7rem;
    margin-bottom: 6px;
  }
  
  // 聊天区域最大化
  .chat-container {
    height: calc(100vh - 220px);
    min-height: 350px;
    border-radius: 12px;
  }
  
  .welcome-message {
    padding: 20px 12px;
    
    .welcome-icon {
      font-size: 2rem;
    }
    
    h3 {
      font-size: 1rem;
    }
    
    p {
      font-size: 0.8rem;
    }
  }
  
  .suggestion-btn {
    padding: 8px 12px;
    font-size: 0.8rem;
    border-radius: 10px;
  }
  
  .message-content {
    padding: 8px 10px;
    font-size: 0.85rem;
  }
  
  .chat-input-container {
    padding: 10px;
  }
  
  .input-wrapper {
    padding: 6px 8px;
    
    textarea {
      font-size: 0.85rem;
    }
    
    .send-btn {
      width: 34px;
      height: 34px;
    }
  }
  
  .input-hint {
    display: none;
  }
}
</style>
