"""
Tests for Kcat Prediction Service
kcat预测服务测试
"""
import pytest


# ============== 工具函数测试 ==============

class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_is_amino_acid_sequence_valid(self):
        """测试有效氨基酸序列"""
        from models.utils import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAYIAKQRQISFVK") == True
        assert is_amino_acid_sequence("ACDEFGHIKLMNPQRSTVWY") == True
    
    def test_is_amino_acid_sequence_invalid(self):
        """测试无效氨基酸序列"""
        from models.utils import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAY123") == False
        assert is_amino_acid_sequence("") == False
        assert is_amino_acid_sequence(None) == False
    
    def test_is_uniprot_id_valid(self):
        """测试有效UniProt ID"""
        from models.utils import is_uniprot_id
        assert is_uniprot_id("P12345") == True
        assert is_uniprot_id("Q9Y6K9") == True
        assert is_uniprot_id("A0A0A0MRZ7") == True
    
    def test_is_uniprot_id_invalid(self):
        """测试无效UniProt ID"""
        from models.utils import is_uniprot_id
        assert is_uniprot_id("MKTAYIAKQRQISFVK") == False
        assert is_uniprot_id("") == False
        assert is_uniprot_id("12345") == False
    
    def test_is_fasta_content(self):
        """测试FASTA格式检测"""
        from models.utils import is_fasta_content
        assert is_fasta_content(">protein\nMKTAYIAK") == True
        assert is_fasta_content("MKTAYIAK") == False
        assert is_fasta_content("") == False
    
    def test_clean_sequence(self):
        """测试序列清理"""
        from models.utils import clean_sequence
        assert clean_sequence("MKT AYI\nAK") == "MKTAYIAK"
        assert clean_sequence("mktayiak") == "MKTAYIAK"
        assert clean_sequence("") == ""
    
    def test_extract_sequence_from_fasta_content(self):
        """测试从FASTA提取序列"""
        from models.utils import extract_sequence_from_fasta_content
        fasta = ">protein\nMKTAYIAK\nQRQISFVK"
        assert extract_sequence_from_fasta_content(fasta) == "MKTAYIAKQRQISFVK"


class TestClassifyInput:
    """输入分类测试"""
    
    def test_classify_sequence(self):
        """测试序列分类"""
        from models.utils import classify_input
        result = classify_input("MKTAYIAKQRQISFVK")
        assert result == "MKTAYIAKQRQISFVK"
    
    def test_classify_fasta_content(self):
        """测试FASTA内容分类"""
        from models.utils import classify_input
        result = classify_input(">protein\nMKTAYIAK")
        assert result == "MKTAYIAK"


# ============== API 类测试 ==============

class TestKcatPredictorAPI:
    """API类测试"""
    
    def test_api_initialization(self):
        """测试API初始化"""
        from main import KcatPredictorAPI
        api = KcatPredictorAPI()
        assert api.weight_path is not None


# ============== FastAPI 端点测试 ==============

class TestFastAPIEndpoints:
    """FastAPI端点测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from starlette.testclient import TestClient
        from main import app
        return TestClient(app)
    
    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "kcat_predict"
    
    def test_root_endpoint(self, client):
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "Kcat Prediction Service"
    
    def test_predict_missing_smiles(self, client):
        """测试缺少SMILES参数"""
        response = client.post(
            "/api/predict/kcat",
            data={
                "enzyme_input_type": "sequence",
                "enzyme_query": "MKTAYIAK"
            }
        )
        assert response.status_code == 422  # Validation error


# ============== 模型测试 ==============

class TestEitlemKcatPredictor:
    """EITLEM Kcat预测器测试"""
    
    def test_model_initialization(self):
        """测试模型初始化"""
        import torch
        from models.kinetics_predictor import EitlemKcatPredictor
        
        model = EitlemKcatPredictor(
            mol_in_dim=167,
            hidden_dim=512,
            protein_dim=1280,
            layer=10,
            dropout=0.5,
            att_layer=10
        )
        assert model is not None
    
    def test_model_components(self):
        """测试模型组件"""
        import torch
        from models.kinetics_predictor import Resnet, AttentionAgg, ProMolAtt
        
        # Test Resnet
        resnet = Resnet(167, 512)
        x = torch.randn(1, 167)
        out = resnet(x)
        assert out.shape == (1, 512)
        
        # Test AttentionAgg
        attn = AttentionAgg(512)
        x = torch.randn(1, 3, 512)
        y = torch.randn(1, 5, 512)
        out = attn(x, y)
        assert out.shape == (1, 512)


# ============== 客户端测试 ==============

class TestClient:
    """客户端测试"""
    
    def test_client_initialization(self):
        """测试客户端初始化"""
        from client import KcatPredictClient
        client = KcatPredictClient("http://localhost:18904")
        assert client.base_url == "http://localhost:18904"
    
    def test_client_base_url_trailing_slash(self):
        """测试客户端URL尾斜杠处理"""
        from client import KcatPredictClient
        client = KcatPredictClient("http://localhost:18904/")
        assert client.base_url == "http://localhost:18904"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
