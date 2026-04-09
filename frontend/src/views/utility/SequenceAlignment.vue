<template>
  <PageContainer
    title="Sequence Alignment"
    description="Perform BLAST sequence alignment to find similar enzymes in public databases."
  >
    <InputCard title="Query Sequence" hint="Enter a protein sequence to search against NCBI nr database" :wide="true">
      <textarea 
        v-model="sequence" 
        placeholder="Enter amino acid sequence (FASTA format or plain sequence)..."
        rows="6"
      ></textarea>
      <div class="options-row">
        <div class="option-group">
          <label>Database</label>
          <select v-model="database">
            <option value="nr">NCBI nr (Non-redundant)</option>
            <option value="swissprot">SwissProt</option>
            <option value="pdb">PDB</option>
          </select>
        </div>
        <div class="option-group">
          <label>E-value threshold</label>
          <select v-model="evalue">
            <option value="1e-10">1e-10 (Very stringent)</option>
            <option value="1e-5">1e-5 (Stringent)</option>
            <option value="0.01">0.01 (Moderate)</option>
            <option value="1">1 (Relaxed)</option>
          </select>
        </div>
        <div class="option-group">
          <label>Max hits</label>
          <select v-model="maxHits">
            <option value="10">10</option>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="500">500</option>
          </select>
        </div>
      </div>
      <div class="btn-group">
        <button class="btn btn-primary" @click="runBlast" :disabled="loading">Run BLAST</button>
        <button class="btn btn-secondary" @click="clearAll">Clear</button>
        <button class="btn btn-outline" @click="loadExample">Load Example</button>
      </div>
    </InputCard>

    <ResultBox :show="showResult" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-main" v-if="result">
        <!-- HTML Result from backend -->
        <div v-if="result.html" class="html-result" v-html="result.html"></div>
        
        <!-- Alignments array result -->
        <div v-else-if="result.alignments && result.alignments.length > 0" class="alignments-section">
          <div class="query-info" v-if="result.queryLength">
            <span>Query length: {{ result.queryLength }} aa</span>
            <span>Results: {{ result.numResults }}</span>
          </div>
          <div v-for="(align, idx) in result.alignments" :key="idx" class="alignment-card">
            <h5 class="alignment-title">
              <span class="success-icon">✅</span> Alignment {{ idx + 1 }}
            </h5>
            <ul class="alignment-details">
              <li><strong>Sequence:</strong> {{ align.title || 'Unknown' }}</li>
              <li><strong>Length:</strong> {{ align.length || 'N/A' }}</li>
              <li><strong>E-value:</strong> {{ formatEvalue(align.e_value) }}</li>
              <li v-if="align.score"><strong>Score:</strong> {{ align.score }}</li>
              <li v-if="align.identities"><strong>Identities:</strong> {{ align.identities }}</li>
            </ul>
            <div class="alignment-sequences">
              <pre v-if="align.query"><strong>Query:</strong>   {{ align.query }}</pre>
              <pre v-if="align.match"><strong>Match:</strong>   {{ align.match }}</pre>
              <pre v-if="align.subject"><strong>Subject:</strong> {{ align.subject }}</pre>
            </div>
          </div>
        </div>

        <!-- No results -->
        <div v-else class="no-results">
          No alignments found for the given query.
        </div>
      </div>
      <div class="result-error" v-else-if="error">{{ error }}</div>
    </ResultBox>

    <LoadingOverlay 
      :show="loading" 
      text="Running BLAST search..."
      hint="This may take 1-3 minutes depending on database size"
    />
  </PageContainer>
</template>

<script setup>
import { ref, computed } from 'vue'
import PageContainer from '@/components/layout/PageContainer.vue'
import InputCard from '@/components/common/InputCard.vue'
import ResultBox from '@/components/common/ResultBox.vue'
import LoadingOverlay from '@/components/common/LoadingOverlay.vue'
import { enzymeApi } from '@/api'
import { copyToClipboard } from '@/utils/clipboard'

const sequence = ref('')
const database = ref('nr')
const evalue = ref('1e-5')
const maxHits = ref('50')
const loading = ref(false)
const showResult = ref(false)
const result = ref(null)
const error = ref('')

const resultStatus = computed(() => error.value ? 'error' : 'success')
const resultTitle = computed(() => error.value ? 'Error' : 'Alignment Results')

const runBlast = async () => {
  if (!sequence.value.trim()) {
    error.value = 'Please enter a protein sequence'
    result.value = null
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  result.value = null
  error.value = ''

  try {
    const response = await enzymeApi.blastSearch({
      query: sequence.value.trim(),
      max_results: parseInt(maxHits.value)
    })
    
    console.log('[DEBUG] BLAST Response:', response)
    
    if (response.error) {
      error.value = response.error
    } else if (response.success === false) {
      error.value = response.error || 'BLAST search failed'
    } else if (response.result) {
      // Backend returns HTML in result field (legacy endpoint)
      result.value = { html: response.result }
    } else if (response.success && response.alignments !== undefined) {
      // Backend returns structured alignments (JSON endpoint)
      if (response.alignments && response.alignments.length > 0) {
        result.value = { 
          alignments: response.alignments,
          queryLength: response.query_length,
          numResults: response.num_results
        }
      } else {
        error.value = 'No significant alignments found for the given query'
      }
    } else {
      error.value = 'Unexpected response format from BLAST query'
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
    showResult.value = true
  }
}

const clearAll = () => {
  sequence.value = ''
  showResult.value = false
  result.value = null
  error.value = ''
}

const loadExample = () => {
  // Example: human lysozyme
  sequence.value = `>sp|P61626|LYSC_HUMAN Lysozyme C
MKALIVLGLVLLSVTVQGKVFERCELARTLKRLGMDGYRGISLANWMCLAKWESGYNTRATNYNAGDRSTDYGIFQINSRYWCNDGKTPGAVNACHLSCSALLQDNIADAVACAKRVVRDPQGIRAWVAWRNRCQNRDVRQYVQGCGV`
}

const formatEvalue = (val) => {
  if (val === undefined || val === null) return 'N/A'
  if (val < 0.0001) return val.toExponential(2)
  return val.toFixed(4)
}

const copyResult = () => {
  let text = ''
  if (result.value?.html) {
    // Extract text from HTML
    const div = document.createElement('div')
    div.innerHTML = result.value.html
    text = div.innerText
  } else if (result.value?.alignments) {
    text = result.value.alignments.map(a => 
      `${a.title}\nE-value: ${a.e_value}\nQuery: ${a.query}\nSubject: ${a.subject}`
    ).join('\n\n')
  } else if (error.value) {
    text = error.value
  }
  copyToClipboard(text)
  // ResultBox component handles the visual feedback automatically
}
</script>

<style lang="scss" scoped>
.options-row {
  display: flex;
  gap: var(--spacing-lg);
  margin: var(--spacing-md) 0;
  flex-wrap: wrap;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  
  label {
    font-size: 0.9rem;
    color: var(--color-text-secondary);
    font-weight: 500;
  }
  
  select {
    padding: 8px 12px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: white;
    min-width: 180px;
  }
}

.btn-group {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.html-result {
  :deep(.alignment-result) {
    margin-bottom: 20px;
    padding: 15px;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: #fafafa;
    
    h4 {
      color: var(--color-primary);
      margin-bottom: 10px;
    }
    
    p {
      margin: 5px 0;
      color: var(--color-text-secondary);
    }
    
    pre {
      font-family: var(--font-mono);
      font-size: 0.85rem;
      margin: 5px 0;
      padding: 8px;
      background: #f0f0f0;
      border-radius: 4px;
      overflow-x: auto;
    }
  }
  
  :deep(.pred-class) {
    padding: 10px;
    border-radius: var(--radius-sm);
    
    &.error {
      color: var(--color-error);
      background: #fff5f5;
    }
  }
}

.alignments-section {
  .query-info {
    display: flex;
    gap: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--color-primary-light);
    border-radius: var(--radius-sm);
    font-size: 0.9rem;
    color: var(--color-text-secondary);
  }
}

.alignment-card {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md) var(--spacing-lg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #fff;
  
  .alignment-title {
    color: #2f8f2f;
    font-weight: 600;
    font-size: 1.1rem;
    margin-bottom: var(--spacing-md);
    
    .success-icon {
      margin-right: var(--spacing-xs);
    }
  }
}

.alignment-details {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--spacing-md) 0;
  font-size: 1rem;
  line-height: 1.8;
  
  li {
    strong {
      color: var(--color-text);
    }
    
    color: var(--color-text-secondary);
  }
}

.alignment-sequences {
  pre {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    margin: 4px 0;
    padding: 8px 12px;
    background: #f0f0f0;
    border-radius: 4px;
    overflow-x: auto;
    white-space: pre;
  }
}

.no-results {
  text-align: center;
  color: var(--color-text-secondary);
  padding: var(--spacing-lg);
}

.result-error {
  color: var(--color-error);
}
</style>
