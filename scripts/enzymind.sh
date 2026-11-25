#!/usr/bin/env bash
# Manage the scientific services, Gateway and frontend in this checkout.
set -u
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 1
action=${1:-start}

usage() {
    echo "用法: $0 {start|stop|restart|status}（默认 start）"
}

if (( $# > 1 )); then usage >&2; exit 2; fi
case "$action" in
    -h|--help) usage; exit 0 ;;
    status)
        failed=0
        bash "$script_dir/status.sh" || failed=1
        bash "$script_dir/start_web.sh" status || failed=1
        exit "$failed"
        ;;
    start|stop|restart) ;;
    *) usage >&2; exit 2 ;;
esac

stop_all() {
    local failed=0
    bash "$script_dir/start_web.sh" stop || failed=1
    bash "$script_dir/stop.sh" || failed=1
    return "$failed"
}

pid_dir="$script_dir/../.pids"
mkdir -p "$pid_dir" || exit 1
exec 9>"$pid_dir/enzymind-control.lock" || exit 1
flock -n -E 75 9 || {
    rc=$?
    if (( rc == 75 )); then echo '另一个启停操作正在进行，请稍后重试。' >&2; fi
    exit "$rc"
}
# Only the controller holds the lock. Detached services must not inherit it.
(
    case "$action" in
        start) bash "$script_dir/start_all.sh" ;;
        stop) stop_all ;;
        restart) stop_all && bash "$script_dir/start_all.sh" ;;
    esac
) 9>&-
