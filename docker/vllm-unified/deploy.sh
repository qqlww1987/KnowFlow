#!/bin/bash
# vLLM 统一服务部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
ACTION="start"
ENV_FILE=".env"
COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="vllm-unified"
WAIT_TIMEOUT=300
HEALTH_CHECK_RETRIES=10
QUIET="false"
FORCE="false"
USE_SUDO="false"

# 显示帮助信息
show_help() {
    cat << EOF
vLLM 统一服务部署脚本

用法: $0 [动作] [选项]

动作:
    start           启动服务 (默认)
    stop            停止服务
    restart         重启服务
    status          查看服务状态
    logs            查看服务日志
    health          检查服务健康状态
    update          更新服务
    clean           清理服务和数据

选项:
    -e, --env-file FILE     环境变量文件 (默认: $ENV_FILE)
    -f, --compose-file FILE Docker Compose 文件 (默认: $COMPOSE_FILE)
    -s, --service NAME      服务名称 (默认: $SERVICE_NAME)
    -t, --timeout SECONDS   等待超时时间 (默认: $WAIT_TIMEOUT)
    -q, --quiet             静默模式
    --force                 强制执行操作
    --sudo                  使用 sudo 执行 Docker 命令
    -h, --help              显示此帮助信息

示例:
    $0 start                    # 启动服务
    $0 stop                     # 停止服务
    $0 restart --timeout 600    # 重启服务，等待10分钟
    $0 logs --follow            # 实时查看日志
    $0 clean --force            # 强制清理所有数据
    $0 start --sudo             # 使用 sudo 启动服务

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        start|stop|restart|status|logs|health|update|clean)
            ACTION="$1"
            shift
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -f|--compose-file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -t|--timeout)
            WAIT_TIMEOUT="$2"
            shift 2
            ;;
        -q|--quiet)
            QUIET="true"
            shift
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --sudo)
            USE_SUDO="true"
            shift
            ;;
        --follow)
            FOLLOW="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}错误: 未知选项 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Docker 命令函数
docker_cmd() {
    if [[ "$USE_SUDO" == "true" ]]; then
        sudo docker "$@"
    else
        docker "$@"
    fi
}

# 日志函数
log_info() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
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

# 检查依赖
check_dependencies() {
    log_info "检查部署依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在 PATH 中"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装或不在 PATH 中"
        exit 1
    fi
    
    if ! docker_cmd info &> /dev/null; then
        log_error "Docker 服务未运行或无权限访问"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 检查文件
check_files() {
    log_info "检查配置文件..."
    
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose 文件不存在: $COMPOSE_FILE"
        exit 1
    fi
    
    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f ".env.example" ]]; then
            log_warning "环境变量文件不存在，从示例文件创建: $ENV_FILE"
            cp .env.example "$ENV_FILE"
        else
            log_error "环境变量文件不存在: $ENV_FILE"
            exit 1
        fi
    fi
    
    log_success "配置文件检查通过"
}

# 获取 Docker Compose 命令
get_compose_cmd() {
    local compose_cmd
    if command -v docker-compose &> /dev/null; then
        compose_cmd="docker-compose"
    else
        compose_cmd="docker compose"
    fi
    
    if [[ "$USE_SUDO" == "true" ]]; then
        echo "sudo $compose_cmd"
    else
        echo "$compose_cmd"
    fi
}

# 等待服务就绪
wait_for_service() {
    local service_url="http://localhost:8000/health"
    local retries=0
    
    log_info "等待服务启动..."
    
    while [[ $retries -lt $HEALTH_CHECK_RETRIES ]]; do
        if curl -s "$service_url" &> /dev/null; then
            log_success "服务已就绪"
            return 0
        fi
        
        retries=$((retries + 1))
        log_info "等待服务启动... ($retries/$HEALTH_CHECK_RETRIES)"
        sleep 10
    done
    
    log_error "服务启动超时"
    return 1
}

# 启动服务
start_service() {
    log_info "启动 vLLM 统一服务..."
    
    local compose_cmd=$(get_compose_cmd)
    
    # 拉取最新镜像
    log_info "拉取最新镜像..."
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
    
    # 启动服务
    log_info "启动服务容器..."
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"
    
    # 等待服务就绪
    if wait_for_service; then
        log_success "vLLM 统一服务启动成功"
        show_service_info
    else
        log_error "服务启动失败"
        show_logs
        exit 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止 vLLM 统一服务..."
    
    local compose_cmd=$(get_compose_cmd)
    
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop "$SERVICE_NAME"
    
    log_success "vLLM 统一服务已停止"
}

# 重启服务
restart_service() {
    log_info "重启 vLLM 统一服务..."
    
    stop_service
    sleep 5
    start_service
}

# 查看服务状态
show_status() {
    log_info "查看服务状态..."
    
    local compose_cmd=$(get_compose_cmd)
    
    echo
    echo -e "${BLUE}=== 容器状态 ===${NC}"
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps "$SERVICE_NAME"
    
    echo
    echo -e "${BLUE}=== 资源使用情况 ===${NC}"
    docker_cmd stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" | grep vllm || echo "服务未运行"
    
    echo
    echo -e "${BLUE}=== 健康检查 ===${NC}"
    check_health
}

# 查看日志
show_logs() {
    log_info "查看服务日志..."
    
    local compose_cmd=$(get_compose_cmd)
    local log_args=()
    
    if [[ "$FOLLOW" == "true" ]]; then
        log_args+=("--follow")
    fi
    
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs "${log_args[@]}" "$SERVICE_NAME"
}

# 健康检查
check_health() {
    local health_url="http://localhost:8000/health"
    local models_url="http://localhost:8000/models"
    local system_url="http://localhost:8000/system/info"
    
    echo "检查服务健康状态..."
    
    # 检查主服务
    if curl -s "$health_url" | jq -e '.status == "healthy"' &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} 主服务: 健康"
    else
        echo -e "  ${RED}✗${NC} 主服务: 异常"
        return 1
    fi
    
    # 检查模型服务
    echo "  模型服务状态:"
    if curl -s "$models_url" | jq -r '.models[] | "    \(.name): \(.status)"' 2>/dev/null; then
        echo -e "    ${GREEN}✓${NC} 模型服务正常"
    else
        echo -e "    ${RED}✗${NC} 模型服务异常"
    fi
    
    # 检查系统信息
    echo "  系统信息:"
    if curl -s "$system_url" | jq -r '"    GPU: \(.gpu_count) 个, 内存: \(.memory_total)"' 2>/dev/null; then
        echo -e "    ${GREEN}✓${NC} 系统信息正常"
    else
        echo -e "    ${RED}✗${NC} 系统信息异常"
    fi
}

# 更新服务
update_service() {
    log_info "更新 vLLM 统一服务..."
    
    local compose_cmd=$(get_compose_cmd)
    
    # 拉取最新镜像
    log_info "拉取最新镜像..."
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull "$SERVICE_NAME"
    
    # 重启服务
    log_info "重启服务以应用更新..."
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"
    
    # 等待服务就绪
    if wait_for_service; then
        log_success "服务更新完成"
    else
        log_error "服务更新失败"
        exit 1
    fi
}

# 清理服务
clean_service() {
    if [[ "$FORCE" != "true" ]]; then
        echo -e "${YELLOW}警告: 此操作将删除所有服务数据，包括模型缓存和日志${NC}"
        read -p "确认继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "操作已取消"
            exit 0
        fi
    fi
    
    log_info "清理 vLLM 统一服务..."
    
    local compose_cmd=$(get_compose_cmd)
    
    # 停止并删除容器
    $compose_cmd --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down "$SERVICE_NAME"
    
    # 删除数据卷
    log_info "删除数据卷..."
    docker_cmd volume rm vllm_models vllm_cache vllm_logs 2>/dev/null || true
    
    # 删除未使用的镜像
    log_info "清理未使用的镜像..."
    docker_cmd image prune -f
    
    log_success "服务清理完成"
}

# 显示服务信息
show_service_info() {
    echo
    echo -e "${BLUE}=== vLLM 统一服务信息 ===${NC}"
    echo "  主服务地址: http://localhost:8000"
    echo "  Chat API: http://localhost:8000/v1/chat/completions"
    echo "  Embedding API: http://localhost:8000/v1/embeddings"
    echo "  Rerank API: http://localhost:8000/v1/rerank"
    echo "  健康检查: http://localhost:8000/health"
    echo "  模型列表: http://localhost:8000/models"
    echo "  系统信息: http://localhost:8000/system/info"
    echo
    echo -e "${BLUE}=== 管理命令 ===${NC}"
    echo "  查看状态: $0 status"
    echo "  查看日志: $0 logs --follow"
    echo "  重启服务: $0 restart"
    echo "  停止服务: $0 stop"
    echo
}

# 主函数
main() {
    echo -e "${BLUE}=== vLLM 统一服务部署脚本 ===${NC}"
    echo
    
    check_dependencies
    check_files
    
    case $ACTION in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        health)
            check_health
            ;;
        update)
            update_service
            ;;
        clean)
            clean_service
            ;;
        *)
            log_error "未知动作: $ACTION"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"