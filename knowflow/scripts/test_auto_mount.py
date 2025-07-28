#!/usr/bin/env python3
"""
测试自动挂载脚本功能
仅用于验证脚本逻辑，不会修改任何文件
"""

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path(__file__).parent))

from auto_mount import DockerComposeManager

def test_auto_mount():
    """测试自动挂载功能"""
    print("🧪 测试自动挂载脚本功能")
    print("=" * 50)
    
    manager = DockerComposeManager()
    
    # 测试容器发现
    print("1. 测试容器发现功能...")
    containers = manager.find_ragflow_containers()
    if containers:
        print(f"   ✅ 发现 {len(containers)} 个 RAGFlow 容器")
        for container in containers:
            print(f"      - {container.get('Names', 'Unknown')}")
    else:
        print("   ⚠️  未发现 RAGFlow 容器（这是正常的，如果没有运行 RAGFlow）")
    
    # 测试 compose 文件查找
    print("\n2. 测试 compose 文件查找...")
    compose_file = manager.find_compose_file()
    if compose_file:
        print(f"   ✅ 发现 compose 文件: {compose_file}")
    else:
        print("   ⚠️  未发现 compose 文件（这是正常的，如果不在 RAGFlow 目录）")
    
    # 测试扩展文件检查
    print("\n3. 测试扩展文件检查...")
    if manager.extensions_dir.exists():
        print(f"   ✅ 扩展目录存在: {manager.extensions_dir}")
        
        enhanced_doc = manager.extensions_dir / "enhanced_doc.py"
        if enhanced_doc.exists():
            print(f"   ✅ 扩展文件存在: {enhanced_doc}")
        else:
            print(f"   ❌ 扩展文件不存在: {enhanced_doc}")
    else:
        print(f"   ❌ 扩展目录不存在: {manager.extensions_dir}")
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 说明：")
    print("- 如果某些测试显示警告，这是正常的")
    print("- 只有在 RAGFlow 运行且 compose 文件存在时才能完全测试")
    print("- 实际挂载功能需要运行完整的 auto_mount.py 脚本")

if __name__ == "__main__":
    test_auto_mount() 