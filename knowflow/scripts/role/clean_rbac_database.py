#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RBAC数据库清空脚本
清空所有RBAC相关表的数据，避免脏数据影响
"""

import sys
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# 添加server目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

try:
    from database import get_db_connection
except ImportError:
    # 如果无法导入，使用默认配置
    def get_db_connection():
        """建立数据库连接"""
        try:
            connection = mysql.connector.connect(
                host='localhost',
                database='rag_flow',
                user='root',
                password='infini_rag_flow',
                port=5455
            )
            return connection
        except Error as e:
            print(f"数据库连接错误: {e}")
            return None

def clean_rbac_database():
    """清空RBAC数据库中的所有数据"""
    connection = None
    cursor = None
    
    try:
        # 建立数据库连接
        connection = get_db_connection()
        if not connection:
            print("❌ 无法连接到数据库")
            return False
            
        cursor = connection.cursor()
        
        print("🚀 开始清空RBAC数据库...")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # 禁用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        print("✓ 禁用外键检查")
        
        # 定义需要清空的RBAC表（按依赖关系排序）
        rbac_tables = [
            'rbac_role_permissions',  # 角色权限关联表（依赖角色和权限）
            'rbac_user_roles',        # 用户角色关联表（依赖角色）
            'rbac_team_roles',        # 团队角色表
            'rbac_permissions',       # 权限表
            'rbac_roles'              # 角色表
        ]
        
        # 统计清空前的数据量
        print("\n📊 清空前数据统计:")
        total_records = 0
        for table in rbac_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} 条记录")
                total_records += count
            except Error as e:
                print(f"  {table}: 表不存在或查询失败 ({e})")
        
        print(f"\n总计: {total_records} 条记录")
        
        if total_records == 0:
            print("\n✅ 数据库已经是空的，无需清空")
            return True
            
        # 确认清空操作
        print(f"\n⚠️  即将清空 {len(rbac_tables)} 个RBAC表中的所有数据")
        confirm = input("确认继续吗？(y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ 操作已取消")
            return False
            
        # 清空表数据
        print("\n🗑️  开始清空表数据...")
        cleared_tables = 0
        
        for table in rbac_tables:
            try:
                # 使用TRUNCATE清空表（比DELETE更快）
                cursor.execute(f"TRUNCATE TABLE {table}")
                print(f"✓ 已清空表: {table}")
                cleared_tables += 1
            except Error as e:
                try:
                    # 如果TRUNCATE失败，尝试DELETE
                    cursor.execute(f"DELETE FROM {table}")
                    print(f"✓ 已清空表: {table} (使用DELETE)")
                    cleared_tables += 1
                except Error as e2:
                    print(f"❌ 清空表失败: {table} - {e2}")
        
        # 重置自增ID
        print("\n🔄 重置自增ID...")
        for table in rbac_tables:
            try:
                cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
                print(f"✓ 已重置 {table} 的自增ID")
            except Error as e:
                print(f"⚠️  重置 {table} 自增ID失败: {e}")
        
        # 启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("✓ 启用外键检查")
        
        # 提交事务
        connection.commit()
        
        # 验证清空结果
        print("\n📊 清空后数据统计:")
        remaining_records = 0
        for table in rbac_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  {table}: {count} 条记录")
                remaining_records += count
            except Error as e:
                print(f"  {table}: 查询失败 ({e})")
        
        print("\n" + "=" * 50)
        if remaining_records == 0:
            print(f"🎉 RBAC数据库清空完成！")
            print(f"✓ 成功清空 {cleared_tables} 个表")
            print(f"✓ 清空时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        else:
            print(f"⚠️  清空不完整，仍有 {remaining_records} 条记录")
            return False
            
    except Error as e:
        print(f"❌ 清空过程中发生错误: {e}")
        if connection:
            connection.rollback()
        return False
        
    finally:
        # 关闭数据库连接
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            print("\n🔌 数据库连接已关闭")

def main():
    """主函数"""
    print("RBAC数据库清空工具")
    print("=" * 30)
    
    success = clean_rbac_database()
    
    if success:
        print("\n✅ 清空操作成功完成")
        return 0
    else:
        print("\n❌ 清空操作失败")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)