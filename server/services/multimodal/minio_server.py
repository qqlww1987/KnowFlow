import os
import sys
import argparse
from minio import Minio
from dotenv import load_dotenv
from io import BytesIO
import json


load_dotenv(".env")

def is_running_in_docker():
     # 检查是否存在/.dockerenv文件
     docker_env = os.path.exists('/.dockerenv')
     # 或者检查cgroup中是否包含docker字符串
     try:
         with open('/proc/self/cgroup', 'r') as f:
             return docker_env or 'docker' in f.read()
     except:
         return docker_env
    

# MINIO_HOST = 'host.docker.internal' if is_running_in_docker() else 'localhost'
MINIO_HOST = 'www.knowflowchat.cn'
 # MinIO连接配置
MINIO_CONFIG = {
     "endpoint": f"{MINIO_HOST}:{os.getenv('MINIO_PORT', '9000')}",
     "access_key": os.getenv("MINIO_USER", "rag_flow"),
     "secret_key": os.getenv("MINIO_PASSWORD", "infini_rag_flow"),
     "secure": False
 }

def get_minio_client():
     """创建MinIO客户端"""
     return Minio(
         endpoint=MINIO_CONFIG["endpoint"],
         access_key=MINIO_CONFIG["access_key"],
         secret_key=MINIO_CONFIG["secret_key"],
         secure=MINIO_CONFIG["secure"]
     )



def upload_file_to_minio(kb_id, file_path):
    """上传文件到MinIO"""
    minio_client = get_minio_client()

      # 检查bucket是否存在
    if not minio_client.bucket_exists(kb_id):
        print(f"[ERROR] Bucket {kb_id} 不存在")
        return

    print(f"[INFO] 处理图像块: {file_path}")
    try:
        # 获取图片路径
        img_path = file_path    
        if os.path.exists(img_path):
            # 直接使用文件名作为img_key
            img_key = os.path.basename(img_path)
            print(f"[INFO] img_key: {img_key}")
            
            # 读取图片内容
            with open(img_path, 'rb') as img_file:
                img_data = img_file.read()
                
            # 设置图片的Content-Type
            content_type = f"image/{os.path.splitext(img_path)[1][1:].lower()}"
            if content_type == "image/jpg":
                content_type = "image/jpeg"
            
            # 上传图片到MinIO
            minio_client.put_object(
                bucket_name=kb_id,
                object_name=img_key,
                data=BytesIO(img_data),
                length=len(img_data),
                content_type=content_type
            )
            
            # 设置图片的公共访问权限
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{kb_id}/*"]
                    }
                ]
            }

            minio_client.set_bucket_policy(kb_id, json.dumps(policy))
            
            print(f"[SUCCESS] 成功上传图片: {img_key}")
        else:
            print(f"[WARNING] 图片文件不存在: {img_path}")
    except Exception as e:
        print(f"[ERROR] 上传图片失败: {str(e)}")


def  upload_directory_to_minio(kb_id, image_dir):
    """上传目录下的所有图片到MinIO
    
    Args:
        kb_id: 知识库ID，用作bucket名称
        image_dir: 图片目录路径
    """
    image_dir = os.path.abspath(image_dir)
    print(f"[INFO] 开始上传目录: {image_dir}")
    
    # 确保目录存在
    if not os.path.exists(image_dir):
        print(f"[ERROR] 目录不存在: {image_dir}")
        return
        
    # 遍历目录下的所有图片
    for img_file in os.listdir(image_dir):
        if img_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            img_path = os.path.join(image_dir, img_file)
            upload_file_to_minio(
                kb_id=kb_id,
                file_path=img_path
            )
    print(f"[SUCCESS] 目录上传完成: {image_dir}")

     # 清空目录中的所有图片
    print(f"[INFO] 清空目录: {image_dir}")
    for img_file in os.listdir(image_dir):
        if img_file.lower().endswith(('.png', '.jpg', '.jpeg')):
            img_path = os.path.join(image_dir, img_file)
            os.remove(img_path)
   


def test_minio_bucket(kb_id):
    minio_client = get_minio_client()
    print("[DEBUG] 当前 buckets：", [b.name for b in minio_client.list_buckets()])
    exists = minio_client.bucket_exists(kb_id)
    print(f"[DEBUG] bucket_exists('{kb_id}') = {exists}")


def get_image_url(kb_id, image_key):
    """获取图片的公共访问URL
    
    Args:
        kb_id: 知识库ID
        image_key: 图片在MinIO中的键
            
    Returns:
        图片的公共访问URL
    """
    try:


        # 获取MinIO服务器配置
        minio_endpoint = MINIO_CONFIG["endpoint"].split(':')[0] 
        # use_ssl = MINIO_CONFIG["secure"]
    
        # 构建URL
        # protocol = "https" if use_ssl else "http"
        protocol  = "https"
        
        # 配置了反向代理
        url = f"{protocol}://{minio_endpoint}/minio/{kb_id}/{image_key}"
        print(f"[DEBUG] 图片URL: {url}")
        
        return url
    except Exception as e:
        print(f"[ERROR] 获取图片URL失败: {str(e)}")
        return None

if __name__ == "__main__":

    upload_directory_to_minio   (
        kb_id="86e6f8481a0e11f088985225ee02e7da",
        image_dir="output/images"
    )
    get_image_url("86e6f8481a0e11f088985225ee02e7da", "1eeff4359ed88f93ef265893bc1f64ad00865cdcb4dac1d30dab7f6a27f614b4.jpg")
    

     






