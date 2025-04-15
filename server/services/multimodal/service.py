from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import os
import subprocess
import logging
import traceback

app = FastAPI()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/api/multimodal/process_pdf")
async def process_pdf(file: UploadFile = File(...)):
    tmp_path = None
    try:
        # 记录请求开始
        logger.info(f"开始处理文件: {file.filename}")
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            logger.info(f"临时文件创建成功: {tmp_path}")

        # 运行处理脚本
        result = process_pdf(
             pdf_path=tmp_path,
             api_key=os.getenv('RAGFLOW_API_KEY'),
             server_ip=os.getenv('RAGFLOW_SERVER_IP'),
             doc_engine=os.getenv('DOC_ENGINE')
        )
        
        # 记录处理结果
        logger.info(f"处理完成, 返回码: {result.returncode}")
        logger.debug(f"标准输出: {result.stdout}")
        logger.debug(f"标准错误: {result.stderr}")

        if result.returncode != 0:
            error_msg = f"处理失败: {result.stderr}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "PDF处理失败",
                    "error": error_msg,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            )
        
        return JSONResponse({
            "message": "处理成功",
            "output": result.stdout
        })
        
    except subprocess.TimeoutExpired:
        error_msg = "PDF处理超时"
        logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail={
                "message": error_msg,
                "error": "处理时间超过60秒"
            }
        )
    except Exception as e:
        error_msg = f"处理异常: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "PDF处理异常",
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
        )
    finally:
        # 清理临时文件
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
                logger.info(f"已删除临时文件: {tmp_path}")
            except Exception as e:
                logger.error(f"删除临时文件失败: {str(e)}")