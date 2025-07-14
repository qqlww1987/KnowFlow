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

echo -e "${BLUE}🚀 KnowFlow 安装脚本${NC}"
echo "=================================="

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
    
    # 检测本机IP
    LOCAL_IP=$(get_local_ip)
    echo -e "${BLUE}🔍 检测到的本机IP: $LOCAL_IP${NC}"
    
    # 检查.env文件是否存在，如果存在则备份
    if [ -f "$PROJECT_ROOT/.env" ]; then
        echo -e "${YELLOW}📋 备份现有.env文件...${NC}"
        if ! cp "$PROJECT_ROOT/.env" "$PROJECT_ROOT/.env.backup.$(date +%Y%m%d_%H%M%S)"; then
            echo -e "${RED}❌ 备份.env文件失败${NC}"
            return 1
        fi
    fi
    
    echo "生成.env文件..."
    if ! cat > "$PROJECT_ROOT/.env" << EOF
# =======================================================
# KnowFlow 环境配置文件
# 由安装脚本自动生成于 $(date)
# =======================================================

# RAGFlow 服务地址 (已自动检测IP)
# 请将端口号替换为实际的RAGFlow服务端口
RAGFLOW_BASE_URL=http://$LOCAL_IP:请填入RAGFlow端口号

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
MYSQL_PORT=3306

# MinIO 对象存储配置
MINIO_HOST=$LOCAL_IP
MINIO_PORT=9000

# Redis 配置
REDIS_HOST=$LOCAL_IP
REDIS_PORT=6379
EOF
    then
        echo -e "${RED}❌ 生成.env文件失败${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ .env文件生成成功${NC}"
    echo -e "${YELLOW}⚠️  请根据你的实际配置修改.env文件${NC}"
    
    echo -e "${GREEN}✅ 阶段 1 完成: 环境变量自动生成${NC}"
    return 0
}

# 阶段2: 自动挂载文件到 RAGFlow
run_auto_mount() {
    # 检查auto_mount.py是否存在
    if [ ! -f "$PROJECT_ROOT/scripts/auto_mount.py" ]; then
        echo -e "${RED}❌ 未找到auto_mount.py脚本${NC}"
        return 1
    fi
    
    # 使用虚拟环境中的Python
    VENV_PYTHON="$VENV_DIR/bin/python"
    
    # 检查虚拟环境是否可用
    if [ ! -f "$VENV_PYTHON" ]; then
        echo -e "${RED}❌ 虚拟环境不可用，请先运行虚拟环境设置${NC}"
        return 1
    fi
    
    echo "运行自动挂载脚本..."
    if ! "$VENV_PYTHON" "$PROJECT_ROOT/scripts/auto_mount.py"; then
        echo -e "${RED}❌ 自动挂载失败${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ 自动挂载完成${NC}"
    echo -e "${GREEN}✅ 阶段 2 完成: 自动挂载文件到 RAGFlow${NC}"
    return 0
}

# 阶段3: 重启 RAGFlow 服务
restart_ragflow_services() {
    echo ""
    echo -e "${BLUE}📋 阶段 3: 重启 RAGFlow 服务${NC}"
    echo "=================================="
    echo -e "${GREEN}✅ 阶段 3 完成: 重启 RAGFlow 服务${NC}"
    return 0
}

# 显示配置说明
show_config_instructions() {
    echo -e "${BLUE}📖 配置说明${NC}"
    echo "=================================="
    echo "请确保以下服务已正确配置："
    echo ""
    echo "  1. RAGFLOW_BASE_URL - 确认端口号是否正确"
    echo ""
    echo "如果需要修改配置，请编辑 .env 文件："
    echo "  nano $PROJECT_ROOT/.env"
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
        echo -e "${RED}❌ 阶段1失败：环境变量自动生成失败，安装终止${NC}"
        exit 1
    fi
    
    # 阶段2: 自动挂载文件到 RAGFlow
    echo ""
    echo -e "${BLUE}📋 阶段 2: 自动挂载文件到 RAGFlow${NC}"
    echo "=================================="
    if ! run_auto_mount; then
        echo -e "${RED}❌ 阶段2失败：自动挂载文件到 RAGFlow失败，安装终止${NC}"
        exit 1
    fi
    
    # 阶段3: 重启 RAGFlow 服务
    if ! restart_ragflow_services; then
        echo -e "${RED}❌ 阶段3失败：重启 RAGFlow 服务失败，安装终止${NC}"
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
