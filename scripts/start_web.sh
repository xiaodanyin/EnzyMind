#!/bin/bash
#
# EnzyMind Web 启动脚本
# 启动 Vue Frontend 和 Gateway 服务
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENZYMIND_RUNTIME_ENV="${ENZYMIND_ENV_FILE:-$PROJECT_DIR/.env.production}"
if [ -f "$ENZYMIND_RUNTIME_ENV" ]; then
    set -a
    source "$ENZYMIND_RUNTIME_ENV" || exit 1
    set +a
fi
FRONTEND_DIR="$PROJECT_DIR/frontend"
GATEWAY_DIR="$PROJECT_DIR/gateway"
LOGS_DIR="$PROJECT_DIR/.logs"
PIDS_DIR="$PROJECT_DIR/.pids"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 端口配置
FRONTEND_PORT=3010
GATEWAY_PORT=8080

# 创建目录
mkdir -p "$LOGS_DIR"
mkdir -p "$PIDS_DIR"

# 打印标题
print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         ${GREEN}EnzyMind Web Services${CYAN}              ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

web_ready() {
    curl --noproxy '*' -fsS --max-time 5 "$1" >/dev/null 2>&1
}

wait_ready() {
    local pid=$1 url=$2
    local deadline=$((SECONDS + ${ENZYMIND_START_TIMEOUT:-60}))
    while kill -0 "$pid" 2>/dev/null && [ "$SECONDS" -lt "$deadline" ]; do
        web_ready "$url" && return 0
        sleep 1
    done
    return 1
}

python_status() {
    # Rootless services are managed by their dedicated user's systemd units.
    # Web startup must not acquire Docker privileges or install software.
    if [ "${ENZYMIND_PYTHON_ENABLED:-false}" = true ]; then
        (cd "$PROJECT_DIR" && python3 -m services.python_sandbox.deploy.integrate \
            --env-file "$ENZYMIND_RUNTIME_ENV" --status)
    else
        echo '  Python sandbox: disabled (optional feature)'
    fi
}

# 启动 Gateway
start_gateway() {
    echo -e "${BLUE}▶ 启动 Gateway 服务...${NC}"
    
    if check_port $GATEWAY_PORT; then
        python3 "$SCRIPT_DIR/service_process.py" adopt gateway "$GATEWAY_DIR" "$GATEWAY_PORT" "$PIDS_DIR/gateway.pid" || return 1
        if web_ready "http://127.0.0.1:$GATEWAY_PORT/health"; then
            echo -e "  ${GREEN}✓${NC} Gateway 已就绪 (端口 $GATEWAY_PORT)"
            return 0
        fi
        echo -e "  ${YELLOW}⚠${NC} Gateway: 端口 $GATEWAY_PORT 已被占用"
        return 1
    fi
    
    if [ ! -d "$GATEWAY_DIR" ]; then
        echo -e "  ${RED}✗${NC} Gateway: 目录不存在"
        return 1
    fi
    
    cd "$GATEWAY_DIR"
    
    # 检查是否有虚拟环境
    if [ -f "venv/bin/python" ]; then
        nohup setsid "$GATEWAY_DIR/venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port $GATEWAY_PORT --workers 1 --no-proxy-headers \
            </dev/null > "$LOGS_DIR/gateway.log" 2>&1 &
        local pid=$!
        echo $pid > "$PIDS_DIR/gateway.pid"
    else
        # 使用系统 Python
        nohup setsid python3 -m uvicorn main:app --host 0.0.0.0 --port $GATEWAY_PORT --workers 1 --no-proxy-headers \
            </dev/null > "$LOGS_DIR/gateway.log" 2>&1 &
        local pid=$!
        echo $pid > "$PIDS_DIR/gateway.pid"
    fi
    
    if wait_ready "$pid" "http://127.0.0.1:$GATEWAY_PORT/health"; then
        echo -e "  ${GREEN}✓${NC} Gateway 已启动 (端口 $GATEWAY_PORT, PID $pid)"
        echo -e "  ${BLUE}📝${NC} 日志: $LOGS_DIR/gateway.log"
        return 0
    else
        echo -e "  ${RED}✗${NC} Gateway 启动失败，请查看日志"
        return 1
    fi
}

# 启动 Vue Frontend
start_frontend() (
    # npm install/build/dev subprocesses must not inherit Gateway's Runner key.
    unset PYTHON_SANDBOX_TOKEN
    echo -e "${BLUE}▶ 启动 Vue Frontend...${NC}"
    
    if check_port $FRONTEND_PORT; then
        python3 "$SCRIPT_DIR/service_process.py" adopt frontend "$FRONTEND_DIR" "$FRONTEND_PORT" "$PIDS_DIR/frontend.pid" || return 1
        if web_ready "http://127.0.0.1:$FRONTEND_PORT/enzymind/"; then
            echo -e "  ${GREEN}✓${NC} Frontend 已就绪 (端口 $FRONTEND_PORT)"
            return 0
        fi
        echo -e "  ${YELLOW}⚠${NC} Frontend: 端口 $FRONTEND_PORT 已被占用"
        return 1
    fi
    
    if [ ! -d "$FRONTEND_DIR" ]; then
        echo -e "  ${RED}✗${NC} Frontend: 目录不存在"
        return 1
    fi
    
    cd "$FRONTEND_DIR"
    
    # 检查 node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "  ${YELLOW}⚠${NC} 正在安装依赖..."
        npm ci > "$LOGS_DIR/frontend_install.log" 2>&1 || return 1
    fi
    
    # 启动开发服务器
    nohup setsid npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT --strictPort \
        </dev/null > "$LOGS_DIR/frontend.log" 2>&1 &
    local pid=$!
    echo $pid > "$PIDS_DIR/frontend.pid"
    
    if wait_ready "$pid" "http://127.0.0.1:$FRONTEND_PORT/enzymind/"; then
        echo -e "  ${GREEN}✓${NC} Frontend 已启动 (端口 $FRONTEND_PORT, PID $pid)"
        echo -e "  ${BLUE}📝${NC} 日志: $LOGS_DIR/frontend.log"
        return 0
    else
        echo -e "  ${RED}✗${NC} Frontend 启动失败，请查看日志"
        return 1
    fi
)

# 仅停止当前项目的监听进程；兼容缺失或过期的 PID 文件。
stop_service() {
    local service=$1 port=$2
    python3 "$SCRIPT_DIR/service_process.py" stop "$service" "$PROJECT_DIR/$service" "$port" "$PIDS_DIR/${service}.pid"
}

# 显示状态
show_status() {
    local failed=0
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}服务状态:${NC}"
    echo ""
    
    # Gateway 状态
    if web_ready "http://127.0.0.1:$GATEWAY_PORT/health"; then
        local gateway_pid=$(lsof -t -iTCP:$GATEWAY_PORT -sTCP:LISTEN 2>/dev/null | head -1)
        echo -e "  ${GREEN}●${NC} Gateway:  http://localhost:$GATEWAY_PORT (PID: $gateway_pid)"
    else
        echo -e "  ${RED}○${NC} Gateway:  HTTP 健康检查失败"
        failed=1
    fi
    
    # Frontend 状态
    if web_ready "http://127.0.0.1:$FRONTEND_PORT/enzymind/"; then
        local frontend_pid=$(lsof -t -iTCP:$FRONTEND_PORT -sTCP:LISTEN 2>/dev/null | head -1)
        echo -e "  ${GREEN}●${NC} Frontend: http://localhost:$FRONTEND_PORT (PID: $frontend_pid)"
    else
        echo -e "  ${RED}○${NC} Frontend: HTTP 检查失败"
        failed=1
    fi
    
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo -e "  🌐 本地访问: http://localhost:$FRONTEND_PORT/enzymind"
    echo -e "  🌐 外部访问: https://cadd.zju.edu.cn/enzymind"
    echo ""
    echo -e "${BLUE}日志文件:${NC}"
    echo -e "  📝 Gateway:  $LOGS_DIR/gateway.log"
    echo -e "  📝 Frontend: $LOGS_DIR/frontend.log"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    return "$failed"
}

# 主函数
main() {
    local action=${1:-start}
    local failed=0
    
    print_header
    
    case $action in
        start)
            start_gateway || failed=1
            start_frontend || failed=1
            show_status
            python_status || failed=1
            ;;
        stop)
            echo -e "${BLUE}▶ 停止服务...${NC}"
            stop_service "gateway" $GATEWAY_PORT || failed=1
            stop_service "frontend" $FRONTEND_PORT || failed=1
            [ "$failed" -ne 0 ] || echo -e "${GREEN}所有 Web 服务已停止${NC}"
            ;;
        restart)
            echo -e "${BLUE}▶ 重启服务...${NC}"
            stop_service "gateway" $GATEWAY_PORT || failed=1
            stop_service "frontend" $FRONTEND_PORT || failed=1
            [ "$failed" -eq 0 ] || return 1
            start_gateway || failed=1
            start_frontend || failed=1
            show_status
            python_status || failed=1
            ;;
        status)
            show_status || failed=1
            python_status || failed=1
            ;;
        gateway)
            start_gateway || failed=1
            show_status
            python_status || failed=1
            ;;
        frontend)
            start_frontend || failed=1
            show_status
            ;;
        *)
            echo -e "用法: $0 {start|stop|restart|status|gateway|frontend}"
            echo ""
            echo "  start     - 启动所有 Web 服务 (Gateway + Frontend)"
            echo "  stop      - 停止所有 Web 服务"
            echo "  restart   - 重启所有 Web 服务"
            echo "  status    - 显示服务状态"
            echo "  gateway   - 仅启动 Gateway"
            echo "  frontend  - 仅启动 Frontend"
            exit 1
            ;;
    esac
    return "$failed"
}

main "$@"
