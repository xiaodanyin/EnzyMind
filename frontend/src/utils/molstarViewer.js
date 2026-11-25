import { PluginContext } from 'molstar/lib/mol-plugin/context';
import { DefaultPluginSpec } from 'molstar/lib/mol-plugin/spec';
import { PluginCommands } from 'molstar/lib/mol-plugin/commands';
import { ColorTheme } from 'molstar/lib/mol-theme/color';
import { Color } from 'molstar/lib/mol-util/color';
import { Structure, StructureElement, StructureProperties as P, StructureQuery } from 'molstar/lib/mol-model/structure';
import { residues } from 'molstar/lib/mol-model/structure/query/queries/generators';
import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder';
import { ParamDefinition as PD } from 'molstar/lib/mol-util/param-definition';
import { Vec4 } from 'molstar/lib/mol-math/linear-algebra/3d/vec4';
import { residueKey } from './residueMapping';

const atomAt = l => ({chain:P.chain.auth_asym_id(l),resi:P.residue.auth_seq_id(l),icode:P.residue.pdbx_PDB_ins_code(l) || '',resn:P.residue.auth_comp_id(l),b:P.atom.B_iso_or_equiv(l),x:l.unit.conformation.x(l.element),y:l.unit.conformation.y(l.element),z:l.unit.conformation.z(l.element)});
const eq = MS.core.rel.eq;
const atomProp = MS.struct.atomProperty.macromolecular;
const identityExpression = a => MS.core.logic.and([eq([atomProp.auth_asym_id(),a.chain]),eq([atomProp.auth_seq_id(),a.resi]),eq([atomProp.pdbx_PDB_ins_code(),a.icode || ''])]);

export async function createProteinViewer(mount, text, format, callbacks) {
  const spec = DefaultPluginSpec();
  spec.layout = {initial:{isExpanded:false,showControls:false}};
  spec.canvas3d = {renderer:{backgroundColor:Color(0xf4f7f8)},camera:{manualReset:true,helper:{axes:{name:'off',params:{}}}}};
  const plugin = new PluginContext(spec);
  let disposed = false, revision = 0, color = () => '#91aabd', components = [], queue = Promise.resolve();
  const subscriptions = [];
  const theme = {name:'enzymind-residues',label:'EnzyMind residues',category:ColorTheme.Category.Residue,
    factory:(ctx,props) => ({factory:theme.factory,granularity:'group',props,contextHash:props.revision,
      color:l => Color(parseInt((StructureElement.Location.is(l) ? color(atomAt(l)) : '#91aabd').slice(1),16))}),
    getParams:()=>({revision:PD.Numeric(0)}),defaultValues:{revision:0},isApplicable:()=>true};
  try {
    await plugin.init();
    plugin.representation.structure.themes.colorThemeRegistry.add(theme);
    if (!await plugin.mountAsync(mount)) throw new Error('Mol* could not initialize WebGL.');
    const raw = await plugin.builders.data.rawData({data:text,label:'EnzyMind structure'});
    const trajectory = await plugin.builders.structure.parseTrajectory(raw,format === 'cif' ? 'mmcif' : format);
    const model = await plugin.builders.structure.createModel(trajectory,{modelIndex:0});
    const structureRef = await plugin.builders.structure.createStructure(model,{name:'model',params:{}});
    const structure = structureRef.obj.data;
    const atoms = [], seen = new Set();
    Structure.eachAtomicHierarchyElement(structure,{atom:l => {
      if (P.atom.label_atom_id(l) !== 'CA' || P.residue.group_PDB(l) !== 'ATOM') return;
      const a = atomAt(l), key = residueKey(a);
      if (!seen.has(key)) {seen.add(key); atoms.push(a);}
    }});
    if (!atoms.length) throw new Error('No protein alpha-carbon coordinates were found.');
    subscriptions.push(plugin.behaviors.interaction.click.subscribe(e => {
      if (!StructureElement.Loci.is(e.current.loci) || StructureElement.Loci.isEmpty(e.current.loci)) return;
      const l = StructureElement.Location.create();
      StructureElement.Loci.getFirstLocation(e.current.loci,l);
      const key = residueKey(atomAt(l));
      const a = atoms.find(a => residueKey(a) === key);
      if (a) callbacks.select(a);
    }));
    // Trackball rotation mutates the camera directly and does not emit
    // camera.stateChanged. Project labels after rendered frames instead.
    subscriptions.push(plugin.canvas3d.didDraw.subscribe(callbacks.camera));
    return {
      atoms,
      async paint(options) {
        const job = async () => {
          if (disposed) return;
          color = options.color;
          if (components.length) {
            const update = plugin.build(); components.forEach(c => update.delete(c.ref)); await update.commit();
          }
          components = [];
          const expression = MS.struct.generator.atomGroups(options.chain === '*' ? {} : {'chain-test':eq([atomProp.auth_asym_id(),options.chain])});
          const main = await plugin.builders.structure.tryCreateComponentFromExpression(structureRef,expression,'visible',{label:'Protein'});
          if (main) {
            components.push(main);
            await plugin.builders.structure.representation.addRepresentation(main,{type:{cartoon:'cartoon',stick:'ball-and-stick',surface:'molecular-surface'}[options.style],color:theme.name,colorParams:{revision:++revision}});
          }
          if (options.sites.length && options.style !== 'stick') {
            const selected = MS.struct.generator.atomGroups({'residue-test':MS.core.logic.or(options.sites.map(identityExpression))});
            const sites = await plugin.builders.structure.tryCreateComponentFromExpression(structureRef,selected,'sites',{label:'Functional sites'});
            if (sites) {components.push(sites); await plugin.builders.structure.representation.addRepresentation(sites,{type:'ball-and-stick',color:theme.name,colorParams:{revision}});}
          }
        };
        queue = queue.catch(()=>{}).then(job);
        return queue;
      },
      focus(a) {
        const loci = StructureQuery.loci(residues({residueTest:ctx => residueKey(atomAt(ctx.element)) === residueKey(a)}),structure);
        plugin.managers.interactivity.lociSelects.selectOnly({loci});
        plugin.managers.camera.focusLoci(loci,{durationMs:300});
      },
      clearSelection() {plugin.managers.interactivity.lociSelects.deselectAll();},
      reset:() => PluginCommands.Camera.Reset(plugin),
      resize() {plugin.handleResize(); callbacks.camera();},
      async snapshot() {await queue; return plugin.helpers.viewportScreenshot.getImageDataUri();},
      project(a) {
        const camera = plugin.canvas3d.camera, p = camera.project(Vec4(),[a.x,a.y,a.z]), v = camera.viewport, r = mount.getBoundingClientRect();
        if (p[2] < 0 || p[2] > 1 || p[3] <= 0 || !v.width || !v.height) return null;
        return {x:(p[0]-v.x)*r.width/v.width,y:r.height-(p[1]-v.y)*r.height/v.height};
      },
      dispose() {disposed = true; subscriptions.forEach(s => s.unsubscribe()); plugin.dispose();}
    };
  } catch (e) {subscriptions.forEach(s => s.unsubscribe()); plugin.dispose(); throw e;}
}
