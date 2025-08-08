#!/bin/bash
# vLLM 统一服务构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
IMAGE_NAME="zxwei/vllm-unified"
IMAGE_TAG="latest"
DOWNLOAD_MODELS="false"
NO_CACHE="false"
QUIET="false"
VERIFY="true"
PUSH="false"
REGISTRY=""
USE_SUDO="false"

# 显示帮助信息
show_help() {
    cat << EOF
vLLM 统一服务构建脚本

用法: $0 [选项]

选项:
    -n, --name NAME         镜像名称 (默认: $IMAGE_NAME)
    -t, --tag TAG           镜像标签 (默认: $IMAGE_TAG)
    -s, --skip-models       跳过模型下载
    -c, --no-cache          不使用构建缓存
    -q, --quiet             静默模式
    -v, --no-verify         跳过构建验证
    -p, --push              构建后推送到仓库
    -r, --registry URL      Docker 仓库地址
    --sudo                  使用 sudo 执行 docker 命令
    -h, --help              显示此帮助信息

示例:
    $0                                    # 默认构建
    $0 --tag v1.0.0                     # 指定标签
    $0 --skip-models --no-cache         # 跳过模型下载，不使用缓存
    $0 --sudo                           # 使用 sudo 执行 docker 命令
    $0 --push --registry registry.com   # 构建并推送到仓库

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -s|--skip-models)
            DOWNLOAD_MODELS="false"
            shift
            ;;
        -c|--no-cache)
            NO_CACHE="true"
            shift
            ;;
        -q|--quiet)
            QUIET="true"
            shift
            ;;
        -v|--no-verify)
            VERIFY="false"
            shift
            ;;
        -p|--push)
            PUSH="true"
            shift
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        --sudo)
            USE_SUDO="true"
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

# Docker 命令包装函数
docker_cmd() {
    if [[ "$USE_SUDO" == "true" ]]; then
        sudo docker "$@"
    else
        docker "$@"
    fi
}

# 检查依赖
check_dependencies() {
    log_info "检查构建依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不在 PATH 中"
        exit 1
    fi
    
    if ! docker_cmd info &> /dev/null; then
        log_error "Docker 服务未运行或无权限访问"
        if [[ "$USE_SUDO" != "true" ]]; then
            log_info "提示: 如果需要 sudo 权限，请使用 --sudo 参数"
        fi
        exit 1
    fi
    
    # 检查 NVIDIA Docker 支持
    if ! docker_cmd run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        log_warning "NVIDIA Docker 支持不可用，GPU 功能可能无法正常工作"
    fi
    
    log_success "依赖检查通过"
    
    # 检查网络连接（预编译 flash-attn 需要下载）
    if ! curl -s --connect-timeout 5 https://github.com &> /dev/null; then
        log_warning "网络连接不可用，flash-attn 预编译包可能下载失败"
        log_info "如果构建失败，请检查网络连接或使用离线安装包"
    fi
}

# 检查磁盘空间
check_disk_space() {
    log_info "检查磁盘空间..."
    
    # 获取当前目录可用空间（GB）
    available_space=$(df . | awk 'NR==2 {print int($4/1024/1024)}')
    required_space=20  # 至少需要 50GB
    
    if [[ $available_space -lt $required_space ]]; then
        log_error "磁盘空间不足。需要至少 ${required_space}GB，当前可用 ${available_space}GB"
        exit 1
    fi
    
    log_success "磁盘空间充足 (${available_space}GB 可用)"
}

# 构建镜像
build_image() {
    log_info "开始构建 vLLM 统一服务镜像..."
    
    # 构建参数
    local build_args=()
    build_args+=("--build-arg" "DOWNLOAD_MODELS=$DOWNLOAD_MODELS")
    
    if [[ "$NO_CACHE" == "true" ]]; then
        build_args+=("--no-cache")
    fi
    
    if [[ "$QUIET" == "true" ]]; then
        build_args+=("--quiet")
    fi
    
    # 完整镜像名
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    fi
    
    # 执行构建
    log_info "构建镜像: $full_image_name"
    log_info "模型下载: $DOWNLOAD_MODELS"
    log_info "使用缓存: $([ "$NO_CACHE" == "true" ] && echo "否" || echo "是")"
    
    if docker_cmd build "${build_args[@]}" -t "$full_image_name" .; then
        log_success "镜像构建完成: $full_image_name"
    else
        log_error "镜像构建失败"
        exit 1
    fi
}

# 验证镜像
verify_image() {
    if [[ "$VERIFY" != "true" ]]; then
        return 0
    fi
    
    log_info "验证镜像..."
    
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    fi
    
    # 检查镜像是否存在
    if ! docker_cmd image inspect "$full_image_name" &> /dev/null; then
        log_error "镜像不存在: $full_image_name"
        exit 1
    fi
    
    # 检查镜像大小
    local image_size=$(docker_cmd image inspect "$full_image_name" --format='{{.Size}}' | awk '{print int($1/1024/1024/1024)}')
    log_info "镜像大小: ${image_size}GB"
    
    # 测试容器启动
    log_info "测试容器启动..."
    if docker_cmd run --rm "$full_image_name" python3 -c "import vllm; print('vLLM 导入成功')"; then
        log_success "镜像验证通过"
    else
        log_error "镜像验证失败"
        exit 1
    fi
}

# 推送镜像
push_image() {
    if [[ "$PUSH" != "true" ]]; then
        return 0
    fi
    
    if [[ -z "$REGISTRY" ]]; then
        log_error "推送镜像需要指定仓库地址 (--registry)"
        exit 1
    fi
    
    local full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    
    log_info "推送镜像到仓库: $full_image_name"
    
    if docker_cmd push "$full_image_name"; then
        log_success "镜像推送完成"
    else
        log_error "镜像推送失败"
        exit 1
    fi
}

# 显示构建信息
show_build_info() {
    log_info "构建配置:"
    echo "  镜像名称: $IMAGE_NAME"
    echo "  镜像标签: $IMAGE_TAG"
    echo "  下载模型: $DOWNLOAD_MODELS"
    echo "  使用缓存: $([ "$NO_CACHE" == "true" ] && echo "否" || echo "是")"
    echo "  使用 sudo: $([ "$USE_SUDO" == "true" ] && echo "是" || echo "否")"
    echo "  验证镜像: $VERIFY"
    echo "  推送镜像: $PUSH"
    if [[ -n "$REGISTRY" ]]; then
        echo "  仓库地址: $REGISTRY"
    fi
    echo
}

# 清理函数
cleanup() {
    log_info "清理临时文件..."
    # 这里可以添加清理逻辑
}

# 信号处理
trap cleanup EXIT
trap 'log_error "构建被中断"; exit 1' INT TERM

# 主函数
main() {
    echo -e "${BLUE}=== vLLM 统一服务构建脚本 ===${NC}"
    echo
    
    show_build_info
    check_dependencies
    check_disk_space
    build_image
    verify_image
    push_image
    
    echo
    log_success "构建完成！"
    
    # 显示使用说明
    local full_image_name="$IMAGE_NAME:$IMAGE_TAG"
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    fi
    
    echo
    echo -e "${BLUE}使用说明:${NC}"
    echo "  启动服务: docker-compose up -d"
    echo "  查看日志: docker-compose logs -f vllm-unified"
    echo "  健康检查: curl http://localhost:8000/health"
    echo "  停止服务: docker-compose down"
    echo
}

# 执行主函数
main "$@"