# 本项目 mineru 并未打包到镜像内，而是挂载到本地已下载的资源
# 通过本脚本可以将 magic-pdf.json 文件路径添加到环境变量，实现自动挂载

import os
import json

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
    home_dir = os.path.expanduser('~')
    
    # 宿主机模型目录
    mineru_models_dir = os.path.join(home_dir, '.cache/huggingface/hub/')
    print(f"mineru_models_dir: {mineru_models_dir}")

    # 宿主机配置文件路径
    config_file = os.path.join(home_dir, 'magic-pdf.json')
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        exit(1)
    
    print(f"找到配置文件: {config_file}")

    # 更新 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"env_path: {env_path}")
    
    # 直接使用宿主机的原始配置文件，无需复制和路径修正
    update_env_file(env_path, {
        'MINERU_MODLES_DIR': mineru_models_dir,
        'MINERU_MAGIC_PDF_JSON_PATH': config_file  # 直接指向宿主机配置文件
    })
    
    print("已将宿主机配置文件路径添加到环境变量，将通过 Docker volume 直接挂载到容器内。")
