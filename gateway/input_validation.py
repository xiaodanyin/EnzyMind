"""Single-protein contracts shared by browser and Agent entry points."""
import re
from fastapi import HTTPException

ACCESSION = re.compile(r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-[1-9][0-9]*)?\Z")
SINGLE_PROTEIN = {'enzy_recognize', 'ecnumber_predict', 'substrate_predict', 'kcat_predict', 'km_predict', 'structure_predict', 'protparam', 'sequence_alignment', 'active_sites'}


def normalize_inputs(service, inputs):
    if service == 'query_mechanism_mcsa' and isinstance(inputs, dict) and isinstance(inputs.get('query_id'), str):
        value = inputs['query_id'].strip()
        match = re.fullmatch(r'(?:M-?CSA[\s:_-]*)?([0-9]+)', value, re.I)
        return {**inputs, 'query_id': match.group(1) if match else value}
    if service not in SINGLE_PROTEIN or not isinstance(inputs, dict):
        return inputs
    result = dict(inputs)
    for field in ('query', 'enzyme_query', 'aa_sequence', 'sequence'):
        if field not in result:
            continue
        value = result[field]
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(422, f'{field}: enter a protein sequence or UniProt accession.')
        value = value.strip().upper()
        method = result.get('enzyme_input_type' if field == 'enzyme_query' else 'input_type')
        if method == 'uniprot' or (method != 'sequence' and field not in ('sequence', 'aa_sequence') and ACCESSION.fullmatch(value)):
            if not ACCESSION.fullmatch(value):
                raise HTTPException(422, 'Enter a valid UniProt accession, for example P00761.')
            result[field] = value
            continue
        lines = value.splitlines()
        headers = [i for i, line in enumerate(lines) if line.lstrip().startswith('>')]
        if headers:
            if len(headers) != 1 or headers[0] != 0:
                raise HTTPException(422, 'This tool accepts one FASTA record. Select a single record; sequences are never concatenated.')
            value = ''.join(lines[1:])
        sequence = re.sub(r'\s+', '', value)
        invalid = [(i + 1, c) for i, c in enumerate(sequence) if c not in 'ACDEFGHIKLMNPQRSTVWY']
        if not sequence or invalid:
            raise HTTPException(422, 'Use the 20 standard amino acids. Invalid residues: ' + ', '.join(f'{c} at {i}' for i, c in invalid[:8]))
        result[field] = sequence
    return result
