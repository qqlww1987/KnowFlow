#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, types, re

# Mock imports
for mod_name in ['config', 'api.apps.chunk_app', 'api.utils',
                 'knowflow.server.services.knowledgebases.common.chunking_interface',
                 'knowflow.server.services.knowledgebases.common.coordinate_mappers']:
    sys.modules[mod_name] = types.ModuleType(mod_name)

for pkg in ['knowflow', 'knowflow.server', 'knowflow.server.services',
            'knowflow.server.services.knowledgebases',
            'knowflow.server.services.knowledgebases.mineru_parse']:
    mod = types.ModuleType(pkg)
    mod.__path__ = []
    sys.modules[pkg] = mod

# Load utils.py content
with open('knowflow/server/services/knowledgebases/mineru_parse/utils.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'from \.\.\.config import CONFIG, APP_CONFIG', 'CONFIG={}; APP_CONFIG={}', code)
code = re.sub(r'from \.\.chunking_interface import', 'from knowflow.server.services.knowledgebases.common.chunking_interface import', code)
code = re.sub(r'from \.\.coordinate_mappers import', 'from knowflow.server.services.knowledgebases.common.coordinate_mappers import', code)

exec(code)

# 读取真实测试文档（从之前创建的测试文件中）
# 由于测试文件已删除，直接使用内嵌的简化版真实文档
TEST_DOC = open('knowflow/server/services/knowledgebases/mineru_parse/test_advanced_split.py', 'r', encoding='utf-8').read()
start = TEST_DOC.find('TEST_DOC = """')
end = TEST_DOC.find('"""\n\n\ndef main')
TEST_DOC = TEST_DOC[start+14:end]

print('=' * 70)
print('测试：真实施工工法文档的分块效果')
print('=' * 70)
print(f'文档总长度: {len(TEST_DOC)} 字符')
print(f'文档总 tokens: {num_tokens_from_string(TEST_DOC)}')

for chunk_size, label in [(1024, '默认1024'), (512, '较小512'), (256, '小256')]:
    print(f"\n{'='*70}")
    print(f'配置: chunk_token_num={chunk_size} ({label})')
    print(f"{'='*70}")

    chunks = split_markdown_to_chunks_advanced(
        TEST_DOC,
        chunk_token_num=chunk_size,
        min_chunk_tokens=10,
        include_metadata=True
    )

    tokens_list = [c['token_count'] for c in chunks]
    print(f'总分块数: {len(chunks)}')
    print(f'Token 分布: min={min(tokens_list)}, max={max(tokens_list)}, avg={sum(tokens_list)/len(tokens_list):.0f}')

    from collections import Counter
    type_counts = Counter(c['chunk_type'] for c in chunks)
    print(f'分块类型: {dict(type_counts)}')

    # 检查是否有超大分块未被切分
    has_oversized = any(c['chunk_type'] == 'oversized_special' for c in chunks)
    oversized_count = sum(1 for c in chunks if c['token_count'] > chunk_size * 1.5)
    print(f'超大分块(>{chunk_size*1.5}): {oversized_count}个')
    print(f'是否有oversized_special类型: {has_oversized}')

    print(f'\n各分块详情:')
    for i, chunk in enumerate(chunks):
        metadata = chunk.get('metadata', {})
        title = ''
        if metadata and isinstance(metadata, dict):
            max_level = max((k for k in metadata.keys() if isinstance(k, int)), default=0)
            if max_level:
                title = metadata[max_level][:35]
        chunk_type = chunk.get('chunk_type', 'unknown')
        marker = ' ***' if chunk['token_count'] > chunk_size * 1.5 else ''
        print(f'  [{i+1:2d}] {chunk["token_count"]:5d} tokens | {chunk_type:25s} | {title}{marker}')
