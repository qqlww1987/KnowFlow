from flask import request, jsonify
from utils import success_response, error_response
from services.files.document_service import DocumentService
from .. import documents_bp
import json
import os

@documents_bp.route('/<doc_id>/chunking-config', methods=['GET'])
def get_document_chunking_config(doc_id):
    """获取文档分块配置"""
    try:
        # 从数据库获取文档信息
        document = DocumentService.get_by_id(doc_id)
        if not document:
            return error_response("文档不存在", code=404)
        
        # 解析parser_config中的chunking_config
        parser_config = {}
        if document.parser_config:
            if isinstance(document.parser_config, str):
                parser_config = json.loads(document.parser_config)
            else:
                parser_config = document.parser_config
        
        chunking_config = parser_config.get('chunking_config', {
            'strategy': 'smart',
            'chunk_token_num': 256,
            'min_chunk_tokens': 10
        })
        
        return success_response(data={'chunking_config': chunking_config})
        
    except Exception as e:
        return error_response(f"获取分块配置失败: {str(e)}", code=500)

@documents_bp.route('/<doc_id>/chunking-config', methods=['PUT'])
def update_document_chunking_config(doc_id):
    """更新文档分块配置"""
    try:
        data = request.get_json()
        if not data or 'chunking_config' not in data:
            return error_response("缺少分块配置数据", code=400)
        
        chunking_config = data['chunking_config']
        
        # 验证分块配置
        required_fields = ['strategy', 'chunk_token_num', 'min_chunk_tokens']
        for field in required_fields:
            if field not in chunking_config:
                return error_response(f"缺少必需字段: {field}", code=400)
        
        # 验证策略类型
        valid_strategies = ['basic', 'smart', 'advanced', 'strict_regex']
        if chunking_config['strategy'] not in valid_strategies:
            return error_response(f"无效的分块策略: {chunking_config['strategy']}", code=400)
        
        # 验证数值范围
        if not (50 <= chunking_config['chunk_token_num'] <= 2048):
            return error_response("chunk_token_num必须在50-2048之间", code=400)
        
        if not (10 <= chunking_config['min_chunk_tokens'] <= 500):
            return error_response("min_chunk_tokens必须在10-500之间", code=400)
        
        # 获取现有文档
        document = DocumentService.get_by_id(doc_id)
        if not document:
            return error_response("文档不存在", code=404)
        
        # 更新parser_config中的chunking_config
        current_parser_config = {}
        if document.parser_config:
            if isinstance(document.parser_config, str):
                current_parser_config = json.loads(document.parser_config)
            else:
                current_parser_config = document.parser_config
        
        current_parser_config['chunking_config'] = chunking_config
        
        # 更新文档
        update_data = {
            'parser_config': json.dumps(current_parser_config)
        }
        
        DocumentService.update(doc_id, update_data)
        
        return success_response(data={'message': '分块配置更新成功'})
        
    except Exception as e:
        return error_response(f"更新分块配置失败: {str(e)}", code=500)

def parse_with_mineru(file_path, page_range=None):
    """
    使用 MinerU 解析 PDF 文件 - 优化版本，复用现有 API 请求方案
    """
    try:
        # 导入必要的模块
        from services.knowledgebases.mineru_parse.fastapi_adapter import get_global_adapter
        
        # 获取全局适配器
        adapter = get_global_adapter()
        
        # 定义进度回调函数（可选）
        def update_progress(progress, message):
            print(f"[进度 {progress*100:.1f}%] {message}")
        
        # 准备请求参数
        kwargs = {
            'return_middle_json': True,   # 确保返回 middle_json 信息
            'return_images': True         # 获取原始图片数据
        }
        
        # 如果指定了页面范围，添加到请求参数中
        if page_range:
            kwargs['page_range'] = page_range
        
        # 使用适配器处理文件
        result = adapter.process_file(
            file_path=file_path,
            update_progress=update_progress,
            **kwargs
        )
        
        # 解析返回的内容
        sections = []
        tables = []
        
        # 处理适配器返回的结果，优先使用包含位置信息的方法
        if 'middle_json' in result and result['middle_json']:
            # 从 middle_json 中提取位置信息
            sections.extend(_parse_middle_json_to_sections_with_positions(result['middle_json']))
        elif 'results' in result and result['results']:
            # 兼容旧格式：从 results 数组中获取
            for item in result['results']:
                if 'middle_json' in item and item['middle_json']:
                    sections.extend(_parse_middle_json_to_sections_with_positions(item['middle_json']))
                elif 'md_content' in item and item['md_content']:
                    sections.extend(_parse_md_content_to_sections(item['md_content']))
        elif 'md_content' in result and result['md_content']:
            # 新格式：直接从结果中获取
            sections.extend(_parse_md_content_to_sections(result['md_content']))
        
        return sections, tables
        
    except Exception as e:
        print(f"MinerU 解析错误: {str(e)}")
        raise Exception(f"MinerU 解析失败: {str(e)}")


@documents_bp.route('/parse-with-mineru', methods=['POST'])
def parse_with_mineru_endpoint():
    """使用MinerU解析文档"""
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return error_response("缺少文件", code=400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("未选择文件", code=400)
        
        # 获取可选参数
        start_page = request.form.get('start_page', type=int)
        end_page = request.form.get('end_page', type=int)
        
        # 保存临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
        
        try:
            # 准备页面范围参数
            page_range = None
            if start_page is not None and end_page is not None:
                page_range = f"{start_page}-{end_page}"
            elif start_page is not None:
                page_range = f"{start_page}-"
            elif end_page is not None:
                page_range = f"-{end_page}"
            
            # 使用新的parse_with_mineru函数
            sections, tables = parse_with_mineru(temp_file_path, page_range)
            print(f"[DEBUG] parse_with_mineru 返回结果: sections数量={len(sections)}, tables数量={len(tables)}")
            if sections:
                print(f"[DEBUG] 第一个section: {sections[0]}")
            if tables:
                print(f"[DEBUG] 第一个table: {tables[0]}")
            else:
                print(f"[DEBUG] 没有找到tables数据")
            
            return success_response(data={
                'sections': sections,
                'tables': tables,
                'total_sections': len(sections),
                'total_tables': len(tables)
            })
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        return error_response(f"解析失败: {str(e)}", code=500)


def _parse_middle_json_to_sections_with_positions(middle_json):
    """
    从 middle_json 中提取文本内容和位置信息
    """
    sections = []
    
    try:
        # 解析 middle_json 字符串为字典
        if isinstance(middle_json, str):
            middle_data = json.loads(middle_json)
        else:
            middle_data = middle_json
        
        # 获取 pdf_info 数组
        pdf_info = middle_data.get('pdf_info', [])
        
        for page_idx, page_data in enumerate(pdf_info):
            # 获取页面的预处理块
            preproc_blocks = page_data.get('preproc_blocks', [])
            
            for block in preproc_blocks:
                block_type = block.get('type', '')
                bbox = block.get('bbox', [])
                
                # 提取文本内容
                text_content = ""
                lines = block.get('lines', [])
                
                for line in lines:
                    spans = line.get('spans', [])
                    for span in spans:
                        if span.get('type') == 'text':
                            text_content += span.get('content', '') + " "
                
                text_content = text_content.strip()
                
                # 过滤太短的内容
                if len(text_content) < 10:
                    continue
                
                # 构建位置信息，格式为 [page_number, x0, x1, y0, y1]
                positions = []
                if len(bbox) >= 4:
                    # bbox 格式通常是 [x0, y0, x1, y1]
                    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
                    positions = [page_idx, x0, x1, y0, y1]
                
                # 构建 section
                section = {
                    'type': 'heading' if block_type == 'title' else 'text',
                    'content': text_content
                }
                
                # 添加位置信息（如果有的话）
                if positions:
                    section['positions'] = [positions]
                
                sections.append(section)
                
    except Exception as e:
        print(f"解析 middle_json 时出错: {str(e)}")
        # 如果解析失败，返回空列表
        return []
    
    return sections


def _parse_md_content_to_sections(md_content):
    """
    将 markdown 内容解析为 sections
    """
    sections = []
    
    # 将 markdown 内容按段落分割
    paragraphs = md_content.split('\n\n')
    
    for paragraph in paragraphs:
        # 清理段落内容
        cleaned_paragraph = paragraph.strip()
        
        # 移除多余的markdown格式
        cleaned_paragraph = cleaned_paragraph.replace('**', '')
        cleaned_paragraph = cleaned_paragraph.replace('*', '')
        
        # 处理标题
        if cleaned_paragraph.startswith('#'):
            # 移除多余的 # 符号，保留一个
            while cleaned_paragraph.startswith('##'):
                cleaned_paragraph = cleaned_paragraph[1:]
            cleaned_paragraph = cleaned_paragraph.lstrip('#').strip()
            
            if len(cleaned_paragraph) > 20:  # 过滤太短的内容
                sections.append({
                    'type': 'heading',
                    'content': cleaned_paragraph
                })
        elif len(cleaned_paragraph) > 20:  # 过滤太短的内容
            sections.append({
                'type': 'text',
                'content': cleaned_paragraph
            })
    
    return sections