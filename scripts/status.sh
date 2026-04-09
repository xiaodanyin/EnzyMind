#!/bin/bash
#
# Enzymind 服务状态检查脚本
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
echo -e "${BLUE}║           Enzymind 微服务状态                              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

printf "%-20s %-8s %-8s %-10s\n" "服务名" "端口" "PID" "状态"
echo "─────────────────────────────────────────────────────"

RUNNING=0
STOPPED=0

for service in $(echo "${!SERVICES[@]}" | tr ' ' '\n' | sort); do
    port=${SERVICES[$service]}
    pid_file="$PIDS_DIR/${service}.pid"
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            printf "%-20s %-8s %-8s ${GREEN}%-10s${NC}\n" "$service" "$port" "$pid" "运行中"
            ((RUNNING++))
        else
            printf "%-20s %-8s %-8s ${RED}%-10s${NC}\n" "$service" "$port" "-" "已停止"
            ((STOPPED++))
        fi
    else
        # 检查端口是否被占用
        port_pid=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$port_pid" ]; then
            printf "%-20s %-8s %-8s ${YELLOW}%-10s${NC}\n" "$service" "$port" "$port_pid" "端口占用"
            ((RUNNING++))
        else
            printf "%-20s %-8s %-8s ${RED}%-10s${NC}\n" "$service" "$port" "-" "未启动"
            ((STOPPED++))
        fi
    fi
done

echo ""
echo -e "运行中: ${GREEN}$RUNNING${NC}  停止: ${RED}$STOPPED${NC}"
