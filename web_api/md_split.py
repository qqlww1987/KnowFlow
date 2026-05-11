import re
from typing import List
# import nltk
# try:
#     # 尝试下载 punkt_tab（新版本）
#     nltk.download('punkt_tab')
# except:
#     # 如果失败，使用传统的 punkt
#     nltk.download('punkt')
# from nltk.tokenize import sent_tokenize

def split_markdown_chunk(chunk: str, max_length: int = 30) -> List[str]:
    """
    将已拆分的markdown块进一步细分，保持语义完整性
    
    Args:
        chunk: 已经按标题拆分的markdown块
        max_length: 每个子块的最大字符长度
    
    Returns:
        细分后的markdown块列表
    """
    # 按子标题拆分
    # sentences = sent_tokenize(chunk)
    sentences=split_text_to_sentences(chunk,max_length=max_length)
    if len(sentences)>1:
        if len(chunk)<300:
            sentences.append(chunk)
    return sentences
    return split_by_sentences_with_table_protection(chunk)
    sub_sections = split_by_subheadings(chunk)
    
    result = []
    
    for section in sub_sections:
        # 如果子块仍然太大，继续细分
        if len(section) > max_length:
            # 按句子拆分（保护表格完整性）
            sentences = split_by_sentences_with_table_protection(section)
            # 合并句子以保持语义完整且不超过max_length
            result.extend(merge_sentences(sentences, max_length))
        else:
            result.append(section)
    
    return result

def split_by_subheadings(chunk: str) -> List[str]:
    """按子标题拆分"""
    # 匹配 ##, ### 等子标题
    pattern = r'(\n#{2,6} .+)'
    parts = re.split(pattern, chunk)
    
    # 重组标题和内容
    result = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and re.match(r'\n#{2,6} ', parts[i + 1]):
            # 合并标题和内容
            combined = parts[i] + parts[i + 1]
            result.append(combined.strip())
            i += 2
        else:
            if parts[i].strip():
                result.append(parts[i].strip())
            i += 1
    
    return result
def split_text_to_sentences(text: str,max_length:int) -> List[str]:
    """
    更智能的文本到句子的切分
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    # 尝试使用 NLTK 进行句子切分
    try:
        sentences = sent_tokenize(text)
        # 清理句子
        cleaned_sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        # 如果切分结果合理，返回结果
        if len(cleaned_sentences) > 1 or (len(cleaned_sentences) == 1 and len(cleaned_sentences[0]) < 300):
            return cleaned_sentences
    except Exception as e:
        # NLTK 不可用或失败时的备选方案
        pass
    
    # 使用正则表达式进行句子切分（中英文混合）
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    
    # 对于过长的句子，进一步处理
    final_sentences = []
    for sentence in sentences:
        if len(sentence) > max_length:  # 如果句子太长
            # 按逗号、分号等进一步切分
            sub_sentences = re.split(r'(?<=[，,；;:])\s*', sentence)
            if len(sub_sentences) > 1:
                # 如果能成功切分，使用子句
                for sub_sentence in sub_sentences:
                    if sub_sentence.strip():
                        final_sentences.append(sub_sentence.strip())
            else:
                # 对于中文，按句号切分
                if re.search(r'[\u4e00-\u9fff]', sentence):  # 包含中文
                    sub_sentences = re.split(r'(?<=[。])', sentence)
                    final_sentences.extend([s.strip() for s in sub_sentences if s.strip()])
                else:
                    final_sentences.append(sentence)
        else:
            final_sentences.append(sentence)
    
    return [s for s in final_sentences if s]
def split_by_sentences_with_table_protection(chunk: str) -> List[str]:
    """
    按句子边界拆分，但保护表格完整性
    """
    # 首先检查是否包含表格
    if contains_table(chunk):
        # 如果包含表格，按表格分割内容
        table_parts = split_around_tables(chunk)
        result = []
        for part in table_parts:
            if contains_table(part):
                # 表格部分保持完整
                result.append(part)
            else:
                # 非表格部分按句子拆分
                sentences = split_by_sentences(part)
                result.extend(sentences)
        return result if result else [chunk]
    
    # 如果不包含表格，按句子拆分
    return split_by_sentences(chunk)

def contains_table(chunk: str) -> bool:
    """
    检查内容是否包含表格
    """
    # 检查HTML表格 - 更宽松的检测
    if re.search(r'<\s*table\b', chunk, re.IGNORECASE):
        return True
    
    if re.search(r'<\s*tr\b', chunk, re.IGNORECASE):
        return True
        
    if re.search(r'<\s*td\b', chunk, re.IGNORECASE):
        return True
    
    # 检查Markdown表格（至少3行，包含|分隔符）
    lines = chunk.split('\n')
    pipe_count = 0
    for line in lines:
        if '|' in line and line.count('|') >= 3:
            pipe_count += 1
    
    # 如果有多行包含|分隔符，可能是表格
    if pipe_count >= 2:
        return True
    
    # 检查表格分隔行模式
    for i, line in enumerate(lines):
        if re.match(r'^\s*\|.*[-|:].*\|\s*$', line):  # 包含---和|的行
            return True
    
    return False

def split_around_tables(chunk: str) -> List[str]:
    """
    在表格周围分割内容，保持表格完整
    """
    # 简单的表格分割：查找HTML表格的开始和结束位置
    result = []
    start = 0
    
    # 查找HTML表格
    table_patterns = [
        (r'<\s*table\b', r'<\s*/\s*table\s*>'),
    ]
    
    for open_pattern, close_pattern in table_patterns:
        # 查找所有表格的位置
        for match in re.finditer(open_pattern, chunk, re.IGNORECASE):
            table_start = match.start()
            
            # 查找对应的结束标签
            close_match = re.search(close_pattern, chunk[table_start:], re.IGNORECASE)
            if close_match:
                table_end = table_start + close_match.end()
                
                # 添加表格前的内容
                if table_start > start:
                    pre_table = chunk[start:table_start].strip()
                    if pre_table:
                        result.append(pre_table)
                
                # 添加完整的表格
                table_content = chunk[table_start:table_end]
                result.append(table_content)
                
                start = table_end
    
    # 添加剩余内容
    if start < len(chunk):
        remaining = chunk[start:].strip()
        if remaining:
            result.append(remaining)
    
    # 如果没有找到表格，返回原始内容
    if not result:
        return [chunk]
    
    return result

def split_by_sentences(chunk: str) -> List[str]:
    """按句子边界拆分"""
    # 使用正则表达式按句子分割，但更保守一些
    # 避免在缩写或数字后错误分割
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z\u4e00-\u9fa5])', chunk)
    return [s.strip() for s in sentences if s.strip()]

def merge_sentences(sentences: List[str], max_length: int) -> List[str]:
    """合并句子以保持语义完整且不超过最大长度"""
    result = []
    current_chunk = ""
    
    for sentence in sentences:
        # 如果加上当前句子超过最大长度，则保存当前块并开始新块
        if len(current_chunk) + len(sentence) > max_length and current_chunk:
            result.append(current_chunk.strip())
            current_chunk = sentence
        else:
            # 特别处理第一个句子
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # 添加最后一个块
    if current_chunk.strip():
        result.append(current_chunk.strip())
    
    return result

# 使用示例
def example_usage():
    # 示例markdown块
    markdown_chunk = """
## 示例标题
    
这是一个段落。它包含多个句子。每个句子都应该被正确处理。如果段落太长，需要拆分。

这是表格前的文字内容。需要被拆分处理。

<table>
<tr>
<td>单元格1</td>
<td>单元格2</td>
</tr>
<tr>
<td>单元格3</td>
<td>单元格4</td>
</tr>
</table>

这是表格后的文字内容。也应该被拆分处理。

1. 第一个列表项
2. 第二个列表项
3. 第三个列表项

这是另一个段落！它也有多个句子？是否需要进一步拆分。
    """
    
    # 拆分块
    chunks = split_markdown_chunk(markdown_chunk, max_length=50)
    
    for i, chunk in enumerate(chunks):
        print(f"块 {i+1}:")
        print(chunk)
        print("-" * 40)

# 运行示例
if __name__ == "__main__":
    example_usage()