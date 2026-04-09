<template>
  <PageContainer
    title="Protein Parameters"
    description="Calculate physicochemical properties of a protein sequence including molecular weight, pI, amino acid composition, and more."
  >
    <InputCard title="Protein Sequence" hint="Enter an amino acid sequence to analyze" :wide="true">
      <textarea 
        v-model="sequence" 
        placeholder="Enter amino acid sequence (one-letter code, FASTA format accepted)..."
        rows="5"
      ></textarea>
      <div class="btn-group">
        <button class="btn btn-primary" @click="analyze" :disabled="loading">Analyze</button>
        <button class="btn btn-secondary" @click="clearAll">Clear</button>
        <button class="btn btn-outline" @click="loadExample">Load Example</button>
      </div>
    </InputCard>

    <ResultBox :show="showResult" :status="resultStatus" :title="resultTitle" @copy="copyResult">
      <div class="result-main" v-if="result">
        <!-- Basic Properties -->
        <div class="result-card" v-if="basicParams">
          <h4><span class="success-icon">✅</span> Basic Properties</h4>
          <div class="param-line"><strong>Number of amino acids:</strong> {{ basicParams.numAminoAcids }}</div>
          <div class="param-line"><strong>Theoretical pI:</strong> {{ basicParams.theoreticalPi }}</div>
          <div class="param-line"><strong>Molecular weight:</strong> {{ basicParams.molecularWeight }}</div>
        </div>

        <!-- Charge Information -->
        <div class="result-card" v-if="chargeInfo">
          <h4><span class="success-icon">✅</span> Charge Information</h4>
          <div class="param-line"><strong>Negatively charged residues:</strong> {{ chargeInfo.negativeResidues }}</div>
          <div class="param-line"><strong>Positively charged residues:</strong> {{ chargeInfo.positiveResidues }}</div>
        </div>

        <!-- Amino Acid Composition -->
        <div class="result-card" v-if="aminoAcidComposition.length > 0">
          <h4><span class="success-icon">✅</span> Amino Acid Composition</h4>
          <table class="aa-table">
            <thead>
              <tr>
                <th>Residue</th>
                <th>Count</th>
                <th>Ratio</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="aa in aminoAcidComposition" :key="aa.letter">
                <td>{{ aa.name }} ({{ aa.letter }})</td>
                <td>{{ aa.count }}</td>
                <td>{{ aa.ratio }}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Atomic Composition -->
        <div class="result-card" v-if="atomicComposition.length > 0">
          <h4><span class="success-icon">✅</span> Atomic Composition</h4>
          <table class="aa-table">
            <thead>
              <tr>
                <th>Element</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="atom in atomicComposition" :key="atom.symbol">
                <td>{{ atom.name }} ({{ atom.symbol }})</td>
                <td>{{ atom.count }}</td>
              </tr>
            </tbody>
          </table>
          <div class="param-line" style="margin-top: 12px;" v-if="atomicInfo">
            <strong>Formula:</strong> {{ atomicInfo.formula }}
          </div>
          <div class="param-line" v-if="atomicInfo">
            <strong>Total number of atoms:</strong> {{ atomicInfo.totalAtoms }}
          </div>
        </div>
      </div>
      <div class="result-error" v-else-if="error">{{ error }}</div>
    </ResultBox>

    <LoadingOverlay :show="loading" text="Calculating protein parameters..." />
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
const loading = ref(false)
const showResult = ref(false)
const result = ref(null)
const error = ref('')

const resultStatus = computed(() => error.value ? 'error' : 'success')
const resultTitle = computed(() => error.value ? 'Error' : 'Protein Parameters')

// 从 markdown 文本中提取行内容
const extractLine = (text, prefix) => {
  if (!text) return 'N/A'
  const line = text.split('\n').find(l => l.includes(prefix))
  return line ? line.split(':').slice(1).join(':').trim() : 'N/A'
}

// 从 markdown 中提取代码块内容
const extractBlock = (text, startMarker, endMarker) => {
  if (!text) return []
  const lines = text.split('\n')
  const start = lines.findIndex(l => l.includes(startMarker))
  const end = endMarker 
    ? lines.findIndex((l, i) => i > start && l.includes(endMarker)) 
    : lines.length
  if (start === -1) return []
  return lines.slice(start + 1, end > start ? end : undefined)
}

// 解析氨基酸组成
const parseAminoAcidComposition = (text) => {
  const rows = extractBlock(text, 'Amino acid composition:', 'Total number of negatively')
    .filter(l => l.includes('('))
  const composition = []
  rows.forEach(row => {
    const match = row.match(/- ([A-Za-z]{3}) \((.)\)\s+(\d+)\s+([\d.]+)%/)
    if (match) {
      composition.push({
        name: match[1],
        letter: match[2],
        count: parseInt(match[3]),
        ratio: parseFloat(match[4])
      })
    }
  })
  return composition
}

// 解析原子组成
const parseAtomicComposition = (text) => {
  const rows = extractBlock(text, 'Atomic composition:', 'Extinction coefficients:')
    .filter(l => l.includes('- '))
  const composition = []
  rows.forEach(row => {
    const match = row.match(/- ([A-Za-z]+)\s+([A-Z])\s+(\d+)/)
    if (match) {
      composition.push({
        name: match[1],
        symbol: match[2],
        count: parseInt(match[3])
      })
    }
  })
  return composition
}

// 计算属性：基本参数
const basicParams = computed(() => {
  if (!result.value?.markdown) return null
  const md = result.value.markdown
  return {
    numAminoAcids: extractLine(md, 'Number of amino acids'),
    theoreticalPi: extractLine(md, 'Theoretical pI'),
    molecularWeight: extractLine(md, 'Molecular weight')
  }
})

// 计算属性：电荷信息
const chargeInfo = computed(() => {
  if (!result.value?.markdown) return null
  const md = result.value.markdown
  return {
    negativeResidues: extractLine(md, 'negatively charged'),
    positiveResidues: extractLine(md, 'positively charged')
  }
})

// 计算属性：氨基酸组成
const aminoAcidComposition = computed(() => {
  if (!result.value?.markdown) return []
  return parseAminoAcidComposition(result.value.markdown)
})

// 计算属性：原子组成
const atomicComposition = computed(() => {
  if (!result.value?.markdown) return []
  return parseAtomicComposition(result.value.markdown)
})

// 计算属性：原子总数和分子式
const atomicInfo = computed(() => {
  if (!result.value?.markdown) return null
  const md = result.value.markdown
  return {
    formula: extractLine(md, 'Formula'),
    totalAtoms: extractLine(md, 'Total number of atoms')
  }
})

const analyze = async () => {
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
    const response = await enzymeApi.getProteinParams({
      query: sequence.value.trim()
    })
    
    console.log('[DEBUG] ProtParam Response:', response)
    
    if (response.error) {
      error.value = response.error
    } else if (response.result) {
      // Legacy format: { result: markdown_string }
      result.value = { markdown: response.result }
    } else if (response.markdown) {
      // New format: { success: true, markdown: string }
      result.value = { markdown: response.markdown }
    } else {
      error.value = 'No valid result returned'
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
  sequence.value = `>sp|P00698|LYSC_CHICK Lysozyme C
KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL`
}

const copyResult = () => {
  let text = result.value?.markdown || error.value || ''
  copyToClipboard(text)
  // ResultBox component handles the visual feedback automatically
}
</script>

<style lang="scss" scoped>
.btn-group {
  display: flex;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.result-card {
  background: #fff;
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  
  h4 {
    color: var(--color-text);
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: var(--spacing-md);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-primary-light);
    
    .success-icon {
      margin-right: var(--spacing-sm);
    }
  }
}

.param-line {
  font-size: 1rem;
  line-height: 1.8;
  color: var(--color-text-secondary);
  
  strong {
    color: var(--color-text);
  }
}

.aa-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: var(--spacing-sm);
  
  th, td {
    padding: 8px 12px;
    border: 1px solid var(--color-border);
    text-align: left;
  }
  
  th {
    background: var(--color-primary-light);
    font-weight: 600;
    color: var(--color-text);
  }
  
  td {
    color: var(--color-text-secondary);
  }
  
  tr:nth-child(even) {
    background: #fafafa;
  }
}

.result-error {
  color: var(--color-error);
}
</style>
