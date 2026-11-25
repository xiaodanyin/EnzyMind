"""Section coverage for EnzyMind's UniProt query APIs."""
COMMENT_TYPES = {'catalytic_activity': 'CATALYTIC ACTIVITY', 'function': 'FUNCTION',
                 'kinetics': 'BIOPHYSICOCHEMICAL PROPERTIES', 'cofactors': 'COFACTOR'}
SITE_TYPES = {'Binding site', 'Active site'}
REGION_TYPES = {'Domain', 'Transmembrane', 'Signal', 'Motif'}
OVERVIEW = {'sequence': 'sequence_info', 'protein_name': 'protein_name', 'organism': 'organism',
            'reviewed': 'reviewed', 'catalytic_activity': 'catalytic_activities',
            'functional_sites': 'functional_sites', 'kinetics': 'kinetic_parameters',
            'function': 'function', 'genes': 'gene_names', 'cofactors': 'cofactors',
            'pdb': 'structure_references', 'regions': 'sequence_features',
            'ec_numbers': 'ec_numbers', 'alphafold': 'alphafold_id'}


def protein_name(data):
    description = data.get('proteinDescription', {})
    names = [description.get('recommendedName', {}), *description.get('submissionNames', [])]
    return next((name['fullName']['value'] for name in names if name.get('fullName', {}).get('value')), None)


def local_scope(data, base):
    scope = set(base)
    if protein_name(data):
        scope.add('protein_name')
    if data.get('organism', {}).get('scientificName'):
        scope.add('organism')
    if 'reviewed' in data.get('entryType', '').lower():
        scope.add('reviewed')
    if data.get('genes'):
        scope.add('genes')
    for c in data.get('comments', []):
        kind = c.get('commentType')
        if kind == 'CATALYTIC ACTIVITY' and c.get('reaction'):
            scope.add('catalytic_activity')
        if kind == 'FUNCTION' and any(t.get('value') for t in c.get('texts', [])):
            scope.add('function')
        if kind == 'BIOPHYSICOCHEMICAL PROPERTIES' and c.get('kineticParameters'):
            scope.add('kinetics')
        if kind == 'COFACTOR' and c.get('cofactors'):
            scope.add('cofactors')
    if any(f.get('type') in SITE_TYPES for f in data.get('features', [])):
        scope.add('functional_sites')
    if ec_numbers(data):
        scope.add('ec_numbers')
    if 'ec_numbers' in scope or 'catalytic_activity' in scope:
        scope.add('enzyme_status')
    if any(r.get('database') == 'AlphaFoldDB' and r.get('id') for r in data.get('uniProtKBCrossReferences', [])):
        scope.add('alphafold')
    if any(r.get('database') == 'PDB' for r in data.get('uniProtKBCrossReferences', [])):
        scope.add('pdb')
    if any(f.get('type') in REGION_TYPES for f in data.get('features', [])):
        scope.add('regions')
    return sorted(scope)


def combine(local, supplement=None, note=None):
    """Keep snapshot sections together. Only a sequence-matched entry may supplement them."""
    src = local['enzymindSource']
    scope = set(src['annotation_scope'])
    if supplement is not None and (supplement.get('primaryAccession') != local['primaryAccession']
            or supplement.get('sequence', {}).get('value') != local['sequence']['value']):
        supplement = None
        note = 'The supplement could not be matched to the local sequence version.'
    other = (supplement or {}).get('enzymindSource') or {'method': 'uniprot_api', 'name': 'UniProt API'}
    fields = {field: src['method'] if cap in scope else other['method'] if supplement is not None else None
              for cap, field in OVERVIEW.items()}
    source = {**src, 'partial': None in fields.values(), 'section_sources': fields}
    merged = dict(local)
    if supplement is not None:
        source.update(name=src['name'] + ' + ' + other['name'], supplement=other, stale=bool(other.get('stale')))
        source['note'] = 'Sections missing from the local snapshot were obtained from ' + other['name'] + '.'
        if other.get('stale'):
            source['note'] += ' The cached supplement may have changed since retrieval.'
        for cap, key in [('protein_name','proteinDescription'), ('organism','organism'), ('reviewed','entryType'), ('genes','genes')]:
            if cap not in scope and key in supplement:
                merged[key] = supplement[key]
        if 'ec_numbers' not in scope:
            # ECs may only occur within the supplement's protein name, even when
            # the name itself is already available from the local snapshot.
            merged['enzymindEcNumbers'] = ec_numbers(supplement)

        def blocks(key, category, covered):
            supplemental = [item for item in supplement.get(key, []) if category(item) not in covered]
            replaced = {category(item) for item in supplemental}
            return [item for item in local.get(key, []) if category(item) not in replaced] + supplemental
        merged['comments'] = blocks('comments', lambda c: c.get('commentType'),
                                    {kind for cap, kind in COMMENT_TYPES.items() if cap in scope})
        types = (SITE_TYPES if 'functional_sites' in scope else set()) | (REGION_TYPES if 'regions' in scope else set())
        merged['features'] = blocks('features', lambda f: f.get('type'), types)
        refs = {r.get('database') for r in local.get('uniProtKBCrossReferences', [])}
        merged['uniProtKBCrossReferences'] = blocks('uniProtKBCrossReferences', lambda r: r.get('database'), refs)
    elif note:
        source['note'] = note
    merged['enzymindSource'] = source
    return merged


def ec_numbers(data):
    desc = data.get('proteinDescription', {})
    names = [desc.get('recommendedName', {}), *desc.get('alternativeNames', []), *desc.get('submissionNames', [])]
    numbers = [n.get('value') for name in names for n in name.get('ecNumbers', [])]
    numbers += [c.get('reaction', {}).get('ecNumber') for c in data.get('comments', []) if c.get('commentType') == 'CATALYTIC ACTIVITY']
    return list(dict.fromkeys(n for n in [*numbers, *data.get('enzymindEcNumbers', [])] if n))


def reaction_smiles(data):
    return {str(r['rheaId']).removeprefix('RHEA:'): r['rxnSmiles'] for r in data.get('easifaLocal', {}).get('reactions', [])
            if r.get('rheaId') and r.get('rxnSmiles')}
