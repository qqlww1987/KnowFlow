#!/bin/bash
# KnowFlow 离线部署包构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/dist"
PACKAGE_NAME="knowflow-offline"
VERSION="$(date +%Y%m%d-%H%M%S)"
INCLUDE_MODELS="true"
COMPRESS="true"
QUIET="false"
CLEAN="true"
VERIFY="true"
USE_SUDO="false"

# 镜像配置
VLLM_IMAGE="knowflow/vllm-unified:latest"
MINERU_IMAGE="knowflow/mineru-sglang:latest"
RAGFLOW_IMAGE="infiniflow/ragflow:v0.7.0"
MYSQL_IMAGE="mysql:8.0"
REDIS_IMAGE="redis:7.2-alpine"
MINIO_IMAGE="quay.io/minio/minio:RELEASE.2023-12-20T01-00-02Z"
ELASTICSEARCH_IMAGE="docker.elastic.co/elasticsearch/elasticsearch:8.11.0"
NGINX_IMAGE="nginx:1.24-alpine"
PROMETHEUS_IMAGE="prom/prometheus:v2.45.0"
GRAFANA_IMAGE="grafana/grafana:10.0.0"

# 显示帮助信息
show_help() {
    cat << EOF
KnowFlow 离线部署包构建脚本

用法: $0 [选项]

选项:
    -o, --output DIR        输出目录 (默认: $OUTPUT_DIR)
    -n, --name NAME         包名称 (默认: $PACKAGE_NAME)
    -v, --version VERSION   版本号 (默认: $VERSION)
    -s, --skip-models       跳过模型下载
    -c, --no-compress       不压缩输出包
    -q, --quiet             静默模式
    --no-clean              不清理临时文件
    --no-verify             跳过验证步骤
    --sudo                  使用 sudo 执行 Docker 命令
    -h, --help              显示此帮助信息

示例:
    $0                                  # 默认构建
    $0 --version v1.0.0                # 指定版本
    $0 --skip-models --no-compress     # 跳过模型，不压缩
    $0 --output /tmp/build             # 指定输出目录
    $0 --sudo                          # 使用 sudo 执行 Docker 命令

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -n|--name)
            PACKAGE_NAME="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -s|--skip-models)
            INCLUDE_MODELS="false"
            shift
            ;;
        -c|--no-compress)
            COMPRESS="false"
            shift
            ;;
        -q|--quiet)
            QUIET="true"
            shift
            ;;
        --no-clean)
            CLEAN="false"
            shift
            ;;
        --no-verify)
            VERIFY="false"
            shift
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

# Docker 命令函数
docker_cmd() {
    if [[ "$USE_SUDO" == "true" ]]; then
        sudo docker "$@"
    else
        docker "$@"
    fi
}

# Docker Compose 命令函数
compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        local cmd="docker-compose"
    else
        local cmd="docker compose"
    fi
    
    if [[ "$USE_SUDO" == "true" ]]; then
        sudo $cmd "$@"
    else
        $cmd "$@"
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
    log_info "检查构建依赖..."
    
    local missing_deps=()
    
    # 检查必需工具
    for cmd in docker tar gzip; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "缺少必需依赖: ${missing_deps[*]}"
        exit 1
    fi
    
    # 检查 Docker 服务
    if ! docker_cmd info &> /dev/null; then
        log_error "Docker 服务未运行或无权限访问"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null && ! compose_cmd version &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 检查磁盘空间
check_disk_space() {
    log_info "检查磁盘空间..."
    
    # 获取输出目录可用空间（GB）
    local output_parent=$(dirname "$OUTPUT_DIR")
    local available_space=$(df "$output_parent" | awk 'NR==2 {print int($4/1024/1024)}')
    local required_space=100  # 至少需要 100GB
    
    if [[ $available_space -lt $required_space ]]; then
        log_error "磁盘空间不足。需要至少 ${required_space}GB，当前可用 ${available_space}GB"
        exit 1
    fi
    
    log_success "磁盘空间充足 (${available_space}GB 可用)"
}

# 创建输出目录
setup_output_dir() {
    log_info "设置输出目录..."
    
    # 创建输出目录结构
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR/images"
    mkdir -p "$OUTPUT_DIR/configs"
    mkdir -p "$OUTPUT_DIR/scripts"
    mkdir -p "$OUTPUT_DIR/docs"
    
    log_success "输出目录已创建: $OUTPUT_DIR"
}

# 构建自定义镜像
build_custom_images() {
    log_info "构建自定义镜像..."
    
    # 构建 vLLM 统一服务镜像
    log_info "构建 vLLM 统一服务镜像..."
    cd "$PROJECT_ROOT/docker/vllm-unified"
    
    local build_args=()
    if [[ "$INCLUDE_MODELS" == "true" ]]; then
        build_args+=("--build-arg" "DOWNLOAD_MODELS=true")
    else
        build_args+=("--build-arg" "DOWNLOAD_MODELS=false")
    fi
    
    if docker_cmd build "${build_args[@]}" -t "$VLLM_IMAGE" .; then
        log_success "vLLM 统一服务镜像构建完成"
    else
        log_error "vLLM 统一服务镜像构建失败"
        exit 1
    fi
    
    # 构建 MinerU SGLang 镜像（如果存在）
    if [[ -d "$PROJECT_ROOT/docker/mineru-sglang" ]]; then
        log_info "构建 MinerU SGLang 镜像..."
        cd "$PROJECT_ROOT/docker/mineru-sglang"
        
        if docker_cmd build -t "$MINERU_IMAGE" .; then
            log_success "MinerU SGLang 镜像构建完成"
        else
            log_warning "MinerU SGLang 镜像构建失败，跳过"
        fi
    fi
    
    cd "$PROJECT_ROOT"
}

# 拉取基础镜像
pull_base_images() {
    log_info "拉取基础镜像..."
    
    local images=(
        "$RAGFLOW_IMAGE"
        "$MYSQL_IMAGE"
        "$REDIS_IMAGE"
        "$MINIO_IMAGE"
        "$ELASTICSEARCH_IMAGE"
        "$NGINX_IMAGE"
        "$PROMETHEUS_IMAGE"
        "$GRAFANA_IMAGE"
    )
    
    for image in "${images[@]}"; do
        log_info "拉取镜像: $image"
        if docker_cmd pull "$image"; then
            log_success "镜像拉取完成: $image"
        else
            log_warning "镜像拉取失败: $image"
        fi
    done
}

# 导出镜像
export_images() {
    log_info "导出 Docker 镜像..."
    
    local images=(
        "$VLLM_IMAGE"
        "$RAGFLOW_IMAGE"
        "$MYSQL_IMAGE"
        "$REDIS_IMAGE"
        "$MINIO_IMAGE"
        "$ELASTICSEARCH_IMAGE"
        "$NGINX_IMAGE"
        "$PROMETHEUS_IMAGE"
        "$GRAFANA_IMAGE"
    )
    
    # 添加 MinerU 镜像（如果存在）
    if docker_cmd image inspect "$MINERU_IMAGE" &> /dev/null; then
        images+=("$MINERU_IMAGE")
    fi
    
    local images_file="$OUTPUT_DIR/images/knowflow-images.tar"
    
    log_info "导出镜像到: $images_file"
    if docker_cmd save -o "$images_file" "${images[@]}"; then
        log_success "镜像导出完成"
        
        # 显示文件大小
        local file_size=$(du -h "$images_file" | cut -f1)
        log_info "镜像文件大小: $file_size"
    else
        log_error "镜像导出失败"
        exit 1
    fi
}

# 打包配置文件
package_configs() {
    log_info "打包配置文件..."
    
    local configs_dir="$OUTPUT_DIR/configs"
    
    # 复制 Docker Compose 配置
    if [[ -f "$PROJECT_ROOT/docker/vllm-unified/docker-compose.yml" ]]; then
        cp "$PROJECT_ROOT/docker/vllm-unified/docker-compose.yml" "$configs_dir/"
    fi
    
    # 复制环境变量配置
    if [[ -f "$PROJECT_ROOT/docker/vllm-unified/.env.example" ]]; then
        cp "$PROJECT_ROOT/docker/vllm-unified/.env.example" "$configs_dir/"
    fi
    
    # 复制 vLLM 配置
    if [[ -d "$PROJECT_ROOT/docker/vllm-unified/config" ]]; then
        cp -r "$PROJECT_ROOT/docker/vllm-unified/config" "$configs_dir/vllm-config"
    fi
    
    # 复制 RAGFlow 配置（如果存在）
    if [[ -d "$PROJECT_ROOT/docker/ragflow" ]]; then
        cp -r "$PROJECT_ROOT/docker/ragflow" "$configs_dir/"
    fi
    
    # 复制 MinerU 配置（如果存在）
    if [[ -d "$PROJECT_ROOT/docker/mineru-sglang" ]]; then
        cp -r "$PROJECT_ROOT/docker/mineru-sglang" "$configs_dir/"
    fi
    
    log_success "配置文件打包完成"
}

# 创建安装脚本
create_install_script() {
    log_info "创建安装脚本..."
    
    cat > "$OUTPUT_DIR/scripts/install.sh" << 'EOF'
#!/bin/bash
# KnowFlow 离线安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
INSTALL_DIR="/opt/knowflow"
DATA_DIR="/var/lib/knowflow"
LOG_DIR="/var/log/knowflow"
USE_SUDO="false"

# 解析参数
while [[ \$# -gt 0 ]]; do
    case \$1 in
        --sudo)
            USE_SUDO="true"
            shift
            ;;
        *)
            echo "用法: \$0 [--sudo]"
            exit 1
            ;;
    esac
done

# Docker 命令函数
docker_cmd() {
    if [[ "\$USE_SUDO" == "true" ]]; then
        sudo docker "\$@"
    else
        docker "\$@"
    fi
}

# Docker Compose 命令函数
compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        local cmd="docker-compose"
    else
        local cmd="docker compose"
    fi
    
    if [[ "\$USE_SUDO" == "true" ]]; then
        sudo \$cmd "\$@"
    else
        \$cmd "\$@"
    fi
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查权限
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        log_error "请使用 root 权限运行此脚本"
        exit 1
    fi
}

# 检查系统要求
check_system_requirements() {
    log_info "检查系统要求..."
    
    # 检查内存
    local memory_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [[ $memory_gb -lt 16 ]]; then
        log_error "系统内存不足，需要至少 16GB，当前 ${memory_gb}GB"
        exit 1
    fi
    
    # 检查磁盘空间
    local disk_gb=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
    if [[ $disk_gb -lt 100 ]]; then
        log_error "磁盘空间不足，需要至少 100GB，当前可用 ${disk_gb}GB"
        exit 1
    fi
    
    # 检查 GPU（可选）
    if command -v nvidia-smi &> /dev/null; then
        local gpu_memory=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
        if [[ $gpu_memory -lt 12000 ]]; then
            log_error "GPU 显存不足，需要至少 12GB，当前 ${gpu_memory}MB"
            exit 1
        fi
        log_success "GPU 检查通过: ${gpu_memory}MB 显存"
    else
        log_warning "未检测到 NVIDIA GPU，将使用 CPU 模式"
    fi
    
    log_success "系统要求检查通过"
}

# 安装 Docker
install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker 已安装"
        return 0
    fi
    
    log_info "安装 Docker..."
    
    # 检测系统类型
    if [[ -f /etc/redhat-release ]]; then
        # CentOS/RHEL
        yum install -y yum-utils
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    elif [[ -f /etc/debian_version ]]; then
        # Ubuntu/Debian
        apt-get update
        apt-get install -y ca-certificates curl gnupg lsb-release
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    else
        log_error "不支持的操作系统"
        exit 1
    fi
    
    # 启动 Docker 服务
    systemctl enable docker
    systemctl start docker
    
    log_success "Docker 安装完成"
}

# 安装 NVIDIA Container Toolkit
install_nvidia_docker() {
    if ! command -v nvidia-smi &> /dev/null; then
        log_info "跳过 NVIDIA Container Toolkit 安装（未检测到 GPU）"
        return 0
    fi
    
    log_info "安装 NVIDIA Container Toolkit..."
    
    # 添加 NVIDIA 仓库
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
    
    apt-get update
    apt-get install -y nvidia-container-toolkit
    
    # 重启 Docker
    systemctl restart docker
    
    log_success "NVIDIA Container Toolkit 安装完成"
}

# 创建目录结构
setup_directories() {
    log_info "创建目录结构..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$LOG_DIR"
    
    # 设置权限
    chown -R 1000:1000 "$DATA_DIR"
    chown -R 1000:1000 "$LOG_DIR"
    
    log_success "目录结构创建完成"
}

# 加载 Docker 镜像
load_images() {
    log_info "加载 Docker 镜像..."
    
    local images_file="./images/knowflow-images.tar"
    
    if [[ ! -f "$images_file" ]]; then
        log_error "镜像文件不存在: $images_file"
        exit 1
    fi
    
    if docker_cmd load -i "$images_file"; then
        log_success "Docker 镜像加载完成"
    else
        log_error "Docker 镜像加载失败"
        exit 1
    fi
}

# 安装配置文件
install_configs() {
    log_info "安装配置文件..."
    
    # 复制配置文件
    cp -r ./configs/* "$INSTALL_DIR/"
    
    # 创建环境变量文件
    if [[ -f "$INSTALL_DIR/.env.example" ]]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    fi
    
    # 设置权限
    chown -R root:root "$INSTALL_DIR"
    chmod 644 "$INSTALL_DIR"/*.yml
    chmod 600 "$INSTALL_DIR/.env"
    
    log_success "配置文件安装完成"
}

# 启动服务
start_services() {
    log_info "启动 KnowFlow 服务..."
    
    cd "$INSTALL_DIR"
    
    # 启动服务
    compose_cmd up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 30
    
    # 检查服务状态
    if compose_cmd ps | grep -q "Up"; then
        log_success "KnowFlow 服务启动成功"
        
        echo
        echo -e "${BLUE}=== 服务访问地址 ===${NC}"
        echo "  vLLM 统一服务: http://localhost:8000"
        echo "  RAGFlow: http://localhost:80"
        echo "  Grafana 监控: http://localhost:3000"
        echo
        echo -e "${BLUE}=== 管理命令 ===${NC}"
        echo "  查看状态: cd $INSTALL_DIR && docker compose ps"
        echo "  查看日志: cd $INSTALL_DIR && docker compose logs -f"
        echo "  重启服务: cd $INSTALL_DIR && docker compose restart"
        echo "  停止服务: cd $INSTALL_DIR && docker compose down"
        echo
    else
        log_error "服务启动失败，请检查日志"
        compose_cmd logs
        exit 1
    fi
}

# 主函数
main() {
    echo -e "${BLUE}=== KnowFlow 离线安装程序 ===${NC}"
    echo
    
    check_permissions
    check_system_requirements
    install_docker
    install_nvidia_docker
    setup_directories
    load_images
    install_configs
    start_services
    
    log_success "KnowFlow 安装完成！"
}

main "$@"
EOF

    chmod +x "$OUTPUT_DIR/scripts/install.sh"
    log_success "安装脚本创建完成"
}

# 创建卸载脚本
create_uninstall_script() {
    log_info "创建卸载脚本..."
    
    cat > "$OUTPUT_DIR/scripts/uninstall.sh" << 'EOF'
#!/bin/bash
# KnowFlow 卸载脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
INSTALL_DIR="/opt/knowflow"
DATA_DIR="/var/lib/knowflow"
LOG_DIR="/var/log/knowflow"
FORCE="false"
USE_SUDO="false"

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

# 解析参数
while [[ \$# -gt 0 ]]; do
    case \$1 in
        --force)
            FORCE="true"
            shift
            ;;
        --sudo)
            USE_SUDO="true"
            shift
            ;;
        *)
            echo "用法: \$0 [--force] [--sudo]"
            exit 1
            ;;
    esac
done

# Docker 命令函数
docker_cmd() {
    if [[ "\$USE_SUDO" == "true" ]]; then
        sudo docker "\$@"
    else
        docker "\$@"
    fi
}

# Docker Compose 命令函数
compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        local cmd="docker-compose"
    else
        local cmd="docker compose"
    fi
    
    if [[ "\$USE_SUDO" == "true" ]]; then
        sudo \$cmd "\$@"
    else
        \$cmd "\$@"
    fi
}

# 确认卸载
confirm_uninstall() {
    if [[ "$FORCE" != "true" ]]; then
        echo -e "${YELLOW}警告: 此操作将完全删除 KnowFlow 及其所有数据${NC}"
        echo "包括:"
        echo "  - 所有 Docker 容器和镜像"
        echo "  - 配置文件 ($INSTALL_DIR)"
        echo "  - 数据文件 ($DATA_DIR)"
        echo "  - 日志文件 ($LOG_DIR)"
        echo
        read -p "确认继续卸载? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "卸载已取消"
            exit 0
        fi
    fi
}

# 停止服务
stop_services() {
    log_info "停止 KnowFlow 服务..."
    
    if [[ -f "\$INSTALL_DIR/docker-compose.yml" ]]; then
        cd "\$INSTALL_DIR"
        compose_cmd down --remove-orphans || true
    fi
    
    # 停止所有相关容器
    docker_cmd ps -a --filter "name=knowflow" --format "{{.ID}}" | xargs -r docker_cmd stop || true
    docker_cmd ps -a --filter "name=vllm" --format "{{.ID}}" | xargs -r docker_cmd stop || true
    docker_cmd ps -a --filter "name=ragflow" --format "{{.ID}}" | xargs -r docker_cmd stop || true
    
    log_success "服务已停止"
}

# 删除容器
remove_containers() {
    log_info "删除 Docker 容器..."
    
    # 删除所有相关容器
    docker_cmd ps -a --filter "name=knowflow" --format "{{.ID}}" | xargs -r docker_cmd rm -f || true
    docker_cmd ps -a --filter "name=vllm" --format "{{.ID}}" | xargs -r docker_cmd rm -f || true
    docker_cmd ps -a --filter "name=ragflow" --format "{{.ID}}" | xargs -r docker_cmd rm -f || true
    
    log_success "容器已删除"
}

# 删除镜像
remove_images() {
    log_info "删除 Docker 镜像..."
    
    # 删除 KnowFlow 相关镜像
    docker_cmd images --filter "reference=knowflow/*" --format "{{.ID}}" | xargs -r docker_cmd rmi -f || true
    docker_cmd images --filter "reference=infiniflow/ragflow*" --format "{{.ID}}" | xargs -r docker_cmd rmi -f || true
    
    log_success "镜像已删除"
}

# 删除数据卷
remove_volumes() {
    log_info "删除 Docker 数据卷..."
    
    # 删除相关数据卷
    docker_cmd volume ls --filter "name=knowflow" --format "{{.Name}}" | xargs -r docker_cmd volume rm || true
    docker_cmd volume ls --filter "name=vllm" --format "{{.Name}}" | xargs -r docker_cmd volume rm || true
    docker_cmd volume ls --filter "name=ragflow" --format "{{.Name}}" | xargs -r docker_cmd volume rm || true
    
    log_success "数据卷已删除"
}

# 删除网络
remove_networks() {
    log_info "删除 Docker 网络..."
    
    # 删除相关网络
    docker_cmd network ls --filter "name=knowflow" --format "{{.ID}}" | xargs -r docker_cmd network rm || true
    
    log_success "网络已删除"
}

# 删除文件
remove_files() {
    log_info "删除文件和目录..."
    
    # 删除安装目录
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        log_success "安装目录已删除: $INSTALL_DIR"
    fi
    
    # 删除数据目录
    if [[ -d "$DATA_DIR" ]]; then
        rm -rf "$DATA_DIR"
        log_success "数据目录已删除: $DATA_DIR"
    fi
    
    # 删除日志目录
    if [[ -d "$LOG_DIR" ]]; then
        rm -rf "$LOG_DIR"
        log_success "日志目录已删除: $LOG_DIR"
    fi
}

# 清理系统服务
cleanup_services() {
    log_info "清理系统服务..."
    
    # 删除可能的 systemd 服务文件
    if [[ -f "/etc/systemd/system/knowflow.service" ]]; then
        systemctl stop knowflow || true
        systemctl disable knowflow || true
        rm -f "/etc/systemd/system/knowflow.service"
        systemctl daemon-reload
        log_success "系统服务已清理"
    fi
}

# 主函数
main() {
    echo -e "${BLUE}=== KnowFlow 卸载程序 ===${NC}"
    echo
    
    # 检查权限
    if [[ $EUID -ne 0 ]]; then
        log_error "请使用 root 权限运行此脚本"
        exit 1
    fi
    
    confirm_uninstall
    stop_services
    remove_containers
    remove_images
    remove_volumes
    remove_networks
    remove_files
    cleanup_services
    
    echo
    log_success "KnowFlow 卸载完成！"
    
    # 提示清理 Docker
    echo
    echo -e "${BLUE}可选清理操作:${NC}"
    echo "  清理未使用的 Docker 资源: docker system prune -a"
    echo "  完全重置 Docker: systemctl stop docker && rm -rf /var/lib/docker && systemctl start docker"
    echo
}

main "$@"
EOF

    chmod +x "$OUTPUT_DIR/scripts/uninstall.sh"
    log_success "卸载脚本创建完成"
}

# 创建文档
create_documentation() {
    log_info "创建文档..."
    
    # 创建 README
    cat > "$OUTPUT_DIR/README.md" << EOF
# KnowFlow 离线部署包

版本: $VERSION  
构建时间: $(date '+%Y-%m-%d %H:%M:%S')

## 概述

KnowFlow 是一个集成了 RAGFlow、MinerU 和统一 vLLM 服务的知识流处理平台。本离线部署包包含了运行 KnowFlow 所需的所有组件。

## 系统要求

### 硬件要求
- **内存**: 16GB+ RAM
- **存储**: 100GB+ 可用磁盘空间
- **GPU**: 12GB+ VRAM (推荐 NVIDIA RTX 4090 或更高)
- **CPU**: 8 核心以上

### 软件要求
- **操作系统**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- **内核**: Linux 5.4+
- **Docker**: 20.10+ (安装脚本会自动安装)
- **NVIDIA 驱动**: 525+ (如果使用 GPU)

## 快速开始

### 1. 解压部署包
\`\`\`bash
tar -xzf knowflow-offline-$VERSION.tar.gz
cd knowflow-offline-$VERSION
\`\`\`

### 2. 运行安装脚本
\`\`\`bash
sudo ./scripts/install.sh
\`\`\`

### 3. 访问服务
- **vLLM 统一服务**: http://localhost:8000
- **RAGFlow**: http://localhost:80
- **Grafana 监控**: http://localhost:3000

## 服务组件

### vLLM 统一服务
- **Chat API**: Qwen3-32B 模型
- **Embedding API**: bge-m3 模型
- **Rerank API**: bge-reranker-v2-m3 模型
- **端口**: 8000 (主服务), 8001-8003 (模型服务)

### RAGFlow
- **功能**: 文档处理和检索增强生成
- **端口**: 80

### 监控服务
- **Prometheus**: 指标收集
- **Grafana**: 可视化监控
- **端口**: 3000

## 管理命令

### 查看服务状态
\`\`\`bash
cd /opt/knowflow
docker compose ps
\`\`\`

### 查看服务日志
\`\`\`bash
cd /opt/knowflow
docker compose logs -f [服务名]
\`\`\`

### 重启服务
\`\`\`bash
cd /opt/knowflow
docker compose restart [服务名]
\`\`\`

### 停止所有服务
\`\`\`bash
cd /opt/knowflow
docker compose down
\`\`\`

### 启动所有服务
\`\`\`bash
cd /opt/knowflow
docker compose up -d
\`\`\`

## API 使用示例

### Chat API
\`\`\`bash
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer token-abc123" \\
  -d '{
    "model": "Qwen3-32B",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下自己"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
\`\`\`

### Embedding API
\`\`\`bash
curl -X POST http://localhost:8000/v1/embeddings \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer token-abc123" \\
  -d '{
    "model": "bge-m3",
    "input": ["这是一个测试文本"]
  }'
\`\`\`

### Rerank API
\`\`\`bash
curl -X POST http://localhost:8000/v1/rerank \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer token-abc123" \\
  -d '{
    "model": "bge-reranker-v2-m3",
    "query": "查询文本",
    "documents": ["文档1", "文档2", "文档3"]
  }'
\`\`\`

## 配置说明

### 环境变量配置
主要配置文件位于 \`/opt/knowflow/.env\`，包含以下重要配置：

- \`CUDA_VISIBLE_DEVICES\`: 指定使用的 GPU 设备
- \`VLLM_API_KEY\`: API 访问密钥
- \`*_GPU_MEMORY_UTILIZATION\`: GPU 内存使用率
- \`*_MAX_MODEL_LEN\`: 模型最大序列长度

### 模型配置
模型配置文件位于 \`/opt/knowflow/vllm-config/models.json\`，可以调整：

- 模型路径和名称
- 服务端口
- GPU 内存分配
- 并行配置

## 故障排除

### 常见问题

1. **服务启动失败**
   - 检查系统资源是否充足
   - 查看服务日志: \`docker compose logs [服务名]\`
   - 确认 GPU 驱动和 NVIDIA Container Toolkit 已正确安装

2. **GPU 不可用**
   - 检查 NVIDIA 驱动: \`nvidia-smi\`
   - 检查 Docker GPU 支持: \`docker run --rm --gpus all nvidia/cuda:12.1-base-ubuntu22.04 nvidia-smi\`

3. **内存不足**
   - 调整 \`.env\` 文件中的 \`*_GPU_MEMORY_UTILIZATION\` 参数
   - 减少并行处理数量

4. **端口冲突**
   - 修改 \`docker-compose.yml\` 中的端口映射
   - 确保所需端口未被其他服务占用

### 日志位置
- **应用日志**: \`/var/log/knowflow/\`
- **Docker 日志**: \`docker compose logs\`
- **系统日志**: \`/var/log/syslog\` 或 \`journalctl\`

## 卸载

如需完全卸载 KnowFlow：

\`\`\`bash
sudo ./scripts/uninstall.sh
\`\`\`

强制卸载（跳过确认）：

\`\`\`bash
sudo ./scripts/uninstall.sh --force
\`\`\`

## 技术支持

如遇到问题，请提供以下信息：

1. 系统信息: \`uname -a\`
2. Docker 版本: \`docker --version\`
3. GPU 信息: \`nvidia-smi\`
4. 服务状态: \`docker compose ps\`
5. 相关日志: \`docker compose logs [服务名]\`

## 更新日志

### $VERSION
- 初始版本发布
- 集成 vLLM 统一服务
- 支持 Qwen3-32B、bge-m3、bge-reranker-v2-m3 模型
- 包含 RAGFlow 和监控服务
- 提供完整的离线部署方案
EOF

    log_success "文档创建完成"
}

# 验证构建结果
verify_package() {
    if [[ "$VERIFY" != "true" ]]; then
        return 0
    fi
    
    log_info "验证构建结果..."
    
    # 检查必需文件
    local required_files=(
        "$OUTPUT_DIR/images/knowflow-images.tar"
        "$OUTPUT_DIR/scripts/install.sh"
        "$OUTPUT_DIR/scripts/uninstall.sh"
        "$OUTPUT_DIR/README.md"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "缺少必需文件: $file"
            exit 1
        fi
    done
    
    # 检查镜像文件大小
    local images_file="$OUTPUT_DIR/images/knowflow-images.tar"
    local file_size_mb=$(du -m "$images_file" | cut -f1)
    
    if [[ $file_size_mb -lt 1000 ]]; then
        log_warning "镜像文件可能不完整，大小仅 ${file_size_mb}MB"
    fi
    
    log_success "构建结果验证通过"
}

# 压缩输出包
compress_package() {
    if [[ "$COMPRESS" != "true" ]]; then
        return 0
    fi
    
    log_info "压缩输出包..."
    
    local package_file="${OUTPUT_DIR%/*}/${PACKAGE_NAME}-${VERSION}.tar.gz"
    
    cd "$(dirname "$OUTPUT_DIR")"
    
    if tar -czf "$package_file" "$(basename "$OUTPUT_DIR")"; then
        log_success "输出包已压缩: $package_file"
        
        # 显示文件大小
        local file_size=$(du -h "$package_file" | cut -f1)
        log_info "压缩包大小: $file_size"
        
        # 计算校验和
        local checksum=$(sha256sum "$package_file" | cut -d' ' -f1)
        echo "$checksum  $(basename "$package_file")" > "${package_file}.sha256"
        log_info "SHA256 校验和: $checksum"
    else
        log_error "输出包压缩失败"
        exit 1
    fi
}

# 清理临时文件
cleanup() {
    if [[ "$CLEAN" != "true" ]]; then
        return 0
    fi
    
    log_info "清理临时文件..."
    
    # 清理 Docker 构建缓存
    docker_cmd builder prune -f &> /dev/null || true
    
    # 清理未使用的镜像
    docker_cmd image prune -f &> /dev/null || true
    
    log_success "临时文件清理完成"
}

# 显示构建摘要
show_summary() {
    echo
    echo -e "${BLUE}=== 构建摘要 ===${NC}"
    echo "  包名称: $PACKAGE_NAME"
    echo "  版本: $VERSION"
    echo "  输出目录: $OUTPUT_DIR"
    echo "  包含模型: $INCLUDE_MODELS"
    echo "  压缩输出: $COMPRESS"
    
    if [[ -f "$OUTPUT_DIR/images/knowflow-images.tar" ]]; then
        local images_size=$(du -h "$OUTPUT_DIR/images/knowflow-images.tar" | cut -f1)
        echo "  镜像大小: $images_size"
    fi
    
    if [[ "$COMPRESS" == "true" ]]; then
        local package_file="${OUTPUT_DIR%/*}/${PACKAGE_NAME}-${VERSION}.tar.gz"
        if [[ -f "$package_file" ]]; then
            local package_size=$(du -h "$package_file" | cut -f1)
            echo "  压缩包大小: $package_size"
        fi
    fi
    
    echo
    echo -e "${BLUE}=== 部署说明 ===${NC}"
    echo "  1. 将部署包传输到目标服务器"
    echo "  2. 解压: tar -xzf ${PACKAGE_NAME}-${VERSION}.tar.gz"
    echo "  3. 安装: sudo ./scripts/install.sh"
    echo "  4. 访问: http://localhost:8000"
    echo
}

# 主函数
main() {
    echo -e "${BLUE}=== KnowFlow 离线部署包构建脚本 ===${NC}"
    echo
    
    check_dependencies
    check_disk_space
    setup_output_dir
    build_custom_images
    pull_base_images
    export_images
    package_configs
    create_install_script
    create_uninstall_script
    create_documentation
    verify_package
    compress_package
    cleanup
    
    show_summary
    log_success "离线部署包构建完成！"
}

# 信号处理
trap cleanup EXIT
trap 'log_error "构建被中断"; exit 1' INT TERM

# 执行主函数
main "$@"