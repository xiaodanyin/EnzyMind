#!/bin/bash
# Existing deployment entry: scientific services, Web dependencies, optional Rootless Python.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 1
declare -A SERVICES=(
    ["enzy_recognize"]="18901"
    ["ecnumber_predict"]="18902"
    ["substrate_predict"]="18903"
    ["kcat_predict"]="18904"
    ["km_predict"]="18905"
    ["structure_predict"]="18906"
    ["active_sites"]="18907"
    ["enzyme_type"]="18908"
    ["protparam"]="18909"
    ["sequence_alignment"]="18910"
    ["function_get"]="18911"
    ["enzyme_subclass"]="18912"
    ["ec_reaction_info"]="18913"
    ["enzyme_check"]="18914"
    ["enzyme_full_info"]="18915"
    ["functional_site"]="18916"
    ["kinetic_params"]="18917"
    ["sequence_info"]="18918"
    ["query_mechanism_mcsa"]="18919"
)
usage() {
    cat <<'USAGE'
Usage: bash scripts/deploy.sh [service ...] [options]
  No targets: all scientific services + gateway + frontend;
              include python_sandbox when enabled in .env.production.
  Targets: existing scientific service names, gateway, frontend, python_sandbox, uniprot, blast_db
  blast_db            Verify and install a versioned local BLAST release using
                      ENZYMIND_BLAST_ARCHIVE and ENZYMIND_BLAST_RELEASE_DIR
  uniprot             Update only shared snapshot dependencies in deployed query
                      environments and check the configured read-only database
  --with-python       Also install/update the optional sandbox (initially disabled)
  --enable-python     Enable Python only after real container and Gateway acceptance
  --agent-ip IP       Verified exact n8n source IP(s); otherwise discover its route
  --n8n-container NAME  Existing n8n container (default: n8n)
  --gateway-url URL   n8n -> Gateway base URL (default: http://host.docker.internal:8080)
  --proxy URL         Loopback build/install proxy for the sandbox only
  --runner-python PATH  Independent Python 3.11+ when the system Python is older
  --check             Read-only sandbox prerequisites, routing and health check
  --dry-run           Print selected stages without installing or changing services
  --help              Show this help
Use the Gateway owner account. Only the Rootless installer requests sudo.
After deployment: bash scripts/start_web.sh restart
USAGE
}
TARGETS=()
SANDBOX_ARGS=()
WITH_PYTHON=false
DRY_RUN=false
CHECK=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --with-python) WITH_PYTHON=true; shift ;;
        --enable-python) WITH_PYTHON=true; SANDBOX_ARGS+=(--enable); shift ;;
        --proxy|--agent-ip|--n8n-container|--gateway-url|--runner-python)
            [ "$#" -ge 2 ] && [[ "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 2; }
            SANDBOX_ARGS+=("$1" "$2"); shift 2 ;;
        --check) CHECK=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --*) echo "Unknown option: $1" >&2; exit 2 ;;
        *)
            if [[ "$1" != gateway && "$1" != frontend && "$1" != python_sandbox && "$1" != uniprot && "$1" != blast_db ]] && [ -z "${SERVICES[$1]:-}" ]; then
                echo "Unknown service: $1" >&2; exit 2
            fi
            TARGETS+=("$1"); shift ;;
    esac
done
command -v python3 >/dev/null || { echo 'python3 is required.' >&2; exit 1; }
ENZYMIND_RUNTIME_ENV="${ENZYMIND_ENV_FILE:-$PROJECT_DIR/.env.production}"
# Read only the boolean for planning; never source or print service credentials.
PYTHON_ENABLED=$(python3 - "$ENZYMIND_RUNTIME_ENV" <<'PYENV'
from pathlib import Path
import sys
from services.python_sandbox.deploy.integrate import settings
p=Path(sys.argv[1])
print(settings(p.read_text()).get('ENZYMIND_PYTHON_ENABLED','false').lower() if p.exists() else 'false')
PYENV
) || exit 1
if "$CHECK"; then
    [ "${#TARGETS[@]}" -eq 0 ] && TARGETS=(python_sandbox)
    for name in "${TARGETS[@]}"; do
        [ "$name" = python_sandbox ] || { echo '--check is only for python_sandbox.' >&2; exit 2; }
    done
    SANDBOX_ARGS+=(--check)
fi
if [ "${#TARGETS[@]}" -eq 0 ]; then
    TARGETS=(gateway frontend "${!SERVICES[@]}")
    [ "$PYTHON_ENABLED" != true ] || WITH_PYTHON=true
fi
"$WITH_PYTHON" && TARGETS+=(python_sandbox)
# Always prepare Web dependencies before sandbox integration; remove duplicates.
ORDERED=()
for preferred in gateway frontend "${!SERVICES[@]}" uniprot blast_db python_sandbox; do
    for target in "${TARGETS[@]}"; do
        if [ "$target" = "$preferred" ]; then ORDERED+=("$target"); break; fi
    done
done
if "$DRY_RUN"; then
    printf 'Deployment stages (no changes):\n'
    printf '  %s\n' "${ORDERED[@]}"
    exit 0
fi
[ "$EUID" -ne 0 ] || { echo 'Run as the Gateway owner; sudo is used only for Rootless installation.' >&2; exit 1; }

install_python_service() (
    local directory=$1
    cd "$directory" || return 1
    [ -f requirements.txt ] || { echo "Missing requirements.txt: $directory" >&2; return 1; }
    [ -x venv/bin/python ] || python3 -m venv venv || return 1
    # Moved venv activation files can contain stale paths. Use the actual interpreter.
    export VIRTUAL_ENV="$directory/venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    for installer in install_torch.sh install_pyg.sh install_dgl.sh; do
        if [ -f "$installer" ]; then bash "$installer" || return 1; fi
    done
    "$directory/venv/bin/python" -m pip install -r requirements.txt
)
failed=0
for target in "${ORDERED[@]}"; do
    echo "Deploying $target ..."
    case "$target" in
        gateway) install_python_service "$PROJECT_DIR/gateway" ;;
        frontend) (cd "$PROJECT_DIR/frontend" && npm ci && npm run build) ;;
        blast_db)
            (
                if [ -f "$ENZYMIND_RUNTIME_ENV" ]; then
                    set -a
                    source "$ENZYMIND_RUNTIME_ENV" || exit 1
                    set +a
                fi
                python3 services/sequence_alignment/deploy/release.py install \
                    "${ENZYMIND_BLAST_ARCHIVE:?Set the path to the release archive}" \
                    "${ENZYMIND_BLAST_RELEASE_DIR:?Set the database installation directory}"
            ) ;;
        uniprot)
            (
                probe_python=''
                for service in sequence_alignment enzyme_check function_get ec_reaction_info enzyme_full_info functional_site kinetic_params sequence_info; do
                    interpreter="$PROJECT_DIR/services/$service/venv/bin/python"
                    [ -x "$interpreter" ] || continue
                    "$interpreter" -m pip install -r "$PROJECT_DIR/shared/requirements-uniprot.txt" || exit 1
                    probe_python="$interpreter"
                done
                [ -n "$probe_python" ] || { echo 'No deployed UniProt query environment found.' >&2; exit 1; }
                "$probe_python" "$SCRIPT_DIR/check_uniprot.py" --env-file "$ENZYMIND_RUNTIME_ENV"
            ) ;;
        python_sandbox)
            if [ "$failed" -ne 0 ]; then
                echo 'Skipping sandbox integration because a prerequisite deployment failed.' >&2
                continue
            fi
            python3 -m services.python_sandbox.deploy.integrate --env-file "$ENZYMIND_RUNTIME_ENV" "${SANDBOX_ARGS[@]}" ;;
        *) install_python_service "$PROJECT_DIR/services/$target" ;;
    esac
    if [ "$?" -ne 0 ]; then
        echo "FAILED: $target" >&2
        failed=1
    else
        echo "OK: $target"
    fi
done
if [ "$failed" -eq 0 ] && ! "$CHECK"; then
    echo 'Deployment completed. Use scripts/start.sh for scientific services and scripts/start_web.sh restart for Web changes.'
fi
exit "$failed"
