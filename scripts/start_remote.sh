#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/software/node-v24.18.0-linux-x64/bin:$HOME/.local/bin:$PATH"
export ESMFOLD_USE_GPU=false
bash "$project_dir/scripts/start.sh"
bash "$project_dir/scripts/start_web.sh" start
