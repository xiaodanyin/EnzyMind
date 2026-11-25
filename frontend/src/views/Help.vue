<template>
  <PageContainer
    title="Help & Documentation"
    description="User guide and API documentation for EnzyMind platform"
    allow-overflow
  >
    <button
      class="mobile-help-nav-toggle"
      :class="{ active: mobileHelpNavOpen }"
      type="button"
      :aria-expanded="mobileHelpNavOpen"
      aria-controls="help-section-navigation"
      @click="toggleMobileHelpNav"
    >
      <span class="mobile-help-nav-icon" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </span>
      <span>{{ mobileHelpNavOpen ? 'Close' : 'Menu' }}</span>
    </button>

    <div
      class="mobile-help-nav-overlay"
      :class="{ active: mobileHelpNavOpen }"
      aria-hidden="true"
      @click="toggleMobileHelpNav"
    ></div>

    <div class="help-layout">
      <aside class="help-sidebar">
        <nav
          id="help-section-navigation"
          class="section-nav"
          :class="{ 'is-sticky': isHelpNavSticky, 'mobile-open': mobileHelpNavOpen }"
          aria-label="Help sections"
        >
          <div class="section-nav-heading">
            <span class="section-nav-mark" aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </span>
            <span>
              <small>Help index</small>
              On this page
            </span>
          </div>
          <ol>
            <li v-for="section in helpSections" :key="section.id">
              <a
                :href="`#${section.id}`"
                :class="{ active: activeHelpSection === section.id }"
                :aria-current="activeHelpSection === section.id ? 'location' : undefined"
                @click.prevent="scrollToHelpSection(section.id)"
              >
                <span class="section-nav-icon" aria-hidden="true">{{ section.icon }}</span>
                <span class="section-nav-label">{{ section.label }}</span>
              </a>
            </li>
          </ol>
        </nav>
      </aside>

      <main class="help-content">
      <!-- Quick Start -->
      <section id="quick-start" class="help-section">
        <h2><span class="section-icon">🚀</span> Quick Start</h2>
        
        <HelpQuickStart />
      </section>

      <!-- API Base URL -->
      <section id="api-base-url" class="help-section">
        <h2><span class="section-icon">🌐</span> API Base URL</h2>
        <div class="base-url-card">
          <div class="base-url-display">
            <span class="protocol">https://</span>
            <span class="domain">cadd.zju.edu.cn</span>
            <span class="base-path">/enzymind/api/</span>
          </div>
          <p class="base-url-note">Append the endpoint paths below to this base URL</p>
        </div>
      </section>

      <!-- Prediction Tools -->
      <section id="prediction-tools" class="help-section">
        <h2><span class="section-icon">🔮</span> Prediction Tools</h2>
        
        <!-- API Card Component Template -->
        <ApiCard 
          v-for="api in predictionApis" 
          :key="api.id"
          :api="api"
          :expanded="expandedCards[api.id]"
          :loading="loading[api.id]"
          :response="responses[api.id]"
          :http-status="responseStatus[api.id]"
          :copy-success="copySuccess[api.id]"
          @toggle="toggleCard"
          @copy-curl="copyCurl"
          @try-api="tryApi"
        />
      </section>

      <!-- Query Tools -->
      <section id="query-tools" class="help-section">
        <h2><span class="section-icon">🔍</span> Query Tools</h2>
        <ApiCard 
          v-for="api in queryApis" 
          :key="api.id"
          :api="api"
          :expanded="expandedCards[api.id]"
          :loading="loading[api.id]"
          :response="responses[api.id]"
          :http-status="responseStatus[api.id]"
          :copy-success="copySuccess[api.id]"
          @toggle="toggleCard"
          @copy-curl="copyCurl"
          @try-api="tryApi"
        />
      </section>

      <!-- Utility Tools -->
      <section id="utility-tools" class="help-section">
        <h2><span class="section-icon">🛠️</span> Utility Tools</h2>
        <ApiCard 
          v-for="api in utilityApis" 
          :key="api.id"
          :api="api"
          :expanded="expandedCards[api.id]"
          :loading="loading[api.id]"
          :response="responses[api.id]"
          :http-status="responseStatus[api.id]"
          :copy-success="copySuccess[api.id]"
          @toggle="toggleCard"
          @copy-curl="copyCurl"
          @try-api="tryApi"
        />
      </section>

      <!-- Input Format Guide -->
      <section id="input-formats" class="help-section">
        <h2><span class="section-icon">📝</span> Input Formats</h2>
        <div class="format-grid">
          <div class="format-card">
            <h4>UniProt ID</h4>
            <code>P12345</code> or <code>Q9Y6K1</code>
            <p>6-10 character alphanumeric identifier from UniProt database</p>
          </div>
          <div class="format-card">
            <h4>Protein Sequence</h4>
            <code>MKTAYIAKQRQISFVKSHFS...</code>
            <p>One-letter amino acid codes, no spaces or numbers</p>
          </div>
          <div class="format-card">
            <h4>FASTA Format</h4>
            <pre>>sp|P12345|PROTEIN_NAME
MKTAYIAKQRQISFVKSHFS...</pre>
            <p>Header line starting with &gt; followed by sequence</p>
          </div>
          <div class="format-card">
            <h4>SMILES</h4>
            <code>CC(=O)O</code>
            <p>Simplified Molecular Input Line Entry System</p>
          </div>
          <div class="format-card">
            <h4>Reaction SMILES</h4>
            <code>CC(=O)O.CCO>>CC(=O)OCC.O</code>
            <p>Substrates >> Products, separated by .</p>
          </div>
          <div class="format-card">
            <h4>EC Number</h4>
            <code>1.1.1.1</code> or <code>3.4.21.-</code>
            <p>Enzyme Commission classification number</p>
          </div>
        </div>
      </section>

      <!-- MCP & Agent Skill -->
      <section id="mcp-agent-skill" class="help-section extension-section">
        <h2><span class="section-icon">⌘</span> MCP & Agent Skill</h2>

        <div class="extension-hero">
          <div>
            <span class="extension-kicker">17 read-only tools</span>
            <h3>Bring EnzyMind into your coding agent.</h3>
            <p>The MCP server runs the tools. The bundled skill tells the agent which tool to use and how to report the result. Install both.</p>
          </div>
          <a
            class="repository-link"
            href="https://github.com/xiaodanyin/enzymind-web-extensions"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub <span aria-hidden="true">↗</span>
          </a>
        </div>

        <div class="extension-steps">
          <article class="extension-step extension-step-wide">
            <div class="step-heading">
              <span class="step-number">01</span>
              <div>
                <h3>Download and install</h3>
                <p>Requires Git, Python 3.10+, and <a href="https://docs.astral.sh/uv/getting-started/installation/" target="_blank" rel="noopener noreferrer">uv</a>.</p>
              </div>
            </div>
            <pre class="install-code"><code>git clone https://github.com/xiaodanyin/enzymind-web-extensions.git
cd enzymind-web-extensions
uv sync --locked
uv run enzymind-mcp --help</code></pre>
            <p class="step-note">The last command should print the server options without an error.</p>
          </article>

          <article class="extension-step">
            <div class="step-heading">
              <span class="step-number">02</span>
              <div>
                <h3>Install in Codex</h3>
                <p>Run from the cloned repository root.</p>
              </div>
            </div>
            <pre class="install-code"><code>codex mcp add enzymind \
  --env ENZYMIND_API_BASE_URL=https://cadd.zju.edu.cn/enzymind/api/ \
  --env ENZYMIND_API_TIMEOUT_SECONDS=600 \
  --env ENZYMIND_API_TRUST_ENV=false \
  -- uv run --directory "$PWD" enzymind-mcp

mkdir -p ~/.agents/skills
cp -R skills/enzymind-mcp-usage ~/.agents/skills/</code></pre>
            <p class="step-note">Restart Codex. Check <code>codex mcp get enzymind</code>, then <code>/mcp</code> and <code>/skills</code>.</p>
          </article>

          <article class="extension-step">
            <div class="step-heading">
              <span class="step-number">03</span>
              <div>
                <h3>Install in Claude Code</h3>
                <p>Run from the cloned repository root.</p>
              </div>
            </div>
            <pre class="install-code"><code>claude mcp add --transport stdio --scope user enzymind \
  --env ENZYMIND_API_BASE_URL=https://cadd.zju.edu.cn/enzymind/api/ \
  --env ENZYMIND_API_TIMEOUT_SECONDS=600 \
  --env ENZYMIND_API_TRUST_ENV=false \
  -- uv run --directory "$PWD" enzymind-mcp

mkdir -p ~/.claude/skills
cp -R skills/enzymind-mcp-usage ~/.claude/skills/</code></pre>
            <p class="step-note">Restart Claude Code after installation.</p>
          </article>

          <article class="extension-step extension-step-wide usage-step">
            <div class="step-heading">
              <span class="step-number">04</span>
              <div>
                <h3>Use it</h3>
                <p>Name the skill when you want disciplined tool selection and compact output.</p>
              </div>
            </div>
            <div class="prompt-example">
              <span class="prompt-mark" aria-hidden="true">›</span>
              <code>Use $enzymind-mcp-usage to calculate the physicochemical properties of MKTIIALSYIFCLVFADYKDDDDK.</code>
            </div>
          </article>
        </div>
      </section>

      <!-- Contact -->
      <section id="contact-support" class="help-section">
        <h2><span class="section-icon">📧</span> Contact & Support</h2>
        <div class="contact-panel">
          <div class="help-card contact-intro">
            <p class="contact-intro-title">For questions, collaboration inquiries, bug reports, or feature requests, please contact the EnzyMind development team below.</p>
            <p class="contact-intro-text">For technical issues, including the input data used, error messages, browser and OS information, and clear reproduction steps will help us resolve problems faster.</p>
          </div>

          <div class="contact-section-card">
            <div class="contact-section-heading">
              <span class="contact-section-kicker">Team</span>
              <h3>Developers</h3>
            </div>
            <div class="contact-grid two-column">
              <article class="contact-person-card">
                <div class="contact-role">Lead Developer</div>
                <h4 class="contact-name">Dr. Xiaodan Yin</h4>
                <a class="contact-link" href="mailto:yinxiaodan@zju.edu.cn">yinxiaodan@zju.edu.cn</a>
                <p class="contact-affiliation">Zhejiang University, Hangzhou, China</p>
              </article>

              <article class="contact-person-card">
                <div class="contact-role">Developer</div>
                <h4 class="contact-name">Dr. Xiaorui Wang</h4>
                <a class="contact-link" href="mailto:wangxr2018@lzu.edu.cn">wangxr2018@lzu.edu.cn</a>
                <p class="contact-affiliation">Zhejiang University, Hangzhou, China</p>
              </article>
            </div>
          </div>

          <div class="contact-section-card">
            <div class="contact-section-heading">
              <span class="contact-section-kicker">Academic</span>
              <h3>Corresponding Authors</h3>
            </div>
            <div class="contact-grid three-column">
              <article class="contact-person-card">
                <h4 class="contact-name">Prof. Tingjun Hou</h4>
                <a class="contact-link" href="mailto:tingjunhou@zju.edu.cn">tingjunhou@zju.edu.cn</a>
                <p class="contact-address">College of Pharmaceutical Sciences<br>Zhejiang University<br>Hangzhou 310000, Zhejiang, China</p>
              </article>

              <article class="contact-person-card">
                <h4 class="contact-name">Prof. Chang-Yu Hsieh</h4>
                <a class="contact-link" href="mailto:kimhsieh@zju.edu.cn">kimhsieh@zju.edu.cn</a>
                <p class="contact-address">College of Pharmaceutical Sciences<br>Zhejiang University<br>Hangzhou 310000, Zhejiang, China</p>
              </article>

              <article class="contact-person-card">
                <h4 class="contact-name">Prof. Xiaojun Yao</h4>
                <a class="contact-link" href="mailto:xjyao@mpu.edu.mo">xjyao@mpu.edu.mo</a>
                <p class="contact-address">Faculty of Applied Sciences<br>Macao Polytechnic University<br>Macao 999078, China</p>
              </article>
            </div>
          </div>

        </div>
      </section>
      </main>
    </div>
  </PageContainer>
</template>

<script setup>
import { ref, reactive, defineComponent, h, onMounted, onBeforeUnmount } from 'vue'
import apiExamples from '@/config/apiExamples.json'
import PageContainer from '@/components/layout/PageContainer.vue'
import { copyToClipboard } from '@/utils/clipboard'
import HelpQuickStart from '@/components/help/HelpQuickStart.vue'

const helpSections = [
  { id: 'quick-start', label: 'Quick Start', icon: '↗' },
  { id: 'api-base-url', label: 'API Base URL', icon: '◎' },
  { id: 'prediction-tools', label: 'Prediction Tools', icon: '◇' },
  { id: 'query-tools', label: 'Query Tools', icon: '⌕' },
  { id: 'utility-tools', label: 'Utility Tools', icon: '＋' },
  { id: 'input-formats', label: 'Input Formats', icon: '≡' },
  { id: 'mcp-agent-skill', label: 'MCP & Agent Skill', icon: '⌘' },
  { id: 'contact-support', label: 'Contact & Support', icon: '@' }
]

const activeHelpSection = ref('quick-start')
const isHelpNavSticky = ref(false)
const mobileHelpNavOpen = ref(false)

const closeMobileHelpNav = () => {
  mobileHelpNavOpen.value = false
  document.body.style.overflow = ''
}

const toggleMobileHelpNav = () => {
  mobileHelpNavOpen.value = !mobileHelpNavOpen.value
  document.body.style.overflow = mobileHelpNavOpen.value ? 'hidden' : ''
}

const scrollToHelpSection = (sectionId) => {
  const section = document.getElementById(sectionId)
  if (!section) return

  const targetTop = section.getBoundingClientRect().top + window.pageYOffset - 100
  window.scrollTo({ top: targetTop, behavior: 'smooth' })
  activeHelpSection.value = sectionId

  if (window.location.hash !== `#${sectionId}`) {
    window.history.pushState(null, '', `#${sectionId}`)
  }

  closeMobileHelpNav()
}

const handleHelpScroll = () => {
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop
  isHelpNavSticky.value = scrollTop > 200

  for (let index = helpSections.length - 1; index >= 0; index -= 1) {
    const { id } = helpSections[index]
    const section = document.getElementById(id)

    if (section && section.getBoundingClientRect().top <= 150) {
      if (activeHelpSection.value !== id) {
        activeHelpSection.value = id
        window.history.replaceState(null, '', `#${id}`)
      }
      break
    }
  }
}

onMounted(() => {
  window.addEventListener('scroll', handleHelpScroll, { passive: true })
  handleHelpScroll()

  const initialSection = window.location.hash.slice(1)
  if (helpSections.some(({ id }) => id === initialSection)) {
    window.setTimeout(() => scrollToHelpSection(initialSection), 100)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleHelpScroll)
  document.body.style.overflow = ''
})

const BASE_URL = 'https://cadd.zju.edu.cn/enzymind/api/'
const buildApiUrl = (path) => `${BASE_URL}${path.replace(/^\/+/, '')}`

// API Data Definitions
const predictionApis = [
  {
    id: 1,
    method: 'POST',
    path: '/recognize/enzyme',
    summary: 'Enzyme Recognition',
    description: 'Determine whether an amino-acid sequence corresponds to an enzyme, and return a confidence score.',
    tags: ['UniProt ID', 'Sequence', 'FASTA file'],
    params: [
      { name: 'input_type', type: 'string', required: true, desc: 'Input type: "uniprot", "sequence", or "fasta"' },
      { name: 'query', type: 'string', required: true, desc: 'UniProt ID, protein sequence, or FASTA content' }
    ],
    requestBody: { input_type: 'uniprot', query: 'P12345' },
    responseExample: { result: { is_enzyme: true, confidence: 0.9542 } }
  },
  {
    id: 2,
    method: 'POST',
    path: '/predict/ec',
    summary: 'EC Number Prediction',
    description: 'Predict the Enzyme Commission (EC) number for an amino-acid sequence, and return the predicted EC label.',
    tags: ['UniProt ID', 'Sequence', 'FASTA file'],
    params: [
      { name: 'input_type', type: 'string', required: true, desc: 'Input type: "uniprot", "sequence", or "fasta"' },
      { name: 'query', type: 'string', required: true, desc: 'UniProt ID, protein sequence, or FASTA content' }
    ],
    requestBody: { input_type: 'uniprot', query: 'P12345' },
    responseExample: { result: { ec_number: '3.4.21.4' } }
  },
  {
    id: 3,
    method: 'POST',
    path: '/query/enzyme-type',
    summary: 'Enzyme Type Recommendation',
    description: 'Recommend suitable enzyme types (e.g., EC classes) for a given chemical reaction.',
    tags: ['Reaction SMILES'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'Reaction SMILES (Substrates >> Products)' }
    ],
    requestBody: { query: 'CC(=O)O>>CCO' },
    responseExample: { success: true, recommendations: [{ ec_number: '1.1.1.1', confidence: 0.95 }], total_count: 1 }
  },
  {
    id: 4,
    method: 'POST',
    path: '/predict/substrate',
    summary: 'Substrate Determination',
    description: 'Determine whether a given enzyme can catalyze a specific substrate molecule, and return a confidence score.',
    tags: ['Enzyme sequence', 'Substrate SMILES'],
    params: [
      { name: 'smiles', type: 'string', required: true, desc: 'Substrate molecule in SMILES format' },
      { name: 'enzyme_input_type', type: 'string', required: true, desc: 'Input type: "uniprot" or "sequence"' },
      { name: 'enzyme_query', type: 'string', required: true, desc: 'UniProt ID or protein sequence' }
    ],
    requestBody: { smiles: 'CC(=O)O', enzyme_input_type: 'uniprot', enzyme_query: 'P12345' },
    responseExample: { result: { is_substrate: true, confidence: 0.8765 } }
  },
  {
    id: 5,
    method: 'POST',
    path: '/predict/kcat',
    summary: 'Kcat Prediction',
    description: 'Predict the turnover number (kcat) for an enzyme–substrate pair, and return the estimated kcat value.',
    tags: ['Enzyme sequence', 'Substrate SMILES'],
    params: [
      { name: 'smiles', type: 'string', required: true, desc: 'Substrate molecule in SMILES format' },
      { name: 'enzyme_input_type', type: 'string', required: false, desc: 'Input type: "uniprot" or "sequence"' },
      { name: 'enzyme_query', type: 'string', required: true, desc: 'UniProt ID or protein sequence' }
    ],
    requestBody: { smiles: 'CC(=O)O', enzyme_input_type: 'uniprot', enzyme_query: 'P12345' },
    responseExample: { success: true, kcat: 12.3456, unit: 's^-1' }
  },
  {
    id: 6,
    method: 'POST',
    path: '/predict/km',
    summary: 'Km Prediction',
    description: 'Predict the Michaelis constant (Km) for an enzyme–substrate pair, and return the estimated Km value.',
    tags: ['Enzyme sequence', 'Substrate SMILES'],
    params: [
      { name: 'smiles', type: 'string', required: true, desc: 'Substrate molecule in SMILES format' },
      { name: 'enzyme_input_type', type: 'string', required: false, desc: 'Input type: "uniprot" or "sequence"' },
      { name: 'enzyme_query', type: 'string', required: true, desc: 'UniProt ID or protein sequence' }
    ],
    requestBody: { smiles: 'CC(=O)O', enzyme_input_type: 'uniprot', enzyme_query: 'P12345' },
    responseExample: { success: true, km: 0.5432, unit: 'mM' }
  },
  {
    id: 7,
    method: 'POST',
    path: '/predict/active-sites',
    summary: 'Active Site Prediction',
    description: 'Predict catalytic active-site residues for a protein sequence, and return the residue identities and their positions.',
    tags: ['UniProt ID', 'Sequence'],
    params: [
      { name: 'uniprot_id', type: 'string', required: false, desc: 'UniProt accession ID' },
      { name: 'aa_sequence', type: 'string', required: false, desc: 'Amino acid sequence (alternative to uniprot_id)' }
    ],
    requestBody: { uniprot_id: 'P12345' },
    responseExample: { result: '| Residue Index | Residue Name | Active Type | Confidence |\n| 65 | GLY | Binding Site | 0.9997 |' }
  }
]

const queryApis = [
  {
    id: 8,
    method: 'POST',
    path: '/check/enzyme',
    summary: 'Enzyme Check',
    description: 'Check whether a protein (UniProt ID) is annotated as an enzyme, and return the enzyme status.',
    tags: ['UniProt ID'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { query: 'P12345' },
    responseExample: { success: true, uniprot_id: 'P12345', is_enzyme: true, message: 'P12345 is an enzyme', ec_numbers: ['1.1.1.1'] }
  },
  {
    id: 9,
    method: 'POST',
    path: '/query/sequence-info',
    summary: 'Sequence Info Query',
    description: 'Retrieve basic information for a protein sequence (UniProt ID), and return the full sequence string along with its length and molecular weight in Da. molWeight_source distinguishes reported and calculated masses. If mass is unavailable, molWeight_note explains why.',
    tags: ['UniProt ID'],
    params: [
      { name: 'uniprot_id', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { uniprot_id: 'P12345' },
    responseExample: { length: 430, molWeight: 47409, value: '…' }
  },
  {
    id: 10,
    method: 'POST',
    path: '/query/catalytic-activity',
    summary: 'Catalytic Activity Query',
    description: 'Retrieve the catalytic activity of an enzyme, and return its annotated EC number(s) together with the corresponding reaction equation(s).',
    tags: ['UniProt ID'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { query: 'P12345' },
    responseExample: apiExamples['catalytic-activity']
  },
  {
    id: 11,
    method: 'POST',
    path: '/query/kinetics',
    summary: 'Kinetic Parameters Query',
    description: 'Retrieve enzyme kinetic parameters, and return available values (e.g., kcat, Km, and kcat/Km).',
    tags: ['UniProt ID'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { query: 'P12345' },
    responseExample: { success: true, uniprot_id: 'P12345', km: [], vmax: [], kcat_note: '' }
  },
  {
    id: 12,
    method: 'POST',
    path: '/query/features',
    summary: 'Active Site Query',
    description: 'Retrieve active site annotations for an enzyme, and return site types and 1-based inclusive start/end positions. A single site has equal bounds. An unknown bound is null.',
    tags: ['UniProt ID'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { query: 'P12345' },
    responseExample: apiExamples['features']
  },
  {
    id: 13,
    method: 'POST',
    path: '/query/function',
    summary: 'Function Query',
    description: 'Retrieve the functional annotation of a UniProt protein entry.',
    tags: ['UniProt ID'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { query: 'P12345' },
    responseExample: { success: true, function: 'Catalyzes the reversible oxidation...', protein_name: 'Alcohol dehydrogenase 1', organism: 'Homo sapiens' }
  },
  {
    id: 14,
    method: 'POST',
    path: '/query/enzyme-info',
    summary: 'Enzyme Full Info Query',
    description: 'One-stop query that determines whether a UniProt entry is an enzyme and returns an integrated summary.',
    tags: ['UniProt ID'],
    params: [
      { name: 'uniprot_id', type: 'string', required: true, desc: 'UniProt accession ID' }
    ],
    requestBody: { uniprot_id: 'P12345' },
    responseExample: { success: true, is_enzyme: true, sequence_info: { length: 375 }, catalytic_activities: [] }
  },
  {
    id: 15,
    method: 'POST',
    path: '/query/enzyme-subclass',
    summary: 'Enzyme Subclass Query',
    description: 'Retrieves EC subclasses under a specified enzyme class.',
    tags: ['Enzyme Class'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'Enzyme class name (e.g., "hydrolase")' },
      { name: 'num_samples', type: 'integer', required: false, desc: 'Number of samples to return (default: 10)' }
    ],
    requestBody: { query: 'hydrolase', num_samples: 10 },
    responseExample: { success: true, enzyme_class: 'Hydrolases', ec_prefix: 3, subclasses: [], total_available: 500 }
  }
]

const utilityApis = [
  {
    id: 16,
    method: 'POST',
    path: '/query/protein-params',
    summary: 'Protein Parameters',
    description: 'Computes basic physicochemical properties for a protein sequence.',
    tags: ['Sequence'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'Amino acid sequence' }
    ],
    requestBody: { query: 'MKFLILLFNILCLFPVLAADNHGVGPQGAS' },
    responseExample: apiExamples['protein-params']
  },
  {
    id: 17,
    method: 'POST',
    path: '/query/blast',
    summary: 'Sequence Alignment',
    description: 'Performs an NCBI BLAST sequence similarity search for a given protein sequence.',
    tags: ['Sequence'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'Protein sequence or UniProt ID' },
      { name: 'max_results', type: 'integer', required: false, desc: 'Maximum number of results (default: 10)' }
    ],
    requestBody: { query: 'P12345', max_results: 3 },
    responseExample: { success: true, query_length: 375, num_results: 3, alignments: [] }
  },
  {
    id: 18,
    method: 'POST',
    path: '/predict/structure',
    summary: 'Structure Prediction',
    description: 'Predicts a protein 3D structure from a UniProt ID or amino-acid sequence. Longer jobs return HTTP 202 with a job ID. Send GET to the Location using your original X-Enzymind-Client header, or the returned poll_token as X-Enzymind-Client. HTTP 200 returns completed coordinates.',
    tags: ['UniProt ID', 'Sequence'],
    params: [
      { name: 'query', type: 'string', required: true, desc: 'UniProt ID or protein sequence' },
      { name: 'input_type', type: 'string', required: true, desc: 'Input type: "uniprot" or "sequence"' },
      { name: 'output_name', type: 'string', required: false, desc: 'Output file name prefix (optional)' }
    ],
    requestBody: { query: 'P12345', input_type: 'uniprot' },
    responseExample: { success: true, pdb_path: 'example.pdb', sequence_length: 430 }
  }
]

// State
const expandedCards = ref(Object.fromEntries([...predictionApis, ...queryApis, ...utilityApis].map(a => [a.id, true])))
const loading = reactive({})
const responses = reactive({})
const responseStatus = reactive({})
const copySuccess = reactive({})

// Methods
const toggleCard = (id) => {
  expandedCards.value[id] = !expandedCards.value[id]
}

const copyCurl = async (api) => {
  const curl = `curl -X POST "${buildApiUrl(api.path)}" -H "Content-Type: application/json" -d '${JSON.stringify(api.requestBody)}'`
  try {
    const copied = await copyToClipboard(curl)
    if (!copied) {
      throw new Error('Clipboard copy was rejected by the browser')
    }
    copySuccess[api.id] = true
    setTimeout(() => { copySuccess[api.id] = false }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

const tryApi = async (api) => {
  if (loading[api.id]) return
  loading[api.id] = true
  responses[api.id] = null
  responseStatus[api.id] = null
  
  try {
    const res = await fetch(buildApiUrl(api.path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(api.requestBody)
    })
    responseStatus[api.id] = res.status
    let data = await res.json()
    if (api.path === '/predict/structure' && res.status === 202) {
      const jobId = data.job_id
      if (!/^[a-f0-9-]{36}$/.test(jobId) || !data.poll_token) throw new Error('Invalid folding job receipt.')
      const headers = { 'X-Enzymind-Client': data.poll_token }
      while (data.status === 'running') {
        responses[api.id] = JSON.stringify({ job_id: jobId, status: 'running' }, null, 2)
        await new Promise(resolve => setTimeout(resolve, 5000))
        const poll = await fetch(buildApiUrl('/predict/structure/jobs/' + jobId), { headers })
        responseStatus[api.id] = poll.status
        data = await poll.json()
      }
    }
    responses[api.id] = JSON.stringify(data, null, 2)
  } catch (err) {
    responseStatus[api.id] = null
    responses[api.id] = JSON.stringify({ error: err.message }, null, 2)
  } finally {
    loading[api.id] = false
  }
}

// ApiCard Component
const ApiCard = defineComponent({
  name: 'ApiCard',
  props: ['api', 'expanded', 'loading', 'response', 'httpStatus', 'copySuccess'],
  emits: ['toggle', 'copy-curl', 'try-api'],
  setup(props, { emit }) {
    const formatJson = (obj) => JSON.stringify(obj, null, 2)
    const requestData = reactive(JSON.parse(JSON.stringify(props.api.requestBody)))
    
    // Watch for deep changes in props (to reset if needed) or just initialize.
    // Assuming api.requestBody structure doesn't change on the fly for the same card instance ID.

    const handleTry = (e) => {
      e.stopPropagation()
      emit('try-api', { ...props.api, requestBody: requestData })
    }

    const handleCopy = (e) => {
      e.stopPropagation()
      emit('copy-curl', { ...props.api, requestBody: requestData })
    }
    
    return () => h('div', { class: 'swagger-card' }, [
      // Header
      h('div', { class: 'swagger-header', onClick: () => emit('toggle', props.api.id) }, [
        h('div', { class: 'swagger-title' }, [
          h('span', { class: `swagger-method ${props.api.method.toLowerCase()}` }, props.api.method),
          h('span', { class: 'swagger-path' }, props.api.path)
        ]),
        h('div', { class: 'swagger-summary' }, props.api.summary),
        h('span', { class: ['swagger-toggle', { expanded: props.expanded }] }, [
          h('svg', { width: '20', height: '20', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
            h('polyline', { points: '6 9 12 15 18 9' })
          ])
        ])
      ]),
      // Body
      props.expanded && h('div', { class: 'swagger-body' }, [
        h('p', { class: 'swagger-description' }, props.api.description),
        h('div', { class: 'swagger-tags' }, props.api.tags.map(tag => h('span', { class: 'param-tag' }, tag))),
        // Parameters
        h('div', { class: 'swagger-section' }, [
          h('h4', 'Request Body Parameters'),
          h('div', { class: 'params-table' }, [
            h('div', { class: 'param-row header' }, [
              h('span', { class: 'param-name' }, 'Parameter'),
              h('span', { class: 'param-type' }, 'Type'),
              h('span', { class: 'param-desc' }, 'Description')
            ]),
            ...props.api.params.map(p => h('div', { class: 'param-row' }, [
              h('span', { class: 'param-name' }, [h('code', p.name), p.required && h('span', { class: 'required' }, '*')]),
              h('span', { class: 'param-type' }, p.type),
              h('span', { class: 'param-desc' }, p.desc)
            ]))
          ])
        ]),
        // cURL
        h('div', { class: 'swagger-section' }, [
          h('h4', 'cURL (Preview)'),
          h('div', { class: 'curl-block' }, [
            h('div', { class: 'curl-header' }, [
              h('span', { class: 'curl-label' }, 'Copy to clipboard'),
              h('button', { class: ['copy-btn', { copied: props.copySuccess }], onClick: handleCopy }, [
                props.copySuccess 
                  ? h('span', { class: 'copy-feedback' }, '✓ Copied!')
                  : [
                      h('svg', { width: '16', height: '16', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
                        h('rect', { x: '9', y: '9', width: '13', height: '13', rx: '2', ry: '2' }),
                        h('path', { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' })
                      ]),
                      h('span', 'Copy')
                    ]
              ])
            ]),
            h('pre', { class: 'code-block curl' }, `curl -X POST "${buildApiUrl(props.api.path)}" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(requestData)}'`)
          ])
        ]),
        // Example
        h('div', { class: 'swagger-section' }, [
          h('div', { class: 'example-tabs' }, [
            h('h4', 'Example'),
            h('button', { 
              class: 'try-btn', 
              disabled: props.loading, 
              onClick: handleTry
            }, [
              !props.loading && h('svg', { width: '14', height: '14', viewBox: '0 0 24 24', fill: 'currentColor' }, [
                h('polygon', { points: '5 3 19 12 5 21 5 3' })
              ]),
              props.loading && h('span', { class: 'spinner' }),
              props.loading ? ' Running...' : ' Try it'
            ])
          ]),
          h('div', { class: 'example-container' }, [
            h('div', { class: 'example-block request-block' }, [
              h('div', { class: 'example-header' }, [
                h('span', { class: 'example-label request' }, 'REQUEST')
              ]),
              // Render as Input Table
              h('div', { class: 'input-table' }, [
                h('div', { class: 'input-table-header' }, [
                  h('span', { class: 'input-col-key' }, 'Parameter'),
                  h('span', { class: 'input-col-value' }, 'Value')
                ]),
                ...Object.keys(requestData).map((key) => {
                  return h('div', { class: 'input-table-row' }, [
                    h('label', { class: 'input-col-key' }, key),
                    h('input', { 
                      class: 'input-col-value',
                      type: typeof requestData[key] === 'number' ? 'number' : 'text',
                      value: requestData[key],
                      onInput: (e) => requestData[key] = typeof requestData[key] === 'number' ? parseFloat(e.target.value) : e.target.value
                    })
                  ])
                })
              ])
            ]),
            h('div', { class: 'example-arrow' }, [
              h('svg', { width: '24', height: '24', viewBox: '0 0 24 24', fill: 'none', stroke: '#9ca3af', 'stroke-width': '2' }, [
                h('line', { x1: '12', y1: '5', x2: '12', y2: '19' }),
                h('polyline', { points: '19 12 12 19 5 12' })
              ])
            ]),
            h('div', { class: 'example-block response-block' }, [
              h('div', { class: 'example-header' }, [
                h('span', { class: 'example-label response' }, 'RESPONSE'),
                props.response && h('span', { class: 'status-code', role: 'status' }, props.httpStatus ? 'HTTP ' + props.httpStatus : 'Request failed')
              ]),
              h('pre', { class: ['code-block', { 'live-response': props.response }] }, props.response || formatJson(props.api.responseExample))
            ])
          ])
        ])
      ])
    ])
  }
})
</script>

<style lang="scss">
.workspace-guide { padding-left: 22px; color: #4f6c79; font-size: 14px; line-height: 1.8; }
.workspace-guide li { margin: 12px 0; }
.workspace-help-notes { border: 1px solid #d8e6e5; border-radius: 12px; background: #f5faf8; padding: 24px; margin: 24px 0; }
.workspace-help-notes h3 { margin: 18px 0 10px; color: #254d49; }
.workspace-help-notes p { font-size: 14px; line-height: 1.8; color: #58717c; margin: 12px 0; }
.help-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: stretch;
  gap: var(--spacing-xl);
  position: relative;
}

.help-sidebar {
  --help-nav-surface: linear-gradient(
    90deg,
    rgba(15, 23, 42, 0.99) 0%,
    rgba(23, 37, 84, 0.98) 58%,
    rgba(30, 64, 175, 0.96) 100%
  );
  min-width: 0;
  position: relative;
  align-self: stretch;
  z-index: 2;
  border: 1px solid rgba(96, 165, 250, 0.32);
  border-radius: 20px;
  background: var(--help-nav-surface);
  box-shadow:
    0 18px 40px rgba(15, 23, 42, 0.2),
    0 3px 12px rgba(37, 99, 235, 0.14),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.section-nav {
  position: sticky;
  top: 100px;
  max-height: calc(100vh - 4rem - 80px);
  padding: 18px 0 14px;
  overflow-x: hidden;
  overflow-y: auto;
  border: 1px solid transparent;
  border-radius: 20px;
  background: var(--help-nav-surface);
  box-shadow: none;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transition: border-color 0.35s ease, background 0.35s ease, box-shadow 0.35s ease, transform 0.35s ease;

  &.is-sticky {
    border-color: rgba(96, 165, 250, 0.52);
    background: var(--help-nav-surface);
    box-shadow:
      0 24px 54px rgba(15, 23, 42, 0.3),
      0 6px 22px rgba(37, 99, 235, 0.24),
      inset 0 1px 0 rgba(255, 255, 255, 0.14);
  }

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    margin: 12px 0;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.28);
  }

  &::-webkit-scrollbar-thumb {
    border-radius: 999px;
    background: linear-gradient(180deg, #60a5fa, #2563eb);

    &:hover {
      background: linear-gradient(180deg, #7dd3fc, #3b82f6);
    }
  }

  ol {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin: 10px 0 0;
    padding: 0;
    list-style: none;
  }

  li {
    animation: helpNavItemIn 0.45s ease-out backwards;

    @for $index from 1 through 8 {
      &:nth-child(#{$index}) {
        animation-delay: #{0.04s * $index};
      }
    }
  }

  a {
    display: grid;
    grid-template-columns: 36px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    padding: 11px 18px;
    overflow: hidden;
    position: relative;
    isolation: isolate;
    border-left: 3px solid transparent;
    color: rgba(226, 232, 240, 0.82);
    font-size: 0.88rem;
    font-weight: 600;
    line-height: 1.4;
    letter-spacing: 0.005em;
    text-decoration: none;
    transition: color 0.32s ease, background 0.32s ease, border-color 0.32s ease, padding 0.32s ease;

    &::before {
      content: '';
      position: absolute;
      inset: 0 auto 0 0;
      width: 0;
      z-index: -1;
      background: linear-gradient(90deg, rgba(59, 130, 246, 0.26), rgba(14, 165, 233, 0.05));
      transition: width 0.38s cubic-bezier(0.4, 0, 0.2, 1);
    }

    &:hover {
      padding-left: 23px;
      border-left-color: rgba(125, 211, 252, 0.62);
      color: #ffffff;

      &::before {
        width: 100%;
      }

      .section-nav-icon {
        border-color: rgba(125, 211, 252, 0.58);
        color: #e0f2fe;
        transform: translateX(2px) rotate(4deg) scale(1.08);
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.2);
      }
    }

    &:focus-visible {
      outline: 2px solid #7dd3fc;
      outline-offset: -2px;
    }

    &.active {
      border-left-color: #7dd3fc;
      color: #ffffff;
      background: linear-gradient(90deg, rgba(37, 99, 235, 0.4), rgba(14, 165, 233, 0.12));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.08),
        0 8px 24px rgba(14, 165, 233, 0.12);

      &::before {
        width: 100%;
      }

      .section-nav-icon {
        border-color: rgba(125, 211, 252, 0.72);
        color: #ffffff;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.65), rgba(14, 165, 233, 0.38));
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.28);
        animation: helpNavIconPulse 1.8s ease-in-out infinite;
      }

      .section-nav-label {
        font-weight: 700;
      }
    }
  }
}

.section-nav-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 2px 18px 17px;
  border-bottom: 1px solid rgba(147, 197, 253, 0.2);
  color: #f8fafc;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;

  > span:last-child {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  small {
    color: #7dd3fc;
    font-size: 0.58rem;
    font-weight: 800;
    letter-spacing: 0.15em;
  }
}

.section-nav-mark {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  padding: 8px;
  border: 1px solid rgba(125, 211, 252, 0.38);
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.2);
  box-shadow: 0 0 20px rgba(37, 99, 235, 0.18);

  span {
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, #7dd3fc, #60a5fa);

    &:nth-child(2) {
      width: 70%;
    }
  }
}

.section-nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(147, 197, 253, 0.22);
  border-radius: 9px;
  color: #93c5fd;
  background: rgba(15, 23, 42, 0.22);
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.9rem;
  font-weight: 800;
  transition: transform 0.32s ease, border-color 0.32s ease, color 0.32s ease, box-shadow 0.32s ease;
}

.section-nav-label {
  position: relative;
  z-index: 1;
  min-width: 0;
  white-space: nowrap;
}

.mobile-help-nav-toggle,
.mobile-help-nav-overlay {
  display: none;
}

@keyframes helpNavItemIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes helpNavIconPulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.06) translateY(-1px);
  }
}

.help-content {
  min-width: 0;
}

.help-section {
  margin-bottom: var(--spacing-xl);
  scroll-margin-top: calc(var(--navbar-height) + 24px);
  
  h2 {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    color: var(--color-text-primary);
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: var(--spacing-lg);
    padding-bottom: var(--spacing-sm);
    border-bottom: 2px solid var(--color-primary);
    
    .section-icon {
      font-size: 1.3rem;
    }
  }
}

.help-card {
  background: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  
  ol, ul {
    margin: var(--spacing-md) 0;
    padding-left: var(--spacing-lg);
  }
  
  li {
    margin: var(--spacing-sm) 0;
    line-height: 1.6;
    color: #4b5563;
  }
  
  a {
    color: var(--color-primary);
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }
}

.contact-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.contact-intro {
  background: linear-gradient(135deg, #f8fafc 0%, #eef6ff 100%);
  border: 1px solid #dbeafe;
}

.contact-intro-title {
  margin: 0 0 var(--spacing-sm);
  color: #1f2937;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.75;
}

.contact-intro-text {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.contact-section-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.contact-section-heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: var(--spacing-md);

  h3 {
    margin: 0;
    color: #1f2937;
    font-size: 1.15rem;
    font-weight: 700;
  }
}

.contact-section-kicker {
  display: inline-flex;
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.contact-grid {
  display: grid;
  gap: var(--spacing-md);

  &.two-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  &.three-column {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.contact-person-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 100%;
  padding: 18px;
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
}

.contact-role {
  color: #6366f1;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.contact-name {
  margin: 0;
  color: #111827;
  font-size: 1.02rem;
  font-weight: 700;
}

.contact-link {
  color: var(--color-primary);
  font-weight: 600;
  text-decoration: none;
  word-break: break-word;

  &:hover {
    text-decoration: underline;
  }
}

.contact-affiliation,
.contact-address,
.support-text {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.support-card {
  background: linear-gradient(135deg, #fffdfa 0%, #f8fafc 100%);
}

.support-email {
  margin-bottom: var(--spacing-sm);
}

.support-checklist {
  margin: 0;
  padding-left: 1.25rem;

  li {
    margin: 8px 0;
    color: #4b5563;
    line-height: 1.6;
  }
}

.extension-section {
  margin-top: calc(var(--spacing-xl) + var(--spacing-md));
}

.extension-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--spacing-xl);
  padding: 28px;
  border: 1px solid #1e3a5f;
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 88% 14%, rgba(56, 189, 248, 0.18), transparent 28%),
    linear-gradient(135deg, #0f172a 0%, #172554 100%);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.16);

  h3 {
    margin: 10px 0 8px;
    color: #f8fafc;
    font-size: 1.35rem;
    font-weight: 700;
  }

  p {
    max-width: 670px;
    margin: 0;
    color: #cbd5e1;
    line-height: 1.7;
  }
}

.extension-kicker {
  color: #7dd3fc;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.repository-link {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid rgba(125, 211, 252, 0.42);
  border-radius: 8px;
  color: #e0f2fe;
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: none;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;

  &:hover {
    border-color: #7dd3fc;
    background: rgba(14, 165, 233, 0.14);
    transform: translateY(-1px);
  }
}

.extension-steps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.extension-step {
  min-width: 0;
  padding: var(--spacing-lg);
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-lg);
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.extension-step-wide {
  grid-column: 1 / -1;
}

.step-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: var(--spacing-md);

  h3 {
    margin: 1px 0 5px;
    color: #0f172a;
    font-size: 1.05rem;
    font-weight: 700;
  }

  p {
    margin: 0;
    color: #64748b;
    font-size: 0.86rem;
    line-height: 1.55;
  }

  a {
    color: #0369a1;
    font-weight: 600;
  }
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 6px;
  background: #e0f2fe;
  color: #0369a1;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.72rem;
  font-weight: 800;
}

.install-code {
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  border: 1px solid #1e293b;
  border-radius: 8px;
  background: #0f172a;
  color: #bae6fd;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.76rem;
  line-height: 1.75;
  tab-size: 2;
  white-space: pre;

  code {
    font: inherit;
  }
}

.step-note {
  margin: 12px 0 0;
  color: #64748b;
  font-size: 0.82rem;
  line-height: 1.6;

  code {
    padding: 2px 5px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #334155;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  }
}

.usage-step {
  background: linear-gradient(135deg, #f8fafc 0%, #f0f9ff 100%);
}

.prompt-example {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 15px 16px;
  border-left: 3px solid #0ea5e9;
  border-radius: 0 8px 8px 0;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px #e2e8f0;

  code {
    color: #0f172a;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.65;
    overflow-wrap: anywhere;
  }
}

.prompt-mark {
  color: #0284c7;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 1.1rem;
  font-weight: 800;
  line-height: 1.3;
}

.feature-cards {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  margin-top: var(--spacing-xl);
}

.feature-showcase {
  background: linear-gradient(135deg, #f8fafc 0%, #e0f2fe 30%, #ede9fe 70%, #f0fdf4 100%);
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.08)), 
              0 0 0 1px rgba(37, 99, 235, 0.08);
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: 
      radial-gradient(ellipse at 0% 0%, rgba(37, 99, 235, 0.06) 0%, transparent 50%),
      radial-gradient(ellipse at 100% 100%, rgba(139, 92, 246, 0.06) 0%, transparent 50%);
    pointer-events: none;
  }
}

.feature-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid rgba(37, 99, 235, 0.08);
  
  &:last-child {
    border-bottom: none;
  }
}

.feature-image-wrapper {
  width: 100%;
  padding: var(--spacing-lg) var(--spacing-xl);
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(8px);
}

.feature-image {
  width: 100%;
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12),
              0 0 0 1px rgba(0, 0, 0, 0.05);
  transition: all var(--transition-normal, 0.3s);
  
  &:hover {
    transform: scale(1.01);
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15),
                0 0 0 1px rgba(37, 99, 235, 0.1),
                0 0 40px rgba(37, 99, 235, 0.08);
  }
}

.feature-content {
  padding: var(--spacing-lg) var(--spacing-xl) var(--spacing-xl);
  position: relative;
  z-index: 1;
}

.feature-title {
  font-size: 1.35rem;
  font-weight: 700;
  margin-bottom: var(--spacing-sm);
  background: var(--color-primary-gradient, linear-gradient(135deg, #2563eb 0%, #7c3aed 100%));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.feature-desc {
  color: var(--color-text-secondary, #475569);
  line-height: 1.8;
  font-size: 0.95rem;
  margin-bottom: var(--spacing-md);
}

.feature-caption {
  font-size: 0.85rem;
  color: var(--color-text-muted, #64748b);
  font-style: italic;
  padding-top: var(--spacing-sm);
  border-top: 1px dashed var(--color-border, #e2e8f0);
}

@media (max-width: 768px) {
  .feature-image-wrapper {
    padding: var(--spacing-md);
  }
  
  .feature-content {
    padding: var(--spacing-md) var(--spacing-lg) var(--spacing-lg);
  }
}

.base-url-card {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  border: 1px solid #e2e8f0;
  text-align: center;
  
  .base-url-display {
    display: inline-flex;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 100%;
    align-items: center;
    background: white;
    padding: 12px 24px;
    border-radius: var(--radius-md);
    border: 2px solid var(--color-primary);
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 1.1rem;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
    
    > span { min-width: 0; overflow-wrap: anywhere; }
    .protocol { color: #6b7280; }
    .domain { color: var(--color-primary); font-weight: 600; }
    .base-path { color: #0f766e; font-weight: 600; }
  }
  
  .base-url-note {
    margin-top: var(--spacing-md);
    color: #6b7280;
    font-size: 0.9rem;
  }
}

.swagger-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid #e5e7eb;
  margin-bottom: var(--spacing-md);
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  transition: box-shadow 0.2s ease;
  &:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
}

.swagger-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background: #fafbfc;
  border-bottom: 1px solid #e5e7eb;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
  &:hover { background: #f3f4f6; }
}

.swagger-title {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.swagger-method {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  min-width: 56px;
  
  &.post { background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; }
  &.get { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
}

.swagger-path {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.9rem;
  color: #1f2937;
  font-weight: 500;
}

.swagger-summary {
  flex: 1;
  margin-left: 20px;
  color: #6b7280;
  font-size: 0.9rem;
}

.swagger-toggle {
  color: #9ca3af;
  transition: transform 0.2s ease;
  &.expanded { transform: rotate(180deg); }
}

.swagger-body {
  padding: 20px;
  background: white;
  border-top: 1px solid #f3f4f6;
}

.swagger-description {
  color: #4b5563;
  line-height: 1.6;
  margin-bottom: var(--spacing-md);
}

.swagger-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: var(--spacing-md);
}

.param-tag {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #1e40af;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  border: 1px solid #bfdbfe;
}

.swagger-section {
  margin-bottom: var(--spacing-md);
  
  h4 {
    color: #374151;
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: var(--spacing-sm);
    padding-bottom: 8px;
    border-bottom: 1px solid #e5e7eb;
  }
}

.params-table {
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-md);
  overflow-x: auto;
  
  .param-row {
    display: grid;
    min-width: 480px;
    grid-template-columns: 180px 100px 1fr;
    padding: 10px 16px;
    border-bottom: 1px solid #f3f4f6;
    font-size: 0.85rem;
    &:last-child { border-bottom: none; }
    &.header { background: #f9fafb; font-weight: 600; color: #374151; }
  }
  
  .param-name {
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; color: #1f2937; }
    .required { color: #ef4444; margin-left: 2px; }
  }
  
  .param-type {
    color: #059669;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 0.8rem;
  }
  
  .param-desc { color: #6b7280; }
}

.curl-block {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid #374151;
  background: #1e293b;
}

.curl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #334155;
  border-bottom: 1px solid #475569;
}

.curl-label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #475569;
  border: none;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 80px;
  justify-content: center;
  
  &:hover { background: #64748b; }
  &.copied { 
    background: #059669; 
    color: white;
  }
  svg { width: 14px; height: 14px; }
}

.copy-feedback {
  font-weight: 600;
  letter-spacing: 0.3px;
}

.example-tabs {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
  h4 { margin: 0; border: none; padding: 0; }
}

.try-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
  
  &:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4);
    transform: translateY(-1px);
  }
  &:disabled { opacity: 0.7; cursor: not-allowed; }
  svg { width: 12px; height: 12px; }
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.example-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.example-arrow {
  display: flex;
  justify-content: center;
  padding: 8px 0;
  background: #f8fafc;
  svg { opacity: 0.6; }
}

.example-block {
  border-radius: 0;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  
  &.request-block { border-radius: var(--radius-md) var(--radius-md) 0 0; border-bottom: none; }
  &.response-block { border-radius: 0 0 var(--radius-md) var(--radius-md); }
}

.example-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #1e293b;
}

.example-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 3px 10px;
  border-radius: 4px;
  
  &.request { background: #3b82f6; color: white; }
  &.response { background: #10b981; color: white; }
}

.status-code {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  
  &.success { background: #065f46; color: #a7f3d0; }
  &.error { background: #7f1d1d; color: #fecaca; }
}

.code-block {
  background: #0f172a;
  color: #e2e8f0;
  padding: 16px 20px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 0.82rem;
  line-height: 1.7;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
  min-height: 60px;
  
  &.curl { background: #1e293b; color: #a5f3fc; font-size: 0.78rem; }
  &.live-response { background: #064e3b; border-left: 3px solid #10b981; }
  
  &.request-editor {
    width: 100%;
    border: none;
    resize: vertical;
    outline: none;
    display: block;
    min-height: 120px;
    
    &:focus {
      background: #172033;
      box-shadow: inset 0 0 0 1px #3b82f6; 
    }
  }
}

.input-table {
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  overflow: hidden;
  background: var(--glass-bg, rgba(255, 255, 255, 0.7));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.3));
  border-top: none;
}

.input-table-header {
  display: grid;
  grid-template-columns: 180px 1fr;
  padding: 10px 16px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(139, 92, 246, 0.08) 100%);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  .input-col-key { color: var(--color-primary, #2563eb); }
  .input-col-value { color: var(--color-accent-1, #8b5cf6); }
}

.input-table-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-light, #f1f5f9);
  transition: all var(--transition-fast, 0.15s);
  
  &:last-child { border-bottom: none; }
  
  &:hover { 
    background: linear-gradient(90deg, var(--color-primary-light, #eff6ff) 0%, transparent 100%);
  }
  
  .input-col-key {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 0.85rem;
    font-weight: 600;
    background: var(--color-primary-gradient, linear-gradient(135deg, #2563eb 0%, #7c3aed 100%));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  input.input-col-value {
    width: 100%;
    padding: 8px 14px;
    border: 1.5px solid var(--color-border, #e2e8f0);
    border-radius: var(--radius-sm, 8px);
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 0.85rem;
    color: var(--color-text, #0f172a);
    background: var(--color-surface, #ffffff);
    transition: all var(--transition-fast, 0.15s);
    
    &:hover { 
      border-color: var(--color-primary, #2563eb);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.05);
    }
    
    &:focus {
      outline: none;
      border-color: var(--color-primary, #2563eb);
      box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12), var(--shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.05));
      background: linear-gradient(135deg, #ffffff 0%, var(--color-primary-light, #eff6ff) 100%);
    }
  }
}

.format-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
  gap: var(--spacing-md);
}

.format-card {
  background: white;
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  
  h4 { color: #1f2937; font-size: 0.95rem; font-weight: 600; margin-bottom: var(--spacing-sm); }
  
  code {
    display: inline-block;
    background: #f3f4f6;
    padding: 4px 8px;
    border-radius: 4px;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 0.85rem;
    color: #1f2937;
  }
  
  pre {
    background: #1f2937;
    color: #e5e7eb;
    padding: 12px;
    border-radius: 6px;
    margin: var(--spacing-sm) 0;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
    font-size: 0.8rem;
    overflow-x: auto;
  }
  
  p { color: #6b7280; font-size: 0.85rem; margin-top: var(--spacing-sm); line-height: 1.5; }
}

@media (max-width: 900px) {
  .contact-grid {
    &.three-column {
      grid-template-columns: 1fr;
    }
  }
}

@media (max-width: 1199px) {
  .help-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .help-sidebar {
    min-width: 0;
    position: static;
    top: auto;
    align-self: auto;
    z-index: auto;
    border: none;
    border-radius: 0;
    background: none;
    box-shadow: none;

    &::before {
      display: none;
    }
  }

  .section-nav {
    position: fixed;
    top: 0;
    bottom: 0;
    left: -340px;
    z-index: 1100;
    width: 310px;
    max-height: 100vh;
    padding: 86px 0 24px;
    border: 1px solid rgba(96, 165, 250, 0.42);
    border-left: none;
    border-radius: 0 24px 24px 0;
    background:
      radial-gradient(circle at 12% 0%, rgba(56, 189, 248, 0.18), transparent 28%),
      linear-gradient(160deg, rgba(15, 23, 42, 0.99) 0%, rgba(23, 37, 84, 0.98) 58%, rgba(30, 64, 175, 0.97) 100%);
    box-shadow: none;
    transition: left 0.42s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.42s ease;

    &.is-sticky {
      border-color: rgba(96, 165, 250, 0.42);
      border-left: none;
      background:
        radial-gradient(circle at 12% 0%, rgba(56, 189, 248, 0.18), transparent 28%),
        linear-gradient(160deg, rgba(15, 23, 42, 0.99) 0%, rgba(23, 37, 84, 0.98) 58%, rgba(30, 64, 175, 0.97) 100%);
      box-shadow: none;
    }

    &.mobile-open {
      left: 0;
      box-shadow:
        26px 0 70px rgba(15, 23, 42, 0.42),
        8px 0 28px rgba(37, 99, 235, 0.24),
        inset 0 1px 0 rgba(255, 255, 255, 0.12);
    }
  }

  .mobile-help-nav-toggle {
    display: flex;
    position: fixed;
    left: 22px;
    bottom: 28px;
    z-index: 1120;
    width: 64px;
    height: 64px;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 0;
    border: 1px solid rgba(125, 211, 252, 0.55);
    border-radius: 50%;
    color: #f8fafc;
    background:
      radial-gradient(circle at 35% 20%, rgba(125, 211, 252, 0.25), transparent 35%),
      linear-gradient(145deg, #0f172a 0%, #1e3a8a 62%, #2563eb 100%);
    box-shadow:
      0 12px 30px rgba(15, 23, 42, 0.3),
      0 4px 18px rgba(37, 99, 235, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.16);
    cursor: pointer;
    transition: transform 0.28s ease, border-color 0.28s ease, box-shadow 0.28s ease, background 0.28s ease;

    > span:last-child {
      font-size: 0.58rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      line-height: 1;
      text-transform: uppercase;
    }

    &:hover {
      border-color: #7dd3fc;
      transform: translateY(-3px) scale(1.05);
      box-shadow:
        0 16px 36px rgba(15, 23, 42, 0.34),
        0 6px 24px rgba(14, 165, 233, 0.42),
        inset 0 1px 0 rgba(255, 255, 255, 0.18);
    }

    &:active {
      transform: scale(0.95);
    }

    &:focus-visible {
      outline: 3px solid rgba(125, 211, 252, 0.7);
      outline-offset: 4px;
    }

    &.active {
      border-color: #bae6fd;
      background:
        radial-gradient(circle at 35% 20%, rgba(255, 255, 255, 0.2), transparent 36%),
        linear-gradient(145deg, #2563eb 0%, #1d4ed8 52%, #0f172a 100%);

      .mobile-help-nav-icon {
        span:first-child {
          top: 6px;
          transform: rotate(45deg);
        }

        span:nth-child(2) {
          opacity: 0;
          transform: scaleX(0);
        }

        span:last-child {
          top: 6px;
          transform: rotate(-45deg);
        }
      }
    }
  }

  .mobile-help-nav-icon {
    display: block;
    width: 20px;
    height: 14px;
    position: relative;

    span {
      position: absolute;
      left: 0;
      width: 100%;
      height: 2px;
      border-radius: 999px;
      background: #bae6fd;
      box-shadow: 0 0 8px rgba(125, 211, 252, 0.42);
      transition: top 0.28s ease, transform 0.28s ease, opacity 0.2s ease;

      &:first-child {
        top: 0;
      }

      &:nth-child(2) {
        top: 6px;
      }

      &:last-child {
        top: 12px;
      }
    }
  }

  .mobile-help-nav-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 1090;
    opacity: 0;
    pointer-events: none;
    background: rgba(2, 6, 23, 0.58);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    transition: opacity 0.3s ease;

    &.active {
      opacity: 1;
      pointer-events: auto;
    }
  }
}

@media (max-width: 768px) {
  .swagger-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }
  .swagger-title { min-width: 0; }
  .swagger-method { flex-shrink: 0; }
  .swagger-path { overflow-wrap: anywhere; }
  .swagger-summary { grid-column: 1; margin-left: 0; }
  .swagger-toggle { grid-column: 2; grid-row: 1 / 3; }
  .input-table-header { display: none; }
  .input-table-row { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .input-table-row .input-col-key { overflow-wrap: anywhere; }

  .section-nav {
    left: -330px;
    width: min(310px, calc(100vw - 48px));
  }

  .mobile-help-nav-toggle {
    left: 18px;
    bottom: 22px;
    width: 60px;
    height: 60px;
  }

  .extension-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--spacing-lg);
  }

  .extension-steps {
    grid-template-columns: 1fr;
  }

  .extension-step-wide {
    grid-column: auto;
  }

  .extension-step {
    padding: var(--spacing-md);
  }

  .contact-grid {
    &.two-column,
    &.three-column {
      grid-template-columns: 1fr;
    }
  }

  .contact-section-card,
  .help-card.contact-intro {
    padding: var(--spacing-md);
  }
}

@media (prefers-reduced-motion: reduce) {
  .section-nav li,
  .section-nav a.active .section-nav-icon {
    animation: none;
  }

  .section-nav,
  .section-nav a,
  .section-nav a::before,
  .section-nav-icon,
  .mobile-help-nav-toggle,
  .mobile-help-nav-overlay {
    transition-duration: 0.01ms;
  }
}
</style>
