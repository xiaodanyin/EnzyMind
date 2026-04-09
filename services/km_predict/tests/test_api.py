"""
Tests for Km Prediction Service
Km预测服务测试
"""
import pytest


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_is_amino_acid_sequence_valid(self):
        from models.utils import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAYIAKQRQISFVK") == True
        assert is_amino_acid_sequence("ACDEFGHIKLMNPQRSTVWY") == True
    
    def test_is_amino_acid_sequence_invalid(self):
        from models.utils import is_amino_acid_sequence
        assert is_amino_acid_sequence("MKTAY123") == False
        assert is_amino_acid_sequence("") == False
        assert is_amino_acid_sequence(None) == False
    
    def test_is_uniprot_id_valid(self):
        from models.utils import is_uniprot_id
        assert is_uniprot_id("P12345") == True
        assert is_uniprot_id("Q9Y6K9") == True
    
    def test_is_uniprot_id_invalid(self):
        from models.utils import is_uniprot_id
        assert is_uniprot_id("MKTAYIAKQRQISFVK") == False
        assert is_uniprot_id("") == False
    
    def test_is_fasta_content(self):
        from models.utils import is_fasta_content
        assert is_fasta_content(">protein\nMKTAYIAK") == True
        assert is_fasta_content("MKTAYIAK") == False
    
    def test_clean_sequence(self):
        from models.utils import clean_sequence
        assert clean_sequence("MKT AYI\nAK") == "MKTAYIAK"
        assert clean_sequence("mktayiak") == "MKTAYIAK"
    
    def test_extract_sequence_from_fasta_content(self):
        from models.utils import extract_sequence_from_fasta_content
        fasta = ">protein\nMKTAYIAK\nQRQISFVK"
        assert extract_sequence_from_fasta_content(fasta) == "MKTAYIAKQRQISFVK"


class TestClassifyInput:
    """输入分类测试"""
    
    def test_classify_sequence(self):
        from models.utils import classify_input
        result = classify_input("MKTAYIAKQRQISFVK")
        assert result == "MKTAYIAKQRQISFVK"
    
    def test_classify_fasta_content(self):
        from models.utils import classify_input
        result = classify_input(">protein\nMKTAYIAK")
        assert result == "MKTAYIAK"


class TestKmPredictorAPI:
    """API类测试"""
    
    def test_api_initialization(self):
        from main import KmPredictorAPI
        api = KmPredictorAPI()
        assert api.weight_path is not None


class TestFastAPIEndpoints:
    """FastAPI端点测试"""
    
    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient
        from main import app
        return TestClient(app)
    
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "km_predict"
    
    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Km Prediction Service"
    
    def test_predict_missing_smiles(self, client):
        response = client.post(
            "/api/predict/km",
            data={"enzyme_input_type": "sequence", "enzyme_query": "MKTAYIAK"}
        )
        assert response.status_code == 422


class TestEitlemKmPredictor:
    """EITLEM Km预测器测试"""
    
    def test_model_initialization(self):
        import torch
        from models.kinetics_predictor import EitlemKmPredictor
        model = EitlemKmPredictor(mol_in_dim=167, hidden_dim=512, protein_dim=1280, layer=10, dropout=0.5, att_layer=10)
        assert model is not None
    
    def test_model_components(self):
        import torch
        from models.kinetics_predictor import Resnet, AttentionAgg
        
        resnet = Resnet(167, 512)
        x = torch.randn(1, 167)
        out = resnet(x)
        assert out.shape == (1, 512)
        
        attn = AttentionAgg(512)
        x = torch.randn(1, 3, 512)
        y = torch.randn(1, 5, 512)
        out = attn(x, y)
        assert out.shape == (1, 512)


class TestClient:
    """客户端测试"""
    
    def test_client_initialization(self):
        from client import KmPredictClient
        client = KmPredictClient("http://localhost:18905")
        assert client.base_url == "http://localhost:18905"
    
    def test_client_base_url_trailing_slash(self):
        from client import KmPredictClient
        client = KmPredictClient("http://localhost:18905/")
        assert client.base_url == "http://localhost:18905"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
