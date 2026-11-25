#!/bin/bash
#
# EnzyMind 服务停止脚本
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PIDS_DIR="$PROJECT_DIR/.pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

stop_service() {
    local service=$1
    python3 "$SCRIPT_DIR/service_process.py" stop "$service" "$PROJECT_DIR/services/$service" "${SERVICES[$service]}" "$PIDS_DIR/${service}.pid"
}

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           EnzyMind 微服务停止脚本                          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

failed=0
if [ -n "${1:-}" ]; then
    if [ -z "${SERVICES[$1]}" ]; then
        echo -e "${RED}错误: 未知服务 '$1'${NC}"
        exit 1
    fi
    echo -e "${YELLOW}停止服务: $1${NC}"
    stop_service "$1" || failed=1
else
    echo -e "${YELLOW}停止所有服务...${NC}"
    echo ""
    for service in "${!SERVICES[@]}"; do
        stop_service "$service" || failed=1
    done
fi

echo ""
[ "$failed" -ne 0 ] || echo -e "${GREEN}完成${NC}"
exit "$failed"
