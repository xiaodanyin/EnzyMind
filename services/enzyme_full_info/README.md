# Enzyme Information Service

## Port: 18915

## API endpoints
- `/health` - Health check
- `/api/query/enzyme-full-info` - Retrieve integrated enzyme information
- `GET /api/query/enzyme-full-info/{accession}/sequence` - Reference sequence for result cards (local first, official API fallback)
- `GET /api/query/enzyme-full-info/{accession}/structure` - Available AlphaFold reference model

The reference-sequence endpoint uses the shared UniProt client, with a 15-second budget and at most four concurrent queries.
It returns the requested identifier, resolved accession, sequence, length and provenance, without local database paths.
The Gateway forwards this GET without creating a result or starting a prediction. The frontend labels it as
reference information retrieved while viewing an older record, rather than the sequence used by that historical run. It uses existing local database
environment settings, requires no database migration, and does not modify EasIFA services or their databases.

## Installation and startup

```bash
cd services/enzyme_full_info
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Examples

```bash
curl -X POST http://localhost:18915/api/query/enzyme-full-info \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'
```

## Tests

```bash
pytest tests/ -v
```

UniProt annotations use the shared local-first client in `shared/uniprot.py`.
Available snapshot sections are returned even when API supplementation fails.
Matching, validated API data can supplement missing sections, with per-section
provenance and availability notices. Failed retrieval is never interpreted as
absence of enzyme function. See [shared UniProt configuration](../../shared/README-uniprot.md)
for transport retries, persistent caching, stale-data labeling and migration.


## Result visualization and reference structures

The result card reuses the shared Mol* viewer, numbered sequence preview,
EC hierarchy, charts and expandable tables. Missing sections remain independent.
UniProt annotations and AlphaFold predictions retain separate provenance.

`GET /api/query/enzyme-full-info/{accession}/structure` retrieves an AlphaFold DB
reference model on demand; it does not run a prediction or invoke EasIFA. The
Gateway exposes the same route. A structure outage does not fail the information
query. Only valid accessions and fixed HTTPS AlphaFold metadata/PDB URLs are
accepted. TLS verification stays enabled; redirects, oversized responses and
invalid coordinates are rejected. Downloads have a 22-second budget, at most
two transport attempts and two concurrent requests per service process.

`ENZYMIND_REFERENCE_STRUCTURE_CACHE_PATH` optionally relocates the separate
EnzyMind-owned SQLite cache. Unset defaults to `files/reference-structures.sqlite`
at the repository root; empty disables it. Never use the EasIFA snapshot or
UniProt annotation-cache path. Cached models are fresh for seven days; on an
upstream outage, models up to 30 days old can be shown with an explicit notice.
The cache retains at most 32 entries / 64 MiB of payload (128 MiB physical cap).
No database or service belonging to EasIFA is modified.

Structure coordinates are a supplementary, separately retrieved reference,
not part of the original saved annotation record. Its version, retrieval date
and sequence coverage are shown beside the viewer; download its PDB separately.
Sequence-to-structure linking is enabled only when every displayed coordinate
matches the saved sequence at the original residue number. Inexact/range site
annotations remain in the table and are not converted to precise 3D sites.
Kinetic charts retain reported units and keep different units in separate plots.
