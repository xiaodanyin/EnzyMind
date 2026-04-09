"""
Enzyme Recognition Service Client
用于调用酶识别API的客户端
"""
import requests
from typing import Optional, Union
from pathlib import Path


class EnzymeRecognitionClient:
    """酶识别服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18901"):
        """
        初始化客户端
        
        Args:
            base_url: 服务基础URL
        """
        self.base_url = base_url.rstrip("/")
    
    def recognize(
        self,
        query: Optional[str] = None,
        file_path: Optional[str] = None,
        input_type: str = "sequence"
    ) -> dict:
        """
        调用酶识别API
        
        Args:
            query: 查询字符串（序列或UniProt ID）
            file_path: FASTA文件路径
            input_type: 输入类型 ("sequence", "uniprot", "fasta")
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/api/recognize/enzyme"
        
        if input_type == "fasta" and file_path:
            # 上传文件
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f, "text/plain")}
                data = {"input_type": input_type}
                response = requests.post(url, data=data, files=files, timeout=300)
        else:
            # 发送查询字符串
            data = {"input_type": input_type, "query": query}
            response = requests.post(url, data=data, timeout=300)
        
        response.raise_for_status()
        return response.json()
    
    def recognize_sequence(self, sequence: str) -> dict:
        """
        识别氨基酸序列是否为酶
        
        Args:
            sequence: 氨基酸序列
            
        Returns:
            识别结果
        """
        return self.recognize(query=sequence, input_type="sequence")
    
    def recognize_uniprot(self, uniprot_id: str) -> dict:
        """
        根据UniProt ID识别是否为酶
        
        Args:
            uniprot_id: UniProt ID
            
        Returns:
            识别结果
        """
        return self.recognize(query=uniprot_id, input_type="uniprot")
    
    def recognize_fasta(self, file_path: str) -> dict:
        """
        识别FASTA文件中的序列是否为酶
        
        Args:
            file_path: FASTA文件路径
            
        Returns:
            识别结果
        """
        return self.recognize(file_path=file_path, input_type="fasta")
    
    def health_check(self) -> dict:
        """
        检查服务健康状态
        
        Returns:
            健康状态响应
        """
        url = f"{self.base_url}/health"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def is_healthy(self) -> bool:
        """
        检查服务是否健康
        
        Returns:
            服务是否健康
        """
        try:
            result = self.health_check()
            return result.get("status") == "healthy"
        except Exception:
            return False


# 便捷函数
def recognize_enzyme(
    query: str,
    base_url: str = "http://localhost:18901"
) -> dict:
    """
    便捷函数：识别序列是否为酶
    
    Args:
        query: 氨基酸序列或UniProt ID
        base_url: 服务地址
        
    Returns:
        识别结果
    """
    client = EnzymeRecognitionClient(base_url=base_url)
    return client.recognize(query=query, input_type="sequence")
