import unittest
from fastapi import HTTPException
from gateway.input_validation import normalize_inputs

class InputValidationTests(unittest.TestCase):
    def test_mcsa_display_labels_resolve_without_changing_protein_ids(self):
        for value in ['203','M-CSA-203','MCSA: 203']:
            self.assertEqual(normalize_inputs('query_mechanism_mcsa',{'query_id':value})['query_id'],'203')
        for value in ['P00698','1dpx','P00698-2']:
            self.assertEqual(normalize_inputs('query_mechanism_mcsa',{'query_id':value})['query_id'],value)
    def test_single_fasta_and_invalid_residues(self):
        self.assertEqual(normalize_inputs('enzy_recognize',{'query':'>first\nac de\nfg','input_type':'sequence'})['query'],'ACDEFG')
        for text in ('>first\nACDE\n>second\nFGHI','ACDE1*','ACDU','>empty\n'):
            with self.assertRaises(HTTPException):normalize_inputs('enzy_recognize',{'query':text,'input_type':'sequence'})
    def test_accessions_and_chemical_queries(self):
        for identifier in ('p00761','A0A024RBG1','P01308-2'):
            self.assertEqual(normalize_inputs('protparam',{'query':identifier})['query'],identifier.upper())
        reaction={'query':'CCO>>CC=O','k':5}
        self.assertEqual(normalize_inputs('enzyme_type',reaction),reaction)
    def test_legacy_inputs_and_valid_protein_pair(self):
        self.assertEqual(normalize_inputs('kcat_predict',{'enzyme_query':'P00761','smiles':'CCO'})['smiles'],'CCO')
        self.assertEqual(normalize_inputs('active_sites',{'aa_sequence':'ACDEFG','rxn_smiles':'CCO>>CC=O'})['aa_sequence'],'ACDEFG')
