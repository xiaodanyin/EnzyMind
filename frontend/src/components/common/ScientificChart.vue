<template>
  <figure class="scientific-chart">
    <figcaption><div><h4>{{ title }}</h4><p>{{ description }}</p></div><div class="chart-actions"><button @click="exportSvg" :disabled="!chartReady">SVG</button><button @click="exportPng" :disabled="!chartReady">PNG</button><button @click="exportCsv">CSV</button></div></figcaption>
    <ResultPreview :title="title" :image-provider="chartImage" :disabled="!chartReady" :click-to-expand="false">
      <div ref="host" class="chart-canvas" :style="{height:`${chartHeight}px`}" :aria-label="title" role="img"></div>
    </ResultPreview>
    <p v-if="error" role="status">{{ error }} The exact values remain available below.</p>
    <details><summary>View values as a table</summary><ResultPreview :title="`${title} — values`"><div class="chart-table"><table><thead><tr><th>{{ xLabel }}</th><th>{{ yLabel }}</th></tr></thead><tbody><tr v-for="(row,i) in rows" :key="i"><th>{{ row.label }}</th><td>{{ row.value == null ? 'Not available' : row.value }}</td></tr></tbody></table></div></ResultPreview></details>
  </figure>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { downloadData } from '@/utils/workspace';
import ResultPreview from './ResultPreview.vue';
const props = defineProps({title:String,description:String,rows:{type:Array,default:()=>[]},type:{type:String,default:'bar'},xLabel:{type:String,default:'Category'},yLabel:{type:String,default:'Value'},max:Number,threshold:Number});
const emit = defineEmits(['select']);
const host=ref(null),error=ref(''),chartReady=ref(false);
const chartHeight=computed(()=>props.type==='line'?300:Math.max(300,props.rows.length*32+84));
let chart,observer,disposed=false;
const chartImage = () => chart?.getDataURL({ type: 'svg', backgroundColor: '#fff' }) || '';
function render() {
  if (!chart) return;
  const line=props.type==='line';
  chart.setOption({animation:false,color:['#6556c9'],aria:{enabled:true},tooltip:{trigger:'axis',renderMode:'richText',valueFormatter:v=>v==null?'Not available':String(v)},grid:{left:line?52:12,right:30,top:line?36:20,bottom:line?(props.rows.length>100?84:64):48,containLabel:!line},
    xAxis:line?{type:'category',data:props.rows.map(r=>r.label),name:props.xLabel,nameLocation:'middle',nameGap:44,axisLabel:{hideOverlap:true,fontSize:10}}:{type:'value',min:0,max:props.max,name:props.yLabel,nameLocation:'middle',nameGap:30,splitNumber:host.value.clientWidth<400?3:5,axisLabel:{hideOverlap:true},splitLine:{lineStyle:{color:'#eef0f5'}}},
    yAxis:line?{type:'value',min:0,max:props.max,name:props.yLabel,splitLine:{lineStyle:{color:'#eef0f5'}}}:{type:'category',inverse:true,data:props.rows.map(r=>r.label),axisLabel:{interval:0,fontSize:11},axisTick:{show:false},axisLine:{show:false}},
    dataZoom:line&&props.rows.length>100?[{type:'inside'},{type:'slider',height:16,bottom:0}]:[],
    series:[{type:props.type,data:props.rows.map(r=>r.value),barMaxWidth:26,showSymbol:props.rows.length<80,connectNulls:false,itemStyle:{borderRadius:line?0:3},lineStyle:{width:1.7},areaStyle:line?{opacity:.06}:undefined,markLine:props.threshold==null?undefined:{symbol:'none',label:{formatter:`Threshold ${props.threshold}`,position:'insideEndTop'},lineStyle:{color:'#836cb1',type:'dashed'},data:[{[line?'yAxis':'xAxis']:props.threshold}]}}]},true);
}
async function exportSvg(){downloadData(chart.renderToSVGString(),`enzymind-${props.title}.svg`,'image/svg+xml');}
async function exportPng(){
  const url=URL.createObjectURL(new Blob([chart.renderToSVGString()],{type:'image/svg+xml'}));
  try {
    const img=new Image();img.src=url;await img.decode();
    const c=document.createElement('canvas');c.width=host.value.clientWidth*2;c.height=host.value.clientHeight*2;
    const ctx=c.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(img,0,0,c.width,c.height);
    const a=document.createElement('a');a.href=c.toDataURL('image/png');a.download=`enzymind-${props.title}.png`;a.click();
  }catch{error.value='PNG export could not complete.';}finally{URL.revokeObjectURL(url);}
}
function exportCsv(){const q=v=>`"${String(v??'').replaceAll('"','""')}"`;downloadData([[props.xLabel,props.yLabel],...props.rows.map(r=>[r.label,r.value])].map(r=>r.map(q).join(',')).join('\n'),`enzymind-${props.title}.csv`,'text/csv');}
watch(()=>[props.rows,props.type,props.max,props.threshold],render,{deep:true});
onMounted(async()=>{try{
  const [{init,use},{BarChart,LineChart},{GridComponent,TooltipComponent,AriaComponent,MarkLineComponent,DataZoomComponent},{SVGRenderer}]=await Promise.all([import('echarts/core'),import('echarts/charts'),import('echarts/components'),import('echarts/renderers')]);
  if(disposed)return;use([BarChart,LineChart,GridComponent,TooltipComponent,AriaComponent,MarkLineComponent,DataZoomComponent,SVGRenderer]);
  chart=init(host.value,null,{renderer:'svg'});chartReady.value=true;chart.on('click',p=>emit('select',p.dataIndex));render();observer=new ResizeObserver(()=>{chart?.resize();render();});observer.observe(host.value);
}catch{error.value='The chart could not load.';}});
onBeforeUnmount(()=>{disposed=true;observer?.disconnect();chart?.dispose();chart=null;});
</script>
<style scoped>
.scientific-chart{margin:24px 0;padding:20px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);min-width:0;}
figcaption{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;}h4{font-size:15px;}p{font-size:12px;line-height:1.6;color:var(--color-text-secondary);margin-top:5px;}
.chart-actions{display:flex;gap:5px;align-items:start;}button{background:white;border:1px solid var(--color-border);border-radius:5px;font:inherit;font-size:11px;padding:5px 8px;cursor:pointer;}.chart-canvas{height:300px;width:100%;min-width:0;}details{font-size:12px;}summary{cursor:pointer;color:var(--color-primary);}.chart-table{max-height:260px;overflow:auto;margin-top:12px;}table{border-collapse:collapse;width:100%;}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--color-border);font-weight:400;}thead th{font-weight:600;}
@media(max-width:600px){.scientific-chart{padding:12px;}}
</style>
