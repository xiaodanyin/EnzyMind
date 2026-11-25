import { toolById } from './tools'

// Vite emits URLs; Help lazily fetches Workspace and the selected tool guide.
const images = import.meta.glob('../assets/help-guides/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
})

const proteinInput = 'Paste a UniProt ID or sequence, or upload a FASTA file and select one protein.'
const pairedInput = 'Add your protein and substrate SMILES, or draw the molecule with Ketcher.'

const alignmentGuide = {
  imageAlt: 'Sequence Alignment three-step walkthrough: review the workflow across the top, enter P00761 and select local UniProt at lower left, then compare completed hits, inspect P08426 aligned residues and Differences, and export JSON at lower right.',
  caption: 'Real local UniProt BLAST example · P00761 against the reviewed snapshot dated 2026-06-14. Alignment and difference views show excerpts; sequence similarity alone does not confirm identical function.',
  steps: [
    { title: 'Choose a tool', text: 'Open Sequence Alignment under Utility. Review the workflow and method details, then select “Go to input”.' },
    { title: 'Add input & run', text: 'Enter an accession or sequence, or upload FASTA. Under Search options, choose Local UniProt and the maximum returned alignment segments, then select “Search with BLAST”.' },
    { title: 'Read results & export', text: 'Compare coverage, identity and E-value. Select a hit for aligned residues; open Differences to inspect changes and expand the table. Use Export JSON or Discuss with Agent to continue.' },
  ],
}

export const WORKSPACE_HELP_GUIDE = {
  id: 'workspace',
  title: 'Workspace',
  description: 'Turn a research question into evidence, figures and downloadable data. Follow the analysis, inspect each result and refine your question.',
  path: '/agent',
  openLabel: 'Open Workspace',
  image: images['../assets/help-guides/12-workspace.webp'],
  imageAlt: 'Workspace walkthrough: ask about carboxylesterase 1 Q0ZPV7, explore stacked protein sequence and 3D site cards, inspect highlighted Python code with its composition plot and CSV, then reuse evidence in a follow-up.',
  caption: 'Illustrative walkthrough · carboxylesterase 1 Q0ZPV7 sequence, AlphaFold model and EasIFA site prediction, with locally computed Python plots and data. Card excerpts are arranged for readability.',
  imageUnavailable: 'Image unavailable. Follow the steps above, or open Workspace and select “Guide” for a walkthrough.',
  steps: [
    { title: 'Start with a question', text: 'Describe your goal and desired output. Add a protein file or reference a saved result when useful.' },
    { title: 'Connect sequence & structure', text: 'Follow the Agent’s queries and predictions. Open result cards to explore sequences, 3D structures, sites and their evidence.' },
    { title: 'Inspect code, figures & data', text: 'Review Analysis code, expand figures and tables, and download the generated plots and calculation data.' },
    { title: 'Reuse & refine', text: 'Choose “Add to question” on a result, then ask a follow-up using the saved evidence.' },
  ],
}

export const HELP_GUIDES = [
  ['recognize', '01-enzyme-recognition', proteinInput, 'Read the enzyme / non-enzyme classification and model score.'],
  ['ec', '02-ec-number-prediction', proteinInput, 'Follow the predicted EC number through the enzyme classification hierarchy.'],
  ['enzyme-type', '03-enzyme-recommendation', 'Paste reactants>>products or draw both sides of the reaction with Ketcher.', 'Compare the ranked EC classes and their reported scores.'],
  ['substrate', '04-substrate-determination', pairedInput, 'Check substrate compatibility and the model score for your submitted pair.'],
  ['kcat', '05-kcat-prediction', pairedInput, 'Read the predicted turnover directly in s⁻¹; no log conversion is needed.'],
  ['km', '06-km-prediction', pairedInput, 'Read the predicted Michaelis constant directly in mM.'],
  ['active-sites', '07-active-site-prediction', 'Enter a UniProt ID, or use sequence / FASTA with an optional reaction.', 'Select a residue to locate its site in the structure; export the residue table as CSV.'],
  ['enzyme-info', '08-enzyme-information', 'Enter a UniProt accession, such as P00761, to retrieve database annotations.', 'Read reported functions, reactions and sites alongside their sources.'],
  ['parameters', '09-protein-parameters', proteinInput, 'Inspect composition, molecular weight and pI; open the full property report.'],
  ['structure', '10-structure-prediction', proteinInput, 'Set Color to pLDDT to inspect confidence; save coordinates with Download PDB.'],
  ['blast', '11-sequence-alignment', 'Add a protein and choose the database and maximum returned alignment segments under Search options.', 'Compare hits, select an alignment, inspect residue differences and export the result.'],
].map(([id, image, input, output]) => {
  const tool = toolById[id]
  return {
    id,
    title: tool.title,
    description: tool.description,
    path: tool.path,
    group: tool.path.startsWith('/predict/') ? 'prediction' : 'utility',
    image: images[`../assets/help-guides/${image}.webp`],
    steps: [
      { title: 'Prepare input', text: input },
      { title: tool.action, text: `Select “${tool.action}” to start. Your result appears below the form.` },
      { title: 'Read & export', text: output },
    ],
    ...(id === 'blast' ? alignmentGuide : {}),
  }
})

export const HELP_GUIDE_GROUPS = [
  { id: 'prediction', label: 'Prediction' },
  { id: 'utility', label: 'Utility' },
].map(group => ({ ...group, count: HELP_GUIDES.filter(guide => guide.group === group.id).length }))
