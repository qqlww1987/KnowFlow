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
    # 解析 magic-pdf.json
    home_dir = os.path.expanduser('~')
  
    mineru_models_dir = os.path.join(home_dir, '.cache/huggingface/hub/')

    # 打印处理后的路径
    print(f"mineru_models_dir: {mineru_models_dir}")

    # 更新 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')

    print(f"env_path: {env_path}")
    
    # 复制 magic-pdf.json 到 server 目录，用于 docker 构建
    config_file = os.path.join(home_dir, 'magic-pdf.json')
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        config_json = json.load(f)

    def fix_cache_path(path):
        idx = path.find('.cache')
        if idx == -1:
            return path
        # 如果.cache前不是/root，则替换
        if not path.startswith('/root/.cache'):
            return '/root/' + path[idx:]
        return path

    if 'models-dir' in config_json:
        config_json['models-dir'] = fix_cache_path(config_json['models-dir'])
    if 'layoutreader-model-dir' in config_json:
        config_json['layoutreader-model-dir'] = fix_cache_path(config_json['layoutreader-model-dir'])

    server_dir = os.path.join(os.path.dirname(__file__), "server")
    target_config_file = os.path.join(server_dir, "magic-pdf.json")
    
    with open(target_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_json, f, ensure_ascii=False, indent=4)
    print(f"已将修正后的配置文件复制到: {target_config_file}")
    
    # 更新环境变量，添加 MINERU_MAGIC_PDF_JSON_PATH
    update_env_file(env_path, {
        'MINERU_MODLES_DIR': mineru_models_dir,
        'MINERU_MAGIC_PDF_JSON_PATH': target_config_file
    })
    
    print("已将配置文件路径添加到环境变量，可以通过 volume 挂载到容器内。")
