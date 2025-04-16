from .. import multimodal_bp
from flask import request, jsonify
import sys
import tempfile
import os
import subprocess
import shutil


@multimodal_bp.route('/process_pdf', methods=['POST'])
def process_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        # 创建临时文件
        original_filename = file.filename
        temp_dir = tempfile.mkdtemp() 
        tmp_path = os.path.join(temp_dir, original_filename)
        file.save(tmp_path)

        python_executable = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'venv', 'bin', 'python3.10')    
        # 调用处理脚本
        result = subprocess.run(
            [python_executable, 'services/multimodal/process_pdf.py', '--pdf_path', tmp_path],
            text=True,
            stdout=sys.stdout,  # 直接输出到控制台
            stderr=sys.stderr  # 直接输出错误到控制台
            # capture_output=True,  # 捕获输出
            # check=False  # 不自动抛出异常，让我们手动处理返回码
        )

        # 清理临时文件
        shutil.rmtree(temp_dir)
        
        # 检查返回码
        if result.returncode != 0:
            return jsonify({
                'code': 500,
                'message': '处理失败',
                'error': result.stderr or result.stdout,  # stderr优先，如果没有则使用stdout
                'returncode': result.returncode
            }), 500
            
        # 即使返回码为0，也检查输出中是否包含错误信息
        if result.stderr or "ERROR" in result.stdout or "Error" in result.stdout:
            return jsonify({
                'code': 500,
                'message': '处理过程中出现错误',
                'error': result.stderr or result.stdout,
                'returncode': result.returncode
            }), 500
            
        return jsonify({
            "code": 0,
            "message": "PDF 处理成功"
        })
        
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({
            'code': 500,
            'message': '处理失败'
        }), 500