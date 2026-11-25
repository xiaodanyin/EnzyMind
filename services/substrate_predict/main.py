"""
Substrate Prediction Service - FastAPI Main Application
底物预测服务 - 预测给定酶和分子是否存在酶-底物关系
"""
import os
import re
import tempfile
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 项目根目录和文件目录
SERVICE_ROOT = Path(__file__).parent
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from shared.uniprot import uniprot_sequence_client

FILES_DIR = PROJECT_ROOT / "files"
FASTA_DIR = FILES_DIR / "fasta"
ESM_DIR = FILES_DIR / "esm"
TEMP_DIR = FILES_DIR / "temp"

# 确保目录存在
for d in [FASTA_DIR, ESM_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Substrate Prediction Service",
    description="预测给定酶和分子是否存在酶-底物关系",
    version="1.0.0"
)


# ============== 工具函数 ==============

def is_amino_acid_sequence(input_str: str) -> bool:
    """检查输入是否为有效的氨基酸序列"""
    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    cleaned = re.sub(r"\s+", "", input_str.upper())
    return len(cleaned) > 0 and all(char in amino_acids for char in cleaned)


def is_uniprot_id(input_str: str) -> bool:
    """检查输入是否为UniProt ID格式"""
    uniprot_regex = re.compile(r"^[A-Z][A-Z0-9]{5,9}$")
    return bool(uniprot_regex.match(input_str.strip()))


def is_fasta_file(path: str) -> bool:
    """检查输入是否为FASTA文件路径"""
    return os.path.isfile(path) and path.lower().endswith(('.fasta', '.fa'))


def is_fasta_content(content: str) -> bool:
    """检查字符串是否为FASTA格式内容"""
    return content.strip().startswith(">")


def get_uniprot_sequence(uniprot_id: str) -> str:
    """Retrieve a validated sequence through the bounded shared transport."""
    return uniprot_sequence_client.fetch(uniprot_id).sequence


def clean_sequence(seq: str) -> str:
    """清理序列，移除非氨基酸字符"""
    return re.sub(r"[^A-Z]", "", seq.upper())


def extract_sequence_from_fasta_content(fasta_content: str) -> str:
    """从FASTA格式内容中提取序列"""
    lines = fasta_content.strip().split('\n')
    sequence_lines = [line.strip() for line in lines if not line.startswith(">")]
    return clean_sequence("".join(sequence_lines))


def classify_input(input_string: str) -> str:
    """
    对输入进行分类并返回氨基酸序列
    """
    input_string = input_string.strip()
    
    # 如果是FASTA文件路径
    if is_fasta_file(input_string):
        with open(input_string, 'r') as f:
            content = f.read()
        return extract_sequence_from_fasta_content(content)
    
    # 如果是FASTA内容
    if is_fasta_content(input_string):
        return extract_sequence_from_fasta_content(input_string)
    
    # 如果是UniProt ID
    if is_uniprot_id(input_string):
        return get_uniprot_sequence(input_string)
    
    # 如果是纯氨基酸序列
    if is_amino_acid_sequence(input_string):
        return clean_sequence(input_string)
    
    raise ValueError(f"Invalid input: {input_string}")


# ============== API 请求/响应模型 ==============

class SubstratePredictionRequest(BaseModel):
    """底物预测请求模型 (JSON格式)"""
    smiles: str                    # 底物分子的SMILES字符串
    enzyme_input_type: str         # 酶输入类型: fasta, sequence, uniprot
    enzyme_query: str              # 酶查询字符串（序列、UniProt ID或FASTA内容）


class SubstratePredictionResponse(BaseModel):
    is_substrate: bool
    confidence: float


# ============== API 类 ==============

class SubstratePredictionAPI:
    """底物预测API类"""
    
    def __init__(
        self,
        model_path: str = None,
        mol_model_path: str = None,
        enzyme_embedding_model_path: str = None,
        esm_script_path: str = None,
        esm_out_dir: str = None,
        gpu: int = 0
    ):
        self.model_path = model_path
        self.mol_model_path = mol_model_path
        self.enzyme_embedding_model_path = enzyme_embedding_model_path
        self.esm_script_path = esm_script_path
        self.esm_out_dir = esm_out_dir or str(ESM_DIR)
        self.gpu = gpu
        self._predictor = None
    
    @property
    def predictor(self):
        """延迟加载预测器"""
        if self._predictor is None:
            from models.substrate_predictor import SubstratePredictor
            self._predictor = SubstratePredictor(
                model_path=self.model_path,
                mol_model_path=self.mol_model_path,
                enzyme_embedding_model_path=self.enzyme_embedding_model_path,
                esm_script_path=self.esm_script_path,
                esm_out_dir=self.esm_out_dir,
                gpu=self.gpu
            )
        return self._predictor
    
    def run(self, smiles: str, enzyme_input: str) -> dict:
        """运行底物预测"""
        try:
            # 处理酶输入，获取序列
            sequence = classify_input(enzyme_input.strip())
            
            # 保存为FASTA文件
            fasta_path = str(FASTA_DIR / "substrate_query.fasta")
            with open(fasta_path, "w") as f:
                f.write(f">substrate_query\n{sequence}\n")
            
            # 运行预测
            is_substrate, confidence = self.predictor.predict(
                uniprot_id="substrate_query",
                smiles=smiles,
                fasta_dir=str(FASTA_DIR)
            )
            
            return {
                "is_substrate": bool(is_substrate),
                "confidence": round(float(confidence), 4)
            }
            
        except Exception as e:
            return {"error": f"Prediction failed: {str(e)}"}


# 全局API实例（延迟初始化）
_substrate_predict_api = None


def get_api():
    """获取API实例"""
    global _substrate_predict_api
    if _substrate_predict_api is None:
        # 从环境变量读取配置
        model_path = os.path.join(SERVICE_ROOT, "checkpoints", "save", "cl_gcn", "model.pt")
        mol_model_path = os.path.join(SERVICE_ROOT, "checkpoints", "mol_ra", "saved_3", "gcn_1024")
        enzyme_embedding_model_path = os.path.join(SERVICE_ROOT, "checkpoints", "clean_data", "pretrained", "split100.pth")
        esm_script_path = os.path.join(SERVICE_ROOT, "script", "extract.py")
        
        
        _substrate_predict_api = SubstratePredictionAPI(
            model_path=model_path,
            mol_model_path=mol_model_path,
            enzyme_embedding_model_path=enzyme_embedding_model_path,
            esm_script_path=esm_script_path
        )
    return _substrate_predict_api


# ============== API 端点 ==============

@app.post("/api/predict/substrate", response_model=dict)
async def predict_substrate(request: SubstratePredictionRequest):
    """
    底物预测API (JSON格式输入)
    
    请求体 (JSON):
    - **smiles**: 底物分子的SMILES字符串
    - **enzyme_input_type**: 酶输入类型，可选值: fasta, sequence, uniprot
    - **enzyme_query**: 酶查询字符串（氨基酸序列、UniProt ID 或 FASTA 格式内容）
    
    返回:
    - **is_substrate**: 是否为该酶的底物
    - **confidence**: 预测置信度
    """
    try:
        smiles = request.smiles
        enzyme_input_type = request.enzyme_input_type
        enzyme_query = request.enzyme_query
        
        # 验证输入
        if not smiles or not smiles.strip():
            raise HTTPException(status_code=400, detail="SMILES is required and cannot be empty")
        
        if enzyme_input_type not in ["fasta", "sequence", "uniprot"]:
            raise HTTPException(status_code=400, detail=f"Invalid enzyme_input_type: {enzyme_input_type}. Must be one of: fasta, sequence, uniprot")
        
        if not enzyme_query or not enzyme_query.strip():
            raise HTTPException(status_code=400, detail="enzyme_query is required and cannot be empty")
        
        api = get_api()
        result = api.run(smiles.strip(), enzyme_query.strip())
        return {"result": result}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "substrate_predict"}


@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "Substrate Prediction Service",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/predict/substrate", "method": "POST", "description": "底物预测"},
            {"path": "/health", "method": "GET", "description": "健康检查"}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18903)
