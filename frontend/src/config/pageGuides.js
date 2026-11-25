import { TOOLS } from './tools.js';

const step = (title, text, target, preview, fallback) => ({ title, text, target, preview, fallback });
export const GUIDE_KEYS = ['agent', 'results', 'result-detail', ...TOOLS.map(t => `model:${t.id}`)];

const outputs = {
  recognize: ['Read the enzyme classification', 'Read the enzyme / non-enzyme decision and enzyme-class score below the form. The score is a model output, not measured accuracy.'],
  ec: ['Read the predicted EC numbers', 'The result lists predicted EC numbers for your protein. Use the EC hierarchy to identify the proposed enzyme class; this endpoint does not provide a confidence interval.'],
  substrate: ['Read the substrate assessment', 'Check the predicted substrate / non-substrate decision and compatibility score for the protein–molecule pair you submitted.'],
  kcat: ['Read the turnover in s⁻¹', 'The result reports predicted kcat in s⁻¹ for your enzyme–substrate pair. Read the displayed value directly; it has already been converted from the model’s logarithmic output.'],
  km: ['Read the Michaelis constant in mM', 'The result reports predicted Km in mM for your enzyme–substrate pair. Read the displayed concentration directly; no logarithmic conversion is needed.'],
  'enzyme-type': ['Compare the ranked EC candidates', 'Compare up to five recommended EC classes and their reported scores in the ranking chart. These are enzyme classes for your reaction, not individual protein sequences.'],
  'active-sites': ['Locate the predicted residues', 'Read residue positions and site classes in the result. When coordinates are available, select a residue to locate it in Mol*. Export residues CSV saves the site table.'],
  structure: ['Inspect the structure and confidence', 'Rotate the predicted structure in Mol*, select residues, and set Color to pLDDT to inspect local confidence. Save the coordinates with Download PDB and the current view with Save PNG.'],
  parameters: ['Read the calculated protein properties', 'Compare amino acid composition in the chart and read molecular weight and theoretical pI. Expand Full physicochemical report for the complete property report.'],
  blast: ['Compare the alignment hits', 'Compare each hit’s query coverage, identity and E-value, then select a hit to inspect aligned Query and Hit residues. Use Differences to review substitutions and gaps, or expand the difference table. Each returned segment may cover only part of your protein; similarity alone does not confirm identical function.'],
  'enzyme-info': ['Read the retrieved annotations', 'Read the returned protein sequence, function, reactions and site annotations. Follow the source links to inspect database evidence; a missing field means no annotation was returned.'],
};

export function pageGuide(route) {
  const tool = TOOLS.find(t => t.path === route.path);
  if (tool) {
    const steps = [];
    if (tool.protein !== false) steps.push(step('Start with your protein', tool.protein === 'uniprot'
      ? `Enter one UniProt accession, such as ${tool.exampleId}, or select Load protein example. This page accepts accessions only; use the other tools for raw sequences.`
      : `Paste one UniProt accession, such as ${tool.exampleId}, or an amino acid sequence / FASTA into Protein input. You can also upload a FASTA file (up to 1 MB). For a multi-record file, select the protein to analyze. Load protein example fills a ready-to-use input.`,
    '.protein-input .field-heading', 'protein', '.protein-input'));
    if (tool.molecule) steps.push(step(tool.molecule === 'molecule' ? 'Draw or paste your molecule' : 'Describe your reaction', tool.molecule === 'molecule'
      ? 'Paste the substrate’s SMILES in the chemical input, or select Draw with Ketcher and draw it. Load substrate example supplies a sample molecule. The SMILES and drawing stay linked; the latest drawing is used on submission.'
      : tool.molecule === 'optional-reaction'
        ? 'A reaction is optional for sequence / FASTA input. Paste reactants>>products, or select Draw with Ketcher and draw both sides of a reaction arrow. With a UniProt accession, this field is hidden and the database pathway is used.'
        : 'Paste reaction SMILES as reactants>>products (separate molecules with dots), or select Draw with Ketcher and draw both sides of a reaction arrow. Load reaction example fills a complete reaction. No protein input is needed.',
    '.chemical-tabs', tool.molecule === 'molecule' ? 'ketcher' : 'reaction', '.protein-input, .tool-form'));
    if (tool.id === 'blast') steps.push(step('Choose a database and alignment limit', 'Open Search options and set Maximum returned alignment segments to 3, 5, 10, 25 or 50. When available, Service default uses local UniProt; choose Local UniProt explicitly for the reviewed snapshot. NCBI nr and Swiss-Prot use the remote queue, and queued searches can be reopened in Results.', '.analysis-options', 'options'));
    steps.push(step(`Submit: ${tool.action}`, `Select ${tool.action} below the inputs. If a field is invalid, correct the message shown beside it and submit again. The button shows progress while the analysis runs; the result appears below this form.${['blast', 'structure'].includes(tool.id) ? ' This analysis can take several minutes.' : ''}`, '.submit-row', 'run'));
    const [title, text] = outputs[tool.id];
    steps.push(step(title, `${text} Use Export JSON to save the complete result before its 90-day expiry.`, '.workbench-result .research-result-header', ['structure', 'active-sites'].includes(tool.id) ? 'structure' : 'result', '.result-expectation, .submit-row'));
    return { key: `model:${tool.id}`, title: tool.title, ready: '.tool-form', tool, steps };
  }
  if (route.path === '/agent') return { key: 'agent', title: 'Research workspace', ready: '.message-composer', steps: [
    step('Load a starting question', 'Select a research example to reveal its protein or reaction input, expected results and follow-up question. Select Load question to copy it into the message box, then edit the protein, molecule or task before sending.', '.examples-heading', 'examples', '.workspace-topbar'),
    step('Enter your question and protein', 'Type the task and a UniProt accession or sequence in Research question. Use ＋ Protein file to attach a FASTA or text file. For a kinetics or substrate question, include the molecule’s SMILES as well.', '.message-composer', 'question'),
    step('Send and follow the streamed answer', 'Select Send question or press Enter (Shift + Enter inserts a new line). Tool progress and the answer appear in the conversation; Stop analysis cancels the running turn. After 10 free turns today, select Use my DeepSeek key to continue with your own key.', '.message-composer', 'run'),
    step('Open results or ask a follow-up', 'Open a result link in the answer to inspect and export its data. To reuse evidence, open Results, select ＋ Attach beside a saved result, and send a follow-up question. Export saves the conversation; download each result’s JSON separately before 90 days.', '[data-guide="agent-results"]', 'library', '.workspace-topbar'),
  ] };
  if (route.path.startsWith('/results')) return route.params.id ? { key: 'result-detail', title: 'Read your result', ready: '.research-result', steps: [
    step('Check the submitted input and output', 'Start with Submitted inputs: inspect the numbered sequence or molecular drawing and the saved text. Then read the output metrics, units and charts. Input & provenance contains the original fields and evidence source.', '.result-inputs', 'result', '.research-result-header'),
    step('Open the complete returned data', 'Expand Complete result data to inspect all fields returned by the analysis. Reuse inputs copies the original input into its tool; Discuss with Agent attaches this result to a research question.', '[data-guide="full-result-data"]', 'data', '.results-page-header'),
    step('Save the result files', 'Select Export JSON for the complete record, including inputs and scientific data. Use the chart or structure export controls for figures and coordinates when available. Download before the displayed expiry date; records are deleted after 90 days.', '.research-result-actions', 'download', '.results-page-header'),
  ] } : { key: 'results', title: 'Your saved results', ready: '.result-search', steps: [
    step('Find a protein or analysis', 'Enter a protein accession, tool name or result ID in Search results. Use Tool, Status and Evidence to narrow the list; Order switches between newest and oldest records.', '.result-filters', 'library', '.result-search'),
    step('Open a saved result', 'Select a result card to see its scientific output and original input. Completed cards contain returned data; Failed cards show the error. Analyses from both model pages and Agent appear in this list.', '.result-library-item', 'result', '.empty-results'),
    step('Download from the result page', 'Open a result, then select Export JSON to save its full record. For further analysis, select Discuss with Agent or Reuse inputs on that page. Save files before the expiry date shown on the card; results are retained for 90 days.', '.result-library-item', 'download', '.empty-results'),
  ] };
  return null;
}
