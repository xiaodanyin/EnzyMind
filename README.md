# EnzyMind

<div align="center">

![EnzyMind Logo](frontend/src/assets/enzymind_logo_icon_v3.png)

**Enzyme Intelligence Platform**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![n8n](https://img.shields.io/badge/n8n-Agent-orange.svg)](https://n8n.io/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.4-green.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/xiaodanyin/EnzyMind?style=social)](https://github.com/xiaodanyin/EnzyMind)
[![WebSite](https://img.shields.io/badge/WebSite-blue)](https://cadd.zju.edu.cn/enzymind/)

</div>

---

**An agent-assisted web platform for enzyme research.**

Ask a enzyme-related question in the Workspace and let the Agent select tools, compare evidence, and generate figures—or run individual tools directly with your own inputs and parameters.

[Website](https://cadd.zju.edu.cn/enzymind/) · [Backup URL](https://cadd.iddd.group/enzymind/) · [User Guide](https://cadd.zju.edu.cn/enzymind/help)  

## Agent Workspace

The Agent is powered by **n8n Workspace v2**, with the FastAPI Gateway managing access control, persistence, and tool execution.

- **Automatic tool selection:** Ask a enzyme-related question and the Agent selects and chains relevant queries, predictions, and calculations, citing saved results in its answer.
- **Reusable evidence:** Attach protein files or saved results, inspect individual result cards, and ask follow-up questions in persistent conversations. Standalone tools and the Agent share the workspace result library.
- **Conversation memory:** Older exchanges can be summarized while preserving original turns. The advisory context threshold is 100,000 estimated tokens, subject to the configured model's actual context limit.
- **Live progress and control:** Stream responses and tool events, reconnect to an in-progress turn, or cancel orchestration (already-submitted scientific predictions may still finish and save their results).
- **Python Analysis (optional):** An offline Python 3.12 sandbox with Biopython, RDKit, NumPy, pandas, SciPy, Matplotlib, and Pillow. It reads authorized saved evidence to run calculations, generate PNG figures, and export CSV/JSON/TXT files.
- **Programmatic access:** The Python/Jupyter [Workspace client](agent_n8n/README.md) supports streaming, session recovery, result references, and downloads via the same API.

**Limits, allowance, and retention:**

- **Per-turn limits:** Up to **12 tool calls** per turn, including at most **3 Python executions** (each runs in a fresh container with a 60-second timeout, 1 CPU, and 1 GiB memory).
- **Daily allowance:** 10 successful Agent turns per day per browser workspace by default; users can supply a personal DeepSeek key for additional turns. Standalone tools do not consume this allowance.
- **Retention and privacy:** Results and conversation turns are retained for **90 days**. Access is tied to a private workspace key—a result URL alone does not grant access. Export the workspace access file to restore access in another browser, and download scientific results before expiry.

## Supported Tools

The web interface provides 11 standalone tools. Protein inputs accept UniProt accessions, sequences, or FASTA where applicable; **Enzyme Information** requires a UniProt accession.

| Tool | Input | Output |
| --- | --- | --- |
| [Enzyme Recognition](services/enzy_recognize/README.md) | Protein | Enzyme/non-enzyme classification and model score |
| [EC Number Prediction](services/ecnumber_predict/README.md) | Protein | Predicted EC classifications |
| [Substrate Determination](services/substrate_predict/README.md) | Protein + substrate SMILES | Substrate compatibility and model score |
| [Kcat Prediction](services/kcat_predict/README.md) | Protein + substrate SMILES | Predicted turnover number (s⁻¹) |
| [Km Prediction](services/km_predict/README.md) | Protein + substrate SMILES | Predicted Michaelis constant (mM) |
| [Enzyme Recommendation](services/enzyme_type/README.md) | Reaction SMILES | Ranked candidate EC classes |
| [Active Site Prediction](services/active_sites/README.md) | Protein (optional reaction for sequence input) | EasIFA functional-site predictions (with coordinates when available) |
| [Structure Prediction](services/structure_predict/README.md) | Protein | ESMFold structure coordinates and residue-level confidence |
| [Protein Parameters](services/protparam/README.md) | Protein | Composition, molecular weight, theoretical pI, and other properties |
| [Sequence Alignment](services/sequence_alignment/README.md) | Protein + database selection | BLAST hits, aligned residues, identity, coverage, and E-values |
| [Enzyme Information](services/enzyme_full_info/README.md) | UniProt accession | Integrated sequence, function, reactions, sites, and annotations |

- **Additional API and Agent queries:** Focused queries cover annotated enzyme status, sequence details, function, EC hierarchy, catalytic reactions, functional sites, and reported kinetic parameters. [M-CSA tools](services/query_mechanism_mcsa/README.md) retrieve enzyme records, catalytic residues, mechanisms, reaction steps, cofactors, and electron flow.
- **Data sources and fallback:** UniProt queries check a configured **local snapshot first**, falling back to the official API for missing records or annotation sections. Local BLAST searches a portable UniProt database, with remote NCBI databases available as explicit alternatives. Partial annotations preserve their source and availability notices.
- **Visualizations and evidence separation:** Results share sequence views, Mol* protein structures, Ketcher molecular depictions, EC hierarchies, and expandable figures and tables (coordinates are displayed only when available). Predicted kinetics, database annotations, and code calculations remain distinct evidence types; model scores are not experimental measurements.


## Project Layout

| Directory | Purpose |
| --- | --- |
| `frontend/` | Vue 3 + Vite web interface and shared result visualizations |
| `gateway/` | FastAPI Gateway, workspace storage, access control, and tool execution |
| `agent_n8n/workspace/` | Current Agent workflow, generation, and deployment |
| `services/` | 19 scientific services and the optional Python sandbox |
| `shared/` | Shared UniProt retrieval, caching, and sequence utilities |
| `scripts/` | Deployment, model downloads, service management, and verification |
| `tests/` | Evaluation and test results |

## Deployment

### 1. Prepare host and configuration

**Prerequisites:** Linux with Python (`venv`), Node.js/npm, and the system dependencies required by your selected services. Neural prediction services require model weights and compatible PyTorch/CUDA environments; ESMFold requires Docker; EasIFA, RetroPlanner, and n8n require reachable external backends. See each service's README for details—the deployment script does not automatically provision external backends or download reference datasets.

Run deployment from the repository root as the Gateway service account. For a **new installation**, copy the template and adjust paths and endpoints for the target host:

```bash
cp scripts/production.env.example .env.production
chmod 600 .env.production
```

Keep the existing environment file during upgrades. Startup scripts load `.env.production` by default, or the file specified by `ENZYMIND_ENV_FILE`. Key settings:

| Setting | Purpose |
| --- | --- |
| `ENZYMIND_WORKSPACE_DB` | Persistent SQLite workspace database (preserve across upgrades) |
| `N8N_WORKSPACE_WEBHOOK_URL` | Webhook URL from the Gateway to the n8n Workspace |
| `ENZYMIND_UNIPROT_LOCAL_DB_PATH` | Path to the read-only local UniProt snapshot |
| `ENZYMIND_UNIPROT_CACHE_PATH` | Separate writable EnzyMind annotation cache |
| `ENZYMIND_BLAST_DB` | Installed local BLAST database prefix (without the `.pin` extension) |
| `ENZYMIND_UNIPROT_SEQUENCE_INDEX` | Optional BLAST prefix reused for exact-accession sequence lookups |
| `ENZYMIND_BLAST_BIN_DIR` | Directory containing BLAST+ executables when outside `PATH` |
| `ESMFOLD_USE_GPU` | Select GPU or bounded CPU folding (configure matching resource settings) |
| `ENZYMIND_PYTHON_ENABLED` | Enable Python Analysis after sandbox acceptance checks (initially `false`) |

> **Note:** Do not overwrite a production workspace with a development database. Store UniProt reference data outside workspace retention directories; sharing a read-only snapshot requires no changes to EasIFA services.

### 2. Install services, models, and data

**Services and frontend:** Review the deployment plan, install dependencies, and build the frontend:

```bash
bash scripts/deploy.sh --dry-run
bash scripts/deploy.sh
```

With no targets specified, `deploy.sh` installs all 19 scientific services, the Gateway, the frontend, and the sandbox (if already enabled). To update specific components, pass their directory names—for example, `bash scripts/deploy.sh gateway frontend sequence_alignment`.

**Model checkpoints:** Download configured checkpoints into the paths expected by each service (uses the active `python` interpreter and requires `huggingface_hub`):

```bash
bash scripts/hf_models_download.sh --dry-run
bash scripts/hf_models_download.sh
```

**Local UniProt and BLAST databases:** For local UniProt access, configure the snapshot and cache paths, then run `bash scripts/deploy.sh uniprot` to verify the shared query environments. To install a portable BLAST release, copy its `.tar.zst` archive and matching `.sha256` file to the host, set `ENZYMIND_BLAST_ARCHIVE` and `ENZYMIND_BLAST_RELEASE_DIR`, and run:

```bash
bash scripts/deploy.sh blast_db
```

Set `ENZYMIND_BLAST_DB` to the installed prefix printed by the installer. See the [UniProt configuration guide](shared/README-uniprot.md) and [BLAST database guide](services/sequence_alignment/README.md) for schema requirements, release verification, and optional API enrichment.

### 3. Start the application

```bash
bash scripts/enzymind.sh start
bash scripts/enzymind.sh status
gateway/venv/bin/python scripts/verify_api.py
```

By default, the frontend serves on `http://localhost:3010/enzymind/`, the Gateway on `http://localhost:8080`, and scientific services on ports `18901–18919`. For public deployments, configure HTTPS, proxy `/enzymind/api/` to Gateway `/api/` while preserving streaming responses and suitable upstream timeouts, and run **a single Gateway worker** (turn execution and model relay state are held in process memory).

Use `bash scripts/enzymind.sh stop` or `restart` to manage the scientific services and web tier, or `bash scripts/start_web.sh restart` for web-only updates. These scripts do not manage n8n, the reverse proxy, or the sandbox systemd services.

### 4. Install or update the n8n Agent

Requires a running n8n instance with a preconfigured language-model node. Generate and deploy the workflow bound to that node:

```bash
python3 agent_n8n/workspace/build_workflow.py
python3 agent_n8n/workspace/deploy.py \
  --model-workflow EXISTING_MODEL_WORKFLOW_ID \
  --model-node 'Research language model' \
  --gateway-url http://host.docker.internal:8080 \
  --activate
```

Replace the model workflow ID and node name with your deployment's values. For **updates**, pass `--target EXISTING_ENZYMIND_WORKSPACE_ID` (omit it only when creating the initial workflow). The deployer prompts privately for the n8n management API key and backs up the target workflow before updating. Ensure `--gateway-url` is reachable from n8n—on Linux Docker, this may require a `host.docker.internal:host-gateway` mapping.

Point `N8N_WORKSPACE_WEBHOOK_URL` to the activated `/webhook/enzymind-workspace-v2` endpoint and restart the web tier. Note that `scripts/deploy.sh` does not update the n8n workflow. See the [Workspace deployment guide](agent_n8n/workspace/README.md) for credentials, model compatibility, streaming, and retention.

### 5. Enable Python Analysis (optional)

**Prerequisites:** A dedicated service account, a separate Rootless Docker daemon, `systemd`, cgroup v2 resource delegation, and a Python 3.11+ Runner environment (execution containers run Python 3.12).

Install, enable, and verify the sandbox using the standard deployment script:

```bash
bash scripts/deploy.sh gateway frontend python_sandbox
bash scripts/deploy.sh python_sandbox --enable-python
bash scripts/start_web.sh restart
bash scripts/deploy.sh python_sandbox --check
```

Initial installation keeps Python Analysis disabled unless `--enable-python` is supplied; enabling requires passing both container and Gateway acceptance checks. The installer uses `sudo` only for Rootless Docker provisioning.

**Security and isolation:** The Runner listens on loopback only, and Agent calls require a valid turn credential from an allowed n8n source (authenticated local debugging remains available). Runtime containers have no network access or host-directory mounts. Note that Rootless Docker shares the host kernel and does not guarantee protection against all container escapes. See [sandbox deployment and validation](services/python_sandbox/README.md) for prerequisites, limits, and local debugging.

## Documentation

- [Gateway and API](gateway/README.md)
- [Agent Workspace](agent_n8n/workspace/README.md)
- [Python Sandbox](services/python_sandbox/README.md)
- [Local UniProt Configuration](shared/README-uniprot.md)
- [Portable BLAST Database](services/sequence_alignment/README.md)
- [Frontend Development](frontend/README.md)

## License

MIT License © 2025 EnzyMind Team.
