import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from io import BytesIO
import json
from database import get_minio_client,MINIO_CONFIG

SUPPORTED_IMAGE_TYPES = ('.png', '.jpg', '.jpeg')


def _set_bucket_policy(minio_client, kb_id):
    """设置存储桶的访问策略（内部方法）"""
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{kb_id}/*"]
        }]
    }
    minio_client.set_bucket_policy(kb_id, json.dumps(policy))

def upload_file_to_minio(kb_id, file_path):
    """上传单个文件到MinIO
    
    Args:
        kb_id: 知识库ID
        file_path: 文件路径
    """

    minio_client = get_minio_client()

    if not minio_client.bucket_exists(kb_id):
        print(f"[ERROR] Bucket {kb_id} 不存在")
        return False

    print(f"[INFO] 处理图像: {file_path}")
    try:
        if not os.path.exists(file_path):
            print(f"[WARNING] 图片文件不存在: {file_path}")
            return False

        img_key = os.path.basename(file_path)
        print(f"[INFO] img_key: {img_key}")
        
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
        
        _set_bucket_policy(minio_client, kb_id)
        print(f"[SUCCESS] 成功上传图片: {img_key}")
        return True
        
    except Exception as e:
        print(f"[ERROR] 上传图片失败: {str(e)}")
        return False

def upload_directory_to_minio(kb_id, image_dir):
    """上传目录下的所有图片到MinIO
    
    Args:
        kb_id: 知识库ID
        image_dir: 图片目录路径
    """
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
    """获取图片的公共访问URL
    
    Args:
        kb_id: 知识库ID
        image_key: 图片在MinIO中的键
            
    Returns:
        str: 图片的公共访问URL
    """
    try:
        # 获取MinIO服务器配置
        minio_endpoint = MINIO_CONFIG["endpoint"]
        use_ssl = MINIO_CONFIG["secure"]
        # 构建URL
        protocol = "https" if use_ssl else "http"
        url = f"{protocol}://{minio_endpoint}/{kb_id}/{image_key}"
        print(f"[DEBUG] 图片URL: {url}")
        return url
    except Exception as e:
        print(f"[ERROR] 获取图片URL失败: {str(e)}")
        return None

if __name__ == "__main__":
    # 测试代码
    test_kb_id = "86e6f8481a0e11f088985225ee02e7da"
    test_image_dir = "output/images"
    
    upload_directory_to_minio(kb_id=test_kb_id, image_dir=test_image_dir)
    get_image_url(test_kb_id, "test.jpg")
    

     






