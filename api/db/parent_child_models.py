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
父子分块数据库模型扩展 - 兼容性导入层
支持 ParentDocumentRetriever 的数据结构

注意：模型现在已经迁移到 api.db.db_models 中以支持自动初始化
此文件作为兼容性层保留，以避免现有代码的导入错误
"""

# 从主模型文件导入父子分块模型（已经合并到db_models.py中）
from api.db.db_models import (
    ParentChunk,
    ChildChunk, 
    ParentChildMapping,
    ParentChildConfig
)

# 保持向后兼容性的导出
__all__ = [
    'ParentChunk',
    'ChildChunk',
    'ParentChildMapping', 
    'ParentChildConfig'
]