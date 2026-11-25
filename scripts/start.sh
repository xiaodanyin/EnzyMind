#!/bin/bash
#
# EnzyMind 服务启动脚本
# 启动所有或指定的微服务
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENZYMIND_RUNTIME_ENV="${ENZYMIND_ENV_FILE:-$PROJECT_DIR/.env.production}"
if [ -f "$ENZYMIND_RUNTIME_ENV" ]; then
    set -a
    source "$ENZYMIND_RUNTIME_ENV" || exit 1
    set +a
fi
# The Runner credential is exclusively for Gateway, never prediction/query workers.
unset PYTHON_SANDBOX_TOKEN
SERVICES_DIR="$PROJECT_DIR/services"
PIDS_DIR="$PROJECT_DIR/.pids"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 服务列表及端口
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

mkdir -p "$PIDS_DIR"

start_service() {
    local service=$1
    local port=${SERVICES[$service]}
    local service_dir="$SERVICES_DIR/$service"
    
    if [ ! -d "$service_dir" ]; then
        echo -e "  ${RED}✗${NC} $service: 目录不存在"
        return 1
    fi
    
    if [ ! -f "$service_dir/venv/bin/python" ]; then
        echo -e "  ${RED}✗${NC} $service: 未部署，请先运行 deploy.sh"
        return 1
    fi
    
    local health_method=GET
    [ "$service" = "query_mechanism_mcsa" ] && health_method=POST
    # Existing healthy services are already started, not failures.
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        python3 "$SCRIPT_DIR/service_process.py" adopt "$service" "$service_dir" "$port" "$PIDS_DIR/${service}.pid" || return 1
        if curl --noproxy '*' -fsS --max-time 15 -X "$health_method" "http://127.0.0.1:$port/health" >/dev/null; then
            echo -e "  ${GREEN}✓${NC} $service: 已就绪 (端口 $port)"
            return 0
        fi
        echo -e "  ${RED}✗${NC} $service: 端口 $port 已占用但健康检查失败"
        return 1
    fi
    
    cd "$service_dir"
    # Invoke the current interpreter directly: activate can contain stale paths
    # after the repository/virtual environments have been moved.
    nohup setsid "$service_dir/venv/bin/python" -u main.py </dev/null > "$PIDS_DIR/${service}.log" 2>&1 &
    local pid=$!
    echo $pid > "$PIDS_DIR/${service}.pid"
    
    local deadline=$((SECONDS + ${ENZYMIND_START_TIMEOUT:-60}))
    while kill -0 "$pid" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do
        if curl --noproxy '*' -fsS --max-time 15 -X "$health_method" "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $service 已就绪 (端口 $port, PID $pid)"
            return 0
        fi
        sleep 1
    done
    echo -e "  ${RED}✗${NC} $service: 未就绪；查看 $PIDS_DIR/${service}.log"
    return 1
}

show_usage() {
    echo "用法: $0 [服务名]"
    echo ""
    echo "不带参数: 启动所有服务"
    echo "带服务名: 只启动指定服务"
    echo ""
    echo "可用服务:"
    for service in "${!SERVICES[@]}"; do
        echo "  - $service (端口 ${SERVICES[$service]})"
    done | sort
}

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           EnzyMind 微服务启动脚本                          ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_usage
    exit 0
fi

if [ -n "$1" ]; then
    # 启动指定服务
    if [ -z "${SERVICES[$1]}" ]; then
        echo -e "${RED}错误: 未知服务 '$1'${NC}"
        show_usage
        exit 1
    fi
    echo -e "${YELLOW}启动服务: $1${NC}"
    start_service "$1"
    exit $?
else
    # 启动所有服务
    echo -e "${YELLOW}启动所有服务...${NC}"
    echo ""
    
    SUCCESS=0
    FAIL=0
    
    for service in "${!SERVICES[@]}"; do
        if start_service "$service"; then
            ((SUCCESS++))
        else
            ((FAIL++))
        fi
    done
    
    echo ""
    echo -e "${GREEN}成功启动: $SUCCESS${NC}"
    echo -e "${RED}启动失败: $FAIL${NC}"
    [ "$FAIL" -eq 0 ] || exit 1
fi

echo ""
echo -e "使用 ${GREEN}./scripts/stop.sh${NC} 停止服务"
echo -e "使用 ${GREEN}./scripts/status.sh${NC} 查看状态"
