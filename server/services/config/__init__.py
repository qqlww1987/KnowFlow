"""
KnowFlow 业务配置管理模块

将业务逻辑配置与环境部署配置分离，提供统一的配置管理接口。
"""

from .config_loader import CONFIG, APP_CONFIG, EXCEL_CONFIG, DATABASE_CONFIG
from .business_config import AppConfig, ExcelConfig, DatabaseConfig

__all__ = [
    "CONFIG",
    "APP_CONFIG",
    "EXCEL_CONFIG",
    "DATABASE_CONFIG",
    "AppConfig",
    "ExcelConfig",
    "DatabaseConfig"
] 