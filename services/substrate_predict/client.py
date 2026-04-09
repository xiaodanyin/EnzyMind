"""
Substrate Prediction Service Client
用于调用底物预测API的客户端
"""
import requests
from typing import Optional
from pathlib import Path


class SubstratePredictionClient:
    """底物预测服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18903"):
        """
        初始化客户端
        
        Args:
            base_url: 服务基础URL
        """
        self.base_url = base_url.rstrip("/")
    
    def predict(
        self,
        smiles: str,
        enzyme_query: Optional[str] = None,
        enzyme_file_path: Optional[str] = None,
        enzyme_input_type: str = "sequence"
    ) -> dict:
        """
        调用底物预测API
        
        Args:
            smiles: 底物分子的SMILES字符串
            enzyme_query: 酶查询字符串（序列或UniProt ID）
            enzyme_file_path: 酶FASTA文件路径
            enzyme_input_type: 酶输入类型 ("sequence", "uniprot", "fasta")
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/api/predict/substrate"
        
        if enzyme_input_type == "fasta" and enzyme_file_path:
            # 上传文件
            with open(enzyme_file_path, "rb") as f:
                files = {"enzyme_file": (Path(enzyme_file_path).name, f, "text/plain")}
                data = {
                    "smiles": smiles,
                    "enzyme_input_type": enzyme_input_type
                }
                response = requests.post(url, data=data, files=files, timeout=300)
        else:
            # 发送查询字符串
            data = {
                "smiles": smiles,
                "enzyme_input_type": enzyme_input_type,
                "enzyme_query": enzyme_query
            }
            response = requests.post(url, data=data, timeout=300)
        
        response.raise_for_status()
        return response.json()
    
    def predict_with_sequence(self, smiles: str, sequence: str) -> dict:
        """
        使用氨基酸序列预测底物关系
        
        Args:
            smiles: 底物分子的SMILES字符串
            sequence: 氨基酸序列
            
        Returns:
            预测结果
        """
        return self.predict(smiles=smiles, enzyme_query=sequence, enzyme_input_type="sequence")
    
    def predict_with_uniprot(self, smiles: str, uniprot_id: str) -> dict:
        """
        使用UniProt ID预测底物关系
        
        Args:
            smiles: 底物分子的SMILES字符串
            uniprot_id: UniProt ID
            
        Returns:
            预测结果
        """
        return self.predict(smiles=smiles, enzyme_query=uniprot_id, enzyme_input_type="uniprot")
    
    def predict_with_fasta(self, smiles: str, fasta_path: str) -> dict:
        """
        使用FASTA文件预测底物关系
        
        Args:
            smiles: 底物分子的SMILES字符串
            fasta_path: FASTA文件路径
            
        Returns:
            预测结果
        """
        return self.predict(smiles=smiles, enzyme_file_path=fasta_path, enzyme_input_type="fasta")
    
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
def predict_substrate(
    smiles: str,
    enzyme_sequence: str,
    base_url: str = "http://localhost:18903"
) -> dict:
    """
    便捷函数：预测酶-底物关系
    
    Args:
        smiles: 底物分子的SMILES字符串
        enzyme_sequence: 酶氨基酸序列
        base_url: 服务地址
        
    Returns:
        预测结果
    """
    client = SubstratePredictionClient(base_url=base_url)
    return client.predict_with_sequence(smiles=smiles, sequence=enzyme_sequence)
