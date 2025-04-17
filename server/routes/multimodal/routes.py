import code
from .. import multimodal_bp
from flask import request, jsonify
import sys
import tempfile
import os
import subprocess
import shutil
import uuid
import threading

# 存储任务状态的全局字典
task_status = {}

def process_pdf_task(task_id, tmp_path):
    try:
        python_executable = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'venv', 'bin', 'python3.10')

        # 调用处理脚本
        process = subprocess.Popen(
            [python_executable, 'services/multimodal/process_pdf.py', '--pdf_path', tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # stdout=sys.stdout,  # 直接输出到控制台
            # stderr=sys.stderr,  # 直接输出错误到控制台
            text=True
        )

        # 读取输出并更新状态
        while True:
            output = process.stdout.readline()
            if output:
                print(f"Debug: {output.strip()}")   
                task_status[task_id]['logs'].append(output.strip())
                # 根据输出更新进度
                if "第1步" in output:
                    task_status[task_id]['progress'] = 20
                elif "第2步" in output:
                    task_status[task_id]['progress'] = 40
                elif "第3步" in output:
                    task_status[task_id]['progress'] = 50
                elif "第4步" in output:
                    task_status[task_id]['progress'] = 60
                elif "第5步" in output:
                    task_status[task_id]['progress'] = 70
                elif "第6步" in output:
                    task_status[task_id]['progress'] = 80
                elif "全部任务处理完成" in output:
                    task_status[task_id]['progress'] = 100
                    task_status[task_id]['status'] = 'completed'
                    break

            # 检查进程是否结束
            if process.poll() is not None:
                # 检查返回码
                if process.returncode != 0:
                    # 获取所有剩余的错误输出
                    remaining_errors = process.stderr.read()
                    if remaining_errors:
                        task_status[task_id]['logs'].append(remaining_errors.strip())
                    task_status[task_id]['status'] = 'failed'
                break

        # 清理临时文件
        shutil.rmtree(os.path.dirname(tmp_path))

    except Exception as e:
        task_status[task_id]['status'] = 'failed'
        task_status[task_id]['logs'].append(str(e))

@multimodal_bp.route('/process_pdf', methods=['POST'])
def process_pdf():
 
    file = request.files['file']

    if file.filename == '':
       return jsonify({'code': 400, 'message': '文件名为空',"data": {"task_id": task_id}})

    try:
        # 创建任务ID
        task_id = str(uuid.uuid4())
        task_status[task_id] = {'status': 'processing', 'progress': 0, 'logs': []}

        # 创建临时文件
        original_filename = file.filename
        temp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(temp_dir, original_filename)
        file.save(tmp_path)

        # 启动后台线程处理任务
        threading.Thread(target=process_pdf_task, args=(task_id, tmp_path)).start()

        return jsonify({ "data": {"task_id": task_id},'code': 0})
        

    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'code': 500, 'message': '解析文档过程中异常',"data": {"task_id": task_id}})

@multimodal_bp.route('/process_status/<string:task_id>', methods=['GET'])
def get_process_status(task_id):
    """获取处理进度"""
    if task_id not in task_status:
        return jsonify({'message': '不存在该任务','code': 404 })

    return jsonify({'code':0,'data':task_status[task_id]})