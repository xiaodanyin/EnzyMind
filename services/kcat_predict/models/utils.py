"""
Utility Functions for Kcat Prediction Service
kcat预测服务工具函数
"""
import re
import requests


def is_amino_acid_sequence(input_str: str) -> bool:
    """检查输入是否为有效的氨基酸序列"""
    if not input_str or not isinstance(input_str, str):
        return False
    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    cleaned = input_str.upper().strip()
    return len(cleaned) > 0 and all(char in amino_acids for char in cleaned)


def is_uniprot_id(input_str: str) -> bool:
    """检查输入是否为UniProt ID"""
    if not input_str or not isinstance(input_str, str):
        return False
    uniprot_regex = re.compile(r"^[A-Z][A-Z0-9]{5,9}$")
    return bool(uniprot_regex.match(input_str.strip().upper()))


def is_fasta_content(input_str: str) -> bool:
    """检查输入是否为FASTA格式内容"""
    if not input_str or not isinstance(input_str, str):
        return False
    return input_str.strip().startswith(">")


def clean_sequence(seq: str) -> str:
    """清理序列，去除非氨基酸字符"""
    if not seq:
        return ""
    return re.sub(r"[^A-Z]", "", seq.upper())


def extract_sequence_from_fasta_content(fasta_text: str) -> str:
    """从FASTA文本内容中提取序列"""
    if not fasta_text:
        return ""
    lines = fasta_text.strip().splitlines()
    seq_lines = [line.strip() for line in lines if not line.startswith(">")]
    return clean_sequence("".join(seq_lines))


def get_uniprot_sequence(uniprot_id: str) -> str:
    """从UniProt ID获取蛋白质序列"""
    url = f"https://www.uniprot.org/uniprot/{uniprot_id}.fasta"
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        return extract_sequence_from_fasta_content(response.text)
    
    # 尝试新的API
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        return extract_sequence_from_fasta_content(response.text)
    
    raise ValueError(f"Failed to retrieve sequence for UniProt ID: {uniprot_id}")


def classify_input(input_string: str) -> str:
    """
    分类并处理输入，返回蛋白质序列
    
    支持的输入类型:
    - 纯氨基酸序列
    - UniProt ID
    - FASTA格式内容
    - FASTA文件路径
    """
    if not input_string:
        raise ValueError("Input string is empty")
    
    input_string = input_string.strip()
    
    # 检查是否为FASTA文件路径
    if input_string.lower().endswith(('.fasta', '.fa')):
        import os
        if os.path.isfile(input_string):
            with open(input_string, 'r') as f:
                content = f.read()
            return extract_sequence_from_fasta_content(content)
    
    # 检查是否为FASTA格式内容
    if is_fasta_content(input_string):
        return extract_sequence_from_fasta_content(input_string)
    
    # 检查是否为UniProt ID
    if is_uniprot_id(input_string):
        return get_uniprot_sequence(input_string)
    
    # 检查是否为氨基酸序列
    if is_amino_acid_sequence(input_string):
        return clean_sequence(input_string)
    
    raise ValueError(f"Cannot classify input: {input_string[:50]}...")
