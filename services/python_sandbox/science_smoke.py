"""Trusted library smoke test, run during image build and dependency verification."""
import io
import json
from importlib.metadata import version
from pathlib import Path
import tempfile


def validate():
    from Bio import SeqIO
    from Bio.SeqUtils.ProtParam import ProteinAnalysis
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Draw, rdFingerprintGenerator
    import numpy as np
    import pandas as pd
    from scipy import stats
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from PIL import Image

    records = list(SeqIO.parse(io.StringIO('>enzyme\nMKWVTF\n>other\nACDE\n'), 'fasta'))
    assert [len(record) for record in records] == [6, 4]
    assert ProteinAnalysis(str(records[0].seq)).molecular_weight() > 700
    molecule = Chem.MolFromSmiles('CCO')
    assert round(Descriptors.MolWt(molecule), 2) == 46.07
    assert rdFingerprintGenerator.GetMorganGenerator(radius=2).GetFingerprint(molecule).GetNumBits() == 2048
    assert np.mean([2, 4]) == 3
    assert stats.describe([1, 2, 3]).mean == 2
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        Draw.MolToFile(molecule, str(directory / 'molecule.png'))
        with Image.open(directory / 'molecule.png') as image:
            image.verify()
        pd.DataFrame([{'id':record.id, 'length':len(record)} for record in records]).to_csv(directory/'sequences.csv', index=False)
        assert pd.read_csv(directory/'sequences.csv')['length'].tolist() == [6, 4]
        fig, ax = plt.subplots()
        ax.plot([1, 2], [6, 4])
        fig.savefig(directory/'plot.png')
        plt.close(fig)
        with Image.open(directory/'plot.png') as image:
            image.verify()
    return {name:version(name) for name in ('biopython','rdkit','numpy','pandas','scipy','matplotlib','Pillow')}


if __name__ == '__main__':
    print(json.dumps({'passed':True, 'versions':validate()}, indent=2))
