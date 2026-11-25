"""Configuration compatibility when combining HTTPS and private-task upgrades."""
import pytest

import main
from models.active_sites_predictor import ActiveSitesPredictor
from models.easifa_access import load_owner_key


@pytest.mark.parametrize('primary,legacy,expected', [
    ('https://primary.example/easifa/api', None, 'https://primary.example/easifa/api'),
    (None, 'https://legacy.example/easifa/api', 'https://legacy.example/easifa/api'),
    ('https://primary.example/easifa/api', 'https://legacy.example/easifa/api', 'https://primary.example/easifa/api'),
    ('', 'https://legacy.example/easifa/api', 'https://legacy.example/easifa/api'),
    ('', '', ActiveSitesPredictor.API_BASES[0]),
])
def test_http_service_and_python_predictor_use_same_configuration(monkeypatch, primary, legacy, expected):
    if primary is not None:
        monkeypatch.setenv('ENZYMIND_EASIFA_API_BASE', primary)
    if legacy is not None:
        monkeypatch.setenv('EASIFA_API_BASE', legacy)
    assert main.get_predictor().api_base == expected
    assert ActiveSitesPredictor().api_base == expected


def test_explicit_endpoint_has_priority_over_both_environment_variables(monkeypatch):
    monkeypatch.setenv('ENZYMIND_EASIFA_API_BASE', 'https://primary.example/easifa/api')
    monkeypatch.setenv('EASIFA_API_BASE', 'https://legacy.example/easifa/api')
    predictor = ActiveSitesPredictor(api_base='http://127.0.0.1:8006/easifa/api/')
    assert predictor.api_bases == ('http://127.0.0.1:8006/easifa/api',)


@pytest.mark.parametrize('corrupt', [False, True])
def test_https_upgrade_preserves_existing_owner_file(monkeypatch, tmp_path, corrupt):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    current = ActiveSitesPredictor.API_BASES
    assert current[-1] == 'https://cadd.iddd.group/easifa/api'
    previous = (*current[:-1], 'http://cadd.iddd.group/easifa/api')
    key = load_owner_key(previous)
    files = list(tmp_path.rglob('session.json'))
    assert len(files) == 1
    if corrupt:
        files[0].write_text('keep damaged credentials')
        with pytest.raises(RuntimeError, match='Preserve'):
            load_owner_key(current)
        assert files[0].read_text() == 'keep damaged credentials'
    else:
        assert load_owner_key(current) == key
        assert load_owner_key(current) == load_owner_key(previous)
    assert list(tmp_path.rglob('session.json')) == files
