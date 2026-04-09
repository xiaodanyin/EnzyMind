#!/bin/bash
#
# Enzymind Web 启动脚本
# 启动 Vue Frontend 和 Gateway 服务
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
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
FRONTEND_PORT=3000
GATEWAY_PORT=8080

# 创建目录
mkdir -p "$LOGS_DIR"
mkdir -p "$PIDS_DIR"

# 打印标题
print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         ${GREEN}Enzymind Web Services${CYAN}              ║${NC}"
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

# 启动 Gateway
start_gateway() {
    echo -e "${BLUE}▶ 启动 Gateway 服务...${NC}"
    
    if check_port $GATEWAY_PORT; then
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
        source venv/bin/activate
        nohup python -m uvicorn main:app --host 0.0.0.0 --port $GATEWAY_PORT \
            > "$LOGS_DIR/gateway.log" 2>&1 &
        local pid=$!
        echo $pid > "$PIDS_DIR/gateway.pid"
        deactivate
    else
        # 使用系统 Python
        nohup python -m uvicorn main:app --host 0.0.0.0 --port $GATEWAY_PORT \
            > "$LOGS_DIR/gateway.log" 2>&1 &
        local pid=$!
        echo $pid > "$PIDS_DIR/gateway.pid"
    fi
    
    sleep 2
    
    if kill -0 $pid 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Gateway 已启动 (端口 $GATEWAY_PORT, PID $pid)"
        echo -e "  ${BLUE}📝${NC} 日志: $LOGS_DIR/gateway.log"
        return 0
    else
        echo -e "  ${RED}✗${NC} Gateway 启动失败，请查看日志"
        return 1
    fi
}

# 启动 Vue Frontend
start_frontend() {
    echo -e "${BLUE}▶ 启动 Vue Frontend...${NC}"
    
    if check_port $FRONTEND_PORT; then
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
        npm install > "$LOGS_DIR/frontend_install.log" 2>&1
    fi
    
    # 启动开发服务器
    nohup npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT \
        > "$LOGS_DIR/frontend.log" 2>&1 &
    local pid=$!
    echo $pid > "$PIDS_DIR/frontend.pid"
    
    sleep 3
    
    if kill -0 $pid 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Frontend 已启动 (端口 $FRONTEND_PORT, PID $pid)"
        echo -e "  ${BLUE}📝${NC} 日志: $LOGS_DIR/frontend.log"
        return 0
    else
        echo -e "  ${RED}✗${NC} Frontend 启动失败，请查看日志"
        return 1
    fi
}

# 停止服务（通过端口）
stop_service() {
    local service=$1
    local port=$2
    
    # 通过端口查找并杀死进程
    local pids=$(lsof -t -i:$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null
        sleep 1
        # 如果还有进程，强制杀死
        pids=$(lsof -t -i:$port 2>/dev/null)
        if [ -n "$pids" ]; then
            echo "$pids" | xargs kill -9 2>/dev/null
        fi
        echo -e "  ${GREEN}✓${NC} $service 已停止 (端口 $port)"
    else
        echo -e "  ${YELLOW}⚠${NC} $service 未在运行 (端口 $port)"
    fi
    
    # 清理 PID 文件
    rm -f "$PIDS_DIR/${service}.pid"
}

# 显示状态
show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}服务状态:${NC}"
    echo ""
    
    # Gateway 状态
    if check_port $GATEWAY_PORT; then
        local gateway_pid=$(cat "$PIDS_DIR/gateway.pid" 2>/dev/null || echo "N/A")
        echo -e "  ${GREEN}●${NC} Gateway:  http://localhost:$GATEWAY_PORT (PID: $gateway_pid)"
    else
        echo -e "  ${RED}○${NC} Gateway:  未运行"
    fi
    
    # Frontend 状态
    if check_port $FRONTEND_PORT; then
        local frontend_pid=$(cat "$PIDS_DIR/frontend.pid" 2>/dev/null || echo "N/A")
        echo -e "  ${GREEN}●${NC} Frontend: http://localhost:$FRONTEND_PORT (PID: $frontend_pid)"
    else
        echo -e "  ${RED}○${NC} Frontend: 未运行"
    fi
    
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo -e "  🌐 本地访问: http://localhost:$FRONTEND_PORT/enzymind"
    echo -e "  🌐 外部访问: http://cadd.iddd.group/enzymind"
    echo ""
    echo -e "${BLUE}日志文件:${NC}"
    echo -e "  📝 Gateway:  $LOGS_DIR/gateway.log"
    echo -e "  📝 Frontend: $LOGS_DIR/frontend.log"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
}

# 主函数
main() {
    local action=${1:-start}
    
    print_header
    
    case $action in
        start)
            start_gateway
            start_frontend
            show_status
            ;;
        stop)
            echo -e "${BLUE}▶ 停止服务...${NC}"
            stop_service "gateway" $GATEWAY_PORT
            stop_service "frontend" $FRONTEND_PORT
            echo -e "${GREEN}所有 Web 服务已停止${NC}"
            ;;
        restart)
            echo -e "${BLUE}▶ 重启服务...${NC}"
            stop_service "gateway" $GATEWAY_PORT
            stop_service "frontend" $FRONTEND_PORT
            sleep 2
            start_gateway
            start_frontend
            show_status
            ;;
        status)
            show_status
            ;;
        gateway)
            start_gateway
            show_status
            ;;
        frontend)
            start_frontend
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
}

main "$@"
