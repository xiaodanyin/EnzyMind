import axios from 'axios'
import { getAccessKey, platformResults } from '@/utils/workspace'

const api = axios.create({
  baseURL: '/enzymind/api',
  timeout: 960000, // Cover the ordinary service's 15-minute deadline plus transport.
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Cover the backend job deadline, including cold model loading / NCBI queueing.
    if (config.url?.startsWith('/predict/structure')) config.timeout = 3720000
    else if (config.url?.startsWith('/query/blast')) config.timeout = 1020000
    config.headers['X-Enzymind-Client'] = getAccessKey()
    if (config.method === 'post') platformResults[config.url] = null
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    if (response.data?.workspace_result) {
      const { workspace_result, ...payload } = response.data
      platformResults[response.config.url] = { ...workspace_result, payload }
    }
    return response.data
  },
  (error) => {
    if (error.response?.data?.workspace_result) {
      const { workspace_result, ...payload } = error.response.data
      platformResults[error.config.url] = { ...workspace_result, payload }
    }
    const message = error.response?.data?.error || error.response?.data?.detail || error.message || 'An error occurred'
    const failure = new Error(typeof message === 'string' ? message : JSON.stringify(message))
    if (error.response?.data?.workspace_result) {
      const { workspace_result, ...payload } = error.response.data
      failure.workspaceResult = { ...workspace_result, payload }
    }
    return Promise.reject(failure)
  }
)

// API functions for different services
export const enzymeApi = {
  // Enzyme Recognition (8001)
  // Request: { input_type: 'uniprot'|'sequence'|'fasta', query: string }
  recognizeEnzyme(data) {
    return api.post('/recognize/enzyme', data)
  },

  // EC Number Prediction (8002)
  // Request: { input_type: 'uniprot'|'sequence'|'fasta', query: string }
  predictEC(data) {
    return api.post('/predict/ec', data)
  },

  // Substrate Prediction (8003)
  // Request: { smiles: string, enzyme_input_type: string, enzyme_query: string }
  predictSubstrate(data) {
    return api.post('/predict/substrate', data)
  },

  // Kcat Prediction (8004)
  // Request: { smiles: string, enzyme_input_type: string, enzyme_query: string }
  predictKcat(data) {
    return api.post('/predict/kcat', data)
  },

  // Km Prediction (8005)
  // Request: { smiles: string, enzyme_input_type: string, enzyme_query: string }
  predictKm(data) {
    return api.post('/predict/km', data)
  },

  // Structure Prediction (8006)
  // Request: { query: string, input_type: 'uniprot'|'sequence'|'fasta', output_name?: string }
  predictStructure(data) {
    return api.post('/predict/structure', data)
  },

  // Active Sites Prediction (8007)
  // Request: { uniprot_id?: string, aa_sequence?: string, rxn_smiles?: string, timeout?: number }
  // Provide either uniprot_id or aa_sequence
  predictActiveSites(data) {
    return api.post('/predict/active-sites', data)
  },

  // Enzyme Type Recommendation (8008)
  // Request: { query: string } - reaction SMILES
  recommendEnzymeType(data) {
    return api.post('/query/enzyme-type', data)
  },

  // Protein Parameters (8009)
  // Request: { query: string } - protein sequence
  getProteinParams(data) {
    return api.post('/query/protein-physchem', data)
  },

  // BLAST Sequence Alignment (8010)
  // Request: { query: string, max_results?: number }
  blastSearch(data) {
    return api.post('/query/blast', data)
  },

  // Enzyme Check (8014)
  // Request: { uniprot_id: string }
  checkEnzyme(data) {
    return api.post('/check/enzyme', data)
  },

  // Enzyme Full Info (8015)
  // Request: { uniprot_id: string }
  getEnzymeFullInfo(data) {
    return api.post('/query/enzyme-full-info', data)
  },

  // Sequence Info (8018)
  // Request: { uniprot_id: string }
  getSequenceInfo(data) {
    return api.post('/query/sequence-info', data)
  },
}

export default api
