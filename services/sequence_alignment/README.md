# Sequence Alignment Service (BLAST)

Protein sequence alignment using local NCBI BLAST+ against a portable UniProt index, with remote NCBI databases available by explicit selection.

## Publishing and migrating the local UniProt database

The local backend runs NCBI BLAST+ `blastp`. The first release uses EasIFA's 2026-06-14 UniProt snapshot: all 575,503 reviewed Swiss-Prot proteins, totaling 208,906,902 residues. Unreviewed entries are outside this search space. Once configured, web, Agent and JSON requests without an explicit database search locally. Callers can explicitly select remote `nr` for broader coverage or remote `swissprot`. [UniProtKB](https://www.uniprot.org/uniprotkb) · [UniProt attribution and terms](https://www.uniprot.org/help/license)

**Release artifacts** are a matching `.tar.zst` archive and `.tar.zst.sha256` file. Each release contains a BLAST v5 protein index, record count, snapshot identifier, builder version, source FASTA SHA-256 and per-file checksums. Index references use relative filenames. The runtime needs Python 3, zstd and system-compatible NCBI BLAST+; the recorded validation used 2.16.0+. The target host does not need the source SQLite database. Only optional annotation enrichment or resolving an accession missing locally may contact UniProt.

### Install an existing release on another host

Copy the archive and its checksum file into the same directory on the target host. Configure host-specific paths in `.env.production` or the file selected by `ENZYMIND_ENV_FILE`, for example:

```bash
ENZYMIND_BLAST_ARCHIVE=/srv/incoming/swissprot-20260614.tar.zst
ENZYMIND_BLAST_RELEASE_DIR=/srv/enzymind/blast
# Needed only when BLAST+ executables are outside PATH
ENZYMIND_BLAST_BIN_DIR=/usr/bin
```

Run the existing deployment script from the repository root. The service account must be able to write the installation directory. Installation verifies the archive, index files, manifest and target-host `blastdbcmd -info` before publishing the version directory. Reinstalling identical content verifies the existing directory; different content with the same name is rejected.

```bash
bash scripts/deploy.sh blast_db
```

The installer prints the absolute database prefix on this host. Add it to the same environment file when enabling the release, **without extensions such as .pin**. Restart Sequence Alignment and the Gateway using the existing scripts. The local-database selector also requires the matching frontend version.

```bash
ENZYMIND_BLAST_DB=/srv/enzymind/blast/swissprot-20260614/uniprot
ENZYMIND_BLAST_THREADS=4
ENZYMIND_BLAST_TIMEOUT=120
ENZYMIND_BLAST_ANNOTATE=true
```

```bash
bash scripts/stop.sh sequence_alignment
bash scripts/start.sh sequence_alignment
bash scripts/start_web.sh restart
curl -fsS http://127.0.0.1:8080/api/query/blast/config
curl -fsS -H 'Content-Type: application/json' -d '{"query":"P00761","max_results":3}' http://127.0.0.1:8080/api/query/blast
```

Check `database=local_uniprot`, `status=completed`, `database_release` and `alignments`. Each service process runs one local alignment at a time; busy returns HTTP 429 and timeout returns 504. Annotation enrichment first reuses local data, then optionally queries missing hit accessions in one API request for names, organisms, EC numbers and functions. Upstream failure preserves index titles and full alignments with `annotation_status`. Set `ENZYMIND_BLAST_ANNOTATE=false` to disable online enrichment. Indexed accessions resolve offline; raw sequences and FASTA are also accepted.

To upgrade, install another version directory, switch `ENZYMIND_BLAST_DB` and restart the affected services. Roll back by restoring the previous prefix. Removing the prefix and restarting restores the remote default. Historical results retain the database identifier used for their run.

### Build a release from a snapshot

Export on a host that can read the EasIFA snapshot. The exporter opens SQLite read-only and checks the reviewed count against the adjacent `manifest.json`. Index building and packaging can run elsewhere with BLAST+, GNU tar, zstd and Python 3.11+. Run these commands from the EnzyMind repository root after setting the environment variables for your host:

```bash
set -eu
: "${UNIPROT_SNAPSHOT:?path to the snapshot SQLite file}"
: "${BLAST_WORK_DIR:?writable build directory}"
: "${BLAST_RELEASE:?versioned directory name, e.g. swissprot-20260614}"
: "${BLAST_RELEASE_LABEL:?source and snapshot date}"
mkdir -p "$BLAST_WORK_DIR"
python3 services/sequence_alignment/deploy/export_reviewed.py "$UNIPROT_SNAPSHOT" > "$BLAST_WORK_DIR/reviewed.gz.part"
mv "$BLAST_WORK_DIR/reviewed.gz.part" "$BLAST_WORK_DIR/reviewed.gz"
python3 services/sequence_alignment/deploy/build_database.py "$BLAST_WORK_DIR/reviewed.gz" "$BLAST_WORK_DIR/$BLAST_RELEASE" --release "$BLAST_RELEASE_LABEL"
python3 services/sequence_alignment/deploy/release.py pack "$BLAST_WORK_DIR/$BLAST_RELEASE" "$BLAST_WORK_DIR"
```

Building reads every indexed sequence back to verify content, boundaries and counts. Allow space for the source FASTA, temporary decompressed data, index and archive. Distribution requires only the final archive and checksum file.

### Recorded local acceptance measurements

On 2026-11-18, BLAST+ 2.16.0+ was tested on Debian 13 with an AMD Ryzen 9 9950X3D. The release archive was 113.6 MiB; the full index and manifest occupied 319.8 MiB. With source FASTA already local, building plus complete read-back verification took 6.93 seconds with peak RSS of 232 MiB. Snapshot export and transfer time were measured separately.

The following measurements use the same migrated database, four threads, five hits per query, E-value threshold 0.01 and no online annotation. Command timings used a warm filesystem cache on persistent development-host storage; HTTP timings used a migrated copy validated under another root directory.

| Query | Length | BLAST command, warm cache | Local HTTP |
| --- | ---: | ---: | ---: |
| P01308 | 110 aa | 0.24 s | 0.261 s |
| P00761 | 231 aa | 0.43 s | 0.492 s |
| P12345 | 430 aa | 0.61 s | 0.664 s |

A separate installed copy on persistent storage was queried for P12345 after requesting eviction of its file cache; HTTP took 3.86 seconds. Idle service RSS was 66.2 MiB, and combined service/child-process peak RSS was approximately 324 MiB at 10 ms sampling intervals. Enabling online annotation for three P00761 hits took 2.28 seconds total and returned three UniProt annotations. These are single-concurrency observations; time and memory vary with hardware, search space, hit count and network conditions.

## Port

**18910**

## Installation

```bash
cd /path/to/EnzyMind/services/sequence_alignment

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the service

```bash
# Development
uvicorn main:app --reload --port 18910

# Production
uvicorn main:app --host 0.0.0.0 --port 18910
```

## Tests

```bash
pytest tests/ -v
```

## API endpoints

### Health check

```bash
curl http://localhost:18910/health
```

Response:
```json
{"status": "healthy", "service": "sequence_alignment"}
```

### BLAST search (JSON)

```bash
curl -X POST http://localhost:18910/api/query/blast \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR",
    "max_results": 3
  }'
```

Response:
```json
{
  "success": true,
  "query_length": 52,
  "num_results": 3,
  "alignments": [
    {
      "title": "sp|P12345|TEST_HUMAN Test protein",
      "length": 500,
      "e_value": 1e-50,
      "score": 200,
      "query": "MKFLILLFNILCLFPVLAADNHGVGPQ...",
      "match": "MKFLILLFNILCLFPVLAADNHGVGPQ...",
      "subject": "MKFLILLFNILCLFPVLAADNHGVGPQ..."
    }
  ]
}
```

Remote queries use the [NCBI Common URL API](https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html).
Requests are spaced at least 10 seconds apart; retrieval is spaced at least
60 seconds per RID. A retrieval failure never sends another `CMD=Put`.
Without a local index the default database is `nr`; `database: "swissprot"` explicitly selects
reviewed proteins (a smaller search space, with different coverage). Both use the
shared NCBI queue; no completion time is guaranteed. E-value cutoff: 0.01.

### Durable browser / Agent jobs

For remote jobs the gateway saves an owner-scoped result **before submission**, immediately returns
`workspace_result` with `status: "submitting"`, and submits once in the background.
Duplicate active requests with identical input, hit count and database reuse this
saved result. Background retrieval updates the same result ID in
`files/workspace/workspace.sqlite3`; closing the browser does not stop retrieval.
No extra job database is created. Restart recovery only retrieves known RIDs.
Historical 14-minute queue errors containing a RID are restored to queued records;
original inputs, sequence provenance, result links and creation/expiry dates remain.

States: `submitting` → `queued` → `completed` / `failed`. Network/parse failures
stay queued with a visible retrieval warning and 60–300 second backoff. An explicit
NCBI `FAILED` / `UNKNOWN` response is terminal. After 24 hours of checks, state
becomes `paused`; the owner can resume the same RID with
`POST /api/workspace/results/{result_id}/refresh`. A manual check respects the
existing polling cooldown and never submits a new search. All records retain the
original 90-day deletion deadline. An interrupted submission without a saved RID
is marked `submission_uncertain` and is never automatically replayed.

### Compatibility and direct API polling

Existing JSON/form/file/HTML/Markdown endpoints and synchronous defaults remain.
A synchronous wait reaching 14 minutes now returns `success: true, status: "queued"`
with `request_id`, rather than treating queueing as a failed search. **`success`
means accepted; only `status: "completed"` means alignments are ready.** Pending
responses do not contain an empty alignment list or claim there were no hits.

Direct API clients can send `wait_for_result: false` and then retrieve
`GET /api/query/blast/results/{RID}?max_results=3&database=nr` (also exposed by the
gateway). These clients manage polling themselves, at most once per minute.
Use the same database as the submission. Workspace clients use the private saved
result endpoint instead; they do not need to contact NCBI. Results use NCBI's
supported `XML2_S` format, with legacy XML parsing retained.

Health checks remain responsive while NCBI is working. Alignment strings and
residue coordinates are returned in full. Existing start/stop scripts are unchanged.

### Reliable UniProt sequence resolution

Accession inputs use the shared local-first UniProt resolver before BLAST submission. A usable snapshot or exact-accession index hit avoids downloading FASTA. A failed sequence lookup does not submit a BLAST search.

- Official API fallback uses bounded TLS compatibility retries, including P-256 and TLS 1.2, while retaining certificate and hostname verification. It does not change system-wide TLS, other model backends or NCBI connection settings.
- Connection/read timeouts and the overall retrieval budget bound retries. Connection failures, timeouts, transient HTTP statuses and invalid FASTA receive limited backoff. Retry-After is respected within the budget; the client does not retry early.
- Not-found responses and certificate-validation failures are not blindly retried. FASTA must contain one valid sequence matching the requested or officially redirected accession. Responses are size-bounded and redirects remain HTTPS on the fixed official host.
- Local records take precedence over cached API data. Shared caches retain validated public sequences/annotations, with provenance and explicit stale-response labeling where supported. Uploaded user sequences are not added to the public reference cache. See [shared UniProt access](../../shared/README-uniprot.md) for current cache limits and fallback rules.
- JSON results retain existing fields and include `sequence` and `sequence_source`: requested/resolved accession, source URL where available, retrieval time, cache status and sequence SHA-256. Cards can therefore show the sequence actually used for the run.
- Lookup failures retain `success: false` and `error`, with `error_stage: sequence_download`, `error_code` and `retryable`. Users can instead paste a sequence or upload FASTA. JSON, form, file, HTML, Markdown and legacy `/query/blast` clients remain supported.

UniProt or NCBI outages can still prevent work that needs those upstream services. Local resolution and bounded retry behavior reduce disruption without unbounded retries, incorrect sequence substitution or duplicate NCBI submissions.

### Form input

```bash
curl -X POST http://localhost:18910/api/query/blast/form \
  -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
  -F "max_results=3"
```

### FASTA upload

```bash
curl -X POST http://localhost:18910/api/query/blast/file \
  -F "file=@protein.fasta" \
  -F "max_results=3"
```

### HTML output

```bash
curl -X POST http://localhost:18910/api/query/blast/html \
  -H "Content-Type: application/json" \
  -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'
```

### Markdown output

```bash
curl -X POST http://localhost:18910/api/query/blast/markdown \
  -H "Content-Type: application/json" \
  -d '{"query": "MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR"}'
```

### Legacy API

```bash
curl -X POST http://localhost:18910/query/blast \
  -F "input_type=sequence" \
  -F "query=MKFLILLFNILCLFPVLAADNHGVGPQGASGVDPITFDINSNQTGVQLTLPLR" \
  -F "max_results=3"
```

## Supported input types

- Raw amino acid sequence
- UniProt accession, such as P12345
- FASTA content
- FASTA File upload

## Parameters

| Parameter | Type | Default | Description |
|------|------|--------|------|
| query | string | Required | Protein sequence, UniProt accession or FASTA |
| max_results | int | 3 | Maximum returned alignment segments (1–50) |

## Project layout

```
sequence_alignment/
├── main.py                  # FastAPI application
├── requirements.txt         # Dependencies
├── README.md                # This document
├── models/
│   ├── __init__.py
│   ├── blast_searcher.py     # BLAST search logic
│   └── uniprot_client.py     # Shared UniProt client compatibility wrapper
└── tests/
    ├── __init__.py
    ├── test_api.py           # API tests
    └── test_uniprot_client.py # Network, TLS, cache and compatibility tests
```

Local UniProt BLAST hits first use protein names and organisms from the index, then
supplement EC numbers and functions from `ENZYMIND_UNIPROT_LOCAL_DB_PATH` and the complete UniProt response cache.
Missing annotations are combined into one official request. Set `ENZYMIND_BLAST_ANNOTATE=false`
to use local data only. Every populated annotation field identifies its source in `annotation.field_sources`.

## External dependencies

- NCBI BLAST: https://blast.ncbi.nlm.nih.gov/
- Biopython: BLAST parsing and sequence utilities

## Notes

- Remote NCBI jobs are queued. Poll each RID at most once per 60 seconds; the synchronous wait is approximately 14 minutes, after which the job can remain queued.
- After obtaining a RID, retrieval failures retry that job only; they never resubmit the search.
- The default E-value threshold is 0.01.

## License

Part of the EnzyMind platform.
