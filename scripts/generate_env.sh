#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查.env文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    log_error ".env 文件不存在，请先创建 .env 文件并添加 RAGFLOW_BASE_URL"
    exit 1
fi

log_info "开始生成环境配置..."

# 读取现有的.env文件
source "$ENV_FILE"

# 检查必要的环境变量
if [ -z "$RAGFLOW_BASE_URL" ]; then
    log_error "RAGFLOW_BASE_URL 未设置，请在 .env 文件中添加"
    exit 1
fi

log_success "环境配置生成完成！"
log_info "请确保以下服务已启动："
echo "  - RAGFlow: $RAGFLOW_BASE_URL"
echo "  - MySQL: localhost:5455"
echo "  - MinIO: localhost:9000"
echo "  - Elasticsearch: localhost:9200"