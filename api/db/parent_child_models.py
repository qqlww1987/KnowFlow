#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

"""
父子分块数据库模型扩展
支持 ParentDocumentRetriever 的数据结构
"""

from peewee import CharField, IntegerField, TextField, ForeignKeyField, BooleanField
from api.db.db_models import DataBaseModel, Document


class ParentChunk(DataBaseModel):
    """父分块模型 - 存储较大的上下文信息"""
    
    # 基本信息
    id = CharField(max_length=128, primary_key=True)
    doc_id = CharField(max_length=128, index=True)  # 对应 Document.id
    kb_id = CharField(max_length=128, index=True)   # 知识库ID
    
    # 内容信息
    content = TextField()                           # 父分块内容
    content_with_weight = TextField()               # 带权重的内容
    
    # 位置信息
    chunk_order = IntegerField(default=0)           # 在文档中的顺序
    page_num = IntegerField(default=0, null=True)   # 页码
    
    # 元数据
    metadata = TextField(default='{}')              # JSON格式的元数据
    token_count = IntegerField(default=0)           # Token数量
    char_count = IntegerField(default=0)            # 字符数量
    
    # 分块策略信息
    chunk_method = CharField(max_length=32, default='parent_smart')
    
    # 状态标识
    available_int = IntegerField(default=1)         # 是否可用
    
    class Meta:
        table_name = "parent_chunk"
        indexes = [
            (('doc_id', 'chunk_order'), False),
            (('kb_id', 'available_int'), False),
        ]


class ChildChunk(DataBaseModel):
    """子分块模型 - 用于精确检索的小文本单元"""
    
    # 基本信息
    id = CharField(max_length=128, primary_key=True)
    parent_chunk_id = CharField(max_length=128, index=True)  # 关联的父分块ID
    doc_id = CharField(max_length=128, index=True)
    kb_id = CharField(max_length=128, index=True)
    
    # 内容信息
    content = TextField()                           # 子分块内容（用于向量化）
    content_ltks = TextField()                      # 用于全文检索的内容
    
    # 在父分块中的位置
    chunk_order_in_parent = IntegerField(default=0) # 在父分块中的顺序
    chunk_order_global = IntegerField(default=0)    # 在整个文档中的全局顺序
    
    # 位置信息
    page_num = IntegerField(default=0, null=True)
    position_int = IntegerField(default=0)          # 在页面中的位置
    
    # 元数据
    metadata = TextField(default='{}')
    token_count = IntegerField(default=0)
    char_count = IntegerField(default=0)
    
    # 向量相关（继承现有ES字段结构）
    img_id = CharField(max_length=128, default="", null=True)
    title_tks = TextField(default="")
    important_kwd = TextField(default="")
    
    # 状态
    available_int = IntegerField(default=1)
    
    class Meta:
        table_name = "child_chunk"
        indexes = [
            (('parent_chunk_id', 'chunk_order_in_parent'), False),
            (('doc_id', 'chunk_order_global'), False),
            (('kb_id', 'available_int'), False),
        ]


class ParentChildMapping(DataBaseModel):
    """父子分块映射关系表 - 用于快速查询"""
    
    child_chunk_id = CharField(max_length=128, index=True)
    parent_chunk_id = CharField(max_length=128, index=True)
    doc_id = CharField(max_length=128, index=True)
    kb_id = CharField(max_length=128, index=True)
    
    # 关系权重（用于相关性计算）
    relevance_score = IntegerField(default=100)     # 子分块在父分块中的重要性
    
    class Meta:
        table_name = "parent_child_mapping"
        primary_key = False
        indexes = [
            (('child_chunk_id', 'parent_chunk_id'), True),  # 唯一约束
            (('kb_id', 'doc_id'), False),
        ]


class ParentChildConfig(DataBaseModel):
    """父子分块配置表 - 存储分块策略配置"""
    
    kb_id = CharField(max_length=128, primary_key=True)
    
    # 父分块配置
    parent_chunk_size = IntegerField(default=1024)          # 父分块大小（tokens）
    parent_chunk_overlap = IntegerField(default=100)        # 父分块重叠（tokens）
    parent_separator = CharField(max_length=64, default=r'\n\n')  # 父分块分隔符
    
    # 子分块配置
    child_chunk_size = IntegerField(default=256)            # 子分块大小（tokens）
    child_chunk_overlap = IntegerField(default=50)          # 子分块重叠（tokens）
    child_separator = CharField(max_length=64, default=r'[。！？.!?]')  # 子分块分隔符
    
    # 检索配置
    retrieval_mode = CharField(max_length=16, default='parent')  # parent/child/hybrid
    top_k_children = IntegerField(default=10)               # 检索的子分块数量
    top_k_parents = IntegerField(default=4)                 # 返回的父分块数量
    
    # 启用标识
    enabled = BooleanField(default=True)
    
    # 其他配置
    config_json = TextField(default='{}')                   # 扩展配置JSON
    
    class Meta:
        table_name = "parent_child_config"