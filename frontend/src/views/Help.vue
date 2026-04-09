<template>
  <PageContainer
    title="Help & Documentation"
    description="User guide and API documentation for Enzymind platform"
  >
    <div class="help-content">
      <!-- Quick Start -->
      <section class="help-section">
        <h2>🚀 Quick Start</h2>
        <div class="help-card">
          <p>Enzymind is an integrated enzyme informatics platform providing prediction, query, and analysis tools for enzyme research.</p>
          <ol>
            <li>Select a tool from the navigation menu</li>
            <li>Enter your input (UniProt ID, sequence, SMILES, etc.)</li>
            <li>Click Submit and wait for results</li>
            <li>Download or copy results as needed</li>
          </ol>
        </div>
      </section>

      <!-- Prediction Tools -->
      <section class="help-section">
        <h2>🔮 Prediction Tools</h2>
        
        <div class="tool-card">
          <h3>Enzyme Recognition</h3>
          <p>Determine whether a protein sequence is an enzyme using a deep learning model.</p>
          <div class="input-types">
            <span class="tag">UniProt ID</span>
            <span class="tag">Sequence</span>
            <span class="tag">FASTA file</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>EC Number Prediction</h3>
          <p>Predict the Enzyme Commission (EC) number for an enzyme sequence, indicating its catalytic function.</p>
          <div class="input-types">
            <span class="tag">UniProt ID</span>
            <span class="tag">Sequence</span>
            <span class="tag">FASTA file</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Substrate Prediction</h3>
          <p>Predict whether an enzyme can catalyze a specific substrate molecule.</p>
          <div class="input-types">
            <span class="tag">Enzyme sequence</span>
            <span class="tag">Substrate SMILES</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Kcat Prediction</h3>
          <p>Predict the turnover number (kcat) for an enzyme-substrate pair.</p>
          <div class="input-types">
            <span class="tag">Enzyme sequence</span>
            <span class="tag">Substrate SMILES</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Km Prediction</h3>
          <p>Predict the Michaelis constant (Km) for an enzyme-substrate pair.</p>
          <div class="input-types">
            <span class="tag">Enzyme sequence</span>
            <span class="tag">Substrate SMILES</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Active Site Prediction</h3>
          <p>Predict catalytic residues and their positions using EasIFA.</p>
          <div class="input-types">
            <span class="tag">UniProt ID</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Enzyme Recommendation</h3>
          <p>Recommend suitable enzyme types for a given chemical reaction.</p>
          <div class="input-types">
            <span class="tag">Reaction SMILES</span>
          </div>
        </div>
      </section>

      <!-- Utility Tools -->
      <section class="help-section">
        <h2>🛠️ Utility Tools</h2>
        
        <div class="tool-card">
          <h3>Enzyme Information</h3>
          <p>Query comprehensive enzyme information from UniProt and other databases.</p>
          <div class="input-types">
            <span class="tag">UniProt ID</span>
            <span class="tag">EC Number</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Structure Prediction</h3>
          <p>Predict or retrieve 3D protein structure using ESMFold or AlphaFold.</p>
          <div class="input-types">
            <span class="tag">UniProt ID</span>
            <span class="tag">Sequence</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Sequence Alignment</h3>
          <p>Perform BLAST sequence alignment to find similar enzymes.</p>
          <div class="input-types">
            <span class="tag">FASTA sequence</span>
          </div>
        </div>

        <div class="tool-card">
          <h3>Protein Parameters</h3>
          <p>Calculate physicochemical properties including MW, pI, amino acid composition.</p>
          <div class="input-types">
            <span class="tag">Sequence</span>
          </div>
        </div>
      </section>

      <!-- Input Format Guide -->
      <section class="help-section">
        <h2>📝 Input Formats</h2>
        
        <div class="format-card">
          <h4>UniProt ID</h4>
          <code>P12345</code> or <code>Q9Y6K1</code>
          <p>6-10 character alphanumeric identifier from UniProt database</p>
        </div>

        <div class="format-card">
          <h4>Protein Sequence</h4>
          <code>MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVK...</code>
          <p>One-letter amino acid codes, no spaces or numbers</p>
        </div>

        <div class="format-card">
          <h4>FASTA Format</h4>
          <pre>>sp|P12345|PROTEIN_NAME Description
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEV
QAPILSRVGDGTQDNLSGAEKAVQVKVK</pre>
          <p>Header line starting with &gt; followed by sequence lines</p>
        </div>

        <div class="format-card">
          <h4>SMILES</h4>
          <code>CC(=O)O</code> (acetic acid)
          <p>Simplified Molecular Input Line Entry System notation</p>
        </div>

        <div class="format-card">
          <h4>Reaction SMILES</h4>
          <code>CC(=O)O.CCO>>CC(=O)OCC.O</code>
          <p>Substrates >> Products, molecules separated by .</p>
        </div>

        <div class="format-card">
          <h4>EC Number</h4>
          <code>1.1.1.1</code> or <code>3.4.21.-</code>
          <p>Enzyme Commission classification number</p>
        </div>
      </section>

      <!-- API Reference -->
      <section class="help-section">
        <h2>🔌 API Reference</h2>
        <div class="api-info">
          <p>All API endpoints are available at <code>/api/</code> prefix. Examples:</p>
          <ul>
            <li><code>POST /api/recognize/enzyme</code> - Enzyme recognition</li>
            <li><code>POST /api/predict/ec</code> - EC number prediction</li>
            <li><code>POST /api/predict/substrate</code> - Substrate prediction</li>
            <li><code>POST /api/predict/kcat</code> - Kcat prediction</li>
            <li><code>POST /api/predict/km</code> - Km prediction</li>
            <li><code>POST /api/predict/active-sites</code> - Active site prediction</li>
            <li><code>POST /api/query/structure</code> - Structure retrieval</li>
            <li><code>POST /api/query/blast</code> - BLAST search</li>
          </ul>
        </div>
      </section>

      <!-- Contact -->
      <section class="help-section">
        <h2>📧 Contact & Support</h2>
        <div class="help-card">
          <p>For questions, bug reports, or feature requests:</p>
          <ul>
            <li>GitHub Issues: <a href="#">github.com/enzymind/issues</a></li>
            <li>Email: yinxiaodan@zju.edu.cn</li>
          </ul>
        </div>
      </section>
    </div>
  </PageContainer>
</template>

<script setup>
import PageContainer from '@/components/layout/PageContainer.vue'
</script>

<style lang="scss" scoped>
.help-content {
  max-width: 900px;
  margin: 0 auto;
}

.help-section {
  margin-bottom: var(--spacing-xl);
  
  h2 {
    color: var(--color-primary);
    font-size: 1.5rem;
    margin-bottom: var(--spacing-lg);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-primary-light);
  }
}

.help-card {
  background: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  
  ol, ul {
    margin: var(--spacing-md) 0;
    padding-left: var(--spacing-lg);
  }
  
  li {
    margin: var(--spacing-sm) 0;
    line-height: 1.6;
  }
}

.tool-card {
  background: white;
  padding: var(--spacing-md) var(--spacing-lg);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--spacing-md);
  border-left: 4px solid var(--color-primary);
  
  h3 {
    color: var(--color-primary);
    margin-bottom: var(--spacing-sm);
    font-size: 1.1rem;
  }
  
  p {
    color: var(--color-text-secondary);
    margin-bottom: var(--spacing-sm);
  }
}

.input-types {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  
  .tag {
    background: var(--color-primary-light);
    color: var(--color-primary);
    padding: 4px 10px;
    border-radius: var(--radius-full);
    font-size: 0.8rem;
    font-weight: 500;
  }
}

.format-card {
  background: white;
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--spacing-md);
  
  h4 {
    color: var(--color-text-primary);
    margin-bottom: var(--spacing-sm);
  }
  
  code {
    background: #f4f4f4;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 0.9rem;
  }
  
  pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: var(--spacing-md);
    border-radius: var(--radius-sm);
    margin: var(--spacing-sm) 0;
    font-family: var(--font-mono);
    font-size: 0.85rem;
    overflow-x: auto;
  }
  
  p {
    color: var(--color-text-secondary);
    font-size: 0.9rem;
    margin-top: var(--spacing-sm);
  }
}

.api-info {
  background: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  
  code {
    background: #f4f4f4;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 0.85rem;
  }
  
  ul {
    margin: var(--spacing-md) 0;
    padding-left: var(--spacing-lg);
  }
  
  li {
    margin: var(--spacing-sm) 0;
    font-family: var(--font-mono);
    font-size: 0.9rem;
  }
}
</style>
