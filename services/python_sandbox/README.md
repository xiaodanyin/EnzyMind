# EnzyMind Python Sandbox (Workspace v2)

Disabled by default. The Gateway owns workspace identities, source-IP digests, budgets, execution records and results. A local FastAPI Runner creates disposable Python 3.12 containers through a **dedicated account's Rootless Docker socket**. Neither n8n nor the browser can access that socket or the Runner service credential. The Agent invokes the sandbox through Workspace v2.

Docker shares the host kernel. Rootless mode reduces the impact of some vulnerabilities but cannot guarantee protection against every container escape. Stronger isolation for untrusted computation requires a dedicated compute host or a stronger sandbox runtime. [Docker Rootless security](https://docs.docker.com/engine/security/rootless/)

## Deploy and update through the existing scripts

Run from the repository root as the Gateway owner, using the existing `scripts/deploy.sh` entry:

```bash
# First installation: matching Docker Rootless extras, cgroup v2/systemd and n8n required
bash scripts/deploy.sh gateway frontend python_sandbox --proxy http://127.0.0.1:7890

# Install and enable after acceptance checks; omit --enable-python to remain disabled
bash scripts/deploy.sh python_sandbox --enable-python --proxy http://127.0.0.1:7890

# Update while preserving the enable flag and credential, then reload the web tier
bash scripts/deploy.sh python_sandbox --proxy http://127.0.0.1:7890
bash scripts/start_web.sh restart
bash scripts/start_web.sh status

# Preview the plan and run read-only deployment checks
bash scripts/deploy.sh --dry-run
bash scripts/deploy.sh python_sandbox --check
```

Omit `--proxy` when no proxy is needed. Default deployment includes scientific services, the Gateway and frontend. The sandbox is included only when already enabled or explicitly selected through `python_sandbox`, `--with-python` or `--enable-python`. Rootless provisioning uses sudo; other stages run as the Gateway user. On a new host, deploy `gateway` first or include it in the same command so its Python environment is available for integration checks.

Runner requires Python 3.11+. If the system interpreter is older, prepare a separate interpreter readable by the dedicated account, such as root-owned `/opt/enzymind-python/python/bin/python3.12`, and pass `--runner-python`. This does not replace `/usr/bin/python3` or other services' virtual environments. Updates reuse a suitable existing Runner interpreter.

Integration privately backs up configuration, creates a maintenance marker, waits for existing Python jobs, runs `deploy/install_rootless.sh`, verifies container and HTTP lifecycle behavior, tests Gateway integration in an isolated database, atomically merges the four Python settings, then removes the marker created by that deployment. Pre-existing manual disable markers remain. Failures preserve the marker and original configuration; rerun after fixing the cause rather than bypassing acceptance. Configuration and reports are backed up under `files/workspace/backups/python-deploy-*/`; old Runner packages and configuration go to `/var/lib/enzymind-python-deploy/backup-*/`, excluding large wheel caches.

Managed Runner updates automatically use `--update`, preserving the service token and execution ledger. Runner stops before modules are copied. The dedicated Docker daemon is restarted only if its configuration changes. An image is reused only when the base digest, Dockerfile, dependency locks, entrypoint and scientific-check fingerprints match and the same immutable image ID still exists locally. Older manifests without fingerprints trigger one rebuild. Every update still runs actual acceptance checks.

Configuration defaults to `.env.production`, overridden by `ENZYMIND_ENV_FILE`, and must belong to the current user with permissions `0600`. Other settings are preserved; proxy trust is not widened. By default, `docker exec n8n node ...` inspects the outbound route to `http://host.docker.internal:8080` without requiring a running Gateway, sending packets or reading n8n credentials. Use `--n8n-container` for another container, `--gateway-url` for the actual deployed workflow URL, or a verified `--agent-ip`. Redeploy and restart the Gateway after an exact source IP changes; do not trust an entire subnet.

Initial low-level Runner HTTP acceptance permits an absent Gateway listener and records `gateway_checked_under_load=false`; an existing Gateway returning non-200 still fails acceptance. Integrated deployment always adds real Gateway-route checks using a temporary database and independent disable marker, without touching production conversations. Web start/status commands check an enabled Runner and return nonzero if it is unhealthy; other components retain their own health checks.

This deployment entry neither changes n8n workflows nor reads a management API key. Install or update the Python Analysis tool through the [existing Workspace deployment procedure](../../agent_n8n/workspace/README.md).

Web startup passes `PYTHON_SANDBOX_TOKEN` only to the Gateway. Frontend installation/startup and scientific-service startup remove it from their environment. Existing scientific processes adopt this restriction when next started.

## API and computation contract

The n8n Agent calls `POST /api/workspace/tools/python` server-side with its short-lived `X-Enzymind-Turn` credential. Browser and public direct calls are denied. The Gateway also checks the actual TCP source against the exact IPs in `ENZYMIND_PYTHON_AGENT_IPS`; an empty list denies access. Source filtering does not replace the turn credential, which must belong to a running, unexpired turn.

The Python route rejects requests carrying `Forwarded`, `X-Forwarded-*`, `X-Real-IP`, `Origin` or `Sec-Fetch-Site`, preventing public requests from borrowing a local proxy address. The public Vite proxy blocks this route and strips `X-Enzymind-Turn`. Users can still ask the Agent questions, view results and download files from their workspace.

Request format:

```json
{
  "code": "from Bio import SeqIO\nfrom io import StringIO\nimport pandas as pd\nrows = [{'id': r.id, 'length': len(r)} for r in SeqIO.parse(StringIO(data['fasta']), 'fasta')]\npd.DataFrame(rows).to_csv(output_dir / 'lengths.csv', index=False)\nresult = rows",
  "data": {"fasta": ">example\nMKWVTF\n"},
  "result_ids": [],
  "file_ids": []
}
```

Only these four fields are accepted. `code` is required; `data` defaults to an empty object. Limits are 12 `result_ids`, 10 `file_ids` and a 256 KB Gateway request body. References must belong to the current workspace; files must be managed outputs of existing Python results. The Gateway copies full JSON payloads and file bytes, never host paths. Total copied input is capped at 6 MiB, including at most 5 MiB of files. The model cannot specify images, mounts, networks or Docker parameters.

The n8n model tool accepts a `code` string and an `inputs` object containing `data`, `result_ids` and `file_ids`; the workflow converts these into the Gateway request above. IDs must appear in `inputs.result_ids`; mentioning them in code does not load data. Within Python, `results[id]` is the parsed payload dictionary, without an outer `data` wrapper: read `success`, `kcat`/`km` and `unit` directly for kinetic predictions, or `results[id]['result']` for prior Python calculations. Rejected HTTP responses pass their `detail` back to the Agent; limits, busy states and disabled service must be reported without repeated calls.

Variables available inside the container:

| Variable | Content |
| --- | --- |
| `data` | JSON object supplied with the call |
| `results` | `{result UUID: complete payload}` |
| `input_files` | `{file UUID: path to its copied file inside the sandbox}` |
| `output_dir` | `Path('/work/output')` |
| `result` | JSON-serializable value assigned by the code, up to 128 KiB; `null` if unassigned |

Output filenames must begin with an ASCII letter or digit, followed only by ASCII letters, digits, `_`, `-` or `.`. Allowed extensions are `.json`, `.csv`, `.txt` and `.png`; save files directly in `output_dir`. Keep only final attachments there. Use `io.BytesIO` or the working directory for temporary images; `_tmp.png`, hidden files and subdirectories cause the entire export to be rejected. JSON cannot contain NaN/Infinity, text must be UTF-8, and PNGs are limited to 16 million pixels. Runtime is offline: retrieve external data with existing query tools first. Code, stdout, stderr, JSON and files are all untrusted data, never executable HTML or new instructions.

Responses use existing result IDs, citation URLs and `tool_start/tool_end` events, with evidence labeled as code calculations. Complete records include code, input data, reference IDs and SHA-256 digests, code SHA-256, runtime image ID, Python/library versions, status, duration, output and file inventory. Input digests cover full payloads, and copying does not truncate them. Source results retain their own expiry dates.

Download through `GET /api/workspace/results/{result_id}/files/{file_id}` with the browser's `X-Enzymind-Client` workspace credential. Both result and file ownership must match. Responses use `attachment`, `nosniff`, `private,no-store` and a restrictive CSP. After authenticated retrieval, the frontend previews PNGs with Blob URLs and CSV/TXT/JSON as Vue text. Previews limit rows and depth; downloads retain the complete data.

## Enforced limits and lifecycle

| Resource | Default / implementation |
| --- | --- |
| Wall time | 60 seconds, including creation, copying, execution, freezing and extraction; timed outside the container |
| CPU / memory / swap | 1 CPU, 1 GiB; MemorySwap=Memory, with no additional swap |
| Processes and threads | 64 total; BLAS/OpenMP default to one thread |
| Workspace | `/work`: 128 MiB tmpfs, noexec/nosuid/nodev; read-only root filesystem |
| Concurrency | Global 2, per workspace 1; checked by Gateway and Runner, without a waiting queue |
| Executions | 3 per turn, also counted against the 12-tool-call budget |
| Hourly rate limits | Workspace 10, source IP 20, global 120; failed and busy attempts also count |
| Code / terminal output | 64 KiB code; 128 KiB combined stdout and stderr |
| Files | At most 10, each up to 2 MiB, 5 MiB total |
| Storage | 100 MiB per workspace, 10 GiB global; reserve 5 MiB per run and reject insufficient capacity |

Limits are fixed server-side in `engine.Limits`, `protocol.py` and `gateway/python_sandbox.py`; request fields cannot override them. Containers use UID/GID 10001, network none, cap-drop ALL, no-new-privileges and default seccomp. No host directories, sockets, GPUs or host devices are mounted, and Runner environment variables are not inherited. Docker supplies standard `/dev` devices; IPC is none, with no shared `/dev/shm` workspace.

Runner creates containers through fixed Docker API calls, copies inputs with the archive API and executes code with exec. Output streams are not written to Docker logs. `/work` uses a separate daemon-managed **local-driver tmpfs volume** for each task, with fixed size, owner and noexec/nosuid/nodev options. This is not a host-directory bind, and models cannot select volume options. Ordinary `HostConfig.Tmpfs` is not used because the archive API sees a separate filesystem view without the task's actual tmpfs data; see [Moby filesystem views](https://github.com/moby/moby/blob/master/daemon/containerfs_linux.go). Driver/options/ownership are checked after creation; tmpfs type, mount flags, ownership and size are tested before execution. Any mismatch rejects the task.

After execution, Runner pauses the entire container and reads a `/work` snapshot without extracting its tar archive onto the host. Links are checked across the writable workspace to reject output hard links into inputs or temporary files. Traversal, symlinks, hard links, devices, sparse files, duplicate paths and output subdirectories are rejected. Snapshots are capped at **16 MiB / 1,024 entries**, including inputs and temporary caches; remove large intermediate files before finishing. Computation still has 128 MiB of tmpfs. Cleanup deletes the container and then its volume. Startup and an independent timer remove expired service-labeled containers/volumes, including those created before a lost API response. Any deletion failure disables new tasks.

Timeouts, excessive output, cancellation and n8n tool disconnects terminate the whole container. Closing browser SSE does not cancel an existing turn; Workspace Stop cancels Python work. Container deletion failure disables new Runner tasks. Startup and every execution verify actual cgroup/security settings. Startup also tests fork, tmpfs, CPU throttling, OOM, timeouts, output limits and scientific libraries. Failed checks leave the tool unavailable without weaker isolation. Rootless CPU/memory/PID limits require cgroup v2, systemd and controller delegation. [Docker resource requirements](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources)

The Gateway atomically saves execution and budget records **before** sending a request. Identical code, data and reference content within a turn reuse the same running, failed or interrupted record; changed code creates a new execution. Reuse consumes no additional Python execution or hourly allowance but still counts against the 12-tool-call budget. Runner also persists job IDs; duplicate POSTs return 409, and DELETE can register cancellation before creation to close races. Transport failure never resubmits code. Gateway restart marks unfinished records interrupted. Runner restart removes its old containers and marks prior jobs interrupted. Expiry labels, a 15-second internal collector and an independent systemd timer handle orphan cleanup after crashes, typically within about 105 seconds of creation. If Docker itself is unavailable, deletion must wait for recovery.

File bytes are SQLite BLOBs in the existing workspace database with server-generated IDs. Results, files and quota counters commit or expire in the same transaction, avoiding host-path and orphan-file issues. Files follow result retention of 90 days and active-reference protection; downloads do not extend expiry. Incremental vacuum reclaims pages. Storage quotas count live file bytes; separately monitor database pages, WAL, result JSON and backups. Expired hourly records are pruned, and Runner's small job-ID ledger stores neither code nor research payloads.

## Deployment: dedicated account and daemon

An administrator with sudo performs the following steps on the target host. **Do not stop or modify the production Docker daemon, or add the sandbox account to the `docker` group.** Use one Gateway worker and one Runner worker.

### Local installer

The repository provides an idempotent installer for Debian/Ubuntu hosts with official Docker Rootless components already installed:

```bash
# Read-only check; no sudo needed
bash services/python_sandbox/deploy/install_rootless.sh --check
# Verify official repository signatures, resolution and downloads without installation
bash services/python_sandbox/deploy/install_rootless.sh --check-apt --proxy http://127.0.0.1:7890
# Administrator installation; credentials are not written to project configuration
sudo bash services/python_sandbox/deploy/install_rootless.sh --proxy http://127.0.0.1:7890
```

`--proxy` selects an existing local HTTP proxy without credentials; omit it when unnecessary. It applies to APT downloads, Runner wheels, image pulls and trusted image builds. Loopback build proxy support depends on the Docker **29.5+** detached-netns default used by this deployment; older daemons such as 29.1 run in a separate network namespace and cannot directly reach a host `127.0.0.1` proxy. Do not weaken runtime isolation or upgrade a shared production daemon merely to work around this. Older setups can build directly or import a trusted image built from the same Git revision: verify the archive SHA-256, pinned base image, `build_fingerprint` and imported immutable image ID, place the matching `image-manifest.json` in the dedicated account's `~/enzymind-sandbox/`, then run full acceptance through the normal entry. Trusted builds use host networking; untrusted execution remains `network=none`. Production Docker configuration is unchanged.

APT uses official sources for the current distribution, the system archive keyring and isolated temporary indexes/cache. It does not edit `/etc/apt` or depend on broken mirrors, duplicate sources or third-party repositories. `APT_CONFIG` selects the isolated configuration at startup. Signature and HTTPS checks remain enabled; any failed index update stops deployment. No `trusted=yes` or authentication bypass is used. Only the four prerequisites below and required dependencies are requested; package removal and full system upgrades are disallowed. Temporary configuration/cache is cleaned afterward. See [APT configuration](https://manpages.debian.org/trixie/apt/apt.conf.5.en.html).

To avoid the observed APT 3.0.3 [delayed retry queue issue](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1152704), internal APT retries are disabled. Index-update/download-only commands run at most three times, reusing verified cache, then fail. All packages are downloaded and verified before a single `--no-download install`; installation scripts are never automatically replayed. Native dependencies in image builds use the same pattern.

The installer adds missing `uidmap`, `dbus-user-session`, `python3-venv` and `slirp4netns`, skipping APT if all are already installed. It creates the dedicated `enzymind-python` account and subordinate IDs, configures cgroup delegation and linger for its user manager, copies the sandbox package, builds the pinned image, runs acceptance and starts Runner/reaper. An existing unmanaged account with the same name is rejected. Directory ownership and 0700 permissions are repaired component by component, including `.config/systemd/user`, without recursively changing subordinate UIDs inside Docker data. `--rootless-only` installs/checks only the daemon and does not establish container-limit acceptance.

After administrator provisioning, `deployment.json`, `acceptance.json`, `http-acceptance.json` and `gateway.env` in `/var/lib/enzymind-python-deploy/` are handed to the sudo caller with permissions 0600. Credentials are never printed. The Gateway fragment retains `ENZYMIND_PYTHON_ENABLED=false` until integration acceptance and merge into the existing runtime configuration. Fix failures and rerun; do not substitute an unrestricted container or the production socket. Runner uses a system Python 3.11+ virtual environment; the **execution image always uses Python 3.12**.

Pre-download hash-verified wheels to avoid repeated large downloads on slow networks:

```bash
python -m pip download --require-hashes --only-binary=:all: \
  -r services/python_sandbox/requirements.lock \
  -d services/python_sandbox/wheelhouse
```

When wheels are present, builds install only from that directory offline; an empty directory uses the package index. Both paths enforce versions and hashes. Wheels are mounted for the build, excluded from final image layers and not committed. Native dependencies include Xrender/Xext/Expat for RDKit drawing. The image runs scientific smoke checks as UID 10001 and verifies entrypoint readability.

### Manual deployment

1. Install `uidmap` and `dbus-user-session`; ensure `docker-ce-rootless-extras` and `dockerd-rootless-setuptool.sh` match the installed Docker version. Follow the [official Rootless prerequisites](https://docs.docker.com/engine/security/rootless/) without uninstalling production Docker.

   ```bash
   sudo apt-get install uidmap dbus-user-session
   sudo adduser --disabled-password --gecos '' enzymind-python
   sudo loginctl enable-linger enzymind-python
   ```

   Check that both `/etc/subuid` and `/etc/subgid` assign the account at least 65,536 non-overlapping subordinate IDs. The installer validates this. `/sys/fs/cgroup/cgroup.controllers` must include cpu, memory and pids.

2. Delegate controllers to **this account's** systemd user manager. For example, create `/etc/systemd/system/user@<DEDICATED_UID>.service.d/delegate.conf`:

   ```ini
   [Service]
   Delegate=cpu cpuset io memory pids
   ```

   Run `sudo systemctl daemon-reload`, then start/restart only the dedicated user manager. Do not broaden production Docker permissions. Follow distribution-specific AppArmor/user-namespace requirements; do not substitute privileged mode, disabled seccomp or missing resource limits.

3. Log into the dedicated account and install its independent user-systemd daemon:

   ```bash
   sudo -iu enzymind-python
   export XDG_RUNTIME_DIR=/run/user/$(id -u)
   dockerd-rootless-setuptool.sh install --force
   systemctl --user enable --now docker
   docker --host unix:///run/user/$(id -u)/docker.sock info
   ```

   `--force` allows coexistence with an existing rootful daemon, not use of the production socket. Confirm rootless mode, CgroupVersion 2 and CgroupDriver systemd. Do not run unrelated workloads in this daemon.

4. Copy only this package to the account's `~/enzymind-sandbox/services/python_sandbox/`, excluding `.env`, project data and production credentials. Create a Python 3.11+ virtual environment and install the Runner lockfile:

   ```bash
   cd ~/enzymind-sandbox
   python3 -m venv .venv
   .venv/bin/python -m pip install --require-hashes -r services/python_sandbox/runner-requirements.lock
   .venv/bin/python -m services.python_sandbox.lock_base
   # Review the official Python 3.12 digest in base-image.lock.json before building.
   .venv/bin/python -m services.python_sandbox.build_image --output image-manifest.json
   ```

   Run `lock_base` only for an intentional image update and version/archive its output. `build_image` rejects mutable tags, uses the dedicated Rootless socket and records the actual `sha256:...` image ID. The Dockerfile pins native libraries through a Debian snapshot; pip dependencies have complete version/hash locks. Builds verify FASTA, RDKit descriptors/fingerprints/PNG, CSV, SciPy and Matplotlib/Pillow. Runtime neither pulls images nor updates dependencies. The repository contains a registry-content-verified base digest; first deployment still requires a real build and final execution image ID.

   RDKit uses the supported `rdkit` PyPI package. Build steps install the Xrender/Xext libraries needed for Cairo drawing. [RDKit installation](https://www.rdkit.org/docs/Install.html)

5. Copy `deploy/runner.env.example` to `~/.config/enzymind-python/runner.env`, with file permissions 0600 and directory permissions 0700. Set the actual UID, absolute state path and manifest `image_id`. Generate an independent random `PYTHON_SANDBOX_TOKEN`, for example with `secrets.token_urlsafe(48)`, and share it only with Gateway configuration. Exclude it from n8n, browsers, source and logs. Create the state directory with permissions 0700.

   Install `enzymind-python-runner.service`, `enzymind-python-reaper.service` and `enzymind-python-reaper.timer` in the dedicated account's `~/.config/systemd/user/`.

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now enzymind-python-reaper.timer
   # Keep Runner stopped for Docker acceptance below, then start it.
   systemctl --user enable --now enzymind-python-runner.service
   ```

   Runner binds to `127.0.0.1:8091` and must not be exposed through nginx. Startup probes can take tens of seconds. `/health` requires the service credential, and execution is accepted only when ready=true. Health reports include active jobs, image and timeout/OOM/rejection/orphan metrics. Logs contain only job IDs, durations, resource values and error categories. Runner exclusively locks its state directory with flock, preventing multiple instances from sharing a daemon.

6. Configure the Gateway environment:

   ```dotenv
   ENZYMIND_PYTHON_ENABLED=false
   ENZYMIND_PYTHON_RUNNER_URL=http://127.0.0.1:8091
   ENZYMIND_PYTHON_AGENT_IPS=172.17.0.2
   PYTHON_SANDBOX_TOKEN=<SAME_DEDICATED_CREDENTIAL_AS_RUNNER>
   ENZYMIND_TRUSTED_PROXIES=127.0.0.1/32,::1/128
   ```

   Replace `ENZYMIND_PYTHON_AGENT_IPS` with the actual n8n-to-Gateway source IP for this deployment; `172.17.0.2` is only an example. Only exact IPs are accepted, not CIDRs, hostnames, wildcards or model fields. Update configuration and restart the Gateway if the n8n container IP changes. Do not trust the whole Docker subnet. Local debugging does not require adding localhost to this list.

   `ENZYMIND_TRUSTED_PROXIES` controls browser-IP rate limiting, not Python execution permission. List only actual trusted proxy addresses/CIDRs, or leave empty without proxies. Start the Gateway with `--workers 1 --no-proxy-headers`, as the existing scripts do, to prevent Uvicorn from rewriting the source first. Proxies must correctly replace/append X-Forwarded-For. Gateway walks left from the nearest trusted proxy to the first untrusted address. Vite uses `xfwd` to append the actual TCP source, preventing spoofing through direct frontend access. The digest is saved when the browser creates a turn; n8n addresses and model fields do not determine this quota. Unparseable addresses share a conservative bucket, and a new workspace does not bypass IP/global limits. n8n calls the Gateway directly, without the public reverse proxy or automatic Python POST retries; allow at least 100 seconds for the tool request.

7. Regenerate and deploy `agent_n8n/workspace/enzymind_workspace_v2.json` through the existing Workspace v2 process. n8n needs no Runner credential. Only after the following checks pass, set `ENZYMIND_PYTHON_ENABLED=true` and restart the single Gateway worker to enable the tool for all workspaces.

## Validation and release checks

### Local debugging

Local administrators retain debugging access without a public debug endpoint or authentication bypass. In addition to binding to `127.0.0.1`, Runner rejects non-loopback sources, proxy/browser requests and non-local Host headers at the ASGI layer. Every route, including health, requires the dedicated service credential.

From the repository root, run as the ordinary user who owns `.env.production`:

```bash
gateway/venv/bin/python -m services.python_sandbox.debug \
  services/python_sandbox/examples/local_debug.py --env-file .env.production
# Optional: --data-file /path/to/data.json --output-dir /path/to/a-new-private-directory
```

The configuration file must belong to the current user with permissions 0600. Credentials are read only from local configuration or the current environment, never command-line arguments. Code runs in the same disposable, offline container with identical image, limits and artifact validation. Debug runs do not write to production workspaces or consume Agent turn budgets, but still obey Runner concurrency and per-job limits. Output goes to a newly created private directory: `execution.json` contains bounded stdout/stderr, computation results and status; `artifacts/` contains CSV/PNG and other files. Existing directories are not overwritten, and transport failure never re-executes code.

Blocking Python `import`, `os` or `subprocess` with regex is not a sandbox. Code is itself untrusted; the boundaries are container isolation and server-side authorization. Structured `data` is transmitted as JSON, never interpolated into host commands. Prompt injection can still influence the Agent's analysis choices; the sandbox cannot eliminate that risk. It does not thereby grant access to host paths, networks, Docker parameters or other workspaces.

Regression checks that do not require Docker:

```bash
python -m pytest gateway/tests services/python_sandbox/tests agent_n8n/workspace/tests -q
cd frontend
npm test
node ../agent_n8n/workspace/tests/workflow.test.mjs
npm run build
# After starting a test Vite instance on :3011:
npx playwright test tests/browser/python-sandbox.spec.mjs
```

To check scientific libraries, install `requirements.lock` in an isolated Python 3.12 environment, then run:

```bash
python -m services.python_sandbox.science_smoke
```

Run actual Docker acceptance on the target server as the dedicated account, with the Gateway feature disabled and Runner stopped:

```bash
cd ~/enzymind-sandbox
set -a
. ~/.config/enzymind-python/runner.env
set +a
.venv/bin/python -m services.python_sandbox.acceptance
```

Acceptance verifies actual cgroups, one-CPU throttling, OOM, fork/thread limits, disk exhaustion, timeouts, excessive output, network isolation (public/private/metadata), read-only root, absence of production paths/credentials, task file isolation, libraries, oversized files, file-count/total limits, symbolic/hard links, cancellation, orphan collection and zero leftover containers. It writes `PYTHON_SANDBOX_STATE/acceptance.json` with checks, actual image ID and library versions. Any failure keeps the tool disabled. Passing mocked tests does not establish Docker acceptance.

The installer next runs `python -m services.python_sandbox.http_acceptance`: real HTTP authentication, global/per-workspace concurrency of 2/1, disconnect cancellation, duplicate/pre-cancelled requests, Gateway responsiveness under CPU load, and recovery/cleanup/replay rejection after SIGKILL of Runner during execution. This deliberately terminates Runner and belongs only in deployment before new jobs are enabled. Authentication uses pure ASGI middleware to preserve disconnect events.

Run `python -m services.python_sandbox.gateway_acceptance` in the repository with the Gateway Python environment to test routes against the real Runner. It uses an independent temporary workspace database without calling a model or changing production sessions. Checks cover result reuse, 3/12 budgets, private CSV/PNG downloads, saved-result/file inputs, cross-workspace 404 and Workspace Stop. The report is `files/workspace/python-gateway-acceptance.json`. Automated regressions cover hourly/storage quotas, interrupted reuse after Gateway restart, archive attacks and transactional 90-day cleanup.

Recorded environment validation is in [VALIDATION.md](VALIDATION.md).

## Disabling, monitoring and maintenance

To block new executions immediately, create `python.disabled` beside the workspace database or the file specified by `ENZYMIND_PYTHON_DISABLE_FILE`. Every request checks it without a restart. Existing jobs retain the 60-second bound. Use Workspace Stop to cancel a running job. Stopping Runner blocks new work while the independent reaper continues. For persistent disablement, set the feature flag false and restart the Gateway. Historical results remain available.

Monitor authenticated `/health` ready/active/metrics, especially timeout, oom, output_limit, busy, cleanup_failed, isolation_check_failed and orphans_removed. In Gateway SQLite, `python_attempts` tracks attempts accepted before hourly rejection, `python_runs.state` tracks busy/storage_quota/failures, and `sum(size)` in `python_files` measures quota usage. Also monitor physical database/WAL/backup size and host free space. Pure rate-limit rejection returns HTTP 429 and can be counted in access logs without logging bodies or headers.

The existing `python -m gateway.retention --dry-run` / `--run`, startup pass and hourly maintenance enforce 90-day retention. New tables use additive migrations and preserve result IDs. Update dependencies in an isolated environment by regenerating both `*.lock` files with `pip-compile --generate-hashes`, resolving the base image, rebuilding and rerunning acceptance. Preserve prior images/locks for reproducibility. Scientific correctness still requires reviewing the code and inputs.
