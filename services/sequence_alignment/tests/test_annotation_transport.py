"""Exercise annotation consumers through the real shared retry/validation layer."""
import importlib

import pytest
import requests

from .test_uniprot_json import transport, response


SERVICES = [
    ('enzyme_check', 'enzyme_checker', 'EnzymeChecker', 'check_enzyme'),
    ('ec_reaction_info', 'catalytic_activity_query', 'CatalyticActivityQuery', 'get_catalytic_activities'),
    ('function_get', 'function_query', 'FunctionQuery', 'get_function'),
    ('functional_site', 'site_query', 'FunctionalSiteQuery', 'get_sites'),
    ('kinetic_params', 'kinetic_query', 'KineticParamsQuery', 'get_kinetics'),
]


@pytest.fixture(params=SERVICES, ids=[s[0] for s in SERVICES])
def lookup(request, transport, monkeypatch):
    service, module, cls, method = request.param
    target = importlib.import_module(f'services.{service}.models.{module}')
    monkeypatch.setattr(target, 'uniprot_json_client', transport[0])
    return getattr(getattr(target, cls)(), method)


def test_ssl_eof_recovers_and_caches_validated_annotation(lookup, transport):
    _, replies, get, sleeps, modes = transport
    replies.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'), response(comments=[{
        'commentType': 'CATALYTIC ACTIVITY', 'reaction': {'name': 'Lysozyme reaction', 'ecNumber': '3.2.1.17'}
    }])])
    result = lookup('P00698')
    assert result['success'] is True
    assert lookup('P00698') == result
    assert get.call_count == 2 and sleeps == [1] and modes == ['P256', 'TLS1.2']
    if 'is_enzyme' in result:
        assert result['is_enzyme'] is True and result['ec_numbers'] == ['3.2.1.17']
    if 'activities' in result:
        assert result['activities'][0]['ec_number'] == '3.2.1.17'


def test_persistent_ssl_outage_never_becomes_negative_annotation(lookup, transport):
    _, replies, get, sleeps, _ = transport
    replies.extend([requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING') for _ in range(4)])
    result = lookup('P00698')
    assert result['success'] is False
    assert 'no annotation result was inferred' in result['error']
    assert 'HTTPSConnectionPool' not in result['error']
    assert result.get('is_enzyme') is None
    assert get.call_count == 4 and sleeps == [1, 2, 4]
    replies.append(response())
    assert lookup('P00698')['success'] is True  # Failures are never cached.
