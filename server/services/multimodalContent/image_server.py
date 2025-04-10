from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

# 创建FastAPI应用
app = FastAPI(title="图片服务器")

# 定义图片存储的绝对路径
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# 确保图片目录存在
os.makedirs(IMAGES_DIR, exist_ok=True)

# 挂载静态文件目录
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/")
def read_root():
    return {"message": "图片服务器运行中", "status": "online"}

if __name__ == "__main__":
    print(f"图片服务器已启动，访问 http://localhost:8000")
    print(f"图片存储目录: {IMAGES_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000)