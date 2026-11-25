#!/usr/bin/env bash
# Start the scientific services as well as the gateway and frontend.
set -u
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=0
bash "$script_dir/start.sh" || failed=1
bash "$script_dir/start_web.sh" start || failed=1
bash "$script_dir/status.sh" || failed=1
exit "$failed"
