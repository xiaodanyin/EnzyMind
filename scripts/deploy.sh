#!/bin/bash
#
# Enzymind 一键部署脚本
# 为所有微服务创建虚拟环境并安装依赖
#

# 注意：不使用 set -e，因为循环中需要处理单个服务的失败而不退出整个脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$PROJECT_DIR/services"

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

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Enzymind 微服务一键部署脚本                      ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}[1/3] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  Python 版本: ${GREEN}$PYTHON_VERSION${NC}"

echo ""
echo -e "${YELLOW}[2/3] 部署微服务...${NC}"
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0
SUCCESS_SERVICES=()
FAIL_SERVICES=()

for service in "${!SERVICES[@]}"; do
    port=${SERVICES[$service]}
    service_dir="$SERVICES_DIR/$service"
    
    if [ ! -d "$service_dir" ]; then
        echo -e "  ${RED}✗${NC} $service (目录不存在)"
        ((FAIL_COUNT++))
        FAIL_SERVICES+=("$service (目录不存在)")
        continue
    fi
    
    echo -n "  部署 $service (端口 $port)... "
    
    cd "$service_dir"
    
    # 创建虚拟环境（忽略错误继续）
    if [ ! -d "venv" ]; then
        if ! python3 -m venv venv 2>/dev/null; then
            echo -e "${RED}✗ (创建 venv 失败)${NC}"
            ((FAIL_COUNT++))
            FAIL_SERVICES+=("$service (创建 venv 失败)")
            continue
        fi
    fi
    
    if [ -f "requirements.txt" ]; then
        source venv/bin/activate
        echo ""
        
        # 如果存在 install_torch.sh，先安装 PyTorch
        if [ -f "install_torch.sh" ]; then
            echo -e "  ${BLUE}安装 PyTorch...${NC}"
            if ! bash install_torch.sh; then
                echo -e "  ${RED}✗ $service PyTorch 安装失败${NC}"
                deactivate
                ((FAIL_COUNT++))
                FAIL_SERVICES+=("$service (PyTorch 安装失败)")
                continue
            fi
        fi
        
        # 如果存在 install_pyg.sh，安装 PyTorch Geometric（必须在 PyTorch 之后）
        if [ -f "install_pyg.sh" ]; then
            echo -e "  ${BLUE}安装 PyTorch Geometric...${NC}"
            if ! bash install_pyg.sh; then
                echo -e "  ${RED}✗ $service PyG 安装失败${NC}"
                deactivate
                ((FAIL_COUNT++))
                FAIL_SERVICES+=("$service (PyG 安装失败)")
                continue
            fi
        fi
        
        # 如果存在 install_dgl.sh，安装 DGL（必须在 PyTorch 之后）
        if [ -f "install_dgl.sh" ]; then
            echo -e "  ${BLUE}安装 DGL...${NC}"
            if ! bash install_dgl.sh; then
                echo -e "  ${RED}✗ $service DGL 安装失败${NC}"
                deactivate
                ((FAIL_COUNT++))
                FAIL_SERVICES+=("$service (DGL 安装失败)")
                continue
            fi
        fi
        
        # 安装其他依赖
        if pip install -r requirements.txt; then
            echo -e "  ${GREEN}✓ $service 安装完成${NC}"
            ((SUCCESS_COUNT++))
            SUCCESS_SERVICES+=("$service")
        else
            echo -e "  ${RED}✗ $service pip install 失败${NC}"
            ((FAIL_COUNT++))
            FAIL_SERVICES+=("$service (pip install 失败)")
        fi
        deactivate
        echo ""
    else
        echo -e "${RED}✗ (缺少 requirements.txt)${NC}"
        ((FAIL_COUNT++))
        FAIL_SERVICES+=("$service (缺少 requirements.txt)")
    fi
done

echo ""
echo -e "${YELLOW}[3/3] 部署完成${NC}"
echo ""
echo -e "${GREEN}成功 ($SUCCESS_COUNT):${NC}"
if [ ${#SUCCESS_SERVICES[@]} -gt 0 ]; then
    for svc in "${SUCCESS_SERVICES[@]}"; do
        echo -e "  ${GREEN}✓${NC} $svc"
    done
else
    echo -e "  (无)"
fi
echo ""
echo -e "${RED}失败 ($FAIL_COUNT):${NC}"
if [ ${#FAIL_SERVICES[@]} -gt 0 ]; then
    for svc in "${FAIL_SERVICES[@]}"; do
        echo -e "  ${RED}✗${NC} $svc"
    done
else
    echo -e "  (无)"
fi
echo ""
echo -e "使用 ${GREEN}./scripts/start.sh${NC} 启动所有服务"
