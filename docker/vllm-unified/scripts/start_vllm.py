#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vLLM 统一服务启动脚本
管理多个模型服务的启动、路由和健康检查
"""

import os
import json
import time
import signal
import asyncio
import logging
import subprocess
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import uvicorn
    import requests
    from fastapi import FastAPI, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import psutil
except ImportError as e:
    print(f"导入错误: {e}")
    print("请安装必要的依赖: pip install fastapi uvicorn requests psutil")
    exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VLLMManager:
    def __init__(self, config_path: str = "/app/config/models.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.app = FastAPI(
            title="vLLM 统一服务",
            description="KnowFlow vLLM 统一模型服务",
            version="1.0.0"
        )
        self.setup_middleware()
        self.setup_routes()
        self.shutdown_event = threading.Event()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def setup_middleware(self):
        """设置中间件"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def get_gpu_info(self) -> Dict[str, Any]:
        """获取 GPU 信息"""
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            gpu_info = []
            for gpu in gpus:
                gpu_info.append({
                    "id": gpu.id,
                    "name": gpu.name,
                    "memory_total": gpu.memoryTotal,
                    "memory_used": gpu.memoryUsed,
                    "memory_free": gpu.memoryFree,
                    "utilization": gpu.load * 100
                })
            return {"gpus": gpu_info, "count": len(gpus)}
        except ImportError:
            return {"gpus": [], "count": 0, "error": "GPUtil not available"}
        except Exception as e:
            return {"gpus": [], "count": 0, "error": str(e)}
    
    def start_model_server(self, model_type: str, model_config: Dict[str, Any]) -> subprocess.Popen:
        """启动单个模型服务"""
        model_path = model_config['path']
        port = model_config['port']
        
        # 检查模型路径是否存在
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        # 构建启动命令
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_path,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--gpu-memory-utilization", str(model_config.get('gpu_memory_utilization', 0.9)),
            "--max-model-len", str(model_config.get('max_model_len', 32768)),
            "--dtype", model_config.get('dtype', 'auto'),
            "--api-key", "token-abc123",  # 设置 API 密钥
            "--served-model-name", model_config['name']
        ]
        
        # 添加可选参数
        if model_config.get('tensor_parallel_size', 1) > 1:
            cmd.extend(["--tensor-parallel-size", str(model_config['tensor_parallel_size'])])
        
        if model_config.get('trust_remote_code', False):
            cmd.append("--trust-remote-code")
        
        # 根据模型类型添加特定参数
        if model_type == "embedding":
            cmd.extend(["--disable-log-requests"])
        
        logger.info(f"启动 {model_type} 服务: {' '.join(cmd)}")
        
        # 设置环境变量
        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = str(model_config.get('cuda_device', '0'))
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=os.setsid  # 创建新的进程组
            )
            
            self.processes[model_type] = process
            logger.info(f"{model_type} 服务已启动，PID: {process.pid}")
            return process
            
        except Exception as e:
            logger.error(f"启动 {model_type} 服务失败: {e}")
            raise
    
    def wait_for_service(self, port: int, timeout: int = 300) -> bool:
        """等待服务启动"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"http://localhost:{port}/health",
                    timeout=5
                )
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(5)
        
        return False
    
    def start_all_models(self):
        """启动所有模型服务"""
        logger.info("开始启动所有模型服务...")
        
        models = self.config.get('models', {})
        startup_timeout = self.config.get('router', {}).get('startup_timeout', 300)
        
        # 按优先级启动模型（embedding 和 rerank 先启动，占用显存较少）
        startup_order = ['embedding', 'rerank', 'chat']
        
        for model_type in startup_order:
            if model_type in models:
                model_config = models[model_type]
                try:
                    # 启动服务
                    self.start_model_server(model_type, model_config)
                    
                    # 等待服务就绪
                    port = model_config['port']
                    logger.info(f"等待 {model_type} 服务启动 (端口 {port})...")
                    
                    if self.wait_for_service(port, startup_timeout):
                        logger.info(f"{model_type} 服务启动成功")
                    else:
                        logger.error(f"{model_type} 服务启动超时")
                        raise TimeoutError(f"{model_type} 服务启动超时")
                    
                    # 启动间隔
                    time.sleep(10)
                    
                except Exception as e:
                    logger.error(f"启动 {model_type} 服务失败: {e}")
                    self.cleanup_processes()
                    raise
        
        logger.info("所有模型服务启动完成")
    
    def cleanup_processes(self):
        """清理所有子进程"""
        logger.info("清理模型服务进程...")
        
        for model_type, process in self.processes.items():
            try:
                if process.poll() is None:  # 进程仍在运行
                    logger.info(f"终止 {model_type} 服务 (PID: {process.pid})")
                    
                    # 尝试优雅关闭
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    
                    # 等待进程结束
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        # 强制终止
                        logger.warning(f"强制终止 {model_type} 服务")
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait()
                    
                    logger.info(f"{model_type} 服务已终止")
            except Exception as e:
                logger.error(f"终止 {model_type} 服务时出错: {e}")
        
        self.processes.clear()
    
    def setup_routes(self):
        """设置路由"""
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            status = {"status": "healthy", "services": {}}
            
            models = self.config.get('models', {})
            for model_type, model_config in models.items():
                port = model_config['port']
                try:
                    response = requests.get(
                        f"http://localhost:{port}/health",
                        timeout=5
                    )
                    status["services"][model_type] = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "port": port,
                        "model": model_config['name']
                    }
                except Exception as e:
                    status["services"][model_type] = {
                        "status": "unhealthy",
                        "port": port,
                        "error": str(e)
                    }
            
            # 检查整体状态
            unhealthy_services = [s for s in status["services"].values() if s["status"] != "healthy"]
            if unhealthy_services:
                status["status"] = "degraded"
            
            return status
        
        @self.app.get("/models")
        async def list_models():
            """列出所有可用模型"""
            models = self.config.get('models', {})
            model_list = []
            
            for model_type, model_config in models.items():
                model_list.append({
                    "id": model_config['name'],
                    "type": model_type,
                    "port": model_config['port'],
                    "path": model_config['path']
                })
            
            return {"data": model_list}
        
        @self.app.get("/system/info")
        async def system_info():
            """系统信息"""
            return {
                "gpu_info": self.get_gpu_info(),
                "processes": {
                    model_type: {
                        "pid": process.pid,
                        "status": "running" if process.poll() is None else "stopped"
                    }
                    for model_type, process in self.processes.items()
                },
                "config": self.config
            }
        
        # Chat 模型路由
        @self.app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            """对话完成接口"""
            chat_port = self.config['models']['chat']['port']
            return await self.proxy_request(request, f"http://localhost:{chat_port}")
        
        # Embedding 模型路由
        @self.app.post("/v1/embeddings")
        async def embeddings(request: Request):
            """嵌入接口"""
            embedding_port = self.config['models']['embedding']['port']
            return await self.proxy_request(request, f"http://localhost:{embedding_port}")
        
        # Rerank 模型路由（自定义接口）
        @self.app.post("/v1/rerank")
        async def rerank(request: Request):
            """重排序接口"""
            rerank_port = self.config['models']['rerank']['port']
            return await self.proxy_request(request, f"http://localhost:{rerank_port}")
    
    async def proxy_request(self, request: Request, target_url: str):
        """代理请求到目标服务"""
        try:
            # 获取请求体
            body = await request.body()
            
            # 构建目标 URL
            path = request.url.path
            query = str(request.url.query)
            full_url = f"{target_url}{path}"
            if query:
                full_url += f"?{query}"
            
            # 转发请求
            response = requests.request(
                method=request.method,
                url=full_url,
                headers=dict(request.headers),
                data=body,
                timeout=300
            )
            
            # 返回响应
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except Exception as e:
            logger.error(f"代理请求失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，开始关闭服务...")
        self.shutdown_event.set()
        self.cleanup_processes()
    
    def start_router(self):
        """启动路由服务"""
        router_config = self.config.get('router', {})
        router_port = router_config.get('port', 8000)
        
        logger.info(f"启动路由服务，端口: {router_port}")
        
        # 注册信号处理器
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            uvicorn.run(
                self.app,
                host="0.0.0.0",
                port=router_port,
                log_level="info",
                access_log=True
            )
        except Exception as e:
            logger.error(f"路由服务启动失败: {e}")
            self.cleanup_processes()
            raise

def main():
    """主函数"""
    try:
        manager = VLLMManager()
        
        # 在后台线程中启动模型服务
        model_thread = threading.Thread(target=manager.start_all_models)
        model_thread.daemon = True
        model_thread.start()
        
        # 等待模型服务启动完成
        model_thread.join()
        
        # 启动路由服务
        manager.start_router()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        exit(1)

if __name__ == "__main__":
    main()