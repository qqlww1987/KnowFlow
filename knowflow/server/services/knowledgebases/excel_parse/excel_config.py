"""
Excel 配置模块

此模块负责为Excel解析提供统一、清晰的配置。
它直接依赖于新的全局配置系统，并允许知识库级别的有限覆盖。
"""
from typing import Dict, Any

# 直接从全局配置系统导入Pydantic模型和实例
from ...config import EXCEL_CONFIG, ExcelConfig as GlobalExcelConfig

def get_excel_config_for_kb(kb_config: Dict[str, Any] = None) -> GlobalExcelConfig:
    """
    根据知识库的具体配置，获取最终的Excel处理配置。

    此函数遵循以下优先级顺序来确定最终配置：
    1. 知识库特定配置 (kb_config): 具有最高优先级。
    2. 全局默认配置 (settings.yaml): 作为基础配置。

    Args:
        kb_config (Dict[str, Any], optional): 
            来自知识库的解析配置。可以包含覆盖全局设置的键值对。
            默认为 None，表示完全使用全局配置。

    Returns:
        GlobalExcelConfig: 一个包含最终配置的Pydantic模型实例。
    """
    if kb_config is None:
        kb_config = {}

    # 1. 以全局配置为基础
    #    我们使用 .copy(deep=True) 来确保不会意外修改全局单例
    final_config = EXCEL_CONFIG.copy(deep=True)

    # 2. 应用知识库级别的覆盖
    
    # 2.1. 处理遗留的 'html4excel' 参数
    # 如果 `html4excel` 在知识库配置中明确设置为 true，则强制使用 'html' 策略。
    # 这是为了向后兼容。
    if kb_config.get("html4excel", False):
        final_config.default_strategy = "html"
    
    # 2.2. 应用所有在 kb_config 中明确定义的、且存在于 ExcelConfig 模型中的配置项
    #    这提供了一种灵活的方式来为特定知识库微调任何Excel相关配置。
    #    `model_dump()` 用于获取模型的所有字段名，以进行安全检查。
    valid_keys = final_config.model_dump().keys()
    for key, value in kb_config.items():
        # 我们在这里检查 key 是否是 ExcelConfig 模型的一个有效字段
        # 以避免将无关的配置项混入。
        if key in valid_keys:
            setattr(final_config, key, value)

    # 在 `get_excel_config_for_kb` 函数中，将 `excel_strategy` 映射到 `default_strategy`
    if "excel_strategy" in kb_config:
        final_config.default_strategy = kb_config["excel_strategy"]

    return final_config

# 为了方便，提供一个直接获取全局配置的函数
def get_default_excel_config() -> GlobalExcelConfig:
    """
    返回全局默认的Excel配置。
    """
    return EXCEL_CONFIG


# 便利函数
def create_default_excel_config() -> GlobalExcelConfig:
    """创建默认Excel配置（从全局配置系统获取）"""
    return get_default_excel_config()


def create_excel_config_from_dict(config_dict: Dict[str, Any]) -> GlobalExcelConfig:
    """从字典创建Excel配置"""
    # 创建一个新的ExcelConfig实例
    new_config = GlobalExcelConfig()
    # 将字典中的键值对应用到新的实例
    for key, value in config_dict.items():
        setattr(new_config, key, value)
    return new_config


if __name__ == "__main__":
    # 测试配置功能
    def test_excel_config():
        print("=== Excel配置测试 ===")
        
        # 测试默认配置
        default_config = get_default_excel_config()
        print(f"默认配置: {default_config.model_dump()}")
        
        # 测试从知识库配置转换
        kb_config = {
            "html4excel": True,
            "excel_chunk_rows": 10,
            "excel_preset": "balanced"
        }
        excel_config = get_excel_config_for_kb(kb_config)
        print(f"\n从知识库配置转换: {excel_config.model_dump()}")
    
    test_excel_config() 