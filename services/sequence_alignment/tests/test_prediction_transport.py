"""Prediction services use verified, bounded downloads before inference."""
import importlib

import pytest
import requests

from .test_uniprot_client import transport, Response, fasta
from shared.uniprot import UniProtDownloadError


@pytest.fixture(params=['services.kcat_predict.models.utils', 'services.km_predict.models.utils',
                        'services.substrate_predict.main', 'services.ecnumber_predict.main',
                        'services.enzy_recognize.main', 'services.structure_predict.models.structure_predictor'])
def lookup(request, transport, monkeypatch):
    consumer = importlib.import_module(request.param)
    monkeypatch.setattr(consumer, 'uniprot_sequence_client', transport[0])
    if hasattr(consumer, 'classify_input_v2'):
        return consumer.classify_input_v2
    if hasattr(consumer, 'classify_input'):
        return consumer.classify_input
    return consumer.get_uniprot_sequence


def test_prediction_sequence_download_recovers_and_reuses_verified_sequence(lookup, transport):
    _, replies, calls, modes, sleeps = transport
    replies.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'), Response()])
    assert lookup('P00698') == 'ACDEFGHIKLMNPQRSTVWY'
    assert lookup('P00698') == 'ACDEFGHIKLMNPQRSTVWY'
    assert len(calls) == 2 and sleeps == [1] and modes == ['P256', 'TLS1.2']
    assert all(url == 'https://rest.uniprot.org/uniprotkb/P00698.fasta' for url, _ in calls)


def test_prediction_download_never_substitutes_a_different_protein(lookup, transport):
    _, replies, _, _, _ = transport
    replies.extend(Response(body=fasta(accession='P00330')) for _ in range(4))
    with pytest.raises(UniProtDownloadError):
        lookup('P00698')
    replies.append(Response())
    assert lookup('P00698') == 'ACDEFGHIKLMNPQRSTVWY'


def test_prediction_download_outage_is_bounded_and_not_cached(lookup, transport):
    _, replies, calls, _, sleeps = transport
    replies.extend(requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING') for _ in range(4))
    with pytest.raises(UniProtDownloadError):
        lookup('P00698')
    assert len(calls) == 4 and sleeps == [1, 2, 4]
    replies.append(Response())
    assert lookup('P00698') == 'ACDEFGHIKLMNPQRSTVWY'
