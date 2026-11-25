"""Enzyme Full Info Query Module."""

import requests
import re
import sys
from pathlib import Path
from typing import Dict, Any, List

root = str(Path(__file__).resolve().parents[3])
if root not in sys.path:
    sys.path.insert(0, root)
from shared.uniprot_sections import ec_numbers, protein_name, reaction_smiles
from shared.sequence_mass import sequence_mass
from shared.uniprot import uniprot_json_client, UniProtDownloadError


class EnzymeFullInfoQuery:
    """Query comprehensive enzyme information from UniProt."""
    
    def __init__(self, timeout: int = 30):
        self.base_url = "https://rest.uniprot.org/uniprotkb"
        self.timeout = timeout
    
    def get_full_info(self, uniprot_id: str) -> Dict[str, Any]:
        try:
            data = uniprot_json_client.fetch_json(uniprot_id, allow_partial=True)
            uniprot_id = data['primaryAccession']
            comments = data.get("comments", [])
            features = data.get("features", [])
            source = data.get('enzymindSource')
            partial = bool(source and source.get('partial'))
            warnings = []
            sections = (source or {}).get('section_sources', {})
            unavailable = [section for section, provider in sections.items() if provider is None]
            if partial:
                if not sections:  # Historical partial records only identified these sections.
                    unavailable = ['kinetic_parameters', 'function']
                warnings.append(source.get('note') or 'Some sections could not be retrieved.')
            elif source and source.get('stale'):
                warnings.append(source['note'])
            provenance = {'source': source, 'partial': partial, 'warnings': warnings,
                          'unavailable_sections': unavailable}

            numbers = ec_numbers(data)
            is_enzyme = bool(numbers) or any(c.get("commentType") == "CATALYTIC ACTIVITY" for c in comments)
            if not is_enzyme and partial:
                warnings.append('No catalytic annotation is available in this local snapshot; enzyme status is not established.')
            function = '\n\n'.join(t['value'] for c in comments if c.get('commentType') == 'FUNCTION'
                                   for t in c.get('texts', []) if t.get('value')) or None
            entry_type = data.get('entryType', '').lower()
            reviewed = False if 'unreviewed' in entry_type else True if 'reviewed' in entry_type else None
            structures = []
            for ref in data.get('uniProtKBCrossReferences', []):
                if ref.get('database') == 'PDB' and re.fullmatch(r'[A-Za-z0-9]{4}', ref.get('id', '')):
                    properties = {p.get('key'): p.get('value') for p in ref.get('properties', [])}
                    structures.append({'id': ref['id'].upper(), 'database': 'PDB', 'method': properties.get('Method'),
                                       'resolution': properties.get('Resolution'), 'chains': properties.get('Chains')})
            cofactors = [cofactor.get('name') for c in comments if c.get('commentType') == 'COFACTOR'
                         for cofactor in c.get('cofactors', []) if cofactor.get('name')]
            
            seq_block = data.get("sequence", {})
            mass, mass_source, mass_note = sequence_mass(seq_block)
            sequence_info = {
                "length": seq_block.get("length"),
                "mol_weight": mass, "mol_weight_source": mass_source, "mol_weight_note": mass_note,
                "sequence": seq_block.get("value")
            }
            
            smiles = reaction_smiles(data)
            catalytic_activities = []
            for c in comments:
                if c.get("commentType") == "CATALYTIC ACTIVITY":
                    r = c.get("reaction", {})
                    if r:
                        rhea_id = None
                        for ref in r.get("reactionCrossReferences", []):
                            if ref.get("database") == "Rhea":
                                rhea_id = ref.get("id", "").replace("RHEA:", "")
                                break
                        catalytic_activities.append({
                            "ec_number": r.get("ecNumber"),
                            "reaction": r.get("name"),
                            "reaction_smiles": smiles.get(rhea_id),
                            "rhea_id": rhea_id
                        })
            
            kinetics = {"km": [], "vmax": [], "kcat_note": ""}
            for c in comments:
                if c.get("commentType") == "BIOPHYSICOCHEMICAL PROPERTIES" and c.get("kineticParameters"):
                    kp = c.get("kineticParameters", {})
                    for km in kp.get("michaelisConstants", []):
                        kinetics["km"].append({
                            "value": km.get("constant"),
                            "unit": km.get("unit"),
                            "substrate": km.get("substrate")
                        })
                    for vmax in kp.get("maximumVelocities", []):
                        kinetics["vmax"].append({
                            "value": vmax.get("velocity"),
                            "unit": vmax.get("unit")
                        })
                    kcat_text = "\n".join(t.get("value", "") for t in kp.get("note", {}).get("texts", [])).strip()
                    if kcat_text:
                        kinetics["kcat_note"] = kcat_text
                    break
            
            functional_sites = []
            for f in features:
                if f.get("type") in ["Binding site", "Active site"]:
                    desc = f.get("description", "")
                    loc = f.get("location", {})
                    start = loc.get("start", {}).get("value")
                    end = loc.get("end", {}).get("value")
                    functional_sites.append({
                        "type": f.get("type"),
                        "start": start,
                        "end": end,
                        "description": desc,
                        "ligand": f.get('ligand', {}).get('name'),
                        "position_exact": all(loc.get(key, {}).get('modifier') in (None, 'EXACT') for key in ('start', 'end')),
                        "evidences": f.get('evidences', [])
                    })
            
            return {
                "success": True,
                "is_enzyme": True if is_enzyme else None if partial else False,
                "uniprot_id": uniprot_id,
                "protein_name": protein_name(data),
                "organism": data.get('organism', {}),
                "gene_names": list(dict.fromkeys(g['geneName']['value'] for g in data.get('genes', []) if g.get('geneName', {}).get('value'))),
                "reviewed": reviewed,
                "function": function,
                "ec_numbers": numbers,
                "alphafold_id": next((r.get("id") for r in data.get("uniProtKBCrossReferences", []) if r.get("database") == "AlphaFoldDB"), None),
                "cofactors": list(dict.fromkeys(cofactors)),
                "structure_references": structures,
                "sequence_features": [{'type': f.get('type'), 'description': f.get('description', ''),
                                       'start': f.get('location', {}).get('start', {}).get('value'),
                                       'end': f.get('location', {}).get('end', {}).get('value')}
                                      for f in features if f.get('type') in ('Domain', 'Transmembrane', 'Signal', 'Motif')],
                "sequence_info": sequence_info,
                "catalytic_activities": catalytic_activities,
                "kinetic_parameters": None if "kinetic_parameters" in unavailable else kinetics,
                "functional_sites": functional_sites,
                "error": None,
                **provenance
            }
            
        except UniProtDownloadError as exc:
            return {"success": False, "error": str(exc)}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
