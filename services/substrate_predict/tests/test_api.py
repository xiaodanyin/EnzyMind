"""
Substrate Prediction Service Tests
底物预测服务测试用例
"""
import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加服务目录到路径
SERVICE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SERVICE_DIR))


class TestUtilityFunctions:
    """测试工具函数"""
    
    def test_is_amino_acid_sequence_valid(self):
        """测试有效的氨基酸序列"""
        from main import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ") is True
        assert is_amino_acid_sequence("ACDEFGHIKLMNPQRSTVWY") is True
    
    def test_is_amino_acid_sequence_invalid(self):
        """测试无效的氨基酸序列"""
        from main import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ123") is False
        assert is_amino_acid_sequence("HELLO WORLD") is False
    
    def test_is_uniprot_id_valid(self):
        """测试有效的UniProt ID"""
        from main import is_uniprot_id
        assert is_uniprot_id("P12345") is True
        assert is_uniprot_id("A0A024R1R8") is True
        assert is_uniprot_id("Q9NZC2") is True
    
    def test_is_uniprot_id_invalid(self):
        """测试无效的UniProt ID"""
        from main import is_uniprot_id
        assert is_uniprot_id("MKTAYIAKQRQ") is False
        assert is_uniprot_id("12345") is False
    
    def test_is_fasta_content(self):
        """测试FASTA内容检测"""
        from main import is_fasta_content
        fasta_content = ">test\nMKTAYIAKQRQ"
        assert is_fasta_content(fasta_content) is True
        assert is_fasta_content("MKTAYIAKQRQ") is False
    
    def test_clean_sequence(self):
        """测试序列清理"""
        from main import clean_sequence
        assert clean_sequence("MKT AYI-AKQ\nRQ") == "MKTAYIAKQRQ"
        assert clean_sequence("mktayiakqrq") == "MKTAYIAKQRQ"
    
    def test_extract_sequence_from_fasta_content(self):
        """测试从FASTA内容提取序列"""
        from main import extract_sequence_from_fasta_content
        fasta_content = ">test\nMKTAYI\nAKQRQ"
        assert extract_sequence_from_fasta_content(fasta_content) == "MKTAYIAKQRQ"


class TestClassifyInput:
    """测试输入分类"""
    
    def test_classify_sequence(self):
        """测试序列分类"""
        from main import classify_input
        result = classify_input("MKTAYIAKQRQISFVK")
        assert result == "MKTAYIAKQRQISFVK"
    
    def test_classify_fasta_content(self):
        """测试FASTA内容分类"""
        from main import classify_input
        fasta_content = ">test_seq\nMKTAYIAKQRQISFVK"
        result = classify_input(fasta_content)
        assert result == "MKTAYIAKQRQISFVK"
    
    @patch('main.get_uniprot_sequence')
    def test_classify_uniprot(self, mock_get_seq):
        """测试UniProt ID分类"""
        from main import classify_input
        mock_get_seq.return_value = "MKTAYIAKQRQISFVK"
        result = classify_input("P12345")
        assert result == "MKTAYIAKQRQISFVK"
        mock_get_seq.assert_called_once_with("P12345")


class TestSubstratePredictionAPI:
    """测试底物预测API类"""
    
    def test_api_initialization(self):
        """测试API初始化"""
        from main import SubstratePredictionAPI
        
        api = SubstratePredictionAPI(
            model_path="/path/to/model.pt",
            mol_model_path="/path/to/mol_model",
            gpu=0
        )
        
        assert api.model_path == "/path/to/model.pt"
        assert api.mol_model_path == "/path/to/mol_model"
        assert api.gpu == 0
        assert api._predictor is None  # 延迟加载


class TestFastAPIEndpoints:
    """测试FastAPI端点"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "substrate_predict"
    
    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Substrate Prediction Service"
        assert "endpoints" in data
    
    def test_predict_missing_smiles(self, client):
        """测试缺少SMILES参数"""
        response = client.post(
            "/api/predict/substrate",
            data={"enzyme_input_type": "sequence", "enzyme_query": "MKTAYIAK"}
        )
        assert response.status_code == 422  # Validation error


class TestMEIModel:
    """测试MEI模型"""
    
    def test_mei_initialization(self):
        """测试MEI模型初始化"""
        try:
            import torch
            from models.substrate_predictor import MEI
            
            model = MEI(n_output=2, projection_dim=256)
            assert model is not None
            assert model.n_output == 2
            assert model.projection_dim == 256
        except ImportError:
            pytest.skip("PyTorch not installed")
    
    def test_mei_forward(self):
        """测试MEI模型前向传播"""
        try:
            import torch
            from models.substrate_predictor import MEI
            
            model = MEI(n_output=2, projection_dim=256)
            mol_emb = torch.randn(1, 1024)
            enzyme_emb = torch.randn(1, 128)
            
            output = model(mol_emb, enzyme_emb)
            assert output.shape == (1, 2)
        except ImportError:
            pytest.skip("PyTorch not installed")


class TestLayerNormNet:
    """测试LayerNormNet模型"""
    
    def test_layer_norm_net_forward(self):
        """测试LayerNormNet前向传播"""
        try:
            import torch
            from models.substrate_predictor import LayerNormNet
            
            device = torch.device('cpu')
            dtype = torch.float32
            model = LayerNormNet(512, 128, device, dtype)
            
            x = torch.randn(1, 1280)
            output = model(x)
            
            assert output.shape == (1, 128)
        except ImportError:
            pytest.skip("PyTorch not installed")


class TestClient:
    """测试客户端"""
    
    def test_client_initialization(self):
        """测试客户端初始化"""
        from client import SubstratePredictionClient
        
        client = SubstratePredictionClient(base_url="http://localhost:18903")
        assert client.base_url == "http://localhost:18903"
    
    def test_client_base_url_trailing_slash(self):
        """测试客户端URL处理"""
        from client import SubstratePredictionClient
        
        client = SubstratePredictionClient(base_url="http://localhost:18903/")
        assert client.base_url == "http://localhost:18903"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
