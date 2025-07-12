#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}🚀 KnowFlow 安装脚本${NC}"
echo "=================================="

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

# 检查并创建虚拟环境
setup_virtual_environment() {
    echo -e "${YELLOW}📦 设置虚拟环境...${NC}"
    
    if [ ! -d "$PROJECT_ROOT/server/venv" ]; then
        echo "创建虚拟环境..."
        cd "$PROJECT_ROOT/server"
        python3 -m venv venv
        echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
    else
        echo -e "${GREEN}✅ 虚拟环境已存在${NC}"
    fi
}

# 安装Python依赖
install_python_dependencies() {
    echo -e "${YELLOW}📦 安装Python依赖...${NC}"
    
    cd "$PROJECT_ROOT/server"
    source venv/bin/activate
    
    echo "升级pip..."
    pip install --upgrade pip
    
    echo "安装依赖包..."
    pip install -r requirements.txt
    
    echo -e "${GREEN}✅ Python依赖安装完成${NC}"
}

# 检查并创建.env文件
setup_env_file() {
    echo -e "${YELLOW}⚙️  检查环境配置...${NC}"
    
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        echo "创建.env文件..."
        cat > "$PROJECT_ROOT/.env" << EOF
# RAGFlow 配置
RAGFLOW_BASE_URL=http://localhost:9380

# 数据库配置
MYSQL_PASSWORD=infini_rag_flow
MINIO_USER=rag_flow
MINIO_PASSWORD=infini_rag_flow
ELASTIC_PASSWORD=infini_rag_flow

# 开发模式配置
DEV_MODE=true
SKIP_MINERU_PROCESSING=true
EOF
        echo -e "${GREEN}✅ .env文件创建成功${NC}"
        echo -e "${YELLOW}⚠️  请根据你的实际配置修改.env文件${NC}"
    else
        echo -e "${GREEN}✅ .env文件已存在${NC}"
    fi
}

# 检查Docker服务
check_docker_services() {
    echo -e "${YELLOW}🐳 检查Docker服务...${NC}"
    
    # 检查Docker是否运行
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker未运行，请启动Docker${NC}"
        return 1
    fi
    
    # 检查必要的容器
    local containers=("ragflow-ragflow-1" "ragflow-mysql-1" "ragflow-minio-1" "ragflow-elasticsearch-1")
    local missing_containers=()
    
    for container in "${containers[@]}"; do
        if ! docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            missing_containers+=("$container")
        fi
    done
    
    if [ ${#missing_containers[@]} -eq 0 ]; then
        echo -e "${GREEN}✅ 所有必要的Docker容器都在运行${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  以下容器未运行:${NC}"
        for container in "${missing_containers[@]}"; do
            echo "  - $container"
        done
        echo -e "${YELLOW}请确保RAGFlow服务已启动${NC}"
        return 1
    fi
}

# 显示配置说明
show_config_instructions() {
    echo -e "${BLUE}📖 配置说明${NC}"
    echo "=================================="
    echo "请确保以下服务已正确配置："
    echo ""
    echo "  1. RAGFLOW_BASE_URL - RAGFlow服务地址"
    echo "  2. 数据库连接配置 - MySQL、MinIO、Elasticsearch"
    echo ""
    echo "如果需要修改配置，请编辑 .env 文件："
    echo "  nano .env"
    echo ""
}

# 显示使用说明
show_usage_instructions() {
    echo -e "${BLUE}🚀 启动说明${NC}"
    echo "=================================="
    echo "安装完成后，你可以："
    echo ""
    echo "1. 启动KnowFlow服务："
    echo "   cd server && source venv/bin/activate && python app.py"
    echo ""
    echo "2. 访问Web界面："
    echo "   http://localhost:5000"
    echo ""
    echo "3. 查看API文档："
    echo "   http://localhost:5000/docs"
    echo ""
}

# 主安装流程
main() {
    echo -e "${BLUE}开始安装KnowFlow...${NC}"
    echo ""
    
    check_python_version
    setup_virtual_environment
    install_python_dependencies
    setup_env_file
    
    echo ""
    echo -e "${GREEN}🎉 KnowFlow安装完成！${NC}"
    echo ""
    
    show_config_instructions
    show_usage_instructions
    
    echo -e "${YELLOW}⚠️  注意：请确保RAGFlow服务已启动并可以访问${NC}"
}

# 运行主函数
main
