import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

from .business_config import RootConfig

logger = logging.getLogger(__name__)

ENV_PREFIX = "KNOWFLOW_"
CONFIG_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "settings.yaml"

def _load_config_from_yaml(path: Path) -> Dict[str, Any]:
    """从YAML文件加载配置"""
    if not path.exists():
        logger.warning(f"配置文件不存在: {path}")
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"加载或解析YAML配置失败: {path}, 错误: {e}")
        raise

def _recursive_update(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    """递归更新字典"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = _recursive_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def _load_env_vars() -> Dict[str, Any]:
    """从环境变量加载配置"""
    env_config = {}
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            parts = key.replace(ENV_PREFIX, "").lower().split('__')
            
            # 类型转换
            if value.lower() in ["true", "false"]:
                processed_value = value.lower() == "true"
            elif value.isdigit():
                processed_value = int(value)
            else:
                try:
                    processed_value = float(value)
                except (ValueError, TypeError):
                    processed_value = value
            
            d = env_config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = processed_value
            
    return env_config

def load_configuration() -> RootConfig:
    """
    加载、合并和验证配置
    加载顺序: 默认YAML -> 环境变量
    """
    # 1. 从默认YAML文件加载
    config_data = _load_config_from_yaml(DEFAULT_CONFIG_PATH)

    # 2. 从环境变量加载并覆盖
    env_data = _load_env_vars()
    if env_data:
        config_data = _recursive_update(config_data, env_data)

    # 3. 使用Pydantic模型进行验证
    try:
        return RootConfig.model_validate(config_data)
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise

# 创建全局配置实例
CONFIG = load_configuration()
APP_CONFIG = CONFIG.app
EXCEL_CONFIG = CONFIG.excel

# 打印加载的配置（在开发模式下）
if APP_CONFIG.dev_mode:
    import json
    logger.info("--- 加载的配置 (开发模式) ---")
    logger.info(json.dumps(CONFIG.model_dump(), indent=2))
    logger.info("-----------------------------") 