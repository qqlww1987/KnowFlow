#!/usr/bin/env python3
"""
KnowFlow 自动 Docker 挂载脚本
在现有 RAGFlow docker-compose 基础上添加 KnowFlow 扩展挂载
"""

import os
import sys
import subprocess
import yaml
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 检查必要的依赖
def check_dependencies():
    """检查必要的Python依赖"""
    try:
        import yaml
        return True
    except ImportError:
        print("❌ 缺少必要的Python依赖: PyYAML")
        print("\n💡 请运行以下命令安装依赖:")
        print("   pip3 install PyYAML")
        return False

# 在导入其他模块之前检查依赖
if not check_dependencies():
    sys.exit(1) 

class DockerComposeManager:
    def __init__(self):
        self.current_dir = Path.cwd()
        # 更新路径：patches 和 plugins 目录都在 server 目录下
        if self.current_dir.name == "server":
            self.patches_dir = self.current_dir / "patches"
            self.plugins_dir = self.current_dir / "plugins"
        else:
            self.patches_dir = self.current_dir / "server" / "patches"
            self.plugins_dir = self.current_dir / "server" / "plugins"
        
    def find_ragflow_containers(self) -> List[Dict]:
        """发现运行中的 RAGFlow 容器"""
        try:
            cmd = ["docker", "ps", "--format", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            containers = []
            main_containers = []
            dependency_containers = []
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    container = json.loads(line)
                    container_name = container.get('Names', '').lower()
                    container_image = container.get('Image', '').lower()
                    
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
                                main_containers.append(container)
                                print(f"✅ 发现可能的 RAGFlow 容器: {container.get('Names')}")
            
            # 优先返回主要容器，如果没有则返回依赖容器
            if main_containers:
                containers = main_containers
                print(f"✅ 找到 {len(main_containers)} 个主要 RAGFlow 容器")
            elif dependency_containers:
                containers = dependency_containers[:1]
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
            project_name = labels.get('com.docker.compose.project')
            service_name = labels.get('com.docker.compose.service')
            working_dir = labels.get('com.docker.compose.project.working_dir')
            
            if project_name and service_name and working_dir:
                project_dir = Path(working_dir)
                print(f"🎯 发现 RAGFlow 项目目录: {project_dir}")
                return project_dir, service_name
                
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 获取容器信息失败: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ 解析容器信息失败: {e}")
            return None
    
    def list_available_compose_files(self, project_dir: Path) -> List[Tuple[int, str, Path]]:
        """列举 RAGFlow 项目目录下所有可用的 compose 文件"""
        compose_files = []
        
        # 常见的 compose 文件名模式
        compose_patterns = [
            "docker-compose*.yml",
            "docker-compose*.yaml", 
            "compose*.yml",
            "compose*.yaml"
        ]
        
        # 查找所有匹配的文件
        for pattern in compose_patterns:
            for file_path in project_dir.glob(pattern):
                if file_path.is_file():
                    compose_files.append(file_path)
        
        # 去重并排序
        compose_files = list(set(compose_files))
        
        # 优先级排序：docker-compose.yml 和 docker-compose-gpu.yml 排在前面
        def sort_key(file_path):
            filename = file_path.name.lower()
            if filename == "docker-compose.yml":
                return (0, filename)
            elif filename == "docker-compose-gpu.yml":
                return (1, filename)
            else:
                return (2, filename)
        
        compose_files.sort(key=sort_key)
        
        # 返回编号、文件名和完整路径的列表
        result = []
        for i, file_path in enumerate(compose_files, 1):
            result.append((i, file_path.name, file_path))
        
        return result
    
    def select_compose_file(self, project_dir: Path) -> Optional[Tuple[str, Path]]:
        """让用户选择 compose 文件"""
        print(f"🔍 在目录 {project_dir} 中查找 compose 文件...")
        
        compose_files = self.list_available_compose_files(project_dir)
        
        if not compose_files:
            print("❌ 未找到任何 compose 文件")
            return None
        
        print("📋 找到以下 compose 文件:")
        for num, filename, filepath in compose_files:
            print(f"  {num}. {filename}")
            print(f"     路径: {filepath}")
        
        while True:
            try:
                choice = input(f"\n请选择要挂载的文件 (1-{len(compose_files)}): ").strip()
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(compose_files):
                    selected_num, selected_filename, selected_filepath = compose_files[choice_num - 1]
                    print(f"✅ 选择文件: {selected_filename}")
                    print(f"   路径: {selected_filepath}")
                    return selected_filename, selected_filepath
                else:
                    print(f"❌ 无效选择，请输入 1-{len(compose_files)} 之间的数字")
            except ValueError:
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n❌ 用户取消操作")
                return None
    
    def auto_discover_ragflow_compose(self) -> Optional[Path]:
        """自动发现 RAGFlow 项目目录"""
        print("🔍 搜索运行中的 RAGFlow 容器...")
        
        containers = self.find_ragflow_containers()
        if not containers:
            print("❌ 未找到运行中的 RAGFlow 容器")
            return None
        
        print(f"✅ 发现 {len(containers)} 个 RAGFlow 容器")
        
        # 从第一个容器获取项目目录信息
        container_id = containers[0]['ID']
        result = self.get_container_compose_info(container_id)
        
        if result:
            project_dir, service_name = result
            print(f"✅ 自动发现成功: {project_dir}")
            return project_dir
        else:
            print("❌ 无法从容器获取 compose 信息")
            return None
    
    def backup_compose_file(self, compose_file: Path) -> Path:
        """备份 compose 文件"""
        backup_file = compose_file.with_suffix('.yml.backup')
        shutil.copy2(compose_file, backup_file)
        print(f"📋 已备份原文件: {backup_file}")
        return backup_file
    
    def load_compose_config(self, compose_file: Path) -> Dict:
        """加载 compose 配置"""
        try:
            with open(compose_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"✅ 成功加载 compose 配置")
            return config
        except Exception as e:
            print(f"❌ 加载 compose 配置失败: {e}")
            return None
    
    def find_ragflow_service(self, config: Dict) -> Optional[str]:
        """在配置中查找 RAGFlow 服务"""
        services = config.get('services', {})
        
        # 查找包含 ragflow 的服务
        for service_name in services:
            service_lower = service_name.lower()
            if 'ragflow' in service_lower:
                # 排除依赖服务
                dependency_services = ['mysql', 'redis', 'elasticsearch', 'es-01', 'es01', 'es_01', 'minio', 'postgres', 'postgres_01', 'postgres-01']
                if not any(dep in service_lower for dep in dependency_services):
                    print(f"✅ 找到 RAGFlow 服务: {service_name}")
                    return service_name
        
        print("❌ 未找到 RAGFlow 服务")
        return None
    
    def add_knowflow_mounts(self, config: Dict, service_name: str) -> Dict:
        """添加 KnowFlow 挂载配置 - 支持插件系统和传统扩展同时共存"""
        if service_name not in config['services']:
            raise ValueError(f"服务 {service_name} 不存在")
        service_config = config['services'][service_name]
        existing_volumes = service_config.get('volumes', [])

        # 检查 plugins 目录下的 *_app.py 文件
        plugin_dir = self.plugins_dir
        plugin_app_files = list(plugin_dir.glob("*_app.py")) if plugin_dir.exists() else []
        
        # 检查 patches 目录下的 *_app.py 文件
        patches_dir = self.patches_dir
        patches_app_files = list(patches_dir.glob("*_app.py")) if patches_dir.exists() else []
        
        knowflow_mounts = []
        
        # 挂载 plugins 目录下的 *_app.py 文件
        if plugin_app_files:
            print(f"✅ 检测到 plugins 目录下的插件文件:")
            for plugin_file in plugin_app_files:
                abs_plugin_file = plugin_file.absolute()
                target_name = plugin_file.name
                mount_str = f"{abs_plugin_file}:/ragflow/api/apps/sdk/{target_name}:ro"
                knowflow_mounts.append(mount_str)
                print(f"   {abs_plugin_file} -> /ragflow/api/apps/sdk/{target_name}")
        
        # 挂载 patches 目录下的 *_app.py 文件
        if patches_app_files:
            print(f"✅ 检测到 patches 目录下的插件文件:")
            for patch_file in patches_app_files:
                abs_patch_file = patch_file.absolute()
                target_name = patch_file.name
                mount_str = f"{abs_patch_file}:/ragflow/api/apps/sdk/{target_name}:ro"
                knowflow_mounts.append(mount_str)
                print(f"   {abs_patch_file} -> /ragflow/api/apps/sdk/{target_name}")
        
        # 如果两个目录都没有 *_app.py 文件，使用传统的扩展文件挂载
        if not plugin_app_files and not patches_app_files:
            abs_patches_dir = self.patches_dir.absolute()
            knowflow_mounts = [
                f"{abs_patches_dir}/enhanced_doc.py:/ragflow/api/apps/sdk/doc.py:ro",
            ]
            print(f"✅ 未检测到插件文件，使用传统扩展挂载模式")
            print(f"   扩展目录: {abs_patches_dir}")

        # 合并挂载点，避免重复
        all_volumes = []
        existing_targets = set()
        for volume in existing_volumes:
            if ':' in volume:
                target = volume.split(':')[1]
                # 检查是否与新的挂载点冲突
                all_app_files = plugin_app_files + patches_app_files
                kf_targets = [f"/ragflow/api/apps/sdk/{f.name}" for f in all_app_files]
                if not any(kf_target in target for kf_target in kf_targets):
                    all_volumes.append(volume)
                    existing_targets.add(target)
            else:
                all_volumes.append(volume)
        for mount in knowflow_mounts:
            mount_target = mount.split(':')[1]
            if mount_target not in existing_targets:
                all_volumes.append(mount)
                existing_targets.add(mount_target)
                print(f"   添加挂载: {mount}")
        service_config['volumes'] = all_volumes
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
        # 检查 plugins 目录下的 *_app.py 文件
        plugin_dir = self.plugins_dir
        plugin_app_files = list(plugin_dir.glob("*_app.py")) if plugin_dir.exists() else []
        
        # 检查 patches 目录下的 *_app.py 文件
        patches_dir = self.patches_dir
        patches_app_files = list(patches_dir.glob("*_app.py")) if patches_dir.exists() else []
        
        # 显示 plugins 目录下的插件文件
        if plugin_app_files:
            print(f"✅ plugins 目录已就绪: {plugin_dir}")
            for plugin_file in plugin_app_files:
                print(f"   - {plugin_file.name}: 插件 (自动挂载)")
        
        # 显示 patches 目录下的插件文件
        if patches_app_files:
            print(f"✅ patches 目录已就绪: {patches_dir}")
            for patch_file in patches_app_files:
                print(f"   - {patch_file.name}: 插件 (自动挂载)")
        
        # 显示新增的 API 接口
        all_app_files = plugin_app_files + patches_app_files
        if all_app_files:
            print(f"")
            print(f"💡 新增的插件 API 接口:")
            for app_file in all_app_files:
                print(f"   POST /api/v1/{app_file.stem.replace('_app','')}/...")
        else:
            # 如果两个目录都没有 *_app.py 文件，使用传统扩展模式
            self.patches_dir.mkdir(exist_ok=True)
            print(f"✅ enhanced_doc.py 已存在: {self.patches_dir}")
            print(f"   - enhanced_doc.py: 增强版 doc.py (包含 batch_add_chunk 方法)")
            print(f"")
            print(f"💡 新增的批量 API 接口:")
            print(f"   POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch")
    
    def restart_services(self, compose_file: Path, compose_filename: str):
        """重新加载 Docker Compose 服务"""
        try:
            print("🔄 重新加载 Docker Compose 服务...")
            
            # 获取 RAGFlow 项目目录（compose 文件所在目录）
            ragflow_project_dir = compose_file.parent
            print(f"📍 RAGFlow 项目目录: {ragflow_project_dir}")
            
            # 使用传入的 compose 文件名
            print(f"✅ 使用 compose 文件: {compose_filename}")
            
            # 拼接完整的 compose 文件路径
            full_compose_path = ragflow_project_dir / compose_filename
            print(f"✅ 完整路径: {full_compose_path}")
            
            # 检查文件是否存在
            if not full_compose_path.exists():
                print(f"❌ 文件不存在: {full_compose_path}")
                print("💡 请检查文件名是否正确，或手动重新加载服务")
                return False
            
            # 直接执行 up -d 重新加载服务配置
            print("🚀 重新加载服务配置...")
            subprocess.run(["docker", "compose", "-f", str(full_compose_path), "up", "-d"], 
                        check=True, cwd=ragflow_project_dir)
            
            print("✅ 服务重新加载完成，KnowFlow 扩展已加载!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 重新加载服务失败: {e}")
            print(f"💡 请手动重新加载服务以应用挂载:")
            print(f"   cd {ragflow_project_dir}")
            print(f"   docker compose -f {compose_filename} up -d")
            return False
    
    def auto_mount(self):
        """自动挂载的主流程"""
        print("🔍 查找指定的 RAGFlow docker-compose 配置...")
        
        # 首先尝试自动发现 RAGFlow 项目目录
        project_dir = self.auto_discover_ragflow_compose()
        if not project_dir:
            print("❌ 未找到运行中的 RAGFlow 容器，无法确定项目目录！")
            return False
        
        # 让用户选择 compose 文件
        selection_result = self.select_compose_file(project_dir)
        if not selection_result:
            print("❌ 用户取消选择或未找到可用文件")
            return False
        
        compose_file_name, compose_file = selection_result
        
        # 加载配置
        config = self.load_compose_config(compose_file)
        if not config:
            return False
        
        # 查找 RAGFlow 服务
        service_name = self.find_ragflow_service(config)
        if not service_name:
            print("❌ 未找到 RAGFlow 服务")
            return False
        print(f"✅ 找到 RAGFlow 服务: {service_name}")
        
        # 创建扩展文件
        print("📁 检查 KnowFlow 扩展...")
        self.create_extension_files()
        
        # 备份原文件
        backup_file = self.backup_compose_file(compose_file)
        
        # 添加 KnowFlow 挂载
        print("🔧 添加 KnowFlow 挂载配置...")
        try:
            updated_config = self.add_knowflow_mounts(config, service_name)
        except ValueError as e:
            print(f"❌ 挂载配置失败: {e}")
            print("💡 可能的解决方案:")
            print("  1. 检查 compose 文件中的服务名称是否正确")
            print("  2. 确保 compose 文件格式正确")
            print("  3. 手动指定正确的服务名称")
            return False
        
        # 保存配置
        self.save_compose_config(updated_config, compose_file)
        
        # 自动重新加载服务以应用挂载
        print("🔄 自动重新加载服务以应用挂载...")
        restart_success = self.restart_services(compose_file, compose_file_name)
        if not restart_success:
            print(f"💡 如果重新加载失败，可以手动恢复: cp {backup_file} {compose_file}")
            print("💡 手动重新加载命令:")
            print(f"   cd {project_dir}")
            print(f"   docker compose -f {compose_file_name} down")
            print(f"   docker compose -f {compose_file_name} up -d")
        
        return True

def main():
    print("🚀 KnowFlow 自动 Docker 挂载工具")
    print("基于现有 docker-compose.yml 添加 KnowFlow 扩展")
    print("=" * 60)
    
    # 检查工具依赖
    TOOLS = [
        ["docker", "--version"],
        ["docker", "compose", "version"],
    ]

    for tool_cmd in TOOLS:
        try:
            subprocess.run(tool_cmd, capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {' '.join(tool_cmd)} 未安装或不可用")
            sys.exit(1)
    
    manager = DockerComposeManager()
    success = manager.auto_mount()
    
    if success:
        print("\n🎉 KnowFlow 扩展挂载完成!")
        
        # 检查插件文件
        plugin_dir = manager.plugins_dir
        plugin_app_files = list(plugin_dir.glob("*_app.py")) if plugin_dir.exists() else []
        
        patches_dir = manager.patches_dir
        patches_app_files = list(patches_dir.glob("*_app.py")) if patches_dir.exists() else []
        
        all_app_files = plugin_app_files + patches_app_files
        
        if all_app_files:
            print("🔌 使用插件系统模式 (批量插件挂载):")
            for app_file in all_app_files:
                source_dir = "plugins" if app_file in plugin_app_files else "patches"
                print(f"  POST /api/v1/{app_file.stem.replace('_app','')}/... - {source_dir} 目录插件")
            print("\n📖 插件系统特点:")
            print("  ✅ 增量挂载 - 无需维护整个文件副本")
            print("  ✅ 模块化设计 - 功能独立，易于扩展")  
            print("  ✅ 集成式实现 - 所有逻辑在单一文件中")
            print("  ✅ 多目录支持 - plugins 和 patches 目录可同时共存")
        else:
            print("📄 使用传统扩展模式:")
            print("  POST /datasets/<dataset_id>/documents/<document_id>/chunks/batch - 原生批量插入")
        
        print("\n📖 使用示例:")
        print("curl -X POST http://localhost:9380/datasets/DATASET_ID/documents/DOC_ID/chunks/batch \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{")
        print("       \"chunks\": [")
        print("         {\"content\": \"第一个chunk内容\", \"important_keywords\": [\"关键词1\"]},")
        print("         {\"content\": \"第二个chunk内容\", \"important_keywords\": [\"关键词2\"]}")
        print("       ],")
        print("       \"batch_size\": 5")
        print("     }'")
        sys.exit(0)
    else:
        print("\n❌ 挂载失败，请检查错误信息")
        sys.exit(1)

if __name__ == "__main__":
    main()