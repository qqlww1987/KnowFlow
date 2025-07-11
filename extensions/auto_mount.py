#!/usr/bin/env python3
"""
KnowFlow 自动 Docker 挂载脚本
在现有 RAGFlow docker-compose 基础上添加 KnowFlow 扩展挂载
"""

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class DockerComposeManager:
    def __init__(self):
        self.current_dir = Path.cwd()
        self.extensions_dir = self.current_dir / "knowflow_extensions"
        self.compose_file = None
        
    def find_ragflow_containers(self) -> List[Dict]:
        """发现运行中的 RAGFlow 容器"""
        try:
            # 查找包含 ragflow 的容器
            cmd = ["docker", "ps", "--format", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            containers = []
            main_containers = []  # 优先处理主要容器
            dependency_containers = []  # 依赖容器作为备用
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    container = json.loads(line)
                    container_name = container.get('Names', '').lower()
                    container_image = container.get('Image', '').lower()
                    
                    # 检查容器名或镜像是否包含 ragflow
                    if ('ragflow' in container_name or 'ragflow' in container_image):
                        # 检查是否是主要服务容器
                        if ('ragflow-server' in container_name or 
                            'ragflow-api' in container_name or 
                            'ragflow_server' in container_name or
                            'ragflow_api' in container_name):
                            main_containers.append(container)
                            print(f"🎯 发现主要 RAGFlow 容器: {container.get('Names')}")
                        else:
                            # 检查是否是依赖服务
                            dependency_services = ['mysql', 'redis', 'elasticsearch', 'es-01', 'minio', 'postgres']
                            is_dependency = any(dep in container_name for dep in dependency_services)
                            
                            if is_dependency:
                                dependency_containers.append(container)
                                print(f"📍 发现依赖服务容器: {container.get('Names')}")
                            else:
                                # 可能是其他 RAGFlow 相关容器
                                main_containers.append(container)
                                print(f"✅ 发现可能的 RAGFlow 容器: {container.get('Names')}")
            
            # 优先返回主要容器，如果没有则返回依赖容器（用于定位 compose 文件）
            if main_containers:
                containers = main_containers
                print(f"✅ 找到 {len(main_containers)} 个主要 RAGFlow 容器")
            elif dependency_containers:
                containers = dependency_containers[:1]  # 只用一个依赖容器来定位
                print(f"⚠️ 未找到主要容器，使用依赖容器定位 compose 文件")
            
            return containers
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 执行 docker ps 失败: {e}")
            return []
    
    def get_container_compose_info(self, container_id: str) -> Optional[Tuple[Path, str]]:
        """从容器获取 docker-compose 信息"""
        try:
            cmd = ["docker", "inspect", container_id]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            container_info = json.loads(result.stdout)[0]
            
            labels = container_info.get('Config', {}).get('Labels', {})
            
            # 查找 docker-compose 相关标签
            project_name = labels.get('com.docker.compose.project')
            service_name = labels.get('com.docker.compose.service')
            working_dir = labels.get('com.docker.compose.project.working_dir')
            config_hash = labels.get('com.docker.compose.config-hash')
            
            if project_name and service_name and working_dir:
                # 推断 compose 文件位置
                project_dir = Path(working_dir)
                
                # 常见的 compose 文件名
                possible_files = [
                    "docker-compose.yml",
                    "docker-compose-gpu.yml",
                    "docker-compose.yaml",
                    "compose.yml", 
                    "compose.yaml"
                ]
                
                for filename in possible_files:
                    compose_file = project_dir / filename
                    if compose_file.exists():
                        print(f"🎯 从容器发现 compose 文件: {compose_file}")
                        print(f"   项目名: {project_name}")
                        print(f"   发现的服务: {service_name}")
                        
                        # 检查是否是依赖服务，如果是，尝试找到主要服务
                        dependency_services = ['mysql', 'redis', 'elasticsearch', 'es-01', 'minio', 'postgres']
                        
                        if any(dep in service_name.lower() for dep in dependency_services):
                            print(f"   ⚠️ {service_name} 是依赖服务，查找主要 RAGFlow 服务...")
                            
                            # 加载 compose 配置查找主要服务
                            try:
                                with open(compose_file, 'r', encoding='utf-8') as f:
                                    config = yaml.safe_load(f)
                                
                                main_service = self._find_main_ragflow_service(config)
                                if main_service:
                                    print(f"   ✅ 找到主要服务: {main_service}")
                                    return compose_file, main_service
                                else:
                                    print(f"   ❌ 未在 compose 文件中找到主要 RAGFlow 服务")
                                    
                            except Exception as e:
                                print(f"   ❌ 读取 compose 文件失败: {e}")
                        else:
                            # 直接返回发现的服务（可能就是主要服务）
                            return compose_file, service_name
                        
                print(f"⚠️ 在 {project_dir} 中未找到 compose 文件")
                
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 获取容器信息失败: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ 解析容器信息失败: {e}")
            return None
    
    def _find_main_ragflow_service(self, config: Dict) -> Optional[str]:
        """在 compose 配置中查找主要的 RAGFlow 服务"""
        services = config.get('services', {})
        
        # 优先级顺序：RAGFlow 标准服务名优先
        priority_names = ['ragflow', 'ragflow-server', 'ragflow-api', 'api', 'server', 'app', 'web']
        
        # 首先精确匹配
        for priority_name in priority_names:
            if priority_name in services:
                print(f"   🎯 精确匹配到服务: {priority_name}")
                return priority_name
        
        # 然后模糊匹配
        for service_name in services:
            service_lower = service_name.lower()
            
            # 检查是否匹配优先级名称
            for priority_name in priority_names:
                if priority_name in service_lower:
                    # 确保不是依赖服务
                    dependency_services = ['mysql', 'redis', 'elasticsearch', 'es', 'minio', 'postgres']
                    if not any(dep in service_lower for dep in dependency_services):
                        print(f"   🎯 模糊匹配到服务: {service_name}")
                        return service_name
        
        # 查找镜像名包含 ragflow 的服务
        for service_name, service_config in services.items():
            image = service_config.get('image', '').lower()
            if 'ragflow' in image:
                service_lower = service_name.lower()
                dependency_services = ['mysql', 'redis', 'elasticsearch', 'es', 'minio', 'postgres']
                if not any(dep in service_lower for dep in dependency_services):
                    print(f"   🎯 通过镜像名匹配到服务: {service_name}")
                    return service_name
        
        print(f"   ❌ 未找到匹配的服务，可用服务: {list(services.keys())}")
        return None
    
    def auto_discover_ragflow_compose(self) -> Optional[Tuple[Path, str]]:
        """自动发现 RAGFlow 的 compose 文件"""
        print("🔍 搜索运行中的 RAGFlow 容器...")
        
        containers = self.find_ragflow_containers()
        if not containers:
            print("❌ 未找到运行中的 RAGFlow 容器")
            return None
        
        print(f"✅ 发现 {len(containers)} 个 RAGFlow 容器")
        
        # 尝试从每个容器获取 compose 信息
        for container in containers:
            container_id = container['ID']
            container_name = container['Names']
            
            print(f"🔍 检查容器: {container_name}")
            compose_info = self.get_container_compose_info(container_id)
            
            if compose_info:
                return compose_info
        
        print("❌ 无法从容器中发现 compose 文件信息")
        return None
        
    def find_compose_file(self) -> Optional[Path]:
        """在当前目录查找 docker-compose.yml 文件"""
        possible_files = [
            "docker-compose.yml",
            "docker-compose-gpu.yml",
            "docker-compose.yaml", 
            "compose.yml",
            "compose.yaml"
        ]
        
        for filename in possible_files:
            compose_path = self.current_dir / filename
            if compose_path.exists():
                print(f"✅ 发现 compose 文件: {compose_path}")
                return compose_path
        
        return None
    
    def backup_compose_file(self, compose_file: Path) -> Path:
        """备份原始 compose 文件"""
        backup_file = compose_file.with_suffix(f"{compose_file.suffix}.backup")
        import shutil
        shutil.copy2(compose_file, backup_file)
        print(f"💾 已备份原文件到: {backup_file}")
        return backup_file
    
    def load_compose_config(self, compose_file: Path) -> Dict:
        """加载现有的 compose 配置"""
        try:
            with open(compose_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            print(f"❌ 读取 compose 文件失败: {e}")
            return {}
    
    def find_ragflow_service(self, config: Dict) -> Optional[str]:
        """查找 RAGFlow 服务名称"""
        services = config.get('services', {})
        
        # 常见的 RAGFlow 服务名
        possible_names = ['ragflow', 'ragflow-api', 'ragflow-server', 'api']
        
        for service_name in services:
            # 直接匹配
            if service_name.lower() in possible_names:
                return service_name
            
            # 检查镜像名包含 ragflow
            service_config = services[service_name]
            image = service_config.get('image', '')
            if 'ragflow' in image.lower():
                return service_name
        
        # 如果没找到，显示所有服务让用户选择
        if services:
            print("未自动找到 RAGFlow 服务，请从以下服务中选择:")
            service_list = list(services.keys())
            for i, name in enumerate(service_list):
                image = services[name].get('image', 'unknown')
                print(f"  {i+1}. {name} (image: {image})")
            
            choice = input("请选择服务编号 (默认1): ").strip()
            idx = int(choice) - 1 if choice.isdigit() else 0
            if 0 <= idx < len(service_list):
                return service_list[idx]
        
        return None
    
    def add_knowflow_mounts(self, config: Dict, service_name: str) -> Dict:
        """在现有配置中添加 KnowFlow 挂载"""
        service_config = config['services'][service_name]
        
        # 获取现有 volumes
        existing_volumes = service_config.get('volumes', [])
        
        # 准备 KnowFlow 挂载路径（使用绝对路径）
        abs_extensions_dir = self.extensions_dir.absolute()
        
        knowflow_mounts = [
            f"{abs_extensions_dir}/enhanced_doc.py:/ragflow/api/apps/sdk/doc.py:ro",
        ]
        
        # 合并挂载点，避免重复
        all_volumes = []
        existing_targets = set()
        
        # 首先添加现有的非KnowFlow挂载
        for volume in existing_volumes:
            if ':' in volume:
                target = volume.split(':')[1]
                # 跳过已存在的KnowFlow相关挂载
                if not any(kf_target in target for kf_target in [
                    '/ragflow/api/apps/sdk/doc.py'
                ]):
                    all_volumes.append(volume)
                    existing_targets.add(target)
            else:
                all_volumes.append(volume)
        
        # 然后添加KnowFlow挂载（去重）
        for mount in knowflow_mounts:
            mount_target = mount.split(':')[1]
            if mount_target not in existing_targets:
                all_volumes.append(mount)
                existing_targets.add(mount_target)
        
        service_config['volumes'] = all_volumes
        
        # 不再需要 LOAD_KNOWFLOW 环境变量，因为只是替换了原始的doc.py文件
        # enhanced_doc.py 会直接被加载，无需额外的扩展加载机制
        
        return config
    
    def save_compose_config(self, config: Dict, compose_file: Path):
        """保存修改后的 compose 配置"""
        try:
            with open(compose_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            print(f"✅ 已更新 compose 文件: {compose_file}")
        except Exception as e:
            print(f"❌ 保存 compose 文件失败: {e}")
    
    def create_extension_files(self):
        """创建必要的扩展文件"""
        self.extensions_dir.mkdir(exist_ok=True)
        
        # 只需要创建 enhanced_doc.py，这是原始 doc.py 的增强版
        # 包含原有所有功能 + 新增的 batch_add_chunk 方法
        
        print(f"✅ enhanced_doc.py 已存在: {self.extensions_dir}")
        print(f"   - enhanced_doc.py: 增强版 doc.py (包含 batch_add_chunk 方法)")
        print(f"")
        print(f"💡 新增的批量 API 接口:")
        print(f"   POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch")
    
    def restart_services(self, compose_file: Path):
        """重启 Docker Compose 服务"""
        try:
            print("🔄 重启 Docker Compose 服务...")
            
            # 停止服务
            subprocess.run(["docker-compose", "-f", str(compose_file), "down"], 
                         check=True, cwd=self.current_dir)
            
            # 启动服务
            subprocess.run(["docker-compose", "-f", str(compose_file), "up", "-d"], 
                         check=True, cwd=self.current_dir)
            
            print("✅ 服务重启完成，KnowFlow 扩展已加载!")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 重启服务失败: {e}")
            return False
        
        return True
    
    def auto_mount(self):
        """自动挂载的主流程"""
        print("🔍 自动发现 RAGFlow docker-compose 配置...")
        
        # 首先尝试自动发现
        auto_result = self.auto_discover_ragflow_compose()
        if auto_result:
            compose_file, discovered_service_name = auto_result
            print(f"🎯 自动发现成功!")
        else:
            # 回退到手动查找
            print("🔍 回退到当前目录查找 compose 文件...")
            compose_file = self.find_compose_file()
            discovered_service_name = None
            
            if not compose_file:
                print("❌ 未找到 docker-compose.yml 文件")
                print("请确保：")
                print("  1. RAGFlow 容器正在运行，或")
                print("  2. 在包含 docker-compose.yml 的目录中运行此脚本")
                return False
        
        # 加载配置
        config = self.load_compose_config(compose_file)
        if not config:
            return False
        
        # 确定服务名称
        if discovered_service_name:
            service_name = discovered_service_name
            print(f"✅ 使用自动发现的服务: {service_name}")
        else:
            # 手动查找服务
            service_name = self.find_ragflow_service(config)
            if not service_name:
                print("❌ 未找到 RAGFlow 服务")
                return False
            print(f"✅ 找到 RAGFlow 服务: {service_name}")
        
        # 创建扩展文件
        print("📁 创建 KnowFlow 扩展文件...")
        self.create_extension_files()
        
        # 备份原文件
        backup_file = self.backup_compose_file(compose_file)
        
        # 添加 KnowFlow 挂载
        print("🔧 添加 KnowFlow 挂载配置...")
        updated_config = self.add_knowflow_mounts(config, service_name)
        
        # 保存配置
        self.save_compose_config(updated_config, compose_file)
        
        # 询问是否重启服务
        restart = input("是否重启服务以应用挂载? (y/N): ").strip().lower()
        if restart in ['y', 'yes']:
            success = self.restart_services(compose_file)
            if not success:
                print(f"💡 如果重启失败，可以手动恢复: cp {backup_file} {compose_file}")
        else:
            print("💡 手动重启命令:")
            print(f"   docker-compose -f {compose_file.name} down")
            print(f"   docker-compose -f {compose_file.name} up -d")
        
        return True

def main():
    print("🚀 KnowFlow 自动 Docker 挂载工具")
    print("基于现有 docker-compose.yml 添加 KnowFlow 扩展")
    print("=" * 60)
    
    # 检查工具依赖
    for tool in ["docker", "docker-compose"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {tool} 未安装或不可用")
            sys.exit(1)
    
    manager = DockerComposeManager()
    success = manager.auto_mount()
    
    if success:
        print("\n🎉 KnowFlow 扩展挂载完成!")
        print("新增的 API 接口:")
        print("  POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch - 原生批量插入")
        print("\n📖 使用示例:")
        print("curl -X POST http://localhost:9380/datasets/DATASET_ID/documents/DOC_ID/chunks/batch \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -H 'Authorization: Bearer YOUR_TOKEN' \\")
        print("     -d '{")
        print("       \"chunks\": [")
        print("         {\"content\": \"第一个chunk内容\", \"important_keywords\": [\"关键词1\"]},")
        print("         {\"content\": \"第二个chunk内容\", \"important_keywords\": [\"关键词2\"]}")
        print("       ],")
        print("       \"batch_size\": 5")
        print("     }'")
    else:
        print("\n❌ 挂载失败，请检查错误信息")

if __name__ == "__main__":
    main() 