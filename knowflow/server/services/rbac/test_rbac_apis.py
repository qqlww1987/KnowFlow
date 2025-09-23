#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC API 完整测试脚本
测试所有RBAC相关接口的功能和权限控制
"""

import requests
import json
import sys
from typing import Dict, Any, List
from datetime import datetime

class RBACAPITester:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = "", response_data: Any = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
    
    def make_request(self, method: str, endpoint: str, data: Dict = None, expected_status: int = 200, params: Dict = None) -> tuple:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            try:
                response_data = response.json()
            except:
                response_data = response.text
            
            success = response.status_code == expected_status
            return success, response.status_code, response_data
            
        except Exception as e:
            return False, 0, str(e)
    
    def test_user_role_management(self):
        """测试用户角色管理接口"""
        print("\n=== 测试用户角色管理 ===")
        
        # 1. 为用户分配角色
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/users/test_user/roles",
            {
                "role_code": "editor",
                "resource_type": "knowledgebase",
                "resource_id": "kb_001"
            }
        )
        self.log_test("分配用户角色", success, f"状态码: {status}", data)
        
        # 2. 查询用户角色
        success, status, data = self.make_request(
            "GET", 
            "/api/v1/rbac/users/test_user/roles"
        )
        self.log_test("查询用户角色", success, f"状态码: {status}, 角色数量: {len(data) if isinstance(data, list) else 0}", data)
        
        # 3. 查询用户有效权限
        success, status, data = self.make_request(
            "GET", 
            "/api/permissions/user/test_user/effective",
            params={"resource_type": "knowledgebase", "resource_id": "kb_001", "tenant_id": "default"}
        )
        self.log_test("查询用户有效权限", success, f"状态码: {status}", data)
        
        # 4. 删除用户角色
        success, status, data = self.make_request(
            "DELETE", 
            "/api/v1/rbac/users/test_user/roles/editor?resource_type=knowledgebase&resource_id=kb_001"
        )
        self.log_test("删除用户角色", success, f"状态码: {status}", data)
    
    def test_permission_check(self):
        """测试权限检查接口"""
        print("\n=== 测试权限检查 ===")
        
        # 先分配一个角色用于测试
        self.make_request(
            "POST", 
            "/api/v1/rbac/users/test_user2/roles",
            {
                "role_code": "viewer",
                "resource_type": "knowledgebase",
                "resource_id": "kb_002"
            }
        )
        
        # 1. 详细权限检查
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/check",
            {
                "user_id": "test_user2",
                "resource_type": "knowledgebase",
                "resource_id": "kb_002",
                "permission_type": "read"
            }
        )
        self.log_test("详细权限检查-读权限", success and data.get("has_permission"), f"状态码: {status}, 有权限: {data.get('has_permission') if isinstance(data, dict) else False}", data)
        
        # 2. 检查写权限（应该被拒绝）
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/check",
            {
                "user_id": "test_user2",
                "resource_type": "knowledgebase",
                "resource_id": "kb_002",
                "permission_type": "write"
            }
        )
        self.log_test("详细权限检查-写权限", success and not data.get("has_permission"), f"状态码: {status}, 无权限: {not data.get('has_permission') if isinstance(data, dict) else False}", data)
        
        # 3. 简化权限检查
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/simple-check",
            {
                "user_id": "test_user2",
                "permission_code": "kb_read",
                "resource_id": "kb_002"
            }
        )
        self.log_test("简化权限检查", success and data.get("has_permission"), f"状态码: {status}, 有权限: {data.get('has_permission') if isinstance(data, dict) else False}", data)
    
    def test_team_management(self):
        """测试团队管理接口"""
        print("\n=== 测试团队管理 ===")
        
        # 1. 创建团队
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/teams",
            {
                "name": "测试团队",
                "description": "用于API测试的团队",
                "owner_id": "system"
            }
        )
        team_id = data.get("data", {}).get("id") if success and isinstance(data, dict) else "test_team"
        self.log_test("创建团队", success, f"状态码: {status}", data)
        
        # 2. 查询团队列表
        success, status, data = self.make_request(
            "GET", 
            "/api/v1/teams"
        )
        team_count = len(data.get("data", {}).get("list", [])) if isinstance(data, dict) else 0
        self.log_test("查询团队列表", success, f"状态码: {status}, 团队数量: {team_count}", data)
        
        # 3. 添加团队成员
        success, status, data = self.make_request(
            "POST", 
            f"/api/v1/teams/{team_id}/members",
            {
                "userId": "team_member1",
                "role": "member"
            }
        )
        self.log_test("添加团队成员", success, f"状态码: {status}", data)
        
        # 4. 查询团队成员
        success, status, data = self.make_request(
            "GET", 
            f"/api/v1/teams/{team_id}/members"
        )
        member_count = len(data.get("data", [])) if isinstance(data, dict) else 0
        self.log_test("查询团队成员", success, f"状态码: {status}, 成员数量: {member_count}", data)
        
        # 4. 为团队分配角色
        success, status, data = self.make_request(
            "POST", 
            f"/api/v1/teams/{team_id}/roles",
            {
                "role_code": "editor",
                "resource_type": "knowledgebase",
                "resource_id": "test_kb",
                "granted_by": "system",
                "tenant_id": "default"
            }
        )
        self.log_test("为团队分配角色", success, f"状态码: {status}", data)
        
        # 6. 查询团队角色
        success, status, data = self.make_request(
            "GET", 
            f"/api/v1/teams/{team_id}/roles"
        )
        self.log_test("查询团队角色", success, f"状态码: {status}", data)
    
    def test_system_management(self):
        """测试系统管理接口"""
        print("\n=== 测试系统管理 ===")
        
        # 1. 查询所有角色
        success, status, data = self.make_request(
            "GET", 
            "/api/v1/rbac/roles"
        )
        self.log_test("查询所有角色", success, f"状态码: {status}, 角色数量: {len(data) if isinstance(data, list) else 0}", data)
        
        # 2. 查询所有权限
        success, status, data = self.make_request(
            "GET", 
            "/api/v1/rbac/permissions"
        )
        self.log_test("查询所有权限", success, f"状态码: {status}, 权限数量: {len(data) if isinstance(data, list) else 0}", data)
        
        # 3. 查询角色权限映射
        success, status, data = self.make_request(
            "GET", 
            "/api/v1/rbac/roles/viewer/permissions"
        )
        self.log_test("查询角色权限映射", success, f"状态码: {status}", data)
    
    def test_super_admin_permissions(self):
        """测试超级管理员权限"""
        print("\n=== 测试超级管理员权限 ===")
        
        # 1. 检查system用户的超级管理员权限
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/check",
            {
                "user_id": "system",
                "resource_type": "knowledgebase",
                "resource_id": "any_kb",
                "permission_type": "admin"
            }
        )
        self.log_test("超级管理员-管理权限", success and data.get("has_permission"), f"状态码: {status}, 有权限: {data.get('has_permission') if isinstance(data, dict) else False}", data)
        
        # 2. 查询超级管理员有效权限
        success, status, data = self.make_request(
            "GET", 
            "/api/permissions/user/system/effective",
            params={"resource_type": "knowledgebase", "resource_id": "any_kb", "tenant_id": "default"}
        )
        self.log_test("超级管理员-有效权限", success, f"状态码: {status}, 权限数量: {len(data.get('data', {})) if isinstance(data, dict) else 0}", data)
    
    def test_edge_cases(self):
        """测试边界情况"""
        print("\n=== 测试边界情况 ===")
        
        # 1. 不存在的用户权限检查
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/check",
            {
                "user_id": "nonexistent_user",
                "resource_type": "knowledgebase",
                "resource_id": "kb_001",
                "permission_type": "read"
            }
        )
        self.log_test("不存在用户权限检查", success and not data.get("has_permission"), f"状态码: {status}, 无权限: {not data.get('has_permission') if isinstance(data, dict) else True}", data)
        
        # 2. 无效的角色分配
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/users/test_user/roles",
            {
                "role_code": "invalid_role",
                "resource_type": "knowledgebase",
                "resource_id": "kb_001"
            },
            expected_status=400
        )
        self.log_test("无效角色分配", success, f"状态码: {status} (应为400)", data)
        
        # 3. 无效的权限类型检查
        success, status, data = self.make_request(
            "POST", 
            "/api/v1/rbac/permissions/check",
            {
                "user_id": "test_user",
                "resource_type": "knowledgebase",
                "resource_id": "kb_001",
                "permission_type": "invalid_permission"
            },
            expected_status=400
        )
        self.log_test("无效权限类型检查", success, f"状态码: {status} (应为400)", data)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始RBAC API完整测试")
        print(f"测试服务器: {self.base_url}")
        print("=" * 50)
        
        try:
            # 检查服务器连接
            success, status, data = self.make_request("GET", "/api/v1/rbac/roles")
            if not success:
                print(f"❌ 无法连接到服务器 {self.base_url}")
                return False
            
            # 运行各项测试
            self.test_user_role_management()
            self.test_permission_check()
            self.test_team_management()
            self.test_system_management()
            self.test_super_admin_permissions()
            self.test_edge_cases()
            
            # 统计测试结果
            total_tests = len(self.test_results)
            passed_tests = sum(1 for result in self.test_results if result["success"])
            failed_tests = total_tests - passed_tests
            
            print("\n" + "=" * 50)
            print("📊 测试结果统计")
            print(f"总测试数: {total_tests}")
            print(f"通过: {passed_tests} ✅")
            print(f"失败: {failed_tests} ❌")
            print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
            
            if failed_tests > 0:
                print("\n❌ 失败的测试:")
                for result in self.test_results:
                    if not result["success"]:
                        print(f"  - {result['test_name']}: {result['message']}")
            
            return failed_tests == 0
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {str(e)}")
            return False
    
    def save_results(self, filename: str = "rbac_test_results.json"):
        """保存测试结果到文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "test_summary": {
                    "total_tests": len(self.test_results),
                    "passed_tests": sum(1 for r in self.test_results if r["success"]),
                    "failed_tests": sum(1 for r in self.test_results if not r["success"]),
                    "test_time": datetime.now().isoformat()
                },
                "test_results": self.test_results
            }, f, indent=2, ensure_ascii=False)
        print(f"📄 测试结果已保存到: {filename}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RBAC API 完整测试脚本")
    parser.add_argument("--url", default="http://localhost:5000", help="API服务器地址")
    parser.add_argument("--save", action="store_true", help="保存测试结果到文件")
    
    args = parser.parse_args()
    
    tester = RBACAPITester(args.url)
    success = tester.run_all_tests()
    
    if args.save:
        tester.save_results()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()