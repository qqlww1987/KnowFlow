#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

# 默认使用容器名配置
USE_DOCKER_CONTAINERS=true

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-ip|--local)
            USE_DOCKER_CONTAINERS=false
            shift
            ;;
        --use-containers|--docker)
            USE_DOCKER_CONTAINERS=true
            shift
            ;;
        -h|--help)
            echo "KnowFlow 安装脚本"
            echo ""
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --use-containers, --docker    使用容器名配置 (默认)"
            echo "  --use-ip, --local            使用本地IP地址配置"
            echo "  -h, --help                   显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                           # 使用容器名配置"
            echo "  $0 --use-containers          # 明确指定使用容器名配置"
            echo "  $0 --use-ip                  # 使用本地IP地址配置"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "请使用 -h 或 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🚀 KnowFlow 安装脚本${NC}"
echo "=================================="

# 显示当前配置模式
if [ "$USE_DOCKER_CONTAINERS" = true ]; then
    echo -e "${GREEN}📋 配置模式: Docker Compose (容器名)${NC}"
else
    echo -e "${YELLOW}📋 配置模式: 本地环境 (IP地址)${NC}"
fi
echo ""

# 自动检测本机IP地址
get_local_ip() {
    local ip=""
    
    # 方法1: 使用 hostname -I (Linux)
    if command -v hostname >/dev/null 2>&1; then
        ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    
    # 方法2: 使用 ip route (Linux)
    if [ -z "$ip" ] && command -v ip >/dev/null 2>&1; then
        ip=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
    fi
    
    # 方法3: 使用 ifconfig (macOS/Linux)
    if [ -z "$ip" ] && command -v ifconfig >/dev/null 2>&1; then
        ip=$(ifconfig | grep -E "inet.*broadcast" | awk '{print $2}' | head -1)
    fi
    
    # 方法4: 使用 route (macOS)
    if [ -z "$ip" ] && command -v route >/dev/null 2>&1; then
        ip=$(route get default 2>/dev/null | grep interface | awk '{print $2}' | xargs -I {} ifconfig {} | grep "inet " | awk '{print $2}' | head -1)
    fi
    
    # 默认回退
    if [ -z "$ip" ]; then
        ip="your_server_ip"
    fi
    
    echo "$ip"
}

# 检查Python版本
check_python_version() {
    echo -e "${YELLOW}📋 检查Python版本...${NC}"
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}✅ Python版本: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}❌ 未找到Python3，请先安装Python 3.8+${NC}"
        exit 1
    fi
}

# 创建和激活虚拟环境
setup_virtual_environment() {
    echo -e "${YELLOW}🐍 设置Python虚拟环境...${NC}"
    
    # 检查虚拟环境是否已存在
    if [ -d "$VENV_DIR" ]; then
        echo -e "${GREEN}✅ 虚拟环境已存在${NC}"
    else
        # 创建虚拟环境
        echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
        if python3 -m venv "$VENV_DIR"; then
            echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
        else
            echo -e "${RED}❌ 创建虚拟环境失败${NC}"
            return 1
        fi
    fi
    
    # 获取虚拟环境的Python和pip路径
    VENV_PYTHON="$VENV_DIR/bin/python"
    VENV_PIP="$VENV_DIR/bin/pip"
    
    # 检查虚拟环境是否可用
    if [ ! -f "$VENV_PYTHON" ]; then
        echo -e "${RED}❌ 虚拟环境Python不可用${NC}"
        return 1
    fi
    
    # 检查PyYAML是否已安装
    if "$VENV_PYTHON" -c "import yaml" 2>/dev/null; then
        echo -e "${GREEN}✅ PyYAML已安装${NC}"
    else
        # 安装依赖
        echo -e "${YELLOW}📦 安装依赖...${NC}"
        
        # 升级pip
        echo -e "${YELLOW}⬆️  升级pip...${NC}"
        if "$VENV_PIP" install --upgrade pip; then
            echo -e "${GREEN}✅ pip升级成功${NC}"
        else
            echo -e "${YELLOW}⚠️  pip升级失败，继续安装依赖${NC}"
        fi
        
        # 安装PyYAML
        echo -e "${YELLOW}📦 安装PyYAML...${NC}"
        if "$VENV_PIP" install PyYAML; then
            echo -e "${GREEN}✅ PyYAML安装成功${NC}"
        else
            echo -e "${RED}❌ PyYAML安装失败${NC}"
            return 1
        fi
    fi
    
    echo -e "${GREEN}✅ 虚拟环境设置完成${NC}"
    return 0
}

# 阶段1: 环境变量自动生成
setup_env_file() {
    echo ""
    echo -e "${BLUE}📋 阶段 1: 环境变量自动生成${NC}"
    echo "=================================="
    
    # 根据参数选择配置模式
    if [ "$USE_DOCKER_CONTAINERS" = true ]; then
        echo -e "${BLUE}🐳 使用容器名配置模式${NC}"
    else
        echo -e "${BLUE}🖥️  使用本地IP地址配置模式${NC}"
        # 检测本机IP
        LOCAL_IP=$(get_local_ip)
        echo -e "${BLUE}🔍 检测到的本机IP: $LOCAL_IP${NC}"
    fi
    
    # 检查.env文件是否存在，如果存在则备份
    if [ -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${YELLOW}📋 备份现有.env文件...${NC}"
        if ! cp "$PROJECT_ROOT/.env" "$PROJECT_ROOT/.env.backup.$(date +%Y%m%d_%H%M%S)"; then
            echo -e "${RED}❌ 备份.env文件失败${NC}"
            return 1
        fi
    fi
    
    echo "生成.env文件..."
    
    if [ "$USE_DOCKER_CONTAINERS" = true ]; then
        # Docker Compose 环境配置
        if ! cat > "$PROJECT_ROOT/.env" << EOF
# =======================================================
# KnowFlow 环境配置文件 (Docker Compose 环境)
# 由安装脚本自动生成于 $(date)
# =======================================================

# RAGFlow 服务地址 (使用容器名)
RAGFLOW_BASE_URL=http://ragflow-server:9380

# =======================================================
# 以下配置使用Docker容器名，适用于Docker Compose环境
# =======================================================

# 数据库配置
DB_HOST=\${DB_HOST:-mysql}
MYSQL_PORT=3306

# MinIO 对象存储配置
MINIO_HOST=\${MINIO_HOST:-minio}
MINIO_PORT=9000

# Elasticsearch 配置
ES_HOST=\${ES_HOST:-es01}
ES_PORT=9200

# Redis 配置
REDIS_HOST=\${REDIS_HOST:-redis}
REDIS_PORT=6379

# KnowFlow API 配置
KNOWFLOW_API_URL=http://knowflow-backend:5000
EOF
        then
            echo -e "${RED}❌ 生成.env文件失败${NC}"
            return 1
        fi
        
        echo -e "${GREEN}✅ .env文件生成成功 (Docker Compose配置)${NC}"
        echo -e "${BLUE}ℹ️  使用容器名进行服务间通信${NC}"
    else
        # 本地环境配置
        if ! cat > "$PROJECT_ROOT/.env" << EOF
# =======================================================
# KnowFlow 环境配置文件 (本地环境)
# 由安装脚本自动生成于 $(date)
# =======================================================

# RAGFlow 服务地址 (已自动检测IP)
RAGFLOW_BASE_URL=http://$LOCAL_IP:9380

# =======================================================
# 以下配置由系统自动生成和管理
# =======================================================

# 检测到的宿主机IP
HOST_IP=$LOCAL_IP

# Elasticsearch 配置
ES_HOST=$LOCAL_IP
ES_PORT=1200

# 数据库配置
DB_HOST=$LOCAL_IP
MYSQL_PORT=5455

# MinIO 对象存储配置
MINIO_HOST=$LOCAL_IP
MINIO_PORT=9000

# Redis 配置
REDIS_HOST=$LOCAL_IP
REDIS_PORT=6379

# KnowFlow API 配置
KNOWFLOW_API_URL=http://localhost:5000
EOF
        then
            echo -e "${RED}❌ 生成.env文件失败${NC}"
            return 1
        fi
        
        echo -e "${GREEN}✅ .env文件生成成功 (本地IP配置)${NC}"
        echo -e "${YELLOW}⚠️  请根据你的实际配置修改.env文件${NC}"
    fi
    
    echo -e "${GREEN}✅ 阶段 1 完成: 环境变量自动生成${NC}"
}



# 显示配置说明
show_config_instructions() {
    echo -e "${BLUE}📖 配置说明${NC}"
    echo "=================================="
    
    if [ "$USE_DOCKER_CONTAINERS" = true ]; then
        echo "Docker Compose 环境配置已自动完成："
        echo ""
        echo "  ✅ 使用容器名进行服务间通信"
        echo "  ✅ RAGFLOW_BASE_URL: http://ragflow-server:9380"
        echo "  ✅ 所有服务使用容器名访问"
        echo ""
        echo "如果需要修改配置，请编辑 .env 文件："
        echo "  nano $PROJECT_ROOT/.env"
    else
        echo "本地环境配置说明："
        echo ""
        echo "  1. RAGFLOW_BASE_URL - 确认端口号是否正确"
        echo "  2. 确保所有服务的IP地址和端口配置正确"
        echo ""
        echo "如果需要修改配置，请编辑 .env 文件："
        echo "  nano $PROJECT_ROOT/.env"
    fi
    echo ""
}

# 显示使用说明
show_usage_instructions() {
    echo -e "${BLUE}🚀 启动说明${NC}"
    echo "=================================="
    echo "安装完成后，你可以："
    echo ""
    echo "1. 启动KnowFlow服务："
    echo "   docker compose up -d"
    echo ""
}

# 主安装流程
main() {
    echo -e "${BLUE}开始安装KnowFlow...${NC}"
    echo ""
    
    check_python_version
    
    # 创建和激活虚拟环境
    if ! setup_virtual_environment; then
        echo -e "${RED}❌ 虚拟环境设置失败，安装终止${NC}"
        exit 1
    fi
    
    # 阶段1: 环境变量自动生成
    if ! setup_env_file; then
        echo -e "${RED}❌ 环境变量自动生成失败，安装终止${NC}"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}🎉 KnowFlow安装完成！${NC}"
    echo ""
    
    show_config_instructions
    show_usage_instructions
    
    echo -e "${YELLOW}⚠️  注意：请确保RAGFlow服务已启动并可以访问${NC}"
}

# 运行主函数
main
