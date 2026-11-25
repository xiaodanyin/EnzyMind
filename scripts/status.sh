#!/bin/bash
#
# EnzyMind 服务状态检查脚本
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

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           EnzyMind 微服务状态                              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

printf "%-20s %-8s %-8s %-10s\n" "服务名" "端口" "PID" "状态"
echo "─────────────────────────────────────────────────────"

RUNNING=0
STOPPED=0

for service in $(echo "${!SERVICES[@]}" | tr ' ' '\n' | sort); do
    port=${SERVICES[$service]}
    pid=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1)
    method=GET
    [ "$service" = "query_mechanism_mcsa" ] && method=POST
    if curl --noproxy '*' -fsS --max-time 5 -X "$method" "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
        printf "%-20s %-8s %-8s ${GREEN}%-10s${NC}\n" "$service" "$port" "${pid:--}" "HTTP 就绪"
        ((RUNNING++))
    else
        printf "%-20s %-8s %-8s ${RED}%-10s${NC}\n" "$service" "$port" "${pid:--}" "未就绪"
        ((STOPPED++))
    fi
done

echo ""
echo -e "HTTP 就绪: ${GREEN}$RUNNING${NC}  未就绪: ${RED}$STOPPED${NC}"
[ "$STOPPED" -eq 0 ]
