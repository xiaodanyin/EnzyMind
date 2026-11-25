"""
序列处理工具函数
"""
import os
import re
from shared.uniprot import ACCESSION, uniprot_sequence_client


def is_amino_acid_sequence(input_str: str) -> bool:
    """检查输入是否为有效的氨基酸序列"""
    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    return all(char in amino_acids for char in input_str.upper())


def is_uniprot_id(input_str: str) -> bool:
    """检查输入是否为UniProt ID格式"""
    return bool(re.fullmatch(ACCESSION, input_str.strip().upper()))


def is_fasta_file(path: str) -> bool:
    """检查输入是否为FASTA文件路径"""
    return os.path.isfile(path) and path.lower().endswith(('.fasta', '.fa'))


def is_fasta_content(content: str) -> bool:
    """检查字符串是否为FASTA格式内容"""
    return content.strip().startswith(">")


def get_uniprot_sequence(uniprot_id: str) -> str:
    """从UniProt获取蛋白质序列"""
    return uniprot_sequence_client.fetch(uniprot_id).sequence


def extract_sequence_from_fasta_content(fasta_content: str) -> str:
    """从FASTA格式内容中提取序列"""
    lines = fasta_content.strip().split('\n')
    sequence_lines = [line.strip() for line in lines if not line.startswith(">")]
    return clean_sequence("".join(sequence_lines))


def extract_sequence_from_fasta_file(fasta_path: str) -> str:
    """从FASTA文件中提取序列"""
    with open(fasta_path, 'r') as f:
        content = f.read()
    return extract_sequence_from_fasta_content(content)


def clean_sequence(seq: str) -> str:
    """清理序列，移除非氨基酸字符"""
    return re.sub(r"[^A-Z]", "", seq.upper())


def save_sequence_as_fasta(sequence: str, output_path: str, header: str = "query") -> str:
    """将序列保存为FASTA文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(f">{header}\n{sequence}")
    return output_path


def classify_input(input_string: str) -> str:
    """
    对输入进行分类并返回序列
    支持：UniProt ID、FASTA文件路径、FASTA内容、原始序列
    """
    input_string = input_string.strip()
    
    # 检查是否为FASTA文件路径
    if is_fasta_file(input_string):
        return extract_sequence_from_fasta_file(input_string)
    
    # 检查是否为FASTA内容
    if is_fasta_content(input_string):
        return extract_sequence_from_fasta_content(input_string)
    
    # 检查是否为UniProt ID
    if is_uniprot_id(input_string):
        return get_uniprot_sequence(input_string)
    
    # 检查是否为纯氨基酸序列
    if is_amino_acid_sequence(input_string):
        return clean_sequence(input_string)
    
    raise ValueError(f"Invalid input: {input_string}. Must be a UniProt ID, FASTA file, FASTA content, or amino acid sequence.")


def classify_input_to_fasta(input_string: str, output_fasta_path: str) -> str:
    """
    对输入进行分类并保存为FASTA文件
    """
    # 如果已经是FASTA文件，直接返回
    if is_fasta_file(input_string):
        return input_string
    
    # 获取序列
    sequence = classify_input(input_string)
    
    # 保存为FASTA文件
    return save_sequence_as_fasta(sequence, output_fasta_path)


def classify_input_v2(raw: str) -> str:
    """
    处理用户提交的输入：
    - 如果是 UniProt ID，则从 UniProt API 拉取序列
    - 如果是 FASTA 格式，自动剥离 header
    - 如果是纯序列，直接返回清洗后版本
    """
    raw = raw.strip()
    
    # 判断是否为 UniProt ID
    if is_uniprot_id(raw):
        return get_uniprot_sequence(raw)
    
    # 判断是否为 FASTA 格式
    if raw.startswith(">") or "\n>" in raw:
        return extract_sequence_from_fasta_content(raw)
    
    # 认为是原始序列
    return clean_sequence(raw)
