"""
Kcat Prediction Service Client
kcat预测服务客户端
"""
import requests
from typing import Optional, Union
from pathlib import Path


class KcatPredictClient:
    """Kcat预测服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18904"):
        """
        初始化客户端
        
        Args:
            base_url: 服务地址
        """
        self.base_url = base_url.rstrip("/")
    
    def health_check(self) -> dict:
        """健康检查"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def predict_from_sequence(self, smiles: str, sequence: str) -> dict:
        """
        使用序列预测kcat
        
        Args:
            smiles: 底物分子SMILES
            sequence: 蛋白质序列
            
        Returns:
            预测结果
        """
        data = {
            "smiles": smiles,
            "enzyme_input_type": "sequence",
            "enzyme_query": sequence
        }
        response = requests.post(
            f"{self.base_url}/api/predict/kcat",
            data=data
        )
        response.raise_for_status()
        return response.json()
    
    def predict_from_uniprot(self, smiles: str, uniprot_id: str) -> dict:
        """
        使用UniProt ID预测kcat
        
        Args:
            smiles: 底物分子SMILES
            uniprot_id: UniProt ID
            
        Returns:
            预测结果
        """
        data = {
            "smiles": smiles,
            "enzyme_input_type": "uniprot",
            "enzyme_query": uniprot_id
        }
        response = requests.post(
            f"{self.base_url}/api/predict/kcat",
            data=data
        )
        response.raise_for_status()
        return response.json()
    
    def predict_from_fasta_file(self, smiles: str, fasta_path: Union[str, Path]) -> dict:
        """
        使用FASTA文件预测kcat
        
        Args:
            smiles: 底物分子SMILES
            fasta_path: FASTA文件路径
            
        Returns:
            预测结果
        """
        fasta_path = Path(fasta_path)
        with open(fasta_path, "rb") as f:
            files = {"enzyme_file": (fasta_path.name, f, "text/plain")}
            data = {
                "smiles": smiles,
                "enzyme_input_type": "fasta"
            }
            response = requests.post(
                f"{self.base_url}/api/predict/kcat",
                data=data,
                files=files
            )
        response.raise_for_status()
        return response.json()
    
    def predict_simple(
        self,
        smiles: str,
        enzyme_input: str,
        enzyme_input_type: str = "sequence"
    ) -> dict:
        """
        简化的预测接口
        
        Args:
            smiles: 底物分子SMILES
            enzyme_input: 酶输入
            enzyme_input_type: 输入类型
            
        Returns:
            预测结果
        """
        json_data = {
            "smiles": smiles,
            "enzyme_input": enzyme_input,
            "enzyme_input_type": enzyme_input_type
        }
        response = requests.post(
            f"{self.base_url}/api/predict/kcat/simple",
            json=json_data
        )
        response.raise_for_status()
        return response.json()


# 便捷函数
def predict_kcat(
    smiles: str,
    enzyme_input: str,
    input_type: str = "sequence",
    base_url: str = "http://localhost:18904"
) -> dict:
    """
    预测kcat值
    
    Args:
        smiles: 底物分子SMILES
        enzyme_input: 酶输入（序列、UniProt ID或FASTA内容）
        input_type: 输入类型
        base_url: 服务地址
        
    Returns:
        预测结果
    """
    client = KcatPredictClient(base_url)
    return client.predict_simple(smiles, enzyme_input, input_type)


if __name__ == "__main__":
    # 测试示例
    client = KcatPredictClient()
    
    # 健康检查
    print("Health check:", client.health_check())
    
    # 示例预测
    test_sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQQIAAALMPGVKSVLKIGCMVKRGQPQGKFTRQSVFLTGKQPVNQSIKKWLSAGTQRMRVYPFRQKSPGGYIEYQGDRLLNAGVEWEIKEQSQQKQRVVQMVHADIAQEQGVPVKSGRNVKGIHRLSGIGPDL"
    test_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    
    try:
        result = client.predict_from_sequence(test_smiles, test_sequence)
        print("Prediction result:", result)
    except Exception as e:
        print(f"Prediction failed (service may not be running): {e}")
