#!/bin/bash

# MinerU SGLang 全镜像构建脚本
# 该脚本构建包含所有模型文件的完全离线部署镜像
# 支持智能启动、环境变量配置和多种部署模式

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 错误处理
trap 'log_error "构建过程中发生错误，退出码: $?"' ERR

# 解析命令行参数
CLEAN_BUILD=false
NO_CACHE=false
QUIET=false
VERIFY=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        --no-verify)
            VERIFY=false
            shift
            ;;
        --model-source)
            MODEL_SOURCE="$2"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --clean          构建前清理相关镜像和容器"
            echo "  --no-cache       不使用 Docker 缓存"
            echo "  --quiet          静默模式"
            echo "  --no-verify      跳过构建验证"
            echo "  --model-source   指定模型源 (modelscope|huggingface)"
            echo "  --tag           指定镜像标签"
            echo "  --help, -h       显示此帮助信息"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 配置参数
IMAGE_NAME="mineru-sglang"
IMAGE_TAG="${IMAGE_TAG:-v2.1.10-offline}"
MINERU_VERSION="2.1.10"
MODEL_SOURCE="${MODEL_SOURCE:-huggingface}"  # 可选: modelscope 或 huggingface
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# 验证模型源参数
if [[ "$MODEL_SOURCE" != "modelscope" && "$MODEL_SOURCE" != "huggingface" ]]; then
    log_error "无效的模型源: $MODEL_SOURCE. 必须是 'modelscope' 或 'huggingface'"
    exit 1
fi

# 清理选项
if [ "$CLEAN_BUILD" = true ]; then
    log_info "清理现有镜像和容器..."
    docker rmi ${IMAGE_NAME}:${IMAGE_TAG} 2>/dev/null || true
    docker system prune -f --filter label=maintainer="KnowFlow Team" 2>/dev/null || true
fi

log_info "开始构建 MinerU SGLang 全镜像..."
log_info "镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
log_info "MinerU 版本: ${MINERU_VERSION}"
log_info "模型源: ${MODEL_SOURCE}"
log_info "构建时间: ${BUILD_DATE}"
log_info "Git 提交: ${GIT_COMMIT}"
log_info "清理构建: ${CLEAN_BUILD}"
log_info "使用缓存: $([[ "$NO_CACHE" == "true" ]] && echo "否" || echo "是")"
echo ""

# 构建 Docker 命令
BUILD_CMD="sudo docker build"
BUILD_CMD="$BUILD_CMD --build-arg MINERU_VERSION=${MINERU_VERSION}"
BUILD_CMD="$BUILD_CMD --build-arg MODEL_SOURCE=${MODEL_SOURCE}"
BUILD_CMD="$BUILD_CMD --label build.date=${BUILD_DATE}"
BUILD_CMD="$BUILD_CMD --label build.git-commit=${GIT_COMMIT}"
BUILD_CMD="$BUILD_CMD --label build.version=${IMAGE_TAG}"
BUILD_CMD="$BUILD_CMD -f Dockerfile.sglang"
BUILD_CMD="$BUILD_CMD -t ${IMAGE_NAME}:${IMAGE_TAG}"

if [ "$NO_CACHE" = true ]; then
    BUILD_CMD="$BUILD_CMD --no-cache"
fi

if [ "$QUIET" = true ]; then
    BUILD_CMD="$BUILD_CMD --quiet"
fi

BUILD_CMD="$BUILD_CMD ."

log_info "执行构建命令: $BUILD_CMD"
echo ""

# 执行构建
if eval $BUILD_CMD; then
    log_success "镜像构建成功！"
else
    log_error "镜像构建失败！"
    exit 1
fi

echo ""
log_success "构建完成！"
log_info "镜像: ${IMAGE_NAME}:${IMAGE_TAG}"

# 获取镜像信息
IMAGE_SIZE=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format '{{.Size}}' | head -n 1)
IMAGE_ID=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format '{{.ID}}' | head -n 1)
CREATED=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format '{{.CreatedSince}}' | head -n 1)

log_info "镜像 ID: ${IMAGE_ID}"
log_info "镜像大小: ${IMAGE_SIZE}"
log_info "创建时间: ${CREATED}"
echo ""
# 构建验证
if [ "$VERIFY" = true ]; then
    log_info "验证镜像构建..."
    
    # 检查镜像是否存在
    if ! docker images ${IMAGE_NAME}:${IMAGE_TAG} --format '{{.Repository}}:{{.Tag}}' | grep -q "${IMAGE_NAME}:${IMAGE_TAG}"; then
        log_error "镜像验证失败：镜像不存在"
        exit 1
    fi
    
    # 检查镜像标签
    LABELS=$(docker inspect ${IMAGE_NAME}:${IMAGE_TAG} --format '{{json .Config.Labels}}' 2>/dev/null || echo '{}')
    if echo "$LABELS" | grep -q "maintainer.*KnowFlow Team"; then
        log_success "镜像标签验证通过"
    else
        log_warning "镜像标签验证失败，但继续执行"
    fi
    
    # 快速启动测试（可选）
    log_info "执行快速启动测试..."
    TEST_CONTAINER="mineru-test-$(date +%s)"
    if docker run --name $TEST_CONTAINER --rm -d ${IMAGE_NAME}:${IMAGE_TAG} /bin/bash -c "sleep 5" >/dev/null 2>&1; then
        log_success "快速启动测试通过"
        docker stop $TEST_CONTAINER >/dev/null 2>&1 || true
    else
        log_warning "快速启动测试失败，但镜像可能仍然可用"
    fi
    
    echo ""
fi

echo "基础使用方法:"
echo "# 默认启动（智能模式，支持环境变量）"
echo "docker run -d -p 8888:8888 -p 30000:30000 ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "# 使用配置文件启动（推荐）"
echo "docker run -d -p 8888:8888 -p 30000:30000 \\"
echo "  -v \$(pwd)/.env:/app/.env \\"
echo "  -v \$(pwd)/mineru.json:/root/mineru.json \\"
echo "  ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "# 高性能配置启动（多GPU）"
echo "docker run -d -p 8888:8888 -p 30000:30000 \\"
echo "  -e SGLANG_TP_SIZE=2 \\"
echo "  -e SGLANG_MEM_FRACTION_STATIC=0.8 \\"
echo "  --gpus all \\"
echo "  ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "核心特性:"
echo "- 基于 SGLang v0.4.7-cu124"
echo "- MinerU ${MINERU_VERSION} 完整功能"
echo "- 所有模型文件已预下载（完全离线部署）"
echo "- 智能启动脚本（start_with_env.sh）"
echo "- 支持环境变量和配置文件"
echo "- 优化的 Docker 缓存策略"
echo "- 生产就绪的健康检查"
echo ""
echo "功能支持:"
echo "- 支持 Pipeline 和 VLM 模式"
echo "- 兼容 MinerU 官方 API 接口"
echo "- 支持多文件批量处理"
echo "- 支持多种后端: pipeline, vlm-transformers, vlm-sglang-engine, vlm-sglang-client"
echo "- 支持多 GPU 并行处理（TP/DP）"
echo "- 支持 torch.compile 优化"
echo ""
echo "服务端口:"
echo "- Web API 服务端口: 8888（可通过 API_PORT 环境变量修改）"
echo "- SGLang 服务端口: 30000（可通过 SGLANG_PORT 环境变量修改）"
echo ""
echo "快速访问:"
echo "- API 文档: http://localhost:8888/docs"
echo "- 健康检查: http://localhost:8888/health"
echo "- 配置说明: 查看 README_MINERU_SGLANG.md"
echo ""
echo "管理命令:"
echo "# 查看镜像详细信息"
echo "docker inspect ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "# 查看镜像层级"
echo "docker history ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "# 导出镜像"
echo "docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip > ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"
echo ""
echo "# 推送到仓库（需要先登录和标记）"
echo "docker tag ${IMAGE_NAME}:${IMAGE_TAG} your-registry/${IMAGE_NAME}:${IMAGE_TAG}"
echo "docker push your-registry/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
log_success "构建脚本执行完成！镜像已准备就绪。"

# 显示构建总结
END_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
log_info "构建总结:"
log_info "  开始时间: ${BUILD_DATE}"
log_info "  结束时间: ${END_TIME}"
log_info "  镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
log_info "  镜像大小: ${IMAGE_SIZE}"
log_info "  模型源: ${MODEL_SOURCE}"
log_info "  Git 提交: ${GIT_COMMIT}"