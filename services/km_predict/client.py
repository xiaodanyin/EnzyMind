"""
Km Prediction Service Client
Km预测服务客户端
"""
import requests
from typing import Optional, Union
from pathlib import Path


class KmPredictClient:
    """Km预测服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:18905"):
        self.base_url = base_url.rstrip("/")
    
    def health_check(self) -> dict:
        """健康检查"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def predict_from_sequence(self, smiles: str, sequence: str) -> dict:
        """使用序列预测Km"""
        data = {
            "smiles": smiles,
            "enzyme_input_type": "sequence",
            "enzyme_query": sequence
        }
        response = requests.post(f"{self.base_url}/api/predict/km", data=data)
        response.raise_for_status()
        return response.json()
    
    def predict_from_uniprot(self, smiles: str, uniprot_id: str) -> dict:
        """使用UniProt ID预测Km"""
        data = {
            "smiles": smiles,
            "enzyme_input_type": "uniprot",
            "enzyme_query": uniprot_id
        }
        response = requests.post(f"{self.base_url}/api/predict/km", data=data)
        response.raise_for_status()
        return response.json()
    
    def predict_from_fasta_file(self, smiles: str, fasta_path: Union[str, Path]) -> dict:
        """使用FASTA文件预测Km"""
        fasta_path = Path(fasta_path)
        with open(fasta_path, "rb") as f:
            files = {"enzyme_file": (fasta_path.name, f, "text/plain")}
            data = {"smiles": smiles, "enzyme_input_type": "fasta"}
            response = requests.post(f"{self.base_url}/api/predict/km", data=data, files=files)
        response.raise_for_status()
        return response.json()
    
    def predict_simple(self, smiles: str, enzyme_input: str, enzyme_input_type: str = "sequence") -> dict:
        """简化的预测接口"""
        json_data = {
            "smiles": smiles,
            "enzyme_input": enzyme_input,
            "enzyme_input_type": enzyme_input_type
        }
        response = requests.post(f"{self.base_url}/api/predict/km/simple", json=json_data)
        response.raise_for_status()
        return response.json()


def predict_km(smiles: str, enzyme_input: str, input_type: str = "sequence", base_url: str = "http://localhost:18905") -> dict:
    """预测Km值便捷函数"""
    client = KmPredictClient(base_url)
    return client.predict_simple(smiles, enzyme_input, input_type)


if __name__ == "__main__":
    client = KmPredictClient()
    print("Health check:", client.health_check())
