#!/bin/bash

# 获取脚本所在目录的父目录（项目根目录）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== RAGFlow 插件安装程序 ==="
echo "项目根目录: $PROJECT_ROOT"
echo

# 自动检测本机IP地址
get_local_ip() {
    # 尝试多种方法获取本机IP
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

# 创建.env文件的函数
create_env_file() {
    local env_file="$PROJECT_ROOT/.env"
    local local_ip="$1"
    
    echo "📝 创建 .env 配置文件..."
    
    cat > "$env_file" << EOF
# =======================================================
# KnowFlow 环境配置文件
# 由安装脚本自动生成于 $(date)
# =======================================================

# RAGFlow API 配置 (必须手动配置)
# 从 RAGFlow API 页面后台获取
RAGFLOW_API_KEY=请在此填入您的RAGFlow_API_KEY

# RAGFlow 服务地址 (已自动检测IP)
# 请将端口号替换为实际的RAGFlow服务端口
RAGFLOW_BASE_URL=http://$local_ip:请填入RAGFlow端口号

# =======================================================
# 以下配置由系统自动生成和管理
# =======================================================

# 检测到的宿主机IP
HOST_IP=$local_ip

# Elasticsearch 配置
ES_HOST=$local_ip
ES_PORT=1200

# 数据库配置
DB_HOST=$local_ip

# MinIO 对象存储配置
MINIO_HOST=$local_ip

# Redis 配置
REDIS_HOST=$local_ip
EOF

    echo "✅ .env 文件已创建: $env_file"
    return 0
}

# 检测本机IP
LOCAL_IP=$(get_local_ip)

echo "🔍 系统信息检测："
echo "  - 检测到的本机IP: $LOCAL_IP"
echo

# 检查.env文件是否存在
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 发现现有的 .env 文件"
    echo
    echo "选择操作："
    echo "1) 保留现有配置，仅运行环境生成脚本"
    echo "2) 重新创建 .env 文件（将覆盖现有配置）"
    echo "3) 跳过，手动配置"
    echo
    read -p "请选择 (1/2/3): " choice
    
    case $choice in
        2)
            echo "🔄 重新创建 .env 文件..."
            create_env_file "$LOCAL_IP"
            ;;
        3)
            echo "⏭️  跳过自动配置"
            ;;
        *)
            echo "📝 保留现有 .env 配置"
            ;;
    esac
else
    echo "📝 未发现 .env 文件，自动创建..."
    create_env_file "$LOCAL_IP"
fi

echo

# 生成环境配置（如果generate_env.sh存在且.env文件存在）
if [ -f "$PROJECT_ROOT/scripts/generate_env.sh" ] && [ -f "$ENV_FILE" ]; then
    echo "🔧 运行环境配置生成器..."
    chmod +x "$PROJECT_ROOT/scripts/generate_env.sh"
    "$PROJECT_ROOT/scripts/generate_env.sh"
    echo
fi

# 提供最终说明
echo "📋 下一步操作："
echo
if [ -f "$ENV_FILE" ]; then
    echo "✅ .env 文件已准备就绪"
    echo
    echo "🔧 需要手动配置的项目："
    echo "  1. RAGFLOW_API_KEY - 从 RAGFlow 后台获取"
    echo "  2. RAGFLOW_BASE_URL - 确认端口号是否正确"
    echo
    echo "💡 编辑配置文件："
    echo "  nano $ENV_FILE"
    echo
    echo "🚀 配置完成后启动服务："
    echo "  docker compose up -d"
    echo
    echo "🌐 访问地址："
    echo "  http://$LOCAL_IP:8888"
else
    echo "⚠️  请手动创建 .env 文件，参考以下模板："
    echo
    echo "RAGFLOW_API_KEY=你的API密钥"
    echo "RAGFLOW_BASE_URL=http://$LOCAL_IP:RAGFlow端口号"
fi

echo
echo "=== 安装完成！==="
