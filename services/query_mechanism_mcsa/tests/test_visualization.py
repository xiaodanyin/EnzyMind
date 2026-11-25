"""Visualization uses recorded evidence and exact reference identities only."""
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Base, Enzyme, ProteinSequence, Reaction, ReactionCompound, Mechanism, MechanismStep, MechanismReference, Cofactor
from retriever import EnzymeRetriever
from main import EnzymeInfoResponse, QueryRequest, query_enzyme


class VisualizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        self.retriever = EnzymeRetriever(str(self.path))
        Base.metadata.create_all(self.retriever.engine)
        with self.retriever.SessionLocal() as session:
            enzyme = Enzyme(mcsa_id=1, enzyme_name='Synthetic test record', reference_uniprot_id='P56868', all_ecs='["5.1.1.3"]')
            enzyme.sequences = [ProteinSequence(uniprot_id='P00698', sequence='CCCC'), ProteinSequence(uniprot_id='P56868', sequence='ACDE')]
            enzyme.reaction = Reaction(ec='5.1.1.3', compounds=[ReactionCompound(compound_type='reactant',name='Test compound',count=2,smiles='CO')])
            enzyme.reaction.mechanisms = [Mechanism(mechanism_id=2, rating=1, references=[MechanismReference(pubmed_id='2',evidence_types='invalid')]),
                Mechanism(mechanism_id=1, rating=3, references=[MechanismReference(pubmed_id='1',evidence_types='["crystallography evidence"]')],
                          steps=[MechanismStep(step_id=5,description='Products',is_product=True),MechanismStep(step_id=2,description='Test step')])]
            enzyme.cofactors = [Cofactor(pdb_code='ZN',name='Zinc',smiles='[Zn+2]')]
            session.add(enzyme);session.commit()

    def tearDown(self):
        self.retriever.engine.dispose();self.temp.cleanup()

    def query(self):
        return self.retriever.get_enzyme_info('1',include_smiles=True,include_visualization=True)

    def test_exact_reference_and_chemical_data_are_preserved_without_writing_database(self):
        before=self.path.stat().st_mtime_ns
        result=self.query()
        self.assertEqual(result['sequence_info']['sequence'],'ACDE')
        self.assertEqual(result['sequence_info']['uniprot_id'],'P56868')
        self.assertEqual(result['reaction']['reactants'][0]['count'],2)
        self.assertEqual(result['reaction']['reactants'][0]['smiles'],'CO')
        self.assertEqual(result['cofactors'][0]['smiles'],'[Zn+2]')
        self.assertEqual(self.path.stat().st_mtime_ns,before)

    def test_missing_reference_never_substitutes_related_protein(self):
        with self.retriever.SessionLocal() as session:
            session.query(ProteinSequence).filter_by(uniprot_id='P56868').delete();session.commit()
        self.assertIsNone(self.query()['sequence_info'])

    def test_conflicting_reference_sequences_disable_mapping(self):
        with self.retriever.SessionLocal() as session:
            session.add(ProteinSequence(mcsa_id=1,uniprot_id='P56868',sequence='OTHER'));session.commit()
        self.assertIsNone(self.query()['sequence_info'])

    def test_proposal_evidence_stays_separate_and_in_source_order(self):
        mechanisms=self.query()['mechanism']['mechanisms']
        self.assertEqual([m['mechanism_id'] for m in mechanisms],[1,2])
        self.assertEqual([s['step_id'] for s in mechanisms[0]['steps']],[2,5])
        self.assertTrue(mechanisms[0]['steps'][-1]['is_product'])
        self.assertEqual(mechanisms[0]['references'][0]['pubmed_id'],'1')
        self.assertEqual(mechanisms[1]['references'][0]['pubmed_id'],'2')
        self.assertEqual(mechanisms[1]['references'][0]['evidence_types'],[])

    def test_full_endpoint_keeps_new_fields_and_missing_records(self):
        with patch('main.retriever',self.retriever):
            result=EnzymeInfoResponse(**asyncio.run(query_enzyme(QueryRequest(query_id='1')))).model_dump()
            self.assertEqual(result['sequence_info']['length'],4)
            self.assertEqual(result['mechanism']['mechanisms'][0]['references'][0]['pubmed_id'],'1')
            self.assertFalse(asyncio.run(query_enzyme(QueryRequest(query_id='999'))).found)

    def test_fine_grained_queries_keep_existing_optional_payload(self):
        result=self.retriever.get_enzyme_info('1')
        self.assertNotIn('sequence_info',result)
        self.assertNotIn('smiles',result['reaction']['reactants'][0])


if __name__ == '__main__':
    unittest.main()
