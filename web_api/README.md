# Markdown 智能分块器 (markdown_chunker)

基于 AST（抽象语法树）的 Markdown 高级分块工具，支持标题层级分块、动态大小控制、表格/图片特殊处理、上下文增强和父子分块结构。

## 目录

- [模块架构](#模块架构)
- [核心流程](#核心流程)
- [配置参数](#配置参数)
- [标题层级分块](#标题层级分块)
- [动态大小控制](#动态大小控制)
- [超大分块处理](#超大分块处理)
- [超小分块处理](#超小分块处理)
- [表格特殊处理](#表格特殊处理)
- [图片特殊处理](#图片特殊处理)
- [其他节点处理](#其他节点处理)
- [上下文增强](#上下文增强)
- [子分块创建](#子分块创建)
- [父子分块结构](#父子分块结构)
- [API 参考](#api-参考)

---

## 模块架构

```
markdown_chunker/
|-- __init__.py          # 主入口：split_markdown_to_chunks_advanced 等
|-- models.py            # 数据模型：ChunkConfig, ChunkInfo, NodeInfo, ASTChunkInfo
|-- tokenizer.py         # Token 计数：tiktoken 封装
|-- ast_utils.py         # AST 解析：markdown-it 解析、节点渲染、标题栈
|-- renderer.py          # 分块渲染：标题链清理、上下文构建、去 # 号
|-- table_handler.py     # 表格处理：检测、标题查找、HTML 解析、按行拆分
|-- chunk_builder.py     # 核心算法：标题分块、大小控制、子分块句子拆分
|-- parent_child.py      # 父子分块：自适应级别、二级切分、关联关系
```

**核心依赖**：`markdown-it-py`（AST 解析）、`tiktoken`（Token 计数）

---

## 核心流程

`split_markdown_to_chunks_advanced` 的完整处理流水线：

```
输入 Markdown 文本
    |
    v
[1] AST 解析（markdown-it）
    |
    v
[2] 节点提取（heading + 内容节点，附标题上下文）
    |
    v
[3] 标题层级初步分块（H1-H3 默认，处理短标题特殊逻辑）
    |
    v
[4] 动态大小控制
    |-- 超大分块 -> [4a] 降级拆分(H4) -> 仍超大 -> 段落级拆分
    |-- 超小分块 -> [4b] 尝试合并 -> 无法合并 -> 上下文增强
    |-- 正常分块 -> 直接保留
    |
    v
[5] 内容渲染（去 # 号、添加上下文标题链）
    |
    v
输出 Chunk 列表
```

---

## 配置参数

### `ChunkConfig`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `chunk_token_num` | int | 1024 | 目标分块大小（tokens），控制分块粒度 |
| `min_chunk_tokens` | int | 10 | 最小分块大小，低于此值视为超小 |
| `overlap_ratio` | float | 0.0 | 重叠比例（预留接口） |
| `headers_to_split_on` | Tuple[int, ...] | (1, 2, 3) | 主分块边界标题级别 |
| `fallback_split_levels` | Tuple[int, ...] | (4,) | 降级拆分层级，当主层级分块超大时尝试 |

### 动态阈值（属性计算）

| 阈值 | 计算方式 | 默认值(1024) | 作用 |
|------|----------|-------------|------|
| `target_min_tokens` | `max(50, min_chunk_tokens // 2)` | 50 | 低于此值为"undersized" |
| `target_tokens` | `min(chunk_token_num, 600)` | 600 | 目标分块大小，用于段落级拆分 |
| `target_max_tokens` | `int(chunk_token_num * 1.5)` | 1536 | 高于此值为"oversized" |

> **注意**：`target_max_tokens` 不硬编码，而是基于 `chunk_token_num` 动态计算。当 `chunk_token_num=256` 时上限为 384，当 `chunk_token_num=4096` 时上限为 6144。

---

## 标题层级分块

### 默认行为

主分块边界标题级别为 `headers_to_split_on = (1, 2, 3)`：

- **H1**（`#`）：一级标题，触发分块
- **H2**（`##`）：二级标题，触发分块
- **H3**（`###`）：三级标题，触发分块
- **H4**（`####`）：四级标题，**不触发**主分块，仅在降级拆分时使用

### 短标题特殊处理

`is_short_numbered_title(title)` 检测短编号标题（如 `"3.7"`、`"A.1"`）：

**判定为短编号的条件**（满足任一）：
1. 纯数字编号：`"3.7"`（`replace(".", "")` 后全为数字）
2. 短编号（<=2 词且含数字）：`"4.1"`
3. 长度 <= 12 字符

**判定为非短编号的条件**（任一即排除）：
- 包含 >= 2 个中文汉字（如 `"5.3施工操作要点"`）
- 长度 > 12

**处理逻辑**：
```
遇到 heading 节点
    |
    v
是短编号标题？
    |-- 是 -> 向前查找 max_lookahead=3 内是否有内容标题
    |       |-- 有 -> 跳过此标题，不作为分块边界（与后续内容合并）
    |       |-- 无 -> 作为正常分块边界
    |
    +-- 否 -> 作为正常分块边界
```

**典型场景**：
- `"3.7"`（短编号）+ 后续有 `"3.7.1 模板控制"`（内容标题） -> 3.7 不单独分块
- `"5.3施工操作要点"`（含中文） -> 正常分块边界

### 降级拆分（Fallback Split）

当主层级（H1-H3）产生的分块超过 `target_max_tokens` 时，尝试用 `fallback_split_levels`（默认 H4）进行二级拆分：

```
Chunk 超大(> target_max)
    |
    v
存在 fallback_split_levels？
    |-- 否 -> 段落级拆分
    |
    +-- 是 -> 依次尝试每个降级层级
            |
            v
            找到能将超大 chunk 拆分为合理大小的最优层级？
                |-- 是 -> 按该层级标题分块，递归优化每个子块
                |-- 否 -> 段落级拆分
```

---

## 动态大小控制

### 三档分类

每个分块经过 `classify_chunk_size` 分为三类：

| 分类 | 条件 | 处理 |
|------|------|------|
| **normal** | `target_min <= tokens <= target_max` | 直接保留 |
| **oversized** | `tokens > target_max` | 降级拆分 或 段落级拆分 或 表格分离 |
| **undersized** | `tokens < target_min` | 尝试合并 或 上下文增强 |

### 表格内容对 oversized 判定的影响

```python
has_special = has_special_content(chunk)  # 是否含表格/代码块/公式

if oversized and not has_special:
    # 普通内容 -> 降级拆分 -> 段落级拆分
elif oversized and has_special:
    # 特殊内容 -> separate_tables（表格分离）
```

---

## 超大分块处理

### 路径 A：降级拆分（优先）

`try_fallback_split(chunk, fallback_levels, max_tokens, token_counter)`

1. 依次尝试 `fallback_levels` 中的每个标题级别
2. 在该 chunk 的节点中查找对应级别的 heading 作为边界
3. 评估拆分质量（评分机制）
4. 选择最优层级返回拆分结果
5. 对拆分后的每个子块递归进行大小分类和优化

### 路径 B：段落级拆分（降级不可用）

`split_oversized_chunk(chunk, target_tokens, max_tokens, token_counter)`

按段落（paragraph）边界累积 token，当超过 `target_tokens` 时切分：

```
遍历 chunk 内的节点
    |
    v
当前累积 + 此节点 > target_tokens？
    |-- 否 -> 追加到当前累积
    |-- 是 -> 保存当前分块，从此节点开始新分块
    |
特殊内容（表格/代码块/LaTeX）单独处理：
    - 超大特殊内容（> max_tokens）：单独成一个分块
    - 正常特殊内容：作为原子节点累积
```

### 路径 C：表格分离（含特殊内容）

`separate_tables(chunk, target_tokens, max_tokens, token_counter)`

将 chunk 中的表格提取为独立子分块，非表格内容单独处理：

1. 扫描节点，遇到表格时：
   - 向前查找表格标题（heading/paragraph）
   - 标题作为 `table_context` 分块
   - 表格内容按行拆分为多个 `table_chunk`（保留完整表头）
2. 非表格内容按段落级拆分处理

---

## 超小分块处理

### 路径 A：与下一个分块合并

`try_merge_with_next(chunk, all_chunks, current_index, target_tokens, token_counter)`

```
当前分块 + 下一个分块 <= target_tokens * 1.2？
    |-- 是 -> 合并为一个分块（chunk_type="merged_small"）
    |-- 否 -> 无法合并，走路径 B
```

### 路径 B：上下文增强

`enhance_small_chunk(chunk)`

在分块前添加标题上下文节点：

1. 提取分块的上级标题（比 chunk 中最低 heading 级别更高的标题）
2. 创建 `context` 类型节点（内容为标题链）
3. 插入到分块节点列表头部
4. chunk_type 设为 `"small_enhanced"`

---

## 表格特殊处理

### 表格检测

两个层面的检测：

| 检测方式 | 条件 |
|----------|------|
| AST 节点类型 | `node.type == "table"`（markdown-it 原生 table） |
| HTML 内容检测 | `node.type == "html_block"` 且内容含 `<table` 标签 |

### 表格标题查找

`find_table_title_nodes(nodes, table_index)` — 向前查找最多 2 个节点：

**heading 节点**：
- 标题以 `"表"` / `"Table"` / `"TABLE"` 开头

**paragraph 节点**（满足任一）：
- 以 `"表"` / `"Table"` / `"TABLE"` / `"T\d"` / `"下表"` / `"表格"` 开头
- 包含 `"如下表"` / `"下表所示"` / `"表所示"` / `"表格如下"` / `"见下表"` / `"参见下表"` / `"下表列出"` / `"下表给出"` / `"下表说明"` 等短语
- 长度 < 60 字符且包含 `"表"` 字

### HTML 表格按行拆分

`split_table_by_rows(table_html, max_tokens, token_counter)`

```
输入: <table>...</table> HTML
    |
    v
解析出 <thead>...</thead>（表头）和 <tbody> 中的 <tr>...</tr> 行
    |
    v
计算表头 token 数，扣除后得到每段可用额度
    |
    v
逐行累积:
    - 当前累积 + 此行 <= 可用额度 -> 追加
    - 超过 -> 保存当前分块（表头 + 已累积行），重新开始
    |
    v
每个子表格: <table><thead>...</thead><tbody>...</tbody></table>
```

**关键特性**：每个子表格都**保留完整表头**，确保独立可读。

### Markdown 表格拆分

`split_markdown_table(table_md, max_tokens, token_counter)`

对 `| 列1 | 列2 |` 格式的 Markdown 表格，同样保留表头+分隔符行后按数据行拆分。

---

## 图片特殊处理

### AST 层面的保护

`extract_text()` 中处理 `image` 子节点：

```python
elif child_type == "image":
    alt_text = extract_text(child)       # 提取 alt 文本
    src = child.attrGet("src") or ""      # 提取图片 URL
    parts.append(f"![{alt_text}]({src})") # 还原为 Markdown 图片语法
```

原始 AST 结构：
```
paragraph
  inline
    image tag=img content='图片描述' attrs={'src': 'url.png'}
      text content='图片描述'
```

渲染后：`![图片描述](url.png)` — 完整的 Markdown 图片语法保留。

### 子分块句子拆分保护

`split_into_sentences()` 中 `![alt](src)` 的 `!` 会被句子结束规则 `(?<=[.!?。！？；;])` 误切。

**保护机制**（步骤0，最先执行）：

```python
# 0. 保护 Markdown 图片语法
image_pattern = re.compile(r"!\[[^\]]*\]\([^)]+\)")
protected = image_pattern.sub(lambda m: f"((IMG_{len(images)}))", text)
```

替换后再进行 URL 保护、句子拆分，拆分完成后还原占位符。确保 `![image](url)` 作为整体原子单位。

---

## 其他节点处理

### 代码块

- 保留完整代码块（含语言标识）
- 不拆分到多个 chunk 中
- 超大时代码块作为原子节点单独成块

### 引用块

逐行添加 `>` 前缀还原为 Markdown 引用格式。

### 列表

| 类型 | 渲染格式 |
|------|----------|
| 无序列表 | `- 项目1\n- 项目2` |
| 有序列表 | `1. 项目1\n2. 项目2` |

### 分隔线

`---`

### html_block

直接返回 `node.content`（原始 HTML 内容），用于处理原始 Markdown 中的 HTML 表格。

---

## 上下文增强

### 标题链构建

`build_header_chain(headers)` — 将标题层级字典转为标题链：

```python
headers = {1: "文档标题", 2: "6材料与设备", 3: "6.1材料"}
# 输出: "# 文档标题\n## 6材料与设备\n### 6.1材料"
```

### 去 # 号处理

`clean_header_chain(chain, use_indentation=False)` — 清理标题符号：

| 模式 | 输入 | 输出 |
|------|------|------|
| `use_indentation=False` | `"## 1前言"` | `"1前言"` |
| `use_indentation=True` | `"# H1\n## H2\n### H3"` | `"H1\n  H2\n    H3"` |

### 渲染时的上下文策略

`build_context_for_chunk()` 根据分块结构决定添加上下文：

```
分块以 heading 开头？
    |-- 是 -> 只添加上级标题（比当前 heading 级别更高的标题）
    |-- 否 -> 添加完整标题链（从 H1 到当前最深标题）
    |
已包含 context 节点（small_enhanced）？
    |-- 是 -> 不再额外添加上下文（避免重复）
```

### 典型的 chunk 输出格式

```
临水大角度V型高墩少支架施工工法    <-- H1 上下文（去 # 号）
  6材料与设备                        <-- H2 上下文（缩进）

6.1材料                              <-- chunk 自身的 heading（去 # 号）

斜腿施工主体结构及支架体系的主要材料...
```

---

## 子分块创建

### `create_sub_chunks(parent_content, sub_chunk_token_num=256, ...)`

将父分块内容重新解析为 AST，按语义单元拆分为更小的子分块：

```
父分块内容
    |
    v
重新解析为 AST
    |
    v
遍历节点:
    - heading: 触发分块边界
    - paragraph/list: 按句子拆分后累积
    - table: 按行拆分（保留表头）
    - code_block: 原子节点
    - image: 受句子拆分保护
    |
    v
输出子分块列表
```

### 句子拆分规则

`split_into_sentences(text)` 的保护顺序（从上到下，依次执行）：

| 步骤 | 保护对象 | 正则/方式 |
|------|----------|----------|
| 0 | Markdown 图片 `![alt](src)` | `!\[[^\]]*\]\([^)]+\)` |
| 1 | URL (`http://...`) | `https?://[^\s)\]）]+` |
| 2 | 页码引用 (`...36`) | `[\.。](?:\s*[\.。])+\s*\d+` |
| 3 | 数字编号 (`2.0.4`) | `(?:\d+\.\d+)(?:\.\d+)*` |
| 4 | 按句子结束符拆分 | `(?<=[.!?。！？；;])\s*` |
| 5 | 还原所有占位符 | 按顺序还原 IMG -> URL -> NUM -> PAGE |

---

## 父子分块结构

### `split_markdown_parent_child()`

创建两层分块结构：父分块（粗粒度）和子分块（细粒度）。

### 自适应父分块级别

```python
compute_adaptive_split_level(enhanced_nodes, target_parent_tokens=(400, 1200))
```

评估 H2-H5 各级别的分块质量，选择评分最高的级别：

| 评分维度 | 权重 | 说明 |
|----------|------|------|
| 分块在目标区间比例 | 10.0 | 越接近目标越好 |
| 超大分块数量 | -2.0 | 惩罚 |
| 碎片分块数量 | -0.8 | 惩罚 |
| 分块数量适中度 | 浮动 | <2 或 >40 惩罚 |
| 平均大小偏差 | -0.5 | 偏离目标中点惩罚 |

### 二级切分

当一级切分后的段仍然超大时，自动尝试更低级别标题进行二级切分。

### 子分块表格处理

子分块中表格标题（heading/paragraph）单独作为子 chunk，表格内容按行拆分，每块保留表头。

---

## API 参考

### 主入口函数

```python
from markdown_chunker import split_markdown_to_chunks_advanced

chunks = split_markdown_to_chunks_advanced(
    txt="# 标题\n\n内容...",
    chunk_token_num=1024,      # 目标分块大小
    min_chunk_tokens=10,        # 最小分块大小
    overlap_ratio=0.0,          # 重叠比例
    include_metadata=False,     # 是否包含元数据
)
```

**返回值**：
- `include_metadata=False` -> `List[str]`（分块内容字符串）
- `include_metadata=True` -> `List[Dict[str, Any]]`（含 content, metadata, token_count, chunk_type 等）

### 子分块

```python
from markdown_chunker import create_child_chunks

children = create_child_chunks(
    content="父分块内容...",
    sub_chunk_token_num=256,
    include_metadata=False,
)
```

### 父子分块

```python
from markdown_chunker.parent_child import split_markdown_parent_child

parents, children, relationships = split_markdown_parent_child(
    txt="内容...",
    chunk_token_num=256,
    doc_id="doc_001",
    adaptive_split=True,        # 启用自适应级别
)
```

### 配置自定义

```python
from markdown_chunker.models import ChunkConfig

config = ChunkConfig(
    chunk_token_num=2048,
    headers_to_split_on=(1, 2),      # 只按 H1-H2 分块
    fallback_split_levels=(3, 4),    # 降级到 H3-H4
)
```
