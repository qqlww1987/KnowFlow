import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from io import BytesIO
import json
import time
from database import get_minio_client, MINIO_CONFIG

SUPPORTED_IMAGE_TYPES = ('.png', '.jpg', '.jpeg')

def _check_bucket_public_access(minio_client, kb_id):
    """检查存储桶是否为公开访问（辅助函数）"""
    try:
        # 尝试获取bucket策略
        policy_str = minio_client.get_bucket_policy(kb_id)
        if policy_str:
            policy = json.loads(policy_str)
            # 检查策略是否包含公开访问权限
            for statement in policy.get("Statement", []):
                if statement.get("Effect") == "Allow":
                    principal_aws = statement.get("Principal", {}).get("AWS")
                    # 支持Principal.AWS为字符串"*"或数组["*"]的情况
                    is_principal_public = (
                        principal_aws == "*" or 
                        (isinstance(principal_aws, list) and "*" in principal_aws)
                    )
                    
                    if (is_principal_public and "s3:GetObject" in statement.get("Action", [])):
                        return True
        return False
    except Exception as e:
        print(f"[DEBUG] 检查bucket公开访问权限时发生错误: {str(e)}")
        return False

def _set_bucket_policy(minio_client, kb_id):
    """设置存储桶的访问策略（内部方法）"""
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
                f"arn:aws:s3:::{kb_id}",
                f"arn:aws:s3:::{kb_id}/*"
            ]
        }]
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 设置存储桶策略
            minio_client.set_bucket_policy(kb_id, json.dumps(policy))
            
            # 验证策略是否设置成功
            try:
                current_policy = minio_client.get_bucket_policy(kb_id)
                if current_policy:
                    print(f"[SUCCESS] 已成功设置bucket {kb_id} 为公开访问")
                    return True
                else:
                    print(f"[WARNING] 策略设置后验证为空，尝试重试 {attempt + 1}/{max_retries}")
            except Exception as verify_e:
                print(f"[WARNING] 无法验证策略设置结果: {str(verify_e)}")
                # 如果无法验证，假设设置成功（有些MinIO版本可能不支持get_bucket_policy）
                print(f"[INFO] 已设置bucket {kb_id} 为公开访问（无法验证）")
                return True
                
        except Exception as e:
            print(f"[ERROR] 设置bucket策略失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                print(f"[ERROR] 多次尝试后仍无法设置bucket {kb_id} 的策略，请手动设置")
                # 打印手动设置的说明
                print(f"[INFO] 手动设置方法：")
                print(f"[INFO] 1. 打开MinIO控制台: http://{MINIO_CONFIG['endpoint']}")
                print(f"[INFO] 2. 进入bucket: {kb_id}")
                print(f"[INFO] 3. 在Access Policy中设置为public或添加以下策略:")
                print(f"[INFO] {json.dumps(policy, indent=2)}")
                return False
            else:
                time.sleep(1)  # 等待1秒后重试
    
    return False

def _ensure_bucket_exists(minio_client, kb_id):
    """确保桶存在，不存在则创建并设置策略"""
    if not minio_client.bucket_exists(kb_id):
        print(f"[INFO] Bucket {kb_id} 不存在，正在创建...")
        minio_client.make_bucket(kb_id)
        print(f"[Parser-INFO] 创建MinIO桶: {kb_id}")
        
        # 尝试设置策略，如果失败也不影响bucket的创建
        if not _set_bucket_policy(minio_client, kb_id):
            print(f"[WARNING] Bucket {kb_id} 创建成功，但策略设置失败，可能需要手动配置")
    else:
        # 桶已存在，检查策略是否已设置
        try:
            current_policy = minio_client.get_bucket_policy(kb_id)
            if not current_policy:
                print(f"[INFO] Bucket {kb_id} 存在但未设置策略，正在设置...")
                _set_bucket_policy(minio_client, kb_id)
        except Exception as e:
            print(f"[WARNING] 无法检查bucket {kb_id} 的策略状态: {str(e)}")
            # 尝试重新设置策略
            _set_bucket_policy(minio_client, kb_id)

def upload_file_to_minio(kb_id, file_path):
    """上传单个文件到MinIO"""
    minio_client = get_minio_client()
    _ensure_bucket_exists(minio_client, kb_id)

    print(f"[INFO] 处理图像: {file_path}")
    if not os.path.exists(file_path):
        print(f"[WARNING] 图片文件不存在: {file_path}")
        return False

    img_key = os.path.basename(file_path)
    print(f"[INFO] img_key: {img_key}")

    try:
        with open(file_path, 'rb') as img_file:
            img_data = img_file.read()

        content_type = f"image/{os.path.splitext(file_path)[1][1:].lower()}"
        if content_type == "image/jpg":
            content_type = "image/jpeg"

        minio_client.put_object(
            bucket_name=kb_id,
            object_name=img_key,
            data=BytesIO(img_data),
            length=len(img_data),
            content_type=content_type
        )
        print(f"[SUCCESS] 成功上传图片: {img_key}")
        return True

    except Exception as e:
        print(f"[ERROR] 上传图片失败: {str(e)}")
        return False

def upload_directory_to_minio(kb_id, image_dir):
    """上传目录下的所有图片到MinIO"""
    image_dir = os.path.abspath(image_dir)
    print(f"[INFO] 开始上传目录: {image_dir}")

    if not os.path.exists(image_dir):
        print(f"[ERROR] 目录不存在: {image_dir}")
        return False

    success_count = 0
    total_count = 0

    for img_file in os.listdir(image_dir):
        if img_file.lower().endswith(SUPPORTED_IMAGE_TYPES):
            total_count += 1
            img_path = os.path.join(image_dir, img_file)
            if upload_file_to_minio(kb_id=kb_id, file_path=img_path):
                success_count += 1
                os.remove(img_path)  # 上传成功后删除文件

    print(f"[INFO] 上传完成: 成功 {success_count}/{total_count}")
    return success_count == total_count

def get_image_url(kb_id, image_key):
    """获取图片的公共访问URL"""
    try:
        minio_endpoint = MINIO_CONFIG["endpoint"]
        use_ssl = MINIO_CONFIG["secure"]
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{minio_endpoint}/{kb_id}/{image_key}"  

        # 如果图片显示 CROS 跨域问题，此时可以通过 nginx 反向代理实现或者配置 minio 证书解决，下面给出 nginx 反向代理方案:
        # 1. 替换上述 url 实现：
        #  RAGFLOW_BASE_URL = os.getenv('RAGFLOW_BASE_URL') 
        #  url = f"{RAGFLOW_BASE_URL}/minio/{kb_id}/{image_key}"   
        # 2. 在服务器的 nginx 配置如下：
        #   location /minio/ {
        #        proxy_pass http://localhost:9000/;
        #       proxy_set_header Host $host;
        #        proxy_set_header X-Real-IP $remote_addr;
        #       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        #       proxy_set_header X-Forwarded-Proto $scheme;
        #       # 去掉 /minio 前缀
        #       rewrite ^/minio/(.*)$ /$1 break;
        #    }

        print(f"[DEBUG] 图片URL: {url}")
        return url
    except Exception as e:
        print(f"[ERROR] 获取图片URL失败: {str(e)}")
        return None

if __name__ == "__main__":
    test_kb_id = "86e6f8481a0e11f088985225ee02e7da"
    test_image_dir = "output/images"
    upload_directory_to_minio(kb_id=test_kb_id, image_dir=test_image_dir)
    get_image_url(test_kb_id, "test.jpg")
    

     






