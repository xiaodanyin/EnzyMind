"""
Enzyme Recognition Service Tests
酶识别服务测试用例
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
        assert is_amino_acid_sequence("P12345") is False
    
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
        assert is_uniprot_id("p12345") is False  # 小写
    
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


class TestClassifyInputToFasta:
    """测试输入分类和FASTA转换"""
    
    def test_classify_sequence_to_fasta(self):
        """测试序列转换为FASTA"""
        from main import classify_input_to_fasta
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.fasta")
            result = classify_input_to_fasta("MKTAYIAKQRQISFVK", output_path)
            
            assert result == output_path
            assert os.path.exists(output_path)
            
            with open(output_path, 'r') as f:
                content = f.read()
            assert ">query" in content
            assert "MKTAYIAKQRQISFVK" in content
    
    def test_classify_fasta_content_to_fasta(self):
        """测试FASTA内容转换"""
        from main import classify_input_to_fasta
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.fasta")
            fasta_content = ">test_seq\nMKTAYIAKQRQISFVK"
            result = classify_input_to_fasta(fasta_content, output_path)
            
            assert result == output_path
            assert os.path.exists(output_path)
    
    @patch('main.get_uniprot_sequence')
    def test_classify_uniprot_to_fasta(self, mock_get_seq):
        """测试UniProt ID转换为FASTA"""
        from main import classify_input_to_fasta
        
        mock_get_seq.return_value = "MKTAYIAKQRQISFVK"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.fasta")
            result = classify_input_to_fasta("P12345", output_path)
            
            assert result == output_path
            mock_get_seq.assert_called_once_with("P12345")


class TestEnzymeRecognitionAPI:
    """测试酶识别API类"""
    
    def test_api_initialization(self):
        """测试API初始化"""
        from main import EnzymeRecognitionAPI
        
        api = EnzymeRecognitionAPI(
            model_weights_path="/path/to/model.pth",
            esm2_model_location="esm2_t33_650M_UR50D",
            nogpu=True
        )
        
        assert api.model_weights_path == "/path/to/model.pth"
        assert api.esm2_model_location == "esm2_t33_650M_UR50D"
        assert api.nogpu is True
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
        assert data["service"] == "enzy_recognize"
    
    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Enzyme Recognition Service"
        assert "endpoints" in data
    
    def test_recognize_missing_query(self, client):
        """测试缺少查询参数"""
        response = client.post(
            "/api/recognize/enzyme",
            data={"input_type": "sequence"}
        )
        assert response.status_code == 400


class TestEnzymePredictor:
    """测试酶预测器模型"""
    
    def test_simple_mlp_forward(self):
        """测试SimpleMLP前向传播"""
        try:
            import torch
            from models.enzyme_predictor import SimpleMLP
            
            model = SimpleMLP(input_dim=1280, hidden_dim=256, output_dim=2)
            x = torch.randn(2, 1280)
            output = model(x)
            
            assert output.shape == (2, 2)
        except ImportError:
            pytest.skip("PyTorch not installed")
    
    def test_predictor_initialization(self):
        """测试预测器初始化"""
        try:
            from models.enzyme_predictor import EnzymePredictor
            
            predictor = EnzymePredictor(
                esm2_model_location="esm2_t33_650M_UR50D",
                nogpu=True
            )
            
            assert predictor.esm2_model_location == "esm2_t33_650M_UR50D"
            assert predictor.nogpu is True
        except ImportError:
            pytest.skip("Required packages not installed")
    
    def test_parse_fasta(self):
        """测试FASTA解析"""
        try:
            from models.enzyme_predictor import EnzymePredictor
            
            predictor = EnzymePredictor(nogpu=True)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
                f.write(">seq1\nMKTAYIAKQRQ\n>seq2\nABCDEFGHIK")
                fasta_path = f.name
            
            try:
                sequences = predictor._parse_fasta(fasta_path)
                assert len(sequences) == 2
                assert sequences[0][0] == "seq1"
                assert sequences[0][1] == "MKTAYIAKQRQ"
                assert sequences[1][0] == "seq2"
            finally:
                os.unlink(fasta_path)
        except ImportError:
            pytest.skip("Required packages not installed")


class TestClient:
    """测试客户端"""
    
    def test_client_initialization(self):
        """测试客户端初始化"""
        from client import EnzymeRecognitionClient
        
        client = EnzymeRecognitionClient(base_url="http://localhost:18901")
        assert client.base_url == "http://localhost:18901"
    
    def test_client_base_url_trailing_slash(self):
        """测试客户端URL处理"""
        from client import EnzymeRecognitionClient
        
        client = EnzymeRecognitionClient(base_url="http://localhost:18901/")
        assert client.base_url == "http://localhost:18901"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
