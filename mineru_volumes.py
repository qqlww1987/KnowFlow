# 本项目 mineru 并未打包到镜像内，而是挂载到本地已下载的资源
# 通过本脚本可以将 magic-pdf.json 文件路径添加到环境变量，实现自动挂载
# 支持同时检测 huggingface 和 modelscope 模型路径

import os
import json

def get_directory_size(path):
    """计算目录大小（以字节为单位）"""
    if not os.path.exists(path):
        return 0
    
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
    except (OSError, IOError):
        pass
    return total_size

def find_best_model_cache_dir():
    """智能检测并返回最佳的模型缓存目录"""
    home_dir = os.path.expanduser('~')
    
    # 定义可能的模型缓存路径
    cache_paths = [
        {
            'path': os.path.join(home_dir, '.cache/modelscope/hub'),
            'type': 'modelscope',
            'priority': 1  # 优先级：1=高，2=中，3=低
        },
        {
            'path': os.path.join(home_dir, '.cache/huggingface/hub'),
            'type': 'huggingface', 
            'priority': 2
        }
    ]
    
    # 检查每个路径并评估
    available_paths = []
    for cache_info in cache_paths:
        path = cache_info['path']
        
        if os.path.exists(path):
            # 计算目录大小
            size = get_directory_size(path)
            cache_info['size'] = size
            cache_info['exists'] = True
            
            print(f"检测到 {cache_info['type']} 缓存: {path}")
            print(f"  - 目录大小: {size / (1024**3):.2f} GB")
            
            # 检查是否包含模型文件
            has_models = False
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path) and ('model' in item.lower() or len(os.listdir(item_path)) > 0):
                        has_models = True
                        break
            except (OSError, IOError):
                pass
            
            cache_info['has_models'] = has_models
            if has_models:
                print(f"  - 包含模型文件: 是")
            else:
                print(f"  - 包含模型文件: 否")
            
            available_paths.append(cache_info)
        else:
            print(f"路径不存在: {path}")
    
    if not available_paths:
        print("警告: 未检测到任何模型缓存目录")
        # 返回默认的 huggingface 路径
        return os.path.join(home_dir, '.cache/huggingface/hub'), 'huggingface'
    
    # 选择最佳路径的策略：
    # 1. 优先选择有模型文件的路径
    # 2. 如果都有或都没有模型文件，选择大小更大的路径
    # 3. 如果大小相近，按优先级选择
    
    paths_with_models = [p for p in available_paths if p.get('has_models', False)]
    
    if paths_with_models:
        # 有模型文件的路径中选择最大的
        best_path = max(paths_with_models, key=lambda x: x['size'])
    else:
        # 没有模型文件的路径中选择最大的
        best_path = max(available_paths, key=lambda x: x['size'])
    
    print(f"\n选择使用: {best_path['type']} 缓存路径")
    print(f"路径: {best_path['path']}")
    
    return best_path['path'], best_path['type']

def update_env_file(env_path, updates):
    # 读取现有 .env 内容
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = []

    # 构建新的 .env 内容
    env_dict = {}
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            env_dict[k.strip()] = v.strip().strip("'").strip('"')

    # 更新/追加变量
    env_dict.update(updates)

    # 打印 env_dict
    print(f"env_dict: {env_dict}")

    # 写回 .env 文件
    with open(env_path, 'w', encoding='utf-8') as f:
        for k, v in env_dict.items():
            f.write(f"{k}='{v}'\n")


if __name__ == "__main__":
    print("=== MinerU 模型路径自动检测 ===")
    
    home_dir = os.path.expanduser('~')
    
    # 智能检测最佳模型缓存目录
    mineru_models_dir, cache_type = find_best_model_cache_dir()
    print(f"\n最终选择的模型目录: {mineru_models_dir}")
    print(f"缓存类型: {cache_type}")

    # 宿主机配置文件路径
    config_file = os.path.join(home_dir, 'magic-pdf.json')
    if not os.path.exists(config_file):
        print(f"\n配置文件不存在: {config_file}")
        exit(1)
    
    print(f"\n找到配置文件: {config_file}")

    # 更新 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"env_path: {env_path}")
    
    # 直接使用宿主机的原始配置文件，无需复制和路径修正
    update_env_file(env_path, {
        'MINERU_MODLES_DIR': mineru_models_dir,
        'MINERU_MAGIC_PDF_JSON_PATH': config_file,
        'MINERU_CACHE_TYPE': cache_type  # 新增：记录使用的缓存类型
    })
    
    print(f"\n=== 配置完成 ===")
    print("已将宿主机配置文件路径添加到环境变量，将通过 Docker volume 直接挂载到容器内。")
    print(f"使用的模型缓存类型: {cache_type}")
    print(f"模型目录: {mineru_models_dir}")
