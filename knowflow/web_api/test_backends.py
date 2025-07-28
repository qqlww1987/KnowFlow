#!/usr/bin/env python3
"""
优化的测试脚本：验证 MinerU 2.0 Web API 的所有后端模式

使用方法:
python test_backends.py                                    # 使用默认demo.pdf文件
python test_backends.py --file /path/to/test.pdf          # 使用指定文件
python test_backends.py --concurrent                      # 并发测试所有后端
python test_backends.py --benchmark 3                     # 性能基准测试（运行3次取平均值）
"""

import argparse
import json
import requests
import time
import threading
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple


class Colors:
    """终端颜色常量"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


class BackendTester:
    """后端测试器类"""
    
    def __init__(self, base_url: str, file_path: str, timeout: int = 300):
        self.base_url = base_url
        self.file_path = file_path
        self.timeout = timeout
        self.results = {}
        
    def _print_colored(self, text: str, color: str = Colors.END):
        """打印彩色文本"""
        print(f"{color}{text}{Colors.END}")
        
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
        
    def _format_duration(self, seconds: float) -> str:
        """格式化时间持续"""
        if seconds < 60:
            return f"{seconds:.2f}秒"
        elif seconds < 3600:
            return f"{seconds // 60:.0f}分{seconds % 60:.0f}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}小时{minutes:.0f}分"

    def test_backend(self, backend: str, server_url: str = None, silent: bool = False, dump_files: bool = False) -> Optional[Dict]:
        """测试指定后端"""
        if not silent:
            self._print_colored(f"\n{'='*60}", Colors.CYAN)
            self._print_colored(f"🧪 测试后端: {backend}", Colors.BOLD)
            self._print_colored(f"{'='*60}", Colors.CYAN)
        
        # 准备请求数据
        try:
            files = {'file': open(self.file_path, 'rb')}
        except FileNotFoundError:
            if not silent:
                self._print_colored(f"❌ 文件不存在: {self.file_path}", Colors.RED)
            return None
            
        data = {
            'backend': backend,
            'return_content_list': True,
            'return_info': False,
            'return_layout': False,
            'return_images': False,
            'is_json_md_dump': dump_files,  # 添加文件保存参数
            'output_dir': 'test_output'  # 指定测试输出目录
        }
        
        # 为不同后端添加特定参数
        if backend == 'vlm-sglang-client':
            if not server_url:
                if not silent:
                    self._print_colored(f"⚠️  跳过 {backend}：需要 server_url 参数", Colors.YELLOW)
                files['file'].close()
                return None
            data['server_url'] = server_url
            
        elif backend == 'pipeline':
            data.update({
                'parse_method': 'auto',
                'lang': 'ch',
                'formula_enable': True,
                'table_enable': True
            })
        
        try:
            start_time = time.time()
            if not silent:
                self._print_colored(f"🚀 发送请求到 {self.base_url}/file_parse", Colors.BLUE)
                if dump_files:
                    self._print_colored(f"📁 将保存解析结果到 test_output 目录", Colors.BLUE)
                
            response = requests.post(
                f"{self.base_url}/file_parse",
                files=files,
                data=data,
                timeout=self.timeout
            )
            end_time = time.time()
            duration = end_time - start_time
            
            files['file'].close()
            
            if response.status_code == 200:
                result = response.json()
                result['_test_duration'] = duration
                result['_test_backend'] = backend
                result['_dump_files'] = dump_files
                
                if not silent:
                    self._print_colored(f"✅ {backend} 测试成功", Colors.GREEN)
                    self._print_colored(f"   ⏱️  耗时: {self._format_duration(duration)}", Colors.GREEN)
                    self._print_colored(f"   📊 返回数据大小: {self._format_size(len(json.dumps(result)))}", Colors.GREEN)
                    
                    if 'md_content' in result:
                        md_length = len(result['md_content'])
                        self._print_colored(f"   📝 Markdown 长度: {self._format_size(md_length)}", Colors.GREEN)
                        
                    if 'content_list' in result:
                        content_count = len(result.get('content_list', []))
                        self._print_colored(f"   📋 内容列表项数: {content_count} 项", Colors.GREEN)
                        
                    actual_backend = result.get('backend', 'unknown')
                    self._print_colored(f"   🔧 实际使用后端: {actual_backend}", Colors.GREEN)
                    
                    if dump_files:
                        self._print_colored(f"   💾 文件已保存到 test_output 目录", Colors.GREEN)
                    
                return result
            else:
                if not silent:
                    self._print_colored(f"❌ {backend} 测试失败", Colors.RED)
                    self._print_colored(f"   📟 状态码: {response.status_code}", Colors.RED)
                    self._print_colored(f"   💬 错误信息: {response.text[:200]}...", Colors.RED)
                return None
                
        except requests.exceptions.Timeout:
            if not silent:
                self._print_colored(f"⏰ {backend} 测试超时（{self.timeout}秒）", Colors.YELLOW)
            files['file'].close()
            return None
        except Exception as e:
            if not silent:
                self._print_colored(f"❌ {backend} 测试出错: {str(e)}", Colors.RED)
            files['file'].close()
            return None

    def test_concurrent(self, backends: List[str], server_url: str = None, dump_files: bool = False) -> Dict[str, Optional[Dict]]:
        """并发测试多个后端"""
        self._print_colored(f"\n🔄 开始并发测试 {len(backends)} 个后端...", Colors.CYAN)
        
        results = {}
        
        def test_single_backend(backend):
            return backend, self.test_backend(backend, server_url, silent=True, dump_files=dump_files)
            
        with ThreadPoolExecutor(max_workers=len(backends)) as executor:
            futures = {executor.submit(test_single_backend, backend): backend for backend in backends}
            
            for future in as_completed(futures):
                backend, result = future.result()
                results[backend] = result
                
                if result:
                    duration = result.get('_test_duration', 0)
                    self._print_colored(f"✅ {backend} 完成 ({self._format_duration(duration)})", Colors.GREEN)
                else:
                    self._print_colored(f"❌ {backend} 失败", Colors.RED)
                    
        return results

    def benchmark_backend(self, backend: str, runs: int = 3, server_url: str = None, dump_files: bool = False) -> Dict:
        """对单个后端进行基准测试"""
        self._print_colored(f"\n🏃‍♂️ 对 {backend} 进行 {runs} 次基准测试...", Colors.CYAN)
        
        durations = []
        successful_runs = 0
        
        for i in range(runs):
            self._print_colored(f"   第 {i+1}/{runs} 次运行...", Colors.BLUE)
            result = self.test_backend(backend, server_url, silent=True, dump_files=dump_files)
            
            if result:
                duration = result.get('_test_duration', 0)
                durations.append(duration)
                successful_runs += 1
                self._print_colored(f"   ✅ 运行 {i+1} 完成: {self._format_duration(duration)}", Colors.GREEN)
            else:
                self._print_colored(f"   ❌ 运行 {i+1} 失败", Colors.RED)
        
        if durations:
            benchmark_result = {
                'backend': backend,
                'successful_runs': successful_runs,
                'total_runs': runs,
                'success_rate': successful_runs / runs * 100,
                'min_duration': min(durations),
                'max_duration': max(durations),
                'avg_duration': statistics.mean(durations),
                'median_duration': statistics.median(durations),
                'std_deviation': statistics.stdev(durations) if len(durations) > 1 else 0
            }
            
            self._print_colored(f"\n📊 {backend} 基准测试结果:", Colors.BOLD)
            self._print_colored(f"   成功率: {benchmark_result['success_rate']:.1f}% ({successful_runs}/{runs})", Colors.GREEN)
            self._print_colored(f"   平均耗时: {self._format_duration(benchmark_result['avg_duration'])}", Colors.GREEN)
            self._print_colored(f"   最快耗时: {self._format_duration(benchmark_result['min_duration'])}", Colors.GREEN)
            self._print_colored(f"   最慢耗时: {self._format_duration(benchmark_result['max_duration'])}", Colors.GREEN)
            if benchmark_result['std_deviation'] > 0:
                self._print_colored(f"   标准差: {benchmark_result['std_deviation']:.2f}秒", Colors.GREEN)
                
            return benchmark_result
        else:
            self._print_colored(f"❌ {backend} 所有测试都失败了", Colors.RED)
            return {'backend': backend, 'successful_runs': 0, 'total_runs': runs, 'success_rate': 0}

def check_api_server(base_url: str) -> bool:
    """检查API服务器是否可访问"""
    try:
        response = requests.get(f"{base_url}/docs", timeout=10)
        if response.status_code == 200:
            print(f"{Colors.GREEN}✅ API服务器可访问: {base_url}{Colors.END}")
            return True
        else:
            print(f"{Colors.YELLOW}⚠️  API服务器响应异常: {response.status_code}{Colors.END}")
            return False
    except Exception as e:
        print(f"{Colors.RED}❌ 无法访问API服务器: {base_url}{Colors.END}")
        print(f"{Colors.RED}   错误: {str(e)}{Colors.END}")
        return False

def get_default_pdf_path() -> Optional[str]:
    """获取默认的PDF文件路径"""
    current_dir = Path(__file__).parent
    demo_pdf = current_dir / "demo.pdf"
    
    if demo_pdf.exists():
        return str(demo_pdf)
    
    # 尝试从项目根目录查找
    project_root = current_dir.parent.parent
    demo_pdf = project_root / "projects" / "web_api" / "demo.pdf"
    
    if demo_pdf.exists():
        return str(demo_pdf)
        
    return None

def print_summary(results: Dict[str, Optional[Dict]], total_backends: int):
    """打印测试总结"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}📋 测试总结{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    
    successful_backends = [k for k, v in results.items() if v is not None]
    failed_backends = [k for k, v in results.items() if v is None]
    
    if successful_backends:
        print(f"{Colors.GREEN}✅ 成功的后端 ({len(successful_backends)}): {', '.join(successful_backends)}{Colors.END}")
        
        # 显示性能排序
        performance_data = []
        for backend in successful_backends:
            result = results[backend]
            if result and '_test_duration' in result:
                performance_data.append((backend, result['_test_duration']))
        
        if performance_data:
            performance_data.sort(key=lambda x: x[1])
            print(f"{Colors.BLUE}\n🏆 性能排名（按耗时排序）:{Colors.END}")
            for i, (backend, duration) in enumerate(performance_data, 1):
                tester = BackendTester("", "")
                print(f"{Colors.BLUE}   {i}. {backend}: {tester._format_duration(duration)}{Colors.END}")
    
    if failed_backends:
        print(f"{Colors.RED}❌ 失败的后端 ({len(failed_backends)}): {', '.join(failed_backends)}{Colors.END}")
    
    success_rate = len(successful_backends) / total_backends * 100
    color = Colors.GREEN if success_rate >= 80 else Colors.YELLOW if success_rate >= 50 else Colors.RED
    print(f"\n{color}📊 总体成功率: {len(successful_backends)}/{total_backends} = {success_rate:.1f}%{Colors.END}")

def main():
    parser = argparse.ArgumentParser(
        description='优化的 MinerU 2.0 Web API 后端测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python test_backends.py                                    # 使用默认demo.pdf
  python test_backends.py --file test.pdf                   # 使用指定文件
  python test_backends.py --concurrent                      # 并发测试
  python test_backends.py --benchmark 5                     # 基准测试5次
  python test_backends.py -b pipeline vlm-transformers      # 只测试指定后端
  python test_backends.py --dump-files                      # 保存解析结果到文件
        """
    )
    
    # 获取默认PDF路径
    default_pdf = get_default_pdf_path()
    
    parser.add_argument('--file', '-f', 
                       default=default_pdf,
                       help=f'测试用的PDF文件路径 (默认: {default_pdf or "未找到demo.pdf"})')
    parser.add_argument('--base-url', '-u', 
                       default='http://localhost:8888', 
                       help='API服务器地址 (默认: http://localhost:8888)')
    parser.add_argument('--sglang-server', '-s', 
                       help='SGLang服务器地址（用于测试 vlm-sglang-client）')
    parser.add_argument('--backends', '-b', nargs='+', 
                       choices=['pipeline', 'vlm-transformers', 'vlm-sglang-engine', 'vlm-sglang-client'],
                       default=['pipeline', 'vlm-transformers', 'vlm-sglang-engine', 'vlm-sglang-client'],
                       help='要测试的后端列表')
    parser.add_argument('--concurrent', '-c', action='store_true',
                       help='并发测试所有后端（更快但资源占用更多）')
    parser.add_argument('--benchmark', '-bm', type=int, metavar='N',
                       help='对每个后端进行N次基准测试')
    parser.add_argument('--timeout', '-t', type=int, default=3000,
                       help='请求超时时间（秒，默认3000）')
    parser.add_argument('--dump-files', '-d', action='store_true',
                       help='保存解析结果到文件（JSON、MD等文件保存到 test_output 目录）')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not args.file:
        print(f"{Colors.RED}❌ 未找到默认的demo.pdf文件，请使用 --file 参数指定PDF文件{Colors.END}")
        return
        
    if not Path(args.file).exists():
        print(f"{Colors.RED}❌ 文件不存在: {args.file}{Colors.END}")
        return
    
    # 检查API服务器
    if not check_api_server(args.base_url):
        return
    
    # 显示测试信息
    file_path = Path(args.file)
    file_size = file_path.stat().st_size
    tester = BackendTester(args.base_url, args.file, args.timeout)
    
    print(f"\n{Colors.BOLD}🚀 开始测试{Colors.END}")
    print(f"{Colors.BLUE}📁 测试文件: {args.file}{Colors.END}")
    print(f"{Colors.BLUE}📏 文件大小: {tester._format_size(file_size)}{Colors.END}")
    print(f"{Colors.BLUE}🎯 目标后端: {', '.join(args.backends)}{Colors.END}")
    print(f"{Colors.BLUE}⏱️  超时设置: {tester._format_duration(args.timeout)}{Colors.END}")
    
    if args.dump_files:
        print(f"{Colors.BLUE}💾 文件保存: 启用（保存到 test_output 目录）{Colors.END}")
    else:
        print(f"{Colors.BLUE}💾 文件保存: 禁用{Colors.END}")
    
    if args.concurrent:
        print(f"{Colors.BLUE}🔄 测试模式: 并发{Colors.END}")
    elif args.benchmark:
        print(f"{Colors.BLUE}🏃‍♂️ 测试模式: 基准测试 ({args.benchmark} 次){Colors.END}")
    else:
        print(f"{Colors.BLUE}📋 测试模式: 顺序{Colors.END}")
    
    # 执行测试
    if args.benchmark:
        # 基准测试模式
        benchmark_results = {}
        for backend in args.backends:
            benchmark_results[backend] = tester.benchmark_backend(backend, args.benchmark, args.sglang_server, args.dump_files)
        
        # 显示基准测试总结
        print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}🏆 基准测试总结{Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        
        successful_benchmarks = [(k, v) for k, v in benchmark_results.items() if v['successful_runs'] > 0]
        successful_benchmarks.sort(key=lambda x: x[1]['avg_duration'])
        
        for i, (backend, result) in enumerate(successful_benchmarks, 1):
            print(f"{Colors.GREEN}{i}. {backend}:")
            print(f"   平均耗时: {tester._format_duration(result['avg_duration'])}")
            print(f"   成功率: {result['success_rate']:.1f}%{Colors.END}")
            
    elif args.concurrent:
        # 并发测试模式
        results = tester.test_concurrent(args.backends, args.sglang_server, args.dump_files)
        print_summary(results, len(args.backends))
    else:
        # 顺序测试模式
        results = {}
        for backend in args.backends:
            result = tester.test_backend(backend, args.sglang_server, dump_files=args.dump_files)
            results[backend] = result
        
        print_summary(results, len(args.backends))


if __name__ == '__main__':
    main() 