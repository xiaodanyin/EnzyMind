import axios from 'axios'

const api = axios.create({
  baseURL: '/enzymind/api',
  timeout: 300000, // 5 minutes for long-running predictions
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add any request preprocessing here
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.error || error.message || 'An error occurred'
    return Promise.reject(new Error(message))
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
