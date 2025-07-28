#!/usr/bin/env python3
"""
MinIO Bucket 权限诊断和修复工具

用法:
python fix_bucket_policy.py [bucket_id]

如果不提供bucket_id，将列出所有bucket并让用户选择
"""

import sys
import os

# 获取当前脚本的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 计算到server目录的路径（向上3级：mineru_parse -> knowledgebases -> services -> server）
server_dir = os.path.join(current_dir, '..', '..', '..')
server_dir = os.path.abspath(server_dir)
# 添加server目录到Python路径
sys.path.insert(0, server_dir)

import json
from database import get_minio_client, MINIO_CONFIG
from minio.error import S3Error

def check_bucket_policy(minio_client, bucket_id):
    """检查bucket策略"""
    print(f"\n=== 检查 Bucket {bucket_id} 的策略 ===")
    
    try:
        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_id):
            print(f"❌ Bucket {bucket_id} 不存在")
            return False
            
        print(f"✅ Bucket {bucket_id} 存在")
        
        # 获取当前策略
        try:
            policy_str = minio_client.get_bucket_policy(bucket_id)
            if policy_str:
                policy = json.loads(policy_str)
                print(f"📋 当前策略:")
                print(json.dumps(policy, indent=2))
                
                # 检查是否为公开访问
                is_public = False
                for statement in policy.get("Statement", []):
                    if statement.get("Effect") == "Allow":
                        principal_aws = statement.get("Principal", {}).get("AWS")
                        # 支持Principal.AWS为字符串"*"或数组["*"]的情况
                        is_principal_public = (
                            principal_aws == "*" or 
                            (isinstance(principal_aws, list) and "*" in principal_aws)
                        )
                        
                        if (is_principal_public and "s3:GetObject" in statement.get("Action", [])):
                            is_public = True
                            break
                
                if is_public:
                    print("✅ Bucket 已设置为公开访问")
                    return True
                else:
                    print("❌ Bucket 未设置为公开访问")
                    return False
            else:
                print("❌ Bucket 没有设置任何策略")
                return False
                
        except S3Error as e:
            if e.code == "NoSuchBucketPolicy":
                print("❌ Bucket 没有设置策略")
                return False
            else:
                print(f"❌ 获取策略时发生错误: {str(e)}")
                return False
                
    except Exception as e:
        print(f"❌ 检查bucket时发生错误: {str(e)}")
        return False

def set_bucket_public_policy(minio_client, bucket_id):
    """设置bucket为公开访问"""
    print(f"\n=== 设置 Bucket {bucket_id} 为公开访问 ===")
    
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                f"arn:aws:s3:::{bucket_id}",
                f"arn:aws:s3:::{bucket_id}/*"
            ]
        }]
    }
    
    try:
        print("🔧 正在设置策略...")
        minio_client.set_bucket_policy(bucket_id, json.dumps(policy))
        print("✅ 策略设置完成")
        
        # 验证策略是否生效
        print("🔍 验证策略是否生效...")
        if check_bucket_policy(minio_client, bucket_id):
            print("🎉 策略设置成功并验证通过!")
            return True
        else:
            print("❌ 策略设置后验证失败")
            return False
            
    except Exception as e:
        print(f"❌ 设置策略时发生错误: {str(e)}")
        return False

def list_all_buckets(minio_client):
    """列出所有bucket"""
    try:
        buckets = minio_client.list_buckets()
        print("\n=== 所有 Bucket 列表 ===")
        for i, bucket in enumerate(buckets, 1):
            print(f"{i}. {bucket.name} (创建时间: {bucket.creation_date})")
        return [bucket.name for bucket in buckets]
    except Exception as e:
        print(f"❌ 获取bucket列表时发生错误: {str(e)}")
        return []

def main():
    """主函数"""
    print("MinIO Bucket 权限诊断和修复工具")
    print("=" * 40)
    
    try:
        # 连接MinIO
        print("🔗 连接到MinIO...")
        minio_client = get_minio_client()
        print(f"✅ 连接成功: {MINIO_CONFIG['endpoint']}")
        
        # 获取bucket ID
        if len(sys.argv) > 1:
            bucket_id = sys.argv[1]
        else:
            # 列出所有bucket让用户选择
            bucket_names = list_all_buckets(minio_client)
            if not bucket_names:
                print("❌ 没有找到任何bucket")
                return
                
            print("\n请选择要检查的bucket:")
            try:
                choice = int(input("请输入序号: "))
                if 1 <= choice <= len(bucket_names):
                    bucket_id = bucket_names[choice - 1]
                else:
                    print("❌ 无效的选择")
                    return
            except ValueError:
                print("❌ 请输入有效的数字")
                return
        
        print(f"\n🎯 目标 Bucket: {bucket_id}")
        
        # 检查当前策略
        is_public = check_bucket_policy(minio_client, bucket_id)
        
        if not is_public:
            # 询问是否要修复
            fix = input("\n是否要设置此bucket为公开访问? (y/N): ").lower().strip()
            if fix in ['y', 'yes']:
                set_bucket_public_policy(minio_client, bucket_id)
            else:
                print("❌ 用户取消修复操作")
        
        # 提供手动修复的指导
        print(f"\n📖 手动修复指南:")
        print(f"1. 打开MinIO控制台: http://{MINIO_CONFIG['endpoint']}")
        print(f"2. 使用账号: {MINIO_CONFIG['access_key']}")
        print(f"3. 进入bucket: {bucket_id}")
        print(f"4. 在 Access Policy 中设置为 public 或添加自定义策略")
        
    except Exception as e:
        print(f"❌ 程序执行时发生错误: {str(e)}")

if __name__ == "__main__":
    main() 