# UniProt local-first access and API fallback

All EnzyMind UniProt FASTA/JSON lookups use `shared/uniprot.py`. The EC,
recognition, structure, kinetic prediction, BLAST and annotation services share
the same resolver: the configured local snapshot is queried first, and the official
API is used when a usable local record is unavailable. EasIFA's own service and
code are not modified.

The production OpenSSL 3.5 default handshake intermittently timed out or ended
with `UNEXPECTED_EOF_WHILE_READING`. P-256 and TLS 1.2 succeeded for the same
public record. When the API is needed, EnzyMind tries P-256 (TLS 1.2/1.3), TLS 1.2, P-256, then
default TLS, with at most four GET attempts and a 60-second retrieval budget.
Certificate and hostname verification remain enabled, including through configured
proxies. Connections and partially received responses are discarded after failure.
HTTP 408/429/5xx are transient; Retry-After is respected. Redirects remain HTTPS
on the fixed UniProt hostname. Requests cannot supply hosts, paths, or TLS options.

## Configure and migrate

Set the following in the existing `.env.production`, or the file selected by
`ENZYMIND_ENV_FILE`:

```dotenv
ENZYMIND_UNIPROT_LOCAL_DB_PATH=/data/uniprot/uniprot_full.sqlite
ENZYMIND_UNIPROT_CACHE_PATH=/data/enzymind/uniprot-api-cache/annotations.sqlite
```

Use an absolute path to an EasIFA-compatible schema-v1 UniProt snapshot. It must
be readable by the EnzyMind service account. Do not grant access to EasIFA's
application database, credentials, or runtime caches. The snapshot is an external
reference dataset; it is not committed to Git or placed inside Workspace's
90-day retention directory. On a new machine, copy/mount the snapshot separately
and change this variable. The optional `ENZYMIND_UNIPROT_SEQUENCE_INDEX` is the
prefix inside an installed EnzyMind UniProt BLAST release, next to its manifest.
Point `ENZYMIND_BLAST_BIN_DIR` at the directory containing `blastdbcmd` if it is
outside PATH. After a snapshot miss, an exact-accession index lookup provides
sequence and indexed identity. This setting works independently of the BLAST
search endpoint. If an existing deployment sets `ENZYMIND_BLAST_DB`, its prefix
serves as the default index. Only the SQLite snapshot resolves secondary IDs.

The optional `ENZYMIND_UNIPROT_CACHE_PATH` points to a **separate EnzyMind-owned**
SQLite file, never the EasIFA snapshot. It saves validated, complete API JSON so
service restarts do not discard previously retrieved annotations. Cache failures
do not fail live lookups. Deployment checks its writable directory separately from
the read-only reference database. Leave it empty to disable persistent caching.

```bash
# Existing deployment entry; only installs the pinned shared decompressor in
# deployed UniProt query environments, then validates a local public record.
bash scripts/deploy.sh uniprot

# Preflight: reference database read-only; optional cache directory write check.
# No network request or model inference.
services/sequence_info/venv/bin/python scripts/check_uniprot.py \
  --env-file .env.production --accession P12345

# After draining active EnzyMind requests, load code/config in affected services.
for service in enzy_recognize ecnumber_predict substrate_predict kcat_predict \
  km_predict structure_predict active_sites protparam sequence_alignment \
  function_get ec_reaction_info enzyme_check enzyme_full_info functional_site \
  kinetic_params sequence_info; do
  bash scripts/stop.sh "$service" && bash scripts/start.sh "$service" || break
done
```

Normal full/selected service deployments also install the decompressor through
each query service's requirements. This update needs no Gateway, n8n, frontend,
Rootless Docker or EasIFA restart for backend-only changes. Frontend notice changes
use the existing frontend deployment and restart scripts. Keep a private backup of EnzyMind's environment
and its previous Git commit for rollback; do not roll back or write the snapshot.

## Lookup order and evidence limits

The local snapshot is preferred. A usable local hit makes **no network request**.
The resolver uses a parameterized accession lookup in SQLite opened with `mode=ro`,
`query_only=ON`, bounded query time and memory. It never creates a missing database,
modifies schema, scans the whole dataset, or imports EasIFA. A missing record,
unreadable/corrupt database, or unsupported annotation scope falls back to the
official API with verified HTTPS and bounded retries. API 404/410 responses remain
not-found errors; certificate failures never trigger insecure HTTPS.

Successful local results are cached for 60 seconds, then checked against the local
snapshot again. API results retain the six-hour bounded cache, but every reuse
checks for a local record first: adding a local record takes priority immediately
over an existing API cache entry. Missing/corrupt local records cannot satisfy a
request. Local sequence length/alphabet and exact isoform identity are checked.
Secondary accessions use the snapshot's accession index; a missing isoform is
looked up through the API and is never substituted with the canonical sequence.

The existing snapshot contains sequence, catalytic-activity and functional-site
data. Compressed JSON is size-limited, checked against its stored SHA-256, and
matched to the accession/sequence index. Annotation responses expose `source`
with `method=local_snapshot`, resolved accession, snapshot creation date and
supported annotation scope, without host filesystem paths. Snapshot dates are
not represented as current UniProt release dates.

Available local EC, reactions, sites, function, kinetics, PDB/AlphaFold
references and identity are reused by their consumers. An indexed EC number
can establish annotated enzyme status even when a reaction name is missing.
Reaction SMILES are joined only by matching Rhea identifiers. AlphaFold references
identify a model; coordinates are retrieved by the existing structure service.

Enzyme Information keeps the snapshot's covered sections and supplements missing
ones from a validated full API response. Both the canonical accession and amino
acid sequence must match before sections are combined. The response identifies
each section in `source.section_sources`. A null source marks an unavailable
section, also listed in `unavailable_sections`. Complete matching API documents
can establish that a field has no annotation. Without a usable supplement the
overview returns available data and warnings. Dedicated function and kinetics
queries reuse matching local annotations and return an availability error if
the requested section cannot be established. Sequence-dependent services also
reuse fresh validated API JSON on disk when neither local dataset has the entry.

When local overview data exist, enrichment uses a 12-second network budget. Partial
results have a 60-second cooldown so retries do not repeatedly wait on the same
outage. The overview endpoints run blocking retrieval in a thread pool to preserve
health and concurrent request responsiveness.

Complete API responses remain fresh for six hours, including across restarts.
After bounded network failures, a verified saved response up to 30 days old may be
returned with `source.method=uniprot_cache`, `retrieved_at` and `stale=true`. The UI
shows the age/provenance; stale results are retried after 60 seconds. Authoritative
404/410 errors do not use stale cached data. Checksums, accession validation and
scope checks prevent corrupted or partial snapshots from masquerading as complete
API records. The cache is bounded to 256 entries / 64 MiB of payload, with a 128 MiB
SQLite page ceiling; expired entries are pruned on writes. It never writes to the
reference snapshot, including when a mistaken cache path aliases it.

Sequence-dependent predictions use the local sequence when available.
For direct Python callers, `UniProtSequence.source` / `UniProtDocument.source`
identify the local source; JSON callers must request a supported `capability` explicitly.

Useful references: [Requests certificate verification](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification),
[SQLite read-only URI connections](https://www.sqlite.org/uri.html),
[OpenSSL supported groups](https://docs.openssl.org/3.5/man3/SSL_CTX_set1_curves/).
