import itertools
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Draw, Lipinski, rdMolDescriptors

keys = [('ek', 'kcat', 's^-1'), ('em', 'km', 'mM'), ('pk', 'kcat', 's^-1'), ('pm', 'km', 'mM')]
values = []
for key, field, unit in keys:
    payload = results[data[key]]
    assert payload['success'] is True and payload['unit'] == unit
    value = float(payload[field])
    assert math.isfinite(value) and value > 0
    values.append(value)
ke, me, kp, mp = values
names, smiles = ['Ethanol', '1-Propanol'], ['CCO', 'CCCO']
mols = [Chem.MolFromSmiles(s) for s in smiles]
assert all(m is not None for m in mols)
Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(400, 300), legends=names).save(str(output_dir / 'substrates.png'))

comparison = []
for name, smi, mol, k, km, ki, mi in zip(names, smiles, mols, [ke, kp], [me, mp], ['ek', 'pk'], ['em', 'pm']):
    comparison.append(dict(substrate=name, smiles=smi, MW_g_mol=Descriptors.MolWt(mol),
        cLogP=Crippen.MolLogP(mol), TPSA_A2=rdMolDescriptors.CalcTPSA(mol),
        HBD=Lipinski.NumHDonors(mol), HBA=Lipinski.NumHAcceptors(mol),
        kcat_s_inv=k, Km_mM=km, efficiency_mM_inv_s_inv=k/km,
        efficiency_M_inv_s_inv=1000*k/km, kcat_result_id=data[ki], km_result_id=data[mi]))
pd.DataFrame(comparison).to_csv(output_dir / 'comparison.csv', index=False)

def rate(k, km, s):
    return 0.1 * k * s / (km + s)

grid = np.logspace(-2, 2, 401)
ve, vp = rate(ke, me, grid), rate(kp, mp, grid)
pd.DataFrame(dict(S_mM=grid, ethanol_uM_s=ve, propanol_uM_s=vp)).to_csv(output_dir / 'rates.csv', index=False)
probe = [0.1, 1.0, 10.0, 100.0]
rates = [dict(S_mM=s, ethanol_uM_s=rate(ke, me, s), propanol_uM_s=rate(kp, mp, s)) for s in probe]
root = (kp*me-ke*mp)/(ke-kp) if ke != kp else None
identical = ke == kp and me == mp
in_range = identical or (root is not None and root > 0 and 0.01 <= root <= 100)
crossing = dict(signed_root_mM=root, identical_curves=identical, crossing_in_range=in_range,
                grid_sign_change=bool(np.any((ve[:-1]-vp[:-1])*(ve[1:]-vp[1:]) < 0)))

scenarios = []
for a, b, c, d in itertools.product([0.5, 1.0, 2.0], repeat=4):
    for s in probe:
        x, y = rate(ke*a, me*b, s), rate(kp*c, mp*d, s)
        winner = 'equal' if math.isclose(x, y, rel_tol=1e-12, abs_tol=0) else ('ethanol' if x > y else 'propanol')
        scenarios.append(dict(ethanol_kcat_factor=a, ethanol_Km_factor=b, propanol_kcat_factor=c,
            propanol_Km_factor=d, S_mM=s, ethanol_uM_s=x, propanol_uM_s=y, rate_ratio=x/y, winner=winner))
pd.DataFrame(scenarios).to_csv(output_dir / 'sensitivity.csv', index=False)
sensitivity = []
for s in probe:
    rows = [r for r in scenarios if r['S_mM'] == s]
    sensitivity.append(dict(S_mM=s, scenarios=len(rows), ethanol_faster=sum(r['winner']=='ethanol' for r in rows),
        propanol_faster=sum(r['winner']=='propanol' for r in rows), equal=sum(r['winner']=='equal' for r in rows),
        min_ratio=min(r['rate_ratio'] for r in rows), max_ratio=max(r['rate_ratio'] for r in rows)))

fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
colors = ['#2878b5', '#d97720']
for values, name, color in zip([ve, vp], names, colors):
    ax[0].semilogx(grid, values, label=name, color=color, linewidth=2)
ax[0].set(xlabel='Substrate S (mM)', ylabel='Initial rate (uM/s)', title='Model-based prediction: E = 0.1 uM')
ax[0].legend(); ax[0].grid(alpha=0.25)
eff = [ke/me, kp/mp]
ax[1].bar(names, eff, color=colors)
ax[1].set(ylabel='kcat/Km (mM$^{-1}$ s$^{-1}$)', title='Model-based catalytic efficiency', ylim=(0, max(eff)*1.2))
for i, value in enumerate(eff):
    ax[1].text(i, value, f'{value:.3f}', ha='center', va='bottom')
x = np.arange(4)
ec, pc, eq = [[r[k] for r in sensitivity] for k in ['ethanol_faster', 'propanol_faster', 'equal']]
ax[2].bar(x, ec, color=colors[0], label='Ethanol faster')
ax[2].bar(x, pc, bottom=ec, color=colors[1], label='1-Propanol faster')
ax[2].bar(x, eq, bottom=np.array(ec)+np.array(pc), color='gray', label='Equal')
ax[2].set(xticks=x, xticklabels=[f'{s:g}' for s in probe], xlabel='Substrate S (mM)',
    ylabel='Scenario count (total 81)', title='Sensitivity scenarios: factors 0.5 / 1 / 2', ylim=(0, 105))
ax[2].legend(fontsize=8, loc='upper right')
fig.tight_layout(); fig.savefig(output_dir / 'analysis.png', dpi=150); plt.close(fig)

summary = dict(enzyme='ADH1 / P00330', sources=data, active_site_concentration_uM=0.1,
    comparison=comparison, specified_rates=rates, crossing=crossing, sensitivity=sensitivity,
    assumptions=['Saturating NAD+, fixed conditions, initial rates without product accumulation.',
        'Independently predicted kcat and Km need not describe matched assay conditions.',
        'Sensitivity scenarios are not probabilities or confidence intervals.',
        'Km is not interpreted as binding affinity; no experimental validation.'])
(output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2))
expected = {'substrates.png', 'analysis.png', 'comparison.csv', 'rates.csv', 'sensitivity.csv', 'summary.json'}
assert {p.name for p in output_dir.iterdir()} == expected
result = dict(efficiency_mM_inv_s_inv=eff, specified_rates=rates, crossing=crossing,
              sensitivity=sensitivity, rows=dict(comparison=2, rates=401, sensitivity=324))
