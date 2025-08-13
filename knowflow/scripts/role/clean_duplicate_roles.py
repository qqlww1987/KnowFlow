#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理重复的角色和用户角色分配记录
"""

import sys
import os
# 添加server目录到Python路径
# 从 scripts/role 向上两级到 knowflow，然后进入 server
script_dir = os.path.dirname(os.path.abspath(__file__))
knowflow_dir = os.path.dirname(os.path.dirname(script_dir))
server_dir = os.path.join(knowflow_dir, 'server')
sys.path.append(server_dir)

from database import get_db_connection

def clean_duplicate_roles():
    """清理重复的角色和用户角色分配记录"""
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        print("=== 清理重复的角色和用户角色分配记录 ===")
        
        # 1. 查看重复的角色
        print("\n1. 检查重复的角色:")
        cursor.execute("""
            SELECT code, COUNT(*) as count
            FROM rbac_roles
            GROUP BY code
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicate_roles = cursor.fetchall()
        
        for role in duplicate_roles:
            code, count = role
            print(f"  角色代码: {code}, 重复次数: {count}")
        
        # 2. 保留每个角色代码的第一个记录，删除其他重复记录
        print("\n2. 清理重复角色记录:")
        for role in duplicate_roles:
            code = role[0]
            
            # 获取该角色代码的所有记录
            cursor.execute("""
                SELECT id, name, code, created_at
                FROM rbac_roles
                WHERE code = %s
                ORDER BY id ASC
            """, (code,))
            role_records = cursor.fetchall()
            
            if len(role_records) > 1:
                # 保留第一个记录，删除其他记录
                keep_id = role_records[0][0]
                delete_ids = [record[0] for record in role_records[1:]]
                
                print(f"  角色 {code}: 保留ID {keep_id}, 删除ID {delete_ids}")
                
                # 先删除用户角色分配中引用这些重复角色的记录
                for delete_id in delete_ids:
                    cursor.execute("""
                        DELETE FROM rbac_user_roles
                        WHERE role_id = %s
                    """, (delete_id,))
                    print(f"    删除角色ID {delete_id} 的用户角色分配记录")
                
                # 删除重复的角色记录
                cursor.execute("""
                    DELETE FROM rbac_roles
                    WHERE id IN ({})
                """.format(','.join(['%s'] * len(delete_ids))), delete_ids)
                print(f"    删除重复的角色记录: {delete_ids}")
        
        # 3. 检查用户角色分配中的重复记录
        print("\n3. 检查重复的用户角色分配:")
        cursor.execute("""
            SELECT user_id, role_id, COUNT(*) as count
            FROM rbac_user_roles
            GROUP BY user_id, role_id
            HAVING COUNT(*) > 1
        """)
        duplicate_user_roles = cursor.fetchall()
        
        for user_role in duplicate_user_roles:
            user_id, role_id, count = user_role
            print(f"  用户ID: {user_id}, 角色ID: {role_id}, 重复次数: {count}")
            
            # 保留第一个记录，删除其他重复记录
            cursor.execute("""
                SELECT id FROM rbac_user_roles
                WHERE user_id = %s AND role_id = %s
                ORDER BY id ASC
            """, (user_id, role_id))
            assignment_records = cursor.fetchall()
            
            if len(assignment_records) > 1:
                keep_id = assignment_records[0][0]
                delete_ids = [record[0] for record in assignment_records[1:]]
                
                cursor.execute("""
                    DELETE FROM rbac_user_roles
                    WHERE id IN ({})
                """.format(','.join(['%s'] * len(delete_ids))), delete_ids)
                print(f"    删除重复的用户角色分配记录: {delete_ids}")
        
        db.commit()
        print("\n✓ 清理完成")
        
        # 4. 验证清理结果
        print("\n4. 验证清理结果:")
        
        # 检查角色是否还有重复
        cursor.execute("""
            SELECT code, COUNT(*) as count
            FROM rbac_roles
            GROUP BY code
            HAVING COUNT(*) > 1
        """)
        remaining_duplicate_roles = cursor.fetchall()
        
        if remaining_duplicate_roles:
            print(f"  ✗ 仍有重复角色: {len(remaining_duplicate_roles)} 个")
        else:
            print(f"  ✓ 无重复角色")
        
        # 检查用户角色分配是否还有重复
        cursor.execute("""
            SELECT user_id, role_id, COUNT(*) as count
            FROM rbac_user_roles
            GROUP BY user_id, role_id
            HAVING COUNT(*) > 1
        """)
        remaining_duplicate_user_roles = cursor.fetchall()
        
        if remaining_duplicate_user_roles:
            print(f"  ✗ 仍有重复用户角色分配: {len(remaining_duplicate_user_roles)} 个")
        else:
            print(f"  ✓ 无重复用户角色分配")
        
        # 显示tom用户的最终角色
        print("\n5. tom用户的最终角色:")
        cursor.execute("""
            SELECT r.name, r.code, ur.is_active
            FROM user u
            JOIN rbac_user_roles ur ON u.id = ur.user_id
            JOIN rbac_roles r ON ur.role_id = r.id
            WHERE u.nickname = 'tom'
            ORDER BY r.code
        """)
        tom_roles = cursor.fetchall()
        
        for role in tom_roles:
            name, code, is_active = role
            status = "激活" if is_active else "未激活"
            print(f"  - {name} ({code}) - {status}")
        
        cursor.close()
        db.close()
        
    except Exception as e:
        print(f"清理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clean_duplicate_roles()