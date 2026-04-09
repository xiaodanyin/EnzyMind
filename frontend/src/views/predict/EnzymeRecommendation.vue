<template>
  <PageContainer
    title="Enzyme Type Recommendation"
    description="Recommend suitable enzyme types for a given chemical reaction. Draw or input reaction SMILES to find potential catalyzing enzymes."
  >
    <!-- Reaction Input (JSME + SMILES in one container) -->
    <InputCard title="Reaction Input" hint="Draw the reaction or enter SMILES directly" :wide="true">
      <!-- JSME Reaction Editor -->
      <div class="jsme-wrapper">
        <JSMEEditor
          v-model="reactionSmiles"
          container-id="jsme_reaction_editor"
          height="400px"
          width="100%"
          options="oldlook,star,nocanonize,reaction"
          @jsme-ready="onJSMEReady"
          @structure-change="onStructureChange"
          ref="jsmeEditor"
        />
      </div>
      
      <!-- Reaction SMILES Input -->
      <div class="smiles-input-section">
        <label class="input-label">Reaction SMILES</label>
        <textarea 
          v-model="reactionSmiles" 
          placeholder="e.g., CC(=O)O.CCO>>CC(=O)OCC.O"
          rows="3"
        ></textarea>
        <div class="input-help">
          <span class="help-icon">💡</span>
          <span>Use '>>' to separate substrates from products. Separate multiple molecules with '.'</span>
        </div>
      </div>
      
      <div class="btn-group">
        <button class="btn btn-primary" @click="submit" :disabled="loading">Recommend Enzymes</button>
        <button class="btn btn-secondary" @click="clearAll">Clear</button>
        <button class="btn btn-outline" @click="loadExample">Load Example</button>
      </div>
    </InputCard>

    <ResultBox :show="showResult" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-main" v-if="recommendations.length > 0">
        <div class="ec-results">
          <h4>Prediction Result</h4>
          <div class="ec-card-grid">
            <div v-for="(rec, idx) in recommendations" :key="idx" class="ec-card">
              <div class="ec-number">EC: {{ rec.ec }}</div>
              <div class="ec-confidence">
                Confidence: <span class="confidence-value">{{ rec.confidence }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="result-error" v-else-if="error">{{ error }}</div>
      <div class="no-result" v-else-if="showResult && recommendations.length === 0">
        No valid recommendation result.
      </div>
    </ResultBox>

    <LoadingOverlay 
      :show="loading" 
      text="Analyzing reaction and searching for suitable enzymes..."
    />
  </PageContainer>
</template>

<script setup>
import { ref, computed } from 'vue'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import JSMEEditor from '@/components/JSMEEditor.vue'
import { enzymeApi } from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

const reactionSmiles = ref('')
const loading = ref(false)
const showResult = ref(false)
const recommendations = ref([])
const error = ref('')
const jsmeEditor = ref(null)
const jsmeReady = ref(false)

const resultStatus = computed(() => error.value ? 'error' : 'success')
const resultTitle = computed(() => error.value ? 'Error' : 'Prediction Result')

// JSME event handlers
const onJSMEReady = (event) => {
  jsmeReady.value = event.success
  if (!event.success) {
    console.error('JSME failed to initialize:', event.error)
  }
}

const onStructureChange = (event) => {
  // SMILES is automatically updated via v-model
  console.log('Reaction SMILES updated:', event.smiles)
}

// Parse response format: "EC: X.X.X.X | Confidence: X.XX"
const parseRecommendations = (data) => {
  const results = []
  const lines = data.formatted || data.result || []
  
  if (Array.isArray(lines)) {
    lines.forEach(line => {
      const parts = line.split(' | ')
      const ecPart = parts[0] || ''
      const confPart = parts[1] || ''
      const ec = ecPart.replace('EC: ', '').trim()
      const confidence = confPart.replace('Confidence: ', '').trim()
      
      if (ec) {
        results.push({ ec, confidence })
      }
    })
  }
  
  return results
}

const submit = async () => {
  if (!reactionSmiles.value.trim()) {
    error.value = 'Please enter a reaction SMILES'
    recommendations.value = []
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  recommendations.value = []
  error.value = ''

  try {
    const response = await enzymeApi.recommendEnzymeType({
      query: reactionSmiles.value.trim()
    })

    if (response.error) {
      error.value = response.error
    } else if (response.success && (response.formatted || response.result)) {
      recommendations.value = parseRecommendations(response)
    } else if (response.result && Array.isArray(response.result)) {
      recommendations.value = parseRecommendations(response)
    } else {
      error.value = 'No valid recommendation result'
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
    showResult.value = true
  }
}

const clearAll = () => {
  reactionSmiles.value = ''
  showResult.value = false
  recommendations.value = []
  error.value = ''
  // Clear JSME editor
  if (jsmeEditor.value && jsmeReady.value) {
    jsmeEditor.value.clear()
  }
}

const loadExample = () => {
  // Esterification reaction: acetic acid + ethanol -> ethyl acetate + water
  reactionSmiles.value = 'CC(=O)O.CCO>>CC(=O)OCC.O'
}

const copyResult = () => {
  let text = ''
  if (recommendations.value.length > 0) {
    text = recommendations.value.map(rec => `EC: ${rec.ec} | Confidence: ${rec.confidence}`).join('\n')
  } else if (error.value) {
    text = error.value
  }
  copyToClipboard(text)
  // ResultBox component handles the visual feedback automatically
}
</script>

<style lang="scss" scoped>
.btn-group {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
  flex-wrap: wrap;
}

.input-help {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary-light);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  color: var(--color-text-secondary);
  
  .help-icon {
    flex-shrink: 0;
  }
}

.ec-results {
  h4 {
    color: var(--color-primary);
    margin-bottom: var(--spacing-md);
    font-size: 1.1rem;
  }
}

.ec-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--spacing-md);
}

.ec-card {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  transition: all var(--transition-normal);
  
  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }
  
  .ec-number {
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--color-primary);
    font-family: var(--font-mono);
    margin-bottom: var(--spacing-sm);
  }
  
  .ec-desc {
    font-size: 0.95rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }
  
  .ec-confidence {
    margin-top: var(--spacing-sm);
    font-size: 0.9rem;
    color: var(--color-text-secondary);
    
    .confidence-value {
      color: var(--color-success);
      font-weight: 600;
    }
  }
}

.no-result {
  color: var(--color-text-secondary);
  text-align: center;
  padding: var(--spacing-lg);
}

.result-error {
  color: var(--color-error);
}

.jsme-wrapper {
  width: 100%;
  min-height: 420px;
  margin-bottom: var(--spacing-md);
}

.smiles-input-section {
  margin-bottom: var(--spacing-md);
  
  .input-label {
    display: block;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-xs);
  }
  
  textarea {
    width: 100%;
  }
}
</style>
