#!/usr/bin/env python3
"""
配置更新工具
用于更新RAGFlow Chat Plugin的配置信息
"""

import json
import os
import sys

def load_current_config():
    """加载当前配置"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"❌ 读取配置文件时出错: {e}")
        return {}

def save_config(config):
    """保存配置"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print(f"✅ 配置已保存到: {config_path}")
        return True
    except Exception as e:
        print(f"❌ 保存配置文件时出错: {e}")
        return False

def update_config_interactive():
    """交互式更新配置"""
    print("🔧 RAGFlow Chat Plugin 配置更新工具")
    print("=" * 50)
    
    # 加载当前配置
    current_config = load_current_config()
    print("📋 当前配置:")
    for key, value in current_config.items():
        if key == "api_key":
            # 隐藏API密钥的大部分内容
            masked_value = value[:10] + "*" * (len(value) - 10) if len(value) > 10 else "*" * len(value)
            print(f"  {key}: {masked_value}")
        else:
            print(f"  {key}: {value}")
    
    print("\n🔄 请输入新的配置信息（直接回车保留当前值）:")
    
    # 更新API密钥
    current_api_key = current_config.get("api_key", "")
    new_api_key = input(f"API密钥 (当前: {'*' * 10}): ").strip()
    if new_api_key:
        current_config["api_key"] = new_api_key
        print("✅ API密钥已更新")
    
    # 更新服务器地址
    current_host = current_config.get("host_address", "www.knowflowchat.cn")
    new_host = input(f"服务器地址 (当前: {current_host}): ").strip()
    if new_host:
        current_config["host_address"] = new_host
        print("✅ 服务器地址已更新")
    
    # 更新Dialog ID
    current_dialog_id = current_config.get("dialog_id", "f48e23383df611f09c9b26d7d2ef55ce")
    new_dialog_id = input(f"Dialog ID (当前: {current_dialog_id}): ").strip()
    if new_dialog_id:
        current_config["dialog_id"] = new_dialog_id
        print("✅ Dialog ID已更新")
    
    return current_config

def test_config(config):
    """测试配置是否有效"""
    print("\n🧪 测试配置...")
    
    required_fields = ["api_key", "host_address", "dialog_id"]
    for field in required_fields:
        if not config.get(field):
            print(f"❌ 缺少必需字段: {field}")
            return False
    
    print("✅ 配置格式检查通过")
    
    # 询问是否运行API测试
    test_api = input("\n是否运行API连接测试? (y/N): ").lower().strip()
    if test_api == 'y':
        try:
            # 更新测试脚本的配置并运行
            print("🚀 启动API测试...")
            os.system("python quick_api_test.py")
        except Exception as e:
            print(f"❌ API测试失败: {e}")
            return False
    
    return True

def main():
    """主函数"""
    print("欢迎使用RAGFlow Chat Plugin配置更新工具!")
    print("此工具将帮助您更新API密钥和其他配置信息。")
    print("=" * 60)
    
    # 交互式更新配置
    new_config = update_config_interactive()
    
    print("\n📋 新配置预览:")
    for key, value in new_config.items():
        if key == "api_key":
            masked_value = value[:10] + "*" * (len(value) - 10) if len(value) > 10 else "*" * len(value)
            print(f"  {key}: {masked_value}")
        else:
            print(f"  {key}: {value}")
    
    # 确认保存
    save_confirm = input("\n确认保存配置? (y/N): ").lower().strip()
    if save_confirm != 'y':
        print("⏭️  配置更新已取消")
        return 0
    
    # 保存配置
    if not save_config(new_config):
        return 1
    
    # 测试配置
    if not test_config(new_config):
        print("\n⚠️  配置可能有问题，请检查后重试")
        return 1
    
    print("\n🎉 配置更新完成！")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n🛑 配置更新被用户中断")
        sys.exit(1) 