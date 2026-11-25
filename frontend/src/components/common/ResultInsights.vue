<template>
  <section v-if="explanation" class="result-explanation"><strong>How to read this result</strong><p>{{ explanation }}</p></section>
  <EcClassification v-if="showClassification" :payload="data" />
  <ScientificChart v-if="scoreRows.length" title="Positive-class model score" :description="record.tool==='recognize'?'Score for the enzyme class; this is not a measurement of catalytic activity.':'Score for the substrate class; this is not a binding affinity.'" :rows="scoreRows" :max="1" :threshold="0.5" y-label="Model score (0–1)" />
  <ScientificChart v-if="recommendations.length" title="Recommended enzyme classes" description="Candidates in the order returned by the model. Scores are retained on their original scale; they are not experimentally validated probabilities." :rows="recommendations" y-label="Reported score" x-label="EC number" />
  <ScientificChart v-if="composition.length" title="Amino acid composition" description="Residue proportions calculated from the supplied sequence." :rows="composition.map(r=>({label:r.residue,value:r.percent}))" y-label="Composition (%)" x-label="Residue" />
</template>
<script setup>
import {computed} from 'vue';
import EcClassification from './EcClassification.vue';
import ScientificChart from './ScientificChart.vue';
import {unpackResult,aminoAcidComposition} from '@/utils/resultData';
const props=defineProps({record:{type:Object,required:true},showClassification:{type:Boolean,default:true}});
const data=computed(()=>unpackResult(props.record.payload));
const explanations={recognize:'The classifier estimates whether this sequence belongs to the enzyme class. A score of at least 0.5 gives the enzyme label; it does not establish the reaction or experimental activity.',ec:'The EC label describes a predicted enzyme function in a four-level hierarchy. This model uses embedding distances and MaxSep selection; the result is not a calibrated confidence estimate.',substrate:'The model evaluates this protein–molecule pair. A positive-class score greater than 0.5 gives a substrate label. Experimental turnover is still needed to establish compatibility.',kcat:'Predicted catalytic turnover, in s⁻¹, on the linear scale returned by the service. Temperature, pH and assay context can change experimental values. Compare only compatible inputs and conditions.',km:'Predicted Michaelis constant, in mM, on the linear scale returned by the service. Km depends on the kinetic mechanism and assay conditions; it is not a direct binding-affinity measurement.', 'active-sites':'Inspect predicted site types in the sequence, residue table and structure. Residue mapping retains source numbers, chains and insertion codes. Site scores describe functional-site predictions, not structure confidence.',structure:'The structure is a model from ESMFold. The pLDDT track describes local structural confidence, not catalytic-site probability; low-confidence regions need cautious interpretation.',parameters:'These properties describe the supplied sequence. Computed physicochemical properties are not direct measurements under experimental conditions.',blast:'Sequence similarity supports comparison with database proteins. Identity, coverage and E-value should be considered together; similarity alone does not establish identical function.', 'enzyme-info':'These are retrieved database annotations. Missing annotation does not imply that a property or function is absent.'};
const explanation=computed(()=>props.record.status==='failed'?'':explanations[props.record.tool] || '');
const scoreRows=computed(()=>['recognize','substrate'].includes(props.record.tool)&&Number.isFinite(data.value.confidence)&&data.value.confidence>=0&&data.value.confidence<=1?[{label:props.record.tool==='recognize'?'Enzyme':'Substrate',value:data.value.confidence}]:[]);
const recommendations=computed(()=>(data.value.recommendations || []).filter(r=>Number.isFinite(r.confidence)).map(r=>({label:r.ec_number,value:r.confidence})));
const composition=computed(()=>props.record.tool==='parameters'?aminoAcidComposition(props.record.payload):[]);
</script>
<style scoped>
.result-explanation{margin:20px 0;padding:16px 20px;border-left:3px solid var(--color-primary);background:var(--color-primary-light);border-radius:0 8px 8px 0;font-size:13px;line-height:1.7;}.result-explanation strong{font-size:12px;}.result-explanation p{margin-top:4px;}
</style>
