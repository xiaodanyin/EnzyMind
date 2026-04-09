"""
EC Number Prediction Service Client
用于调用EC号预测API的客户端
"""
import requests
from typing import Optional
from pathlib import Path


class ECNumberPredictionClient:
    """EC号预测服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18902"):
        """
        初始化客户端
        
        Args:
            base_url: 服务基础URL
        """
        self.base_url = base_url.rstrip("/")
    
    def predict(
        self,
        query: Optional[str] = None,
        file_path: Optional[str] = None,
        input_type: str = "sequence"
    ) -> dict:
        """
        调用EC号预测API
        
        Args:
            query: 查询字符串（序列或UniProt ID）
            file_path: FASTA文件路径
            input_type: 输入类型 ("sequence", "uniprot", "fasta")
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/api/predict/ec"
        
        if input_type == "fasta" and file_path:
            # 上传文件
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f, "text/plain")}
                data = {"input_type": input_type}
                response = requests.post(url, data=data, files=files, timeout=600)
        else:
            # 发送查询字符串
            data = {"input_type": input_type, "query": query}
            response = requests.post(url, data=data, timeout=600)
        
        response.raise_for_status()
        return response.json()
    
    def predict_sequence(self, sequence: str) -> dict:
        """
        预测氨基酸序列的EC号
        
        Args:
            sequence: 氨基酸序列
            
        Returns:
            预测结果
        """
        return self.predict(query=sequence, input_type="sequence")
    
    def predict_uniprot(self, uniprot_id: str) -> dict:
        """
        根据UniProt ID预测EC号
        
        Args:
            uniprot_id: UniProt ID
            
        Returns:
            预测结果
        """
        return self.predict(query=uniprot_id, input_type="uniprot")
    
    def predict_fasta(self, file_path: str) -> dict:
        """
        预测FASTA文件中序列的EC号
        
        Args:
            file_path: FASTA文件路径
            
        Returns:
            预测结果
        """
        return self.predict(file_path=file_path, input_type="fasta")
    
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
def predict_ec_number(
    query: str,
    base_url: str = "http://localhost:18902"
) -> dict:
    """
    便捷函数：预测序列的EC号
    
    Args:
        query: 氨基酸序列或UniProt ID
        base_url: 服务地址
        
    Returns:
        预测结果
    """
    client = ECNumberPredictionClient(base_url=base_url)
    return client.predict(query=query, input_type="sequence")
