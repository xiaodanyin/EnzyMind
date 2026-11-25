<template>
  <section class="enzyme-pair-result result-inputs" aria-label="Enzyme and molecule pairing">
    <header class="pair-header"><div><span class="eyebrow">{{ recommendation ? 'REACTION → ENZYME CLASSES' : 'ENZYME + CHEMICAL CONTEXT' }}</span><h4>{{ recommendation ? 'Enzyme classes for this reaction' : reaction ? 'Enzyme–reaction pair' : 'Enzyme–substrate pair' }}</h4></div><span class="pair-badge">{{ pairs.length>1 ? `${pairs.length} returned pairs` : 'Same analysis' }}</span></header>
    <p class="pair-intro">{{ recommendation ? 'Candidate EC functions are paired with the submitted transformation.' : 'Read the enzyme and its paired molecule together, then inspect the result below.' }}</p>
    <article v-for="(pair,i) in pairs" :key="pair.key" class="pair-record">
      <h5 v-if="pairs.length>1" class="pair-index">Pair {{ i+1 }}</h5>
      <div class="pair-grid">
        <section class="pair-partner enzyme-side" aria-label="Enzyme partner"><div class="partner-heading"><span class="partner-number">01</span><div><h5>{{ recommendation ? 'Candidate enzyme classes' : 'Enzyme' }}</h5><small>{{ pair.protein.structure ? 'Saved structure & annotations' : pair.protein.sequences.length ? 'Saved protein sequence' : pair.protein.ecCodes.length ? 'EC function hierarchy' : 'Protein identity & reference context' }}</small></div></div>
          <div v-if="pair.recommendations.length" class="candidate-ranks"><div v-for="(candidate,j) in pair.recommendations" :key="j"><span>{{ j+1 }}</span><strong>EC {{ candidate.ec_number }}</strong><small v-if="candidate.confidence!=null">Score {{ candidate.confidence }}</small></div></div>
          <EnzymePartner :protein="pair.protein" />
        </section>
        <div class="pair-connector">
          <div class="pair-link">
            <span class="pair-link-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 20V4m-4 4 4-4 4 4M16 4v16m-4-4 4 4 4-4" /></svg>
            </span>
            <div class="pair-link-label">
              <strong>{{ recommendation ? 'Candidate classes & reaction' : pair.isReaction ? 'Enzyme–reaction pair' : 'Enzyme–substrate pair' }}</strong>
              <small>{{ recommendation ? 'Candidate association · model prediction' : 'Paired inputs · same analysis' }}</small>
            </div>
          </div>
        </div>
        <section class="pair-partner chemical-side" aria-label="Chemical partner"><div class="partner-heading"><span class="partner-number">02</span><div><h5>{{ pair.isReaction ? 'Reaction' : 'Substrate' }}</h5><small>{{ pair.chemicalSource }}</small></div></div><ChemicalPreview v-if="pair.smiles" :smiles="pair.smiles" :title="pair.isReaction ? 'Paired reaction' : 'Paired substrate'" /><div v-for="(activity,j) in pair.reactions" :key="j" class="recorded-reaction"><span>Recorded reaction {{ j+1 }}</span><p>{{ activity.reaction_name }}</p><small v-if="activity.ec_number">EC {{ activity.ec_number }}</small><a v-if="rheaId(activity.rhea_id)" :href="`https://www.rhea-db.org/rhea/${rheaId(activity.rhea_id)}`" target="_blank" rel="noopener noreferrer">Rhea {{ rheaId(activity.rhea_id) }} ↗</a></div><p v-if="!pair.smiles && !pair.reactions.length" class="pair-intro">No molecular input was saved with this result.</p><details v-if="pair.smiles" class="chemical-source"><summary>Original {{ pair.isReaction ? 'reaction' : 'substrate' }} SMILES</summary><pre>{{ pair.smiles }}</pre></details><p v-if="pair.smiles" class="pair-footnote">{{ pair.isReaction ? 'Reaction direction follows the saved SMILES.' : 'Molecular structure from the saved SMILES.' }} Separate views show the input pairing.</p><p v-else-if="pair.reactions.length" class="pair-footnote">Reaction notation as recorded by the source. Molecular SMILES were not included.</p></section>
      </div>
    </article>
    <div v-if="$slots.default" class="pair-outcome"><span class="eyebrow">RESULT FOR THIS {{ reaction ? 'REACTION' : 'PAIR' }}</span><slot /></div>
  </section>
</template>
<script setup>
import {computed} from 'vue';
import EnzymePartner from './EnzymePartner.vue';
import ChemicalPreview from './ChemicalPreview.vue';
const props=defineProps({pairs:{type:Array,required:true},tool:String});
const recommendation=computed(()=>props.tool==='enzyme-type');
const reaction=computed(()=>props.pairs.some(p=>p.isReaction));
const rheaId=value=>String(value || '').match(/^(?:RHEA:)?(\d+)$/i)?.[1] || '';
</script>
<style scoped>
.enzyme-pair-result{container-type:inline-size;min-width:0;margin:22px 0;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);overflow:hidden}.pair-header{padding:20px 20px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.eyebrow{font-size:9px;letter-spacing:.1em;color:var(--color-text-muted);font-weight:600}.pair-header h4{font-size:17px;line-height:1.5;margin:5px 0 0}.pair-badge{font-size:10px;padding:5px 9px;border-radius:5px;background:var(--color-primary-light);color:var(--color-primary)}.pair-intro{font-size:12px;line-height:1.7;color:var(--color-text-secondary);margin:10px 20px 18px}.pair-record{margin:0 16px 16px;padding:12px;border:1px solid #dbe7fb;border-radius:14px;background:#f5f8fe}.pair-index{font-size:12px;font-weight:700;color:var(--color-primary-dark);margin:0 2px 12px}.pair-grid{display:grid;grid-template-columns:minmax(0,1fr);align-items:start}.pair-partner{min-width:0;border:1px solid #a9c4f4;border-top:3px solid var(--color-primary);border-radius:10px;padding:16px;background:var(--color-surface);box-shadow:0 3px 12px rgb(37 99 235 / 7%)}.partner-heading{display:flex;align-items:center;gap:10px;padding:12px;margin-bottom:16px;border:1px solid #dbe7fb;border-radius:7px;background:var(--color-primary-light)}.partner-number{height:30px;width:30px;flex-shrink:0;display:grid;place-items:center;border-radius:8px;background:var(--color-primary);color:#fff;font:600 12px monospace}.partner-heading h5{font-size:14px;margin:0 0 4px}.partner-heading small{font-size:11px;color:var(--color-text-secondary)}/* A shared frame and a visible vertical link keep each pair together. */
.pair-connector{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:0}
.pair-connector::before,.pair-connector::after{content:"";width:2px;height:14px;flex-shrink:0;background:#8fb3ef}
.pair-link{display:flex;align-items:center;gap:11px;max-width:100%;padding:10px 16px;border:1px solid #9fbdf1;border-radius:12px;background:var(--color-primary-light);box-shadow:0 2px 6px rgb(37 99 235 / 8%)}
.pair-link-icon{display:grid;place-items:center;flex-shrink:0;width:34px;height:34px;border-radius:50%;background:var(--color-primary);color:#fff}
.pair-link-icon svg{width:22px;height:22px}
.pair-link-label{min-width:0}
.pair-link-label strong{display:block;font-size:13px;line-height:1.5;font-weight:700;color:var(--color-primary-dark);overflow-wrap:anywhere}
.pair-link-label small{display:block;font-size:11px;line-height:1.6;color:var(--color-text-secondary);margin-top:2px}
.chemical-source{margin-top:14px;font-size:11px}.chemical-source summary{cursor:pointer;color:var(--color-text-secondary)}.chemical-source pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.8 monospace;padding:10px;border-radius:5px;background:var(--color-background);max-height:160px;overflow:auto}.pair-footnote{font-size:10px;line-height:1.7;color:var(--color-text-muted);margin:12px 0 0}.pair-outcome{padding:16px 20px 0;border-top:1px solid var(--color-border);background:var(--color-primary-light)}.candidate-ranks{margin-bottom:16px}.candidate-ranks>div{display:flex;align-items:center;gap:9px;padding:8px 0;border-bottom:1px solid var(--color-border);font-size:11px;flex-wrap:wrap}.candidate-ranks>div>span{color:var(--color-text-muted);font:11px monospace}.candidate-ranks small{margin-left:auto;color:var(--color-text-secondary)}.chemical-side :deep(.chemical-preview){padding:0;border:0;margin:0;min-height:0}
@container(max-width:850px){.pair-record{margin:0 12px 12px;padding:8px}.pair-partner{padding:14px}.pair-header{padding:16px 16px 0}.pair-header h4{font-size:15px}.pair-intro{margin:10px 16px 16px}.pair-outcome{padding:14px 16px 0}}
@container(max-width:450px){.pair-link{padding:10px;gap:9px}.pair-link-label strong{font-size:12px}.partner-heading{padding:10px}}
</style>
<style scoped>
.recorded-reaction{padding:16px;background:var(--color-background);border:1px solid var(--color-border);border-radius:8px;margin:12px 0}.recorded-reaction>span{font-size:10px;color:var(--color-text-muted)}.recorded-reaction p{font-size:14px;line-height:1.9;overflow-wrap:anywhere;margin:12px 0}.recorded-reaction small,.recorded-reaction a{font-size:11px;margin-right:14px}.recorded-reaction a{color:var(--color-primary)}
</style>
