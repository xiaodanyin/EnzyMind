<template>
  <PageContainer
    title="Enzyme Information"
    description="Query comprehensive enzyme information from UniProt, Brenda, and other databases by UniProt ID."
  >
    <InputCard title="Query by UniProt ID" hint="Enter a UniProt accession number to get enzyme details" :wide="true">
      <input type="text" v-model="uniprotId" placeholder="e.g., P12345" @keyup.enter="queryByUniprot" />
      <div class="btn-group">
        <button class="btn btn-primary" @click="queryByUniprot" :disabled="loading">Query</button>
        <button class="btn btn-secondary" @click="clearAll">Clear</button>
        <button class="btn btn-outline" @click="loadExample">Load Example</button>
      </div>
    </InputCard>

    <ResultBox :show="showResult" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-main" v-if="result">
        <!-- Basic Information -->
        <div class="info-section">
          <h4><span class="section-icon">✅</span> Basic Information</h4>
          <table class="info-table">
            <tr>
              <th>UniProt ID</th>
              <td>{{ result.uniprot_id }}</td>
            </tr>
            <tr v-if="sequenceInfo.length">
              <th>Sequence Length</th>
              <td>{{ sequenceInfo.length }} aa</td>
            </tr>
            <tr v-if="sequenceInfo.mol_weight">
              <th>Molecular Weight</th>
              <td>{{ sequenceInfo.mol_weight }} Da</td>
            </tr>
            <tr v-if="sequenceInfo.sequence">
              <th>Sequence</th>
              <td class="sequence-cell">
                <code class="sequence-code">{{ displaySequence }}</code>
                <button v-if="sequenceInfo.sequence.length > 60" 
                        class="btn btn-sm" 
                        @click="toggleSequence">
                  {{ seqExpanded ? '🔼' : '🔽' }}
                </button>
              </td>
            </tr>
          </table>
        </div>

        <!-- Catalytic Activities -->
        <div v-if="catalyticActivities.length > 0" class="info-section">
          <h4><span class="section-icon">✅</span> Catalytic Activities</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th>EC</th>
                <th>Reaction</th>
                <th>Rhea</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(activity, idx) in catalyticActivities" :key="idx">
                <td class="nowrap">{{ activity.ec_number || 'N/A' }}</td>
                <td>{{ activity.reaction || 'Unknown' }}</td>
                <td class="nowrap">{{ activity.rhea_id || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Functional Sites -->
        <div v-if="functionalSites.length > 0" class="info-section">
          <h4><span class="section-icon">✅</span> Functional Sites</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th>Position</th>
                <th>Type</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(site, idx) in functionalSites" :key="idx">
                <td class="nowrap">{{ formatPosition(site) }}</td>
                <td class="nowrap">{{ site.type }}</td>
                <td>{{ site.description || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Kinetic Parameters -->
        <div v-if="hasKineticParams" class="info-section">
          <h4><span class="section-icon">✅</span> Kinetic Parameters</h4>
          
          <!-- Km -->
          <div v-if="kineticParams.km && kineticParams.km.length > 0">
            <h5>K<sub>m</sub></h5>
            <table class="data-table">
              <thead>
                <tr>
                  <th>Value</th>
                  <th>Unit</th>
                  <th>Substrate</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(k, idx) in kineticParams.km" :key="idx">
                  <td>{{ k.value }}</td>
                  <td>{{ k.unit }}</td>
                  <td>{{ k.substrate }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Vmax -->
          <div v-if="kineticParams.vmax && kineticParams.vmax.length > 0">
            <h5>V<sub>max</sub></h5>
            <table class="data-table">
              <thead>
                <tr>
                  <th>Value</th>
                  <th>Unit</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(v, idx) in kineticParams.vmax" :key="idx">
                  <td>{{ v.value }}</td>
                  <td>{{ v.unit }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Kcat note -->
          <div v-if="kineticParams.kcat_note" class="kcat-note">
            <strong>k<sub>cat</sub> note:</strong> {{ kineticParams.kcat_note }}
          </div>
        </div>
      </div>

      <!-- Not an enzyme -->
      <div v-else-if="notEnzyme" class="result-warning">
        ⚠️ {{ notEnzymeMessage }}
      </div>

      <!-- Error -->
      <div class="result-error" v-else-if="error">{{ error }}</div>
    </ResultBox>

    <LoadingOverlay :show="loading" text="Retrieving enzyme info..." />
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

const uniprotId = ref('')
const loading = ref(false)
const showResult = ref(false)
const result = ref(null)
const error = ref('')
const notEnzyme = ref(false)
const notEnzymeMessage = ref('')
const seqExpanded = ref(false)

const resultStatus = computed(() => {
  if (error.value) return 'error'
  if (notEnzyme.value) return 'warning'
  return 'success'
})

const resultTitle = computed(() => {
  if (error.value) return 'Error'
  if (notEnzyme.value) return 'Not an Enzyme'
  return 'Enzyme Info'
})

const sequenceInfo = computed(() => result.value?.sequence_info || {})
const catalyticActivities = computed(() => result.value?.catalytic_activities || [])
const functionalSites = computed(() => result.value?.functional_sites || [])
const kineticParams = computed(() => result.value?.kinetic_parameters || {})

const hasKineticParams = computed(() => {
  const kp = kineticParams.value
  return (kp.km && kp.km.length > 0) || 
         (kp.vmax && kp.vmax.length > 0) || 
         kp.kcat_note
})

const displaySequence = computed(() => {
  const seq = sequenceInfo.value?.sequence || ''
  if (seqExpanded.value || seq.length <= 60) return seq
  return seq.slice(0, 60) + '…'
})

const toggleSequence = () => {
  seqExpanded.value = !seqExpanded.value
}

// Format position from start/end to display string
const formatPosition = (site) => {
  const start = site.start
  const end = site.end
  if (start != null && end != null) {
    return start === end ? `${start}` : `${start}-${end}`
  }
  if (start != null) return `${start}`
  if (end != null) return `${end}`
  return '-'
}

const queryByUniprot = async () => {
  if (!uniprotId.value.trim()) {
    error.value = 'Please enter a UniProt ID'
    result.value = null
    showResult.value = true
    return
  }

  loading.value = true
  showResult.value = false
  result.value = null
  error.value = ''
  notEnzyme.value = false
  notEnzymeMessage.value = ''

  try {
    const response = await enzymeApi.getEnzymeFullInfo({
      uniprot_id: uniprotId.value.trim()
    })
    
    if (response.error) {
      error.value = response.error
    } else if (response.is_enzyme === false) {
      notEnzyme.value = true
      notEnzymeMessage.value = response.message || 'This protein is not classified as an enzyme.'
    } else {
      result.value = response
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
    showResult.value = true
  }
}

const clearAll = () => {
  uniprotId.value = ''
  showResult.value = false
  result.value = null
  error.value = ''
  notEnzyme.value = false
  seqExpanded.value = false
}

// Load example data
const loadExample = () => {
  uniprotId.value = 'P00761' // Trypsin - a well-characterized serine protease
}

const copyResult = () => {
  let text = ''
  if (result.value) {
    text = JSON.stringify(result.value, null, 2)
  } else if (notEnzymeMessage.value) {
    text = notEnzymeMessage.value
  } else if (error.value) {
    text = error.value
  }
  copyToClipboard(text)
}
</script>

<style lang="scss" scoped>
.btn-group {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.info-section {
  margin-bottom: var(--spacing-xl);
  
  h4 {
    color: var(--color-text);
    margin-bottom: var(--spacing-md);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-primary-light);
    font-size: 1.1rem;
    
    .section-icon {
      color: var(--color-success);
      margin-right: var(--spacing-sm);
    }
  }
  
  h5 {
    color: var(--color-text-secondary);
    margin: var(--spacing-md) 0 var(--spacing-sm);
    font-size: 1rem;
  }
}

.info-table {
  width: 100%;
  border-collapse: collapse;
  
  th, td {
    padding: 12px 16px;
    border: 1px solid var(--color-border);
    text-align: left;
  }
  
  th {
    width: 180px;
    background: var(--color-primary-light);
    font-weight: 600;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }
  
  td {
    color: var(--color-text-primary);
  }
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: var(--spacing-md);
  
  th, td {
    padding: 10px 14px;
    border: 1px solid var(--color-border);
    text-align: left;
  }
  
  thead th {
    background: var(--color-primary-light);
    font-weight: 600;
  }
  
  .nowrap {
    white-space: nowrap;
  }
}

.sequence-cell {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.sequence-code {
  word-break: break-all;
  color: #d63384;
  font-family: var(--font-mono);
  font-size: 0.9rem;
}

.btn-sm {
  padding: 2px 8px;
  font-size: 0.75rem;
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  
  &:hover {
    background: var(--color-primary-light);
  }
}

.kcat-note {
  margin-top: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-primary-light);
  border-radius: var(--radius-sm);
}

.result-warning {
  color: var(--color-warning);
  font-size: 1.1rem;
}

.result-error {
  color: var(--color-error);
}
</style>
