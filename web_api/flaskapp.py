import tempfile
from typing import Optional, Tuple, Union
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.utils.enum_class import MakeMode
from mineru.utils.draw_bbox import draw_layout_bbox
from mineru.data.data_reader_writer import FileBasedDataWriter

from markdown_chunker import split_markdown_to_chunks_advanced,create_child_chunks
from popeline import create_document_file_mineru, create_segments_from_chunks, update_markdown_image_urls_with_api, upload_document_segments
from vlm import process_file_vlm
app = Flask(__name__)

# 允许上传的文件类型
pdf_extensions = [".pdf"]
office_extensions = [".ppt", ".pptx", ".doc", ".docx"]

def allowed_file(filename):
    return '.' in filename and os.path.splitext(filename)[1].lower() in pdf_extensions

@app.route('/file_parse', methods=['POST'])
def file_parse():
    print("Received request for file parsing")
    file = request.files.get('file')
    file_path = request.form.get('file_path')
    start_page = int(request.form.get('start_page', -1))
    end_page = request.form.get('end_page')  # 可为 None
    output_dir = request.form.get('output_dir', 'output')

    if not file and not file_path:
        return jsonify({"error": "Must provide either file or file_path"}), 400

    if file and not allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400

    try:
        if file:
            filename = secure_filename(file.filename)
            file.save(filename)
            with open(filename, 'rb') as f:
                file_bytes = f.read()
            os.remove(filename)
        else:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
        output_path = f"{output_dir}/{filename}"
        output_image_path = f"{output_path}/images"
        output_path_checked = output_path if output_path else "output"
        output_image_path_checked = output_image_path if output_image_path else f"{output_path_checked}/images"
        writer = FileBasedDataWriter(output_path_checked)
        image_writer = FileBasedDataWriter(output_image_path_checked)
        os.makedirs(output_image_path_checked, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        # Initialize readers/writers and get PDF content
       
        # 解析起始和结束页码
        start = start_page
        end = int(end_page) if end_page is not None else None

        # 分页处理
        all_results = []
        page_idx = start
        output_image_path = os.path.join(output_dir, 'images')
        os.makedirs(output_image_path, exist_ok=True)
        image_writer = FileBasedDataWriter(output_image_path)  # ✅ 新增
        while True:
            # 提取单页内容
            processed_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(file_bytes, page_idx, page_idx + 1)
            if not processed_bytes:
                break
            parse_method = "ocr"
            lang = "ch"
            ocrenble= True
            # 调用解析模块
            infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze([processed_bytes], ["ch"], parse_method, True, True)
            model_list = infer_results[0]
            images_list = all_image_lists[0] # 假设无图像
            pdf_doc = all_pdf_docs[0]   # 假设不返回完整 PDF 文档结构
            # model_json = json.loads(json.dumps(model_list)) # deepcopy
            middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, "ch", ocrenble, True)

            # 构建结果
            md_content = pipeline_union_make(middle_json["pdf_info"], MakeMode.MM_MD, "images")
            # content_list = pipeline_union_make(middle_json["pdf_info"], MakeMode.CONTENT_LIST, "images")

            all_results.append({
                "page": page_idx,
                # "content_list": content_list,
                "md_content": md_content,
                # "layout": model_list
            })

            page_idx += 1
            if end is not None and page_idx >= end:
                break

        # 保存结果（可选）
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'results.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        combined_md_path = os.path.join(output_dir, "combined_output.md")
        with open(combined_md_path, "w", encoding="utf-8") as f:
            for result in all_results:
                page_idx = result["page"]
                md_content = result["md_content"]
                # f.write(f"<!-- Page {page_idx} -->\n")
                f.write(md_content)
                # f.write("\n\n---\n\n")
        return jsonify({
            "results": all_results,
            "output_file": output_file
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/file_parseNew', methods=['POST'])
def file_parseNew():
    print("Received request for file parsing")
    file = request.files.get('file')
    file_path = request.form.get('file_path')
    output_dir = request.form.get('output_dir', 'output')

    if not file and not file_path:
        return jsonify({"error": "Must provide either file or file_path"}), 400

    if file and not allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400

    try:
        if file:
            filename = secure_filename(file.filename)
            file.save(filename)
            with open(filename, 'rb') as f:
                file_bytes = f.read()
            os.remove(filename)
        else:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
        output_path = f"{output_dir}/{filename}"
        output_image_path = f"{output_path}/images"
        output_path_checked = output_path if output_path else "output"
        output_image_path_checked = output_image_path if output_image_path else f"{output_path_checked}/images"
        writer = FileBasedDataWriter(output_path_checked)
        image_writer = FileBasedDataWriter(output_image_path_checked)
        os.makedirs(output_image_path_checked, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        # Initialize readers/writers and get PDF content
       


        # 分页处理
        all_results = []
        output_image_path = os.path.join(output_dir, 'images')
        os.makedirs(output_image_path, exist_ok=True)
        image_writer = FileBasedDataWriter(output_image_path)  # ✅ 新增
    
        processed_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(file_bytes, 0, None)
        parse_method = "ocr"
        lang = "ch"
        ocrenble= True
        # 调用解析模块
        infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze([processed_bytes], ["ch"], parse_method, True, True)
        model_list = infer_results[0]
        images_list = all_image_lists[0] # 假设无图像
        pdf_doc = all_pdf_docs[0]   # 假设不返回完整 PDF 文档结构
        #这里VLM模式解析先不管
        # backend='vlm-transformers'
        # # if backend == "pipeline":
        # #     model_json, middle_json, content_list, md_content, processed_bytes, pdf_info = process_file_pipeline(
        # #         file_bytes, file_extension, image_writer, parse_method, lang, formula_enable, table_enable
        # #     )
        # # else:
        #     # VLM backends
        # vlm_backend = backend[4:] if backend.startswith("vlm-") else backend
        # model_json, middle_json, content_list, md_content, processed_bytes, pdf_info = process_file_vlm(
        #     file_bytes, "pdf", image_writer, vlm_backend, ""
        # )
        model_json = json.loads(json.dumps(model_list)) # deepcopy
        middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, "ch", ocrenble, True)

        # 构建结果
        md_content = pipeline_union_make(middle_json["pdf_info"], MakeMode.MM_MD, "images")
        content_list = pipeline_union_make(middle_json["pdf_info"], MakeMode.CONTENT_LIST, "images")

        all_results.append({

            "content_list": content_list,
            "md_content": md_content,
            "layout": model_list
        })

        # 保存结果（可选）
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'results.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        combined_md_path = os.path.join(output_dir, "combined_output.md")
        with open(combined_md_path, "w", encoding="utf-8") as f:
            for result in all_results:
                md_content = result["md_content"]
                # f.write(f"<!-- Page {page_idx} -->\n")
                f.write(md_content)
                # f.write("\n\n---\n\n")
        return jsonify({
            "results": all_results,
            "output_file": output_file
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/file_parse_dify', methods=['POST'])
def file_parse_dify():
    print("Received request for file parsing")
    file = request.files.get('file')
    file_path = request.form.get('file_path')
    # document_id = request.form.get('document_id')
    dataset_id = request.form.get('dataset_id')
    api_key = request.form.get('api_key')
    daset_key = request.form.get('daset_key')
    daset_key='dataset-FP88yXDLcUecN69mI8ifFZXl'
    api_base_url= request.form.get('api_base_url')
    if not file and not file_path:
        return jsonify({"error": "Must provide either file or file_path"}), 400

    # if file and not allowed_file(file.filename):
    #     return jsonify({"error": "File type not supported"}), 400

    try:
        if file:
            filename = secure_filename(file.filename)
            file.save(filename)
            with open(filename, 'rb') as f:
                file_bytes = f.read()
            os.remove(filename)
        else:
            with open(file_path, 'rb') as f:
                filename = os.path.basename(file_path)
                file_bytes = f.read()
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, filename)
        os.makedirs(output_path, exist_ok=True)
        output_image_path = f"{output_path}/images"
        output_path_checked = output_path if output_path else "output"
        output_image_path_checked = output_image_path if output_image_path else f"{output_path_checked}/images"
        os.makedirs(output_image_path_checked, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        # Initialize readers/writers and get PDF content
       


        # 分页处理
        all_results = []
        image_writer = FileBasedDataWriter(output_image_path)  # ✅ 新增
    
        processed_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(file_bytes, 0, None)
        parse_method = "ocr"
        lang = "ch"
        ocrenble= True
        # 调用解析模块
        infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze([processed_bytes], ["ch"], parse_method, True, True)
        model_list = infer_results[0]
        images_list = all_image_lists[0] # 假设无图像
        pdf_doc = all_pdf_docs[0]   # 假设不返回完整 PDF 文档结构
        model_json = json.loads(json.dumps(model_list)) # deepcopy
        middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, "ch", ocrenble, True)

        # 构建结果
        md_content = pipeline_union_make(middle_json["pdf_info"], MakeMode.MM_MD, "images")
        # content_list = pipeline_union_make(middle_json["pdf_info"], MakeMode.CONTENT_LIST, "images")

        all_results.append({

            # "content_list": content_list,
            "md_content": md_content,
            "layout": model_list
        })
        # 这里循环对应的文件文件夹循环
        
        # 保存结果（可选）
        os.makedirs(output_path, exist_ok=True)
        # output_file = os.path.join(output_path, 'results.json')
        # with open(output_file, 'w', encoding='utf-8') as f:
        #     json.dump(all_results, f, ensure_ascii=False, indent=2)
        combined_md_path = os.path.join(output_path, "combined_output.md")
        with open(combined_md_path, "w", encoding="utf-8") as f:
            for result in all_results:
                md_content = result["md_content"]
                # f.write(f"<!-- Page {page_idx} -->\n")
                f.write(md_content)
                # f.write("\n\n---\n\n")
        # 这里已经可以进行操作了
        txtNew= update_markdown_image_urls_with_api(md_file_path=combined_md_path,api_base_url=api_base_url, image_dir=output_image_path, api_key=api_key)
        # txtNew= update_markdown_image_urls_with_api(combined_md_path, output_image_path, "app-zLh7zvRCvSQGmSQZjAqDiAiO")
        # 然后这里进行文件分块处理
        # chunks=split_markdown_to_chunks_parent_child(txtNew)
        chunks= split_markdown_to_chunks_advanced(txtNew)
        # chunks= split_markdown_to_chunks_with_hierarchy(txtNew)
        seglist= create_segments_from_chunks(chunks)
        api_base_url= 'http://10.1.30.45'
        document_id=create_document_file_mineru(dataset_id=dataset_id,base_url=api_base_url,api_key=daset_key,file_path=file_path)
        upload_document_segments(dataset_id=dataset_id,document_id=document_id,segments=seglist,api_base_url=api_base_url,datasetKey=daset_key)
        # upload_document_segments(dataset_id='e8ef43b0-b26e-4b04-8133-814cb10d071d',document_id='17dca107-fb35-43c8-90a6-54a3bf31f5c1',
        #                           segments=seglist)
        # upload_document_segments(dataset_id='150b46ab-872d-4a56-9a02-c9810dfd57da',document_id='83eff70e-ea81-46cc-871a-22037953ec01',
        #                           segments=seglist)
        return jsonify({
            "results": all_results,
            # "output_file": output_file
        }), 200

    except Exception as e:
        print(f"Error during file parsing: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/file_parse_dify_file', methods=['POST'])
def file_parse_dify_file():
    print("Received request for file parsing")
    combined_md_path = request.form.get('combined_md_path')
    output_image_path = request.form.get('output_image_path')
    dataset_id = request.form.get('dataset_id')
    api_key = request.form.get('api_key')
    daset_key = request.form.get('daset_key')
    api_base_url= request.form.get('api_base_url')
    try:
        # 这里已经可以进行操作了
        txtNew= update_markdown_image_urls_with_api(md_file_path=combined_md_path, image_dir=output_image_path,api_base_url=api_base_url,api_key=api_key)
        # txtNew= update_markdown_image_urls_with_api(combined_md_path, output_image_path, "app-zLh7zvRCvSQGmSQZjAqDiAiO")
        # 然后这里进行文件分块处理
        chunks= split_markdown_to_chunks_advanced(txtNew)
        docid=create_document_file_mineru(dataset_id=dataset_id,base_url=api_base_url,api_key=daset_key)
        # chunks= split_markdown_to_chunks_with_hierarchy(txtNew)
        seglist= create_segments_from_chunks(chunks)
        
        upload_document_segments(dataset_id=dataset_id,document_id=docid,segments=seglist,api_base_url=api_base_url,datasetKey=daset_key)
        # upload_document_segments(dataset_id='e8ef43b0-b26e-4b04-8133-814cb10d071d',document_id='17dca107-fb35-43c8-90a6-54a3bf31f5c1',
        #                           segments=seglist)
        # upload_document_segments(dataset_id='150b46ab-872d-4a56-9a02-c9810dfd57da',document_id='83eff70e-ea81-46cc-871a-22037953ec01',
        #                           segments=seglist)
        return jsonify({
            "results":True,
            "document_id": docid
            # "output_file": output_file
        }), 200
    except Exception as e:
        print(f"Error during file parsing: {e}")
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)