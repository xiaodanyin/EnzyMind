#!/bin/bash
#
# Enzymind 服务停止脚本
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
    local pid_file="$PIDS_DIR/${service}.pid"
    
    if [ ! -f "$pid_file" ]; then
        echo -e "  ${YELLOW}⚠${NC} $service: 无 PID 文件"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    
    if kill -0 $pid 2>/dev/null; then
        kill $pid 2>/dev/null
        sleep 1
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null
        fi
        rm -f "$pid_file"
        echo -e "  ${GREEN}✓${NC} $service (PID $pid) 已停止"
        return 0
    else
        rm -f "$pid_file"
        echo -e "  ${YELLOW}⚠${NC} $service: 进程已不存在"
        return 1
    fi
}

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Enzymind 微服务停止脚本                          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ -n "$1" ]; then
    if [ -z "${SERVICES[$1]}" ]; then
        echo -e "${RED}错误: 未知服务 '$1'${NC}"
        exit 1
    fi
    echo -e "${YELLOW}停止服务: $1${NC}"
    stop_service "$1"
else
    echo -e "${YELLOW}停止所有服务...${NC}"
    echo ""
    for service in "${!SERVICES[@]}"; do
        stop_service "$service"
    done
fi

echo ""
echo -e "${GREEN}完成${NC}"
