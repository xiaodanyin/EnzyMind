"""Offline fault injection for the shared UniProt resolver and snapshot boundary."""
import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest
import requests
import zstandard

from shared.uniprot import UniProtClient, UniProtJSONClient, UniProtDownloadError, P256Adapter
from shared.uniprot_local import LocalUniProt, LocalUniProtError


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    path = tmp_path / 'snapshot ? #.sqlite'
    data = {'primaryAccession': 'P12345', 'secondaryAccessions': ['Q12345'],
            'sequence': {'value': 'ACDEFGHIK', 'length': 9},
            'comments': [{'commentType': 'CATALYTIC ACTIVITY', 'reaction': {'ecNumber': '1.1.1.1'}}],
            'features': [{'type': 'Binding Site', 'location': {'start': {'value': 2}, 'end': {'value': 2}}}]}
    raw = json.dumps(data).encode()
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE uniprot_entry(primary_accession TEXT PRIMARY KEY,
            sequence_value TEXT, sequence_length INTEGER, payload_zstd BLOB, payload_json_sha256 TEXT);
            CREATE TABLE uniprot_accession(accession TEXT PRIMARY KEY, primary_accession TEXT);
            CREATE TABLE uniprot_meta(key TEXT PRIMARY KEY, value TEXT);''')
        db.execute('INSERT INTO uniprot_entry VALUES(?,?,?,?,?)', ('P12345','ACDEFGHIK',9,zstandard.ZstdCompressor().compress(raw),hashlib.sha256(raw).hexdigest()))
        db.executemany('INSERT INTO uniprot_accession VALUES(?,?)', [('P12345','P12345'),('Q12345','P12345')])
        db.executemany('INSERT INTO uniprot_meta VALUES(?,?)', [('schema_version','1'),('created_at','2026-06-14T18:34:36Z')])
    monkeypatch.setenv('ENZYMIND_UNIPROT_LOCAL_DB_PATH', str(path))
    monkeypatch.setattr('shared.uniprot.time.sleep', lambda _: None)
    return path


def offline(client, monkeypatch, error=None):
    get = Mock(side_effect=error or requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING'))
    monkeypatch.setattr(client, '_get', get)
    return get


def test_read_only_exact_and_secondary_accessions(snapshot):
    before = snapshot.read_bytes()
    provider = LocalUniProt()
    assert provider.fetch('P12345')[1] == 'ACDEFGHIK'
    primary, text, source = provider.fetch('Q12345', annotations=True)
    assert primary == 'P12345'
    assert source['requested_accession'] == 'Q12345'
    assert json.loads(text)['features'][0]['type'] == 'Binding site'
    assert str(snapshot) not in text
    assert snapshot.read_bytes() == before
    assert sorted(p.name for p in snapshot.parent.iterdir()) == [snapshot.name]
    assert provider.fetch("P12345' OR 1=1--") is None
    with provider._connect() as db, pytest.raises(sqlite3.OperationalError, match='readonly'):
        db.execute("DELETE FROM uniprot_entry")


def test_missing_path_never_creates_database(tmp_path):
    path = tmp_path / 'absent.sqlite'
    with pytest.raises(LocalUniProtError):
        LocalUniProt(str(path)).fetch('P12345')
    assert not path.exists()


def test_isoform_never_substitutes_canonical_sequence(snapshot):
    assert LocalUniProt().fetch('P12345-2') is None
    with sqlite3.connect(snapshot) as db:
        db.execute('INSERT INTO uniprot_accession VALUES(?,?)', ('P12345-2','P12345'))
    with pytest.raises(LocalUniProtError, match='isoform'):
        LocalUniProt().fetch('P12345-2')


@pytest.mark.parametrize('mutation', [
    "UPDATE uniprot_entry SET sequence_value='ACD1'",
    "UPDATE uniprot_entry SET sequence_length=100",
    "UPDATE uniprot_entry SET payload_json_sha256='bad'",
    "UPDATE uniprot_meta SET value='99' WHERE key='schema_version'",
])
def test_corrupt_snapshot_is_not_used(snapshot, mutation):
    with sqlite3.connect(snapshot) as db: db.execute(mutation)
    with pytest.raises(LocalUniProtError): LocalUniProt().fetch('P12345', annotations=True)


def test_bounded_decompression_and_accession_validation(snapshot):
    data = {'primaryAccession':'P99999','sequence':{'value':'ACDEFGHIK'}}
    for raw in [json.dumps(data).encode(), b'x' * (LocalUniProt.MAX_JSON + 1)]:
        with sqlite3.connect(snapshot) as db:
            db.execute('UPDATE uniprot_entry SET payload_zstd=?,payload_json_sha256=?', (zstandard.ZstdCompressor().compress(raw),hashlib.sha256(raw).hexdigest()))
        with pytest.raises(LocalUniProtError): LocalUniProt().fetch('P12345', annotations=True)


def test_local_hits_never_connect_and_refresh_from_snapshot_after_short_ttl(snapshot, monkeypatch):
    client = UniProtClient()
    now = [100.]
    monkeypatch.setattr('shared.uniprot.time.monotonic', lambda: now[0])
    get = offline(client, monkeypatch)
    record = client.fetch('p12345')
    assert record.sequence == 'ACDEFGHIK' and record.source['method'] == 'local_snapshot'
    assert not get.called
    assert client.fetch('P12345').cache_hit
    assert client.fetch('Q12345').accession == 'P12345'
    assert not get.called
    with sqlite3.connect(snapshot) as db:
        db.execute("UPDATE uniprot_entry SET sequence_value='MACDEFGHIK',sequence_length=10")
    now[0] += client.LOCAL_CACHE_TTL + 1
    assert client.fetch('P12345').sequence == 'MACDEFGHIK'
    assert not get.called


def test_local_miss_preserves_authoritative_api_not_found(snapshot, monkeypatch):
    client = UniProtClient()
    get = offline(client, monkeypatch, UniProtDownloadError('Not found','uniprot_not_found',False))
    with pytest.raises(UniProtDownloadError) as exc: client.fetch('Q99999')
    assert exc.value.code == 'uniprot_not_found'
    assert get.call_count == 1


def test_new_local_record_takes_priority_over_cached_api_response(snapshot, monkeypatch):
    client = UniProtClient()
    with sqlite3.connect(snapshot) as db:
        db.execute("DELETE FROM uniprot_accession WHERE accession='P12345'")
    online = client._parse_record('>sp|P12345|X\nMACDEFGHIK\n', 'P12345', 'https://rest.uniprot.org/uniprotkb/P12345.fasta')
    get = Mock(return_value=(online, 0))
    monkeypatch.setattr(client, '_get', get)
    assert client.fetch('P12345').source is None
    assert client.fetch('P12345').cache_hit
    assert get.call_count == 1
    with sqlite3.connect(snapshot) as db:
        db.execute('INSERT INTO uniprot_accession VALUES(?,?)', ('P12345','P12345'))
    record = client.fetch('P12345')
    assert record.source['method'] == 'local_snapshot'
    assert record.sequence == 'ACDEFGHIK' and not record.cache_hit
    assert get.call_count == 1


def test_local_miss_does_not_weaken_api_certificate_verification(snapshot, monkeypatch):
    client = UniProtClient()
    get = offline(client, monkeypatch, requests.exceptions.SSLError('CERTIFICATE_VERIFY_FAILED'))
    with pytest.raises(UniProtDownloadError) as exc: client.fetch('Q99999')
    assert exc.value.code == 'uniprot_certificate_error'
    assert get.call_count == 1


@pytest.mark.parametrize('local_state', ['disabled', 'missing_file', 'corrupt'])
def test_unavailable_snapshot_uses_api(snapshot, monkeypatch, local_state):
    if local_state == 'disabled':
        monkeypatch.delenv('ENZYMIND_UNIPROT_LOCAL_DB_PATH')
    elif local_state == 'missing_file':
        snapshot.unlink()
    else:
        with sqlite3.connect(snapshot) as db:
            db.execute('UPDATE uniprot_entry SET sequence_length=0')
    client = UniProtClient()
    online = client._parse_record('>sp|P12345|X\nACDEFGHIK\n', 'P12345', 'https://rest.uniprot.org/uniprotkb/P12345.fasta')
    get = Mock(return_value=(online, 0))
    monkeypatch.setattr(client, '_get', get)
    assert client.fetch('P12345').source is None
    assert get.call_count == 1


def test_missing_local_isoform_uses_exact_api_record(snapshot, monkeypatch):
    client = UniProtClient()
    online = client._parse_record('>sp|P12345-2|X\nMACDEFGHIK\n', 'P12345-2', 'https://rest.uniprot.org/uniprotkb/P12345-2.fasta')
    get = Mock(return_value=(online, 0))
    monkeypatch.setattr(client, '_get', get)
    record = client.fetch('P12345-2')
    assert record.accession == 'P12345-2' and record.sequence == 'MACDEFGHIK'
    assert get.call_args.args[1] == 'P12345-2'


def test_partial_annotation_snapshot_cannot_claim_missing_kinetics_or_function(snapshot, monkeypatch):
    client = UniProtJSONClient()
    get = offline(client, monkeypatch)
    for capability in ['sequence','functional_sites','catalytic_activity']:
        data = client.fetch_json('P12345',capability=capability)
        assert data['enzymindSource']['method'] == 'local_snapshot'
    data['sequence']['value'] = 'MUTATED'
    assert client.fetch_json('P12345',capability='sequence')['sequence']['value'] == 'ACDEFGHIK'
    assert not get.called
    for capability in ['full','function','kinetics']:
        with pytest.raises(UniProtDownloadError) as exc: client.fetch_json('P12345',capability=capability)
        assert exc.value.code == 'uniprot_local_incomplete'


def test_partial_snapshot_never_short_circuits_full_annotation_retries(snapshot, monkeypatch):
    client = UniProtJSONClient()
    document = client._parse_record(json.dumps({'primaryAccession':'P12345','comments':[{'commentType':'FUNCTION'}]}), 'P12345', 'https://rest.uniprot.org/uniprotkb/P12345.json')
    get = Mock(side_effect=[requests.ConnectionError(),requests.ConnectionError(),(document,0)])
    monkeypatch.setattr(client, '_get', get)
    assert client.fetch_json('P12345')['comments'][0]['commentType'] == 'FUNCTION'
    assert get.call_count == 3


def test_invalid_and_missing_accessions_never_return_another_protein(snapshot, monkeypatch):
    client = UniProtClient()
    get = offline(client,monkeypatch)
    with pytest.raises(UniProtDownloadError): client.fetch('../P12345')
    assert not get.called
    with pytest.raises(UniProtDownloadError): client.fetch('Q99999')
    assert get.call_count == 4


def test_p256_is_uniprot_scoped_and_preserves_certificate_and_proxy_verification():
    import ssl
    with UniProtClient()._session('P256') as session:
        adapter = session.get_adapter('https://rest.uniprot.org/uniprotkb/P12345.fasta')
        assert isinstance(adapter,P256Adapter)
        assert adapter.tls_context.minimum_version == ssl.TLSVersion.TLSv1_2
        assert adapter.tls_context.maximum_version == ssl.TLSVersion.MAXIMUM_SUPPORTED
        assert adapter.tls_context.check_hostname and adapter.tls_context.verify_mode == ssl.CERT_REQUIRED
        assert session.verify is True
        assert not isinstance(session.get_adapter('https://example.com/'),P256Adapter)
        assert adapter.proxy_manager_for('http://localhost:1234').connection_pool_kw['ssl_context'] is adapter.tls_context


@pytest.mark.parametrize('module_name,class_name,method,available', [
    ('functional_site.models.site_query','FunctionalSiteQuery','get_sites',True),
    ('ec_reaction_info.models.catalytic_activity_query','CatalyticActivityQuery','get_catalytic_activities',True),
    ('enzyme_check.models.enzyme_checker','EnzymeChecker','check_enzyme',True),
    ('kinetic_params.models.kinetic_query','KineticParamsQuery','get_kinetics',False),
    ('function_get.models.function_query','FunctionQuery','get_function',False),
    ('enzyme_full_info.models.full_info_query','EnzymeFullInfoQuery','get_full_info',True),
])
def test_query_consumers_preserve_snapshot_scope_and_provenance(snapshot, monkeypatch, module_name, class_name, method, available):
    import importlib
    module = importlib.import_module('services.' + module_name)
    client = UniProtJSONClient()
    offline(client, monkeypatch)
    monkeypatch.setattr(module, 'uniprot_json_client', client)
    result = getattr(getattr(module, class_name)(), method)('P12345')
    assert result['success'] is available
    if available:
        assert result['source']['method'] == 'local_snapshot'
        if method == 'get_full_info':
            assert result['partial'] is True and result['kinetic_parameters'] is None
            assert set(result['unavailable_sections']) == {'kinetic_parameters', 'function', 'protein_name', 'organism',
                                                          'reviewed', 'gene_names', 'cofactors', 'structure_references',
                                                          'sequence_features', 'alphafold_id'}
            assert result['warnings'] and result['catalytic_activities'] and result['functional_sites']
    else:
        assert 'not evidence of absence' in result['error']


def test_snapshot_single_range_and_unknown_positions(snapshot):
    with sqlite3.connect(snapshot) as db:
        doc = json.loads(zstandard.ZstdDecompressor().decompress(db.execute('SELECT payload_zstd FROM uniprot_entry').fetchone()[0]))
        locations = [{'position': {'value': 2}}, {'start': {'value': 3}, 'end': {'value': 5}}, {'position': {}}]
        doc['features'] = [{'type': 'Active Site', 'location': loc} for loc in locations]
        raw = json.dumps(doc).encode()
        db.execute('UPDATE uniprot_entry SET payload_zstd=?,payload_json_sha256=?',
                   (zstandard.ZstdCompressor().compress(raw), hashlib.sha256(raw).hexdigest()))
    normalized = json.loads(LocalUniProt().fetch('P12345', annotations=True)[1])['features']
    assert [(f['location']['start'].get('value'), f['location']['end'].get('value')) for f in normalized] == [(2,2), (3,5), (None,None)]

def update_snapshot_doc(path, edit):
    with sqlite3.connect(path) as db:
        compressed = db.execute('SELECT payload_zstd FROM uniprot_entry').fetchone()[0]
        doc = json.loads(zstandard.ZstdDecompressor().decompress(compressed))
        edit(doc)
        raw = json.dumps(doc).encode()
        db.execute('UPDATE uniprot_entry SET payload_zstd=?, payload_json_sha256=?',
                   (zstandard.ZstdCompressor().compress(raw), hashlib.sha256(raw).hexdigest()))


def test_local_kinetics_and_function_require_no_connection(snapshot, monkeypatch):
    def add_annotations(doc):
        doc['comments'] += [{'commentType': 'FUNCTION', 'texts': [{'value': 'Local function.'}]},
                            {'commentType': 'BIOPHYSICOCHEMICAL PROPERTIES',
                             'kineticParameters': {'michaelisConstants': [{'constant': 1}]}}]
    update_snapshot_doc(snapshot, add_annotations)
    client = UniProtJSONClient()
    get = offline(client, monkeypatch)
    for cap in ('function', 'kinetics'):
        assert client.fetch_json('P12345', capability=cap)['enzymindSource']['method'] == 'local_snapshot'
    get.assert_not_called()
    overview = client.fetch_json('P12345', allow_partial=True)
    assert overview['enzymindSource']['section_sources']['kinetic_parameters'] == 'local_snapshot'


@pytest.mark.parametrize('sequence', ['ACDEFGHIK', 'MACDEFGHIK'])
def test_overview_supplements_only_matching_record_and_keeps_local_sites(snapshot, monkeypatch, sequence):
    client = UniProtJSONClient()
    remote = {'primaryAccession': 'P12345', 'sequence': {'value': sequence}, 'features': [],
              'comments': [{'commentType': 'FUNCTION', 'texts': [{'value': 'Reported function.'}]}]}
    get = Mock(return_value=(client._parse_record(json.dumps(remote), 'P12345', ''), 0))
    monkeypatch.setattr(client, '_get', get)
    overview = client.fetch_json('Q12345', allow_partial=True)
    source = overview['enzymindSource']
    assert get.call_args.args[1] == 'P12345'  # Secondary ID resolves before enrichment.
    assert overview['sequence']['value'] == 'ACDEFGHIK'
    assert source['section_sources']['functional_sites'] == 'local_snapshot' and overview['features']
    matched = sequence == 'ACDEFGHIK'
    assert source['partial'] is not matched
    assert source['section_sources']['function'] == ('uniprot_api' if matched else None)
    assert any(c['commentType'] == 'FUNCTION' for c in overview['comments']) is matched
    assert client.fetch_json('Q12345', capability='functional_sites')['features'] == overview['features']
    assert get.call_count == 1


def test_indexed_ec_without_catalytic_comment(snapshot, monkeypatch):
    from services.enzyme_check.models import enzyme_checker
    from services.enzyme_full_info.models import full_info_query
    update_snapshot_doc(snapshot, lambda doc: doc.update(comments=[]))
    with sqlite3.connect(snapshot) as db:
        db.execute('CREATE TABLE uniprot_ec(primary_accession TEXT, ec_number TEXT)')
        db.execute("INSERT INTO uniprot_ec VALUES('P12345', '1.1.1.1')")
    client = UniProtJSONClient()
    get = offline(client, monkeypatch)
    for module in (enzyme_checker, full_info_query):
        monkeypatch.setattr(module, 'uniprot_json_client', client)
    check = enzyme_checker.EnzymeChecker().check_enzyme('P12345')
    assert check['is_enzyme'] and check['ec_numbers'] == ['1.1.1.1']
    get.assert_not_called()
    info = full_info_query.EnzymeFullInfoQuery().get_full_info('P12345')
    assert info['is_enzyme'] and info['ec_numbers'] == check['ec_numbers']
    assert 'catalytic_activities' in info['unavailable_sections'] and not info['catalytic_activities']

def test_index_identity_can_be_supplemented_by_ec_only_api_record():
    from shared.uniprot_sections import combine, ec_numbers
    base = {'primaryAccession': 'P12345', 'sequence': {'value': 'ACD'},
            'proteinDescription': {'recommendedName': {'fullName': {'value': 'Indexed name'}}},
            'enzymindSource': {'name': 'Index', 'method': 'local_snapshot',
                               'annotation_scope': ['sequence', 'protein_name']}}
    doc = {'primaryAccession': 'P12345', 'sequence': {'value': 'ACD'},
           'proteinDescription': {'recommendedName': {'ecNumbers': [{'value': '1.1.1.1'}]}},
           'uniProtKBCrossReferences': [{'database': 'AlphaFoldDB', 'id': 'P12345'}]}
    merged = combine(base, doc)
    assert merged['proteinDescription'] == base['proteinDescription']
    assert ec_numbers(merged) == ['1.1.1.1']
    sources = merged['enzymindSource']['section_sources']
    assert sources['ec_numbers'] == sources['alphafold_id'] == 'uniprot_api'
    assert sources['protein_name'] == 'local_snapshot'
