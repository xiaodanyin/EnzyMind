"""
FastAPI请求处理工具函数
"""
import io
import os
import tempfile
from typing import Tuple, Dict, Optional, Any
from fastapi import UploadFile

from .sequence_utils import (
    is_fasta_file,
    is_fasta_content,
    is_uniprot_id,
    is_amino_acid_sequence,
)


def prepare_sequence_payload(query: str) -> Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    准备序列请求的payload
    
    Args:
        query: 输入查询（可以是UniProt ID、序列、FASTA文件路径或FASTA内容）
        
    Returns:
        (input_type, data_dict, files_dict)
    """
    query = query.strip()
    
    # 检查是否为FASTA文件路径
    if is_fasta_file(query):
        with open(query, "rb") as f:
            content = f.read()
        file_obj = io.BytesIO(content)
        file_obj.name = os.path.basename(query)
        return "fasta", {"input_type": "fasta"}, {"file": (file_obj.name, file_obj, "text/plain")}
    
    # 检查是否为FASTA内容
    if is_fasta_content(query):
        file_obj = io.BytesIO(query.encode("utf-8"))
        file_obj.name = "input.fasta"
        return "fasta", {"input_type": "fasta"}, {"file": ("input.fasta", file_obj, "text/plain")}
    
    # 检查是否为UniProt ID
    if is_uniprot_id(query):
        return "uniprot", {"input_type": "uniprot", "query": query}, None
    
    # 默认认为是原始序列
    return "sequence", {"input_type": "sequence", "query": query}, None


async def process_input_request(
    input_type: str,
    query: Optional[str] = None,
    file: Optional[UploadFile] = None
) -> str:
    """
    处理API请求中的输入
    
    Args:
        input_type: 输入类型（fasta, sequence, uniprot）
        query: 查询字符串
        file: 上传的文件
        
    Returns:
        处理后的输入字符串（可以是文件路径或查询字符串）
    """
    if input_type == "fasta" and file is not None:
        content = (await file.read()).decode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".fasta", mode="w", encoding="utf-8") as tmpf:
            tmpf.write(content)
            tmpf.flush()
            return tmpf.name
    else:
        return query


async def process_enzyme_input(
    enzyme_input_type: str,
    enzyme_query: Optional[str] = None,
    enzyme_file: Optional[UploadFile] = None
) -> Tuple[str, Optional[str]]:
    """
    处理酶输入请求
    
    Args:
        enzyme_input_type: 输入类型
        enzyme_query: 查询字符串
        enzyme_file: 上传的文件
        
    Returns:
        (enzyme_input, temp_file_path)
    """
    temp_file_path = None
    enzyme_input = None
    
    if enzyme_input_type == "fasta" and enzyme_file is not None:
        content = (await enzyme_file.read()).decode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".fasta", mode="w", encoding="utf-8") as tmpf:
            tmpf.write(content)
            tmpf.flush()
            enzyme_input = tmpf.name
            temp_file_path = enzyme_input
            
    elif enzyme_input_type == "sequence" and enzyme_query:
        # 如果包含FASTA头，转换为临时文件
        if enzyme_query.strip().startswith(">") or "\n" in enzyme_query.strip():
            with tempfile.NamedTemporaryFile(delete=False, suffix=".fasta", mode="w", encoding="utf-8") as tmpf:
                tmpf.write(enzyme_query)
                tmpf.flush()
                enzyme_input = tmpf.name
                temp_file_path = enzyme_input
        else:
            enzyme_input = enzyme_query
            
    elif enzyme_input_type == "uniprot" and enzyme_query:
        enzyme_input = enzyme_query
        
    return enzyme_input, temp_file_path


def cleanup_temp_file(file_path: Optional[str]):
    """清理临时文件"""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
