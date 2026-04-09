"""
Km Prediction Service - FastAPI Main Application
Km预测服务 - 端口 18905
"""
import os
import tempfile
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models.kinetics_predictor import BaseKineticsPredictor, EitlemKmPredictor
from models.utils import (
    classify_input,
    is_amino_acid_sequence,
    is_uniprot_id,
    is_fasta_content,
    clean_sequence,
    extract_sequence_from_fasta_content,
    get_uniprot_sequence
)

# 项目根目录和文件目录
SERVICE_ROOT = Path(__file__).parent
PROJECT_ROOT = Path(__file__).parent.parent.parent
FILES_DIR = PROJECT_ROOT / "files"
FASTA_DIR = FILES_DIR / "fasta"
ESM_DIR = FILES_DIR / "esm"

# 确保目录存在
FASTA_DIR.mkdir(parents=True, exist_ok=True)
ESM_DIR.mkdir(parents=True, exist_ok=True)

# ============== FastAPI 应用 ==============

app = FastAPI(
    title="Km Prediction Service",
    description="米氏常数(Km)预测服务 - 使用EITLEM模型",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 请求/响应模型 ==============

class KmPredictionRequest(BaseModel):
    """Km预测请求模型 (JSON格式)"""
    smiles: str                          # 底物分子SMILES
    enzyme_input_type: str = "sequence"  # sequence, uniprot, fasta
    enzyme_query: str                    # 酶序列、UniProt ID 或 FASTA 内容


class KmPredictionResponse(BaseModel):
    """Km预测响应模型"""
    success: bool
    km: Optional[float] = None
    unit: str = "mM"
    error: Optional[str] = None


# ============== API 类 ==============

class KmPredictorAPI:
    """Km预测器API封装"""
    
    def __init__(self, weight_path: str = None):
        """
        初始化Km预测器
        
        Args:
            weight_path: 模型权重路径
        """
        self.weight_path = weight_path or os.path.join(
            SERVICE_ROOT, 
            "checkpoints",
            "iter8_trainR2_0.9303_devR2_0.7163_RMSE_0.6960_MAE_0.4802")
        self._predictor = None
    
    @property
    def predictor(self) -> BaseKineticsPredictor:
        """延迟加载预测器"""
        if self._predictor is None:
            self._predictor = BaseKineticsPredictor(
                model_class=EitlemKmPredictor,
                weight_path=self.weight_path
            )
        return self._predictor
    
    def predict(self, smiles: str, sequence: str) -> dict:
        """
        预测Km值
        
        Args:
            smiles: 底物分子SMILES
            sequence: 蛋白质序列
            
        Returns:
            预测结果字典
        """
        try:
            km_val = self.predictor.predict(sequence, smiles)
            return {
                "success": True,
                "km": round(km_val, 4),
                "unit": "mM"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Km prediction failed: {str(e)}"
            }
    
    def run(self, smiles: str, enzyme_input: str) -> dict:
        """
        处理酶输入并预测Km
        
        Args:
            smiles: 底物分子SMILES
            enzyme_input: 酶输入（序列、UniProt ID或FASTA内容）
            
        Returns:
            预测结果字典
        """
        try:
            sequence = classify_input(enzyme_input.strip())
            if not sequence:
                return {"success": False, "error": "Failed to extract sequence from input"}
            return self.predict(smiles, sequence)
        except Exception as e:
            return {"success": False, "error": f"Failed to process enzyme input: {str(e)}"}


# 全局预测器实例
km_predictor_api = None


def get_predictor() -> KmPredictorAPI:
    """获取预测器实例"""
    global km_predictor_api
    if km_predictor_api is None:
        km_predictor_api = KmPredictorAPI()
    return km_predictor_api


# ============== API 端点 ==============

@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "Km Prediction Service",
        "version": "1.0.0",
        "description": "米氏常数(Km)预测服务"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "km_predict"}


@app.post("/api/predict/km", response_model=KmPredictionResponse)
async def predict_km(request: KmPredictionRequest):
    """
    预测酶的Km值 (JSON格式输入)
    
    请求体 (JSON):
    - **smiles**: 底物分子的SMILES表示
    - **enzyme_input_type**: 输入类型 (sequence/uniprot/fasta)
    - **enzyme_query**: 酶序列、UniProt ID 或 FASTA 内容
    """
    try:
        smiles = request.smiles
        enzyme_input_type = request.enzyme_input_type
        enzyme_query = request.enzyme_query
        
        # 验证输入
        if not smiles or not smiles.strip():
            return KmPredictionResponse(success=False, error="SMILES is required")
        
        if enzyme_input_type not in ["fasta", "sequence", "uniprot"]:
            return KmPredictionResponse(success=False, error=f"Invalid enzyme_input_type: {enzyme_input_type}")
        
        if not enzyme_query or not enzyme_query.strip():
            return KmPredictionResponse(success=False, error="enzyme_query is required")
        
        # 处理输入
        enzyme_input = None
        if enzyme_input_type == "fasta":
            sequence = extract_sequence_from_fasta_content(enzyme_query)
            enzyme_input = sequence
        elif enzyme_input_type == "sequence":
            if enzyme_query.strip().startswith(">") or "\n" in enzyme_query.strip():
                sequence = extract_sequence_from_fasta_content(enzyme_query)
                enzyme_input = sequence
            else:
                enzyme_input = clean_sequence(enzyme_query)
        elif enzyme_input_type == "uniprot":
            enzyme_input = enzyme_query.strip()
        
        # 执行预测
        predictor = get_predictor()
        result = predictor.run(smiles.strip(), enzyme_input)
        
        return KmPredictionResponse(
            success=result.get("success", False),
            km=result.get("km"),
            unit=result.get("unit", "mM"),
            error=result.get("error")
        )
        
    except Exception as e:
        return KmPredictionResponse(
            success=False,
            error=str(e)
        )


# ============== 启动服务 ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18905)
