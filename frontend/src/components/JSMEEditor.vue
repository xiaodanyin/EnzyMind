<template>
  <div class="jsme-editor">
    <div class="jsme-container" :class="{ 'loading': !jsmeLoaded }">
      <div v-if="!jsmeLoaded" class="jsme-loading">
        <div class="spinner-border text-primary mb-2" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p class="mb-0">Loading molecular editor...</p>
      </div>
      <div 
        :id="containerId" 
        v-show="jsmeLoaded" 
        class="border rounded" 
        :style="{ width: width, height: height }"
      ></div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'JSMEEditor',
  props: {
    containerId: {
      type: String,
      default: 'jsme_container'
    },
    height: {
      type: String,
      default: '100%'
    },
    width: {
      type: String,
      default: '100%'
    },
    options: {
      type: String,
      default: 'oldlook,star,nocanonize,reaction'
    },
    modelValue: {
      type: String,
      default: ''
    }
  },
  emits: ['update:modelValue', 'jsme-ready', 'structure-change'],
  data() {
    return {
      jsmeApplet: null,
      jsmeLoaded: false,
      isInitializing: false
    }
  },
  mounted() {
    this.loadJSME()
  },
  beforeUnmount() {
    this.cleanup()
  },
  watch: {
    modelValue(newValue, oldValue) {
      if (newValue !== oldValue && this.jsmeApplet && this.jsmeLoaded && newValue) {
        this.setSmiles(newValue)
      }
    }
  },
  methods: {
    async loadJSME() {
      if (this.isInitializing) return
      this.isInitializing = true

      try {
        // Use the path relative to public folder with /enzymind prefix for production
        const basePath = import.meta.env.BASE_URL || '/enzymind/'
        await this.loadScript(`${basePath}static/jsme/jsme.nocache.js`)
        
        // Wait for JSME to be available
        await this.waitForJSME()
        this.initializeJSME()
      } catch (error) {
        console.error('Failed to load JSME:', error)
        this.$emit('jsme-ready', { success: false, error })
      } finally {
        this.isInitializing = false
      }
    },

    loadScript(src) {
      return new Promise((resolve, reject) => {
        const existingScript = document.querySelector(`script[src="${src}"]`)
        if (existingScript) {
          resolve()
          return
        }

        const script = document.createElement('script')
        script.src = src
        script.onload = resolve
        script.onerror = reject
        document.head.appendChild(script)
      })
    },

    waitForJSME() {
      return new Promise((resolve, reject) => {
        let attempts = 0
        const maxAttempts = 20

        const checkJSME = () => {
          attempts++
          if (typeof window.JSApplet !== 'undefined' && window.JSApplet.JSME) {
            resolve()
          } else if (attempts >= maxAttempts) {
            reject(new Error('JSME failed to load after maximum attempts'))
          } else {
            setTimeout(checkJSME, 200)
          }
        }

        checkJSME()
      })
    },

    initializeJSME() {
      try {
        // Create unique callback name
        const callbackName = `jsmeCallback_${this.containerId}`
        
        this.jsmeApplet = new window.JSApplet.JSME(this.containerId, "100%", "100%", {
          "options": this.options
        })
        
        // Set up callback for structure changes
        window[callbackName] = this.onStructureChange.bind(this)
        this.jsmeApplet.setNotifyStructuralChangeJSfunction(callbackName)
        
        this.jsmeLoaded = true
        
        // Set initial value if provided
        if (this.modelValue) {
          this.setSmiles(this.modelValue)
        }
        
        this.$emit('jsme-ready', { success: true, applet: this.jsmeApplet })
        console.log('JSME initialized successfully')
      } catch (error) {
        console.error('Error initializing JSME:', error)
        this.$emit('jsme-ready', { success: false, error })
      }
    },

    onStructureChange() {
      if (this.jsmeApplet && this.jsmeLoaded) {
        try {
          this.jsmeApplet.options("canonize")
          const smiles = this.jsmeApplet.smiles()
          
          // Clean up the SMILES (remove numbered atoms)
          const patt = /\[([A-Za-z][a-z]?)H?\d*:\d+\]/g
          const cleanSmiles = smiles.replace(patt, '$1')
          
          this.$emit('update:modelValue', cleanSmiles)
          this.$emit('structure-change', {
            smiles: cleanSmiles,
            rawSmiles: smiles
          })
        } catch (error) {
          console.error('Error getting SMILES from JSME:', error)
        }
      }
    },

    setSmiles(smiles) {
      if (this.jsmeApplet && this.jsmeLoaded && smiles) {
        try {
          this.jsmeApplet.readMolFile(smiles)
        } catch (error) {
          console.error('Error setting SMILES in JSME:', error)
        }
      }
    },

    clear() {
      if (this.jsmeApplet && this.jsmeLoaded) {
        try {
          this.jsmeApplet.clear()
          this.$emit('update:modelValue', '')
        } catch (error) {
          console.error('Error clearing JSME:', error)
        }
      }
    },

    getSmiles() {
      if (this.jsmeApplet && this.jsmeLoaded) {
        try {
          this.jsmeApplet.options("canonize")
          return this.jsmeApplet.smiles()
        } catch (error) {
          console.error('Error getting SMILES from JSME:', error)
          return ''
        }
      }
      return ''
    },

    cleanup() {
      const callbackName = `jsmeCallback_${this.containerId}`
      if (window[callbackName]) {
        delete window[callbackName]
      }
      this.jsmeApplet = null
      this.jsmeLoaded = false
    }
  }
}
</script>

<style scoped>
.jsme-container {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
  height: 100%;
  width: 100%;
}

.jsme-container.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.jsme-loading {
  text-align: center;
  color: #6c757d;
}

.jsme-container .border {
  border: 2px solid #dee2e6 !important;
  border-radius: 8px;
  background: white;
}
</style>
