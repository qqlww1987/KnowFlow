#!/usr/bin/env python3
"""
RAGFlow Chat Plugin 测试运行器
用于测试 dialog_id: f48e23383df611f09c9b26d7d2ef55ce 的接口功能
"""

import os
import sys
import subprocess

def run_unit_tests():
    """运行单元测试（使用Mock，不需要真实API）"""
    print("🧪 开始运行单元测试...")
    print("=" * 50)
    
    try:
        result = subprocess.run([
            sys.executable, 
            'test_ragflow_chat.py'
        ], cwd=os.path.dirname(__file__), capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
            
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行测试时出错: {e}")
        return False

def run_integration_test():
    """运行集成测试（需要真实API配置）"""
    print("\n🌐 开始运行集成测试...")
    print("=" * 50)
    print("⚠️  集成测试需要有效的API配置才能运行")
    
    # 检查是否要运行集成测试
    response = input("是否运行真实API集成测试? (y/N): ").lower().strip()
    if response != 'y':
        print("⏭️  跳过集成测试")
        return True
        
    # 运行集成测试
    try:
        # 首先修改测试文件，取消skip装饰器
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_ragflow_chat.py')
        with open(test_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 临时取消skip
        modified_content = content.replace('@unittest.skip("需要真实API配置才能运行")', '# @unittest.skip("需要真实API配置才能运行")')
        
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        try:
            result = subprocess.run([
                sys.executable, 
                '-c',
                'import unittest; from test_ragflow_chat import TestRAGFlowChatIntegration; unittest.main(module=None, argv=[""], testRunner=unittest.TextTestRunner(verbosity=2), testLoader=unittest.TestLoader().loadTestsFromTestCase(TestRAGFlowChatIntegration))'
            ], cwd=os.path.dirname(__file__), capture_output=True, text=True)
            
            print(result.stdout)
            if result.stderr:
                print("错误输出:")
                print(result.stderr)
                
        finally:
            # 恢复原始文件
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ 运行集成测试时出错: {e}")
        return False

def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查依赖...")
    
    try:
        import requests
        print("✅ requests 已安装")
    except ImportError:
        print("❌ requests 未安装，请运行: pip install requests")
        return False
        
    return True

def main():
    """主函数"""
    print("🚀 RAGFlow Chat Plugin 测试工具")
    print(f"📋 测试 Dialog ID: f48e23383df611f09c9b26d7d2ef55ce")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 运行单元测试
    unit_test_success = run_unit_tests()
    
    # 运行集成测试
    integration_test_success = run_integration_test()
    
    # 总结结果
    print("\n" + "=" * 60)
    print("📊 测试结果总结:")
    print(f"  单元测试: {'✅ 通过' if unit_test_success else '❌ 失败'}")
    print(f"  集成测试: {'✅ 通过' if integration_test_success else '❌ 失败'}")
    
    if unit_test_success and integration_test_success:
        print("\n🎉 所有测试都通过了！接口功能正常。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查配置和网络连接。")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 