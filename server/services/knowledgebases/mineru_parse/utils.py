#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import mysql.connector
import os
import tiktoken
import tempfile
import json



def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


tiktoken_cache_dir = tempfile.gettempdir()
os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
encoder = tiktoken.get_encoding("cl100k_base")


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0


def truncate(string: str, max_len: int) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    return encoder.decode(encoder.encode(string)[:max_len])


def split_markdown_to_chunks(txt, chunk_token_num=128):
    sections = []
    for sec in txt.split("\n"):
        if num_tokens_from_string(sec) > 3 * chunk_token_num:
            sections.append(sec[:int(len(sec) / 2)])
            sections.append(sec[int(len(sec) / 2):])
        else:
            if sec.strip().find("#") == 0:
                sections.append(sec)
            elif sections and sections[-1].strip().find("#") == 0:
                sec_ = sections.pop(-1)
                sections.append(sec_ + "\n" + sec)
            else:
                sections.append(sec)
    return sections

_blocks_cache = {}
def get_blocks_from_md(md_file_path):
    if md_file_path in _blocks_cache:
        return _blocks_cache[md_file_path]
    json_path = md_file_path.replace('.md', '_middle.json')
    with open(json_path, 'r') as f:
        data = json.load(f)
        block_list = []
        for page_idx, page in enumerate(data['pdf_info']):
            for block in page['preproc_blocks']:
                if block['type'] in ('text', 'title'):
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            content = span.get('content', '').strip()
                            bbox = block.get('bbox')
                            if content and bbox:
                                block_list.append({'content': content, 'bbox': bbox, 'page_number': page_idx })
    _blocks_cache[md_file_path] = block_list
    return block_list

def get_bbox_for_chunk(md_file_path, chunk_content):
    """
    根据 md 文件路径和 chunk 内容，返回 chunk_content 中包含的最长 block['content'] 的 bbox，并追加 page_number。
    """
    block_list = get_blocks_from_md(md_file_path)
    best_block = None
    max_len = 0
    for block in block_list:
        if block['content'] and block['content'] in chunk_content:
            if len(block['content']) > max_len:
                best_block = block
                max_len = len(block['content'])
    if best_block:
        bbox = best_block['bbox']
        page_number = best_block['page_number']
        position_int = [[page_number, bbox[0], bbox[2], bbox[1], bbox[3]]]
        return position_int
    return None


def update_document_progress(doc_id, progress=None, message=None, status=None, run=None, chunk_count=None, process_duration=None):
    """更新数据库中文档的进度和状态"""
    conn = None
    cursor = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = []
        params = []

        if progress is not None:
            updates.append("progress = %s")
            params.append(float(progress))
        if message is not None:
            updates.append("progress_msg = %s")
            params.append(message)
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if run is not None:
            updates.append("run = %s")
            params.append(run)
        if chunk_count is not None:
             updates.append("chunk_num = %s")
             params.append(chunk_count)
        if process_duration is not None:
            updates.append("process_duation = %s")
            params.append(process_duration)


        if not updates:
            return

        query = f"UPDATE document SET {', '.join(updates)} WHERE id = %s"
        params.append(doc_id)
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"[Parser-ERROR] 更新文档 {doc_id} 进度失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()