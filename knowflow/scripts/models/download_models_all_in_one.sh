#!/bin/bash
# 一体化模型下载脚本
# 功能：创建虚拟环境、安装依赖、下载模型

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项] [模型名称...]"
    echo
    echo "选项:"
    echo "  --all              下载所有支持的模型"
    echo "  --list             列出所有支持的模型"
    echo "  --force            强制重新下载"
    echo "  --base-dir DIR     指定模型保存目录 (默认: /var/lib/docker/volumes/gpustack-data/_data/models)"
    echo "  --hf-token TOKEN   Hugging Face 访问令牌"
    echo "  --help, -h         显示此帮助信息"
    echo
    echo "支持的模型:"
    echo "  qwen3-14b          Qwen2.5 14B 指令微调模型 (约 28GB)"
    echo "  bge-reranker-v2-m3 BGE Reranker v2 M3 模型 (约 2GB)"
    echo "  bge-m3             BGE M3 嵌入模型 (约 2GB)"
    echo
    echo "示例:"
    echo "  $0 --all                    # 下载所有模型"
    echo "  $0 qwen3-14b                # 下载单个模型"
    echo "  $0 bge-m3 bge-reranker-v2-m3 # 下载多个模型"
    echo "  $0 --list                   # 列出支持的模型"
    echo "  $0 --all --force            # 强制重新下载所有模型"
}

# 检查 Python 环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装，请先安装 Python3"
        exit 1
    fi
    print_info "Python3 已安装: $(python3 --version)"
}

# 创建和激活虚拟环境
setup_venv() {
    local venv_dir="./venv"
    
    if [ ! -d "$venv_dir" ]; then
        print_info "创建 Python 虚拟环境..."
        if python3 -m venv "$venv_dir"; then
            print_success "虚拟环境创建成功"
        else
            print_error "虚拟环境创建失败"
            exit 1
        fi
    else
        print_info "虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    print_info "激活虚拟环境..."
    source "$venv_dir/bin/activate"
    print_success "虚拟环境已激活"
}

# 安装依赖
install_dependencies() {
    print_info "安装 Python 依赖..."
    if pip install -r requirements.txt; then
        print_success "依赖安装完成"
    else
        print_error "依赖安装失败"
        exit 1
    fi
}

# 运行模型下载
run_download() {
    print_info "开始下载模型..."
    if python download_models.py "$@"; then
        print_success "模型下载完成！"
    else
        print_error "模型下载失败"
        exit 1
    fi
}

# 主函数
main() {
    # 检查帮助参数
    for arg in "$@"; do
        if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
            show_help
            exit 0
        fi
    done
    
    echo
    print_info "=== 一体化模型下载脚本 ==="
    echo
    
    # 检查 Python 环境
    check_python
    
    # 创建和激活虚拟环境
    setup_venv
    
    # 安装依赖
    install_dependencies
    
    # 运行模型下载
    run_download "$@"
    
    echo
    print_success "所有操作完成！"
    print_info "模型已下载到 /var/lib/docker/volumes/gpustack-data/_data/models/ 目录"
    print_info "您现在可以在 GPUStack 中添加这些本地模型"
}

# 如果脚本被直接执行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi