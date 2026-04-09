"""
Enzyme Recognition Service - FastAPI Main Application
酶识别服务 - 判断给定蛋白质序列是否为酶
"""
import os
import re
import tempfile
import requests
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 项目根目录和文件目录
SERVICE_ROOT = Path(__file__).parent
PROJECT_ROOT = Path(__file__).parent.parent.parent
FILES_DIR = PROJECT_ROOT / "files"
FASTA_DIR = FILES_DIR / "fasta"

# 确保目录存在
FASTA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Enzyme Recognition Service",
    description="判断给定蛋白质序列是否为酶",
    version="1.0.0"
)


# ============== 工具函数 ==============

def is_amino_acid_sequence(input_str: str) -> bool:
    """检查输入是否为有效的氨基酸序列"""
    amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    return all(char in amino_acids for char in input_str.upper())


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
    """从UniProt获取蛋白质序列"""
    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        lines = response.text.strip().split('\n')
        sequence = ''.join(lines[1:])
        return sequence
    else:
        raise ValueError(f"Failed to retrieve sequence for UniProt ID: {uniprot_id}")


def clean_sequence(seq: str) -> str:
    """清理序列，移除非氨基酸字符"""
    return re.sub(r"[^A-Z]", "", seq.upper())


def extract_sequence_from_fasta_content(fasta_content: str) -> str:
    """从FASTA格式内容中提取序列"""
    lines = fasta_content.strip().split('\n')
    sequence_lines = [line.strip() for line in lines if not line.startswith(">")]
    return clean_sequence("".join(sequence_lines))


def classify_input_to_fasta(input_string: str, output_fasta_path: str) -> str:
    """
    对输入进行分类并保存为FASTA文件
    """
    input_string = input_string.strip()
    
    # 如果已经是FASTA文件，直接返回
    if is_fasta_file(input_string):
        return input_string
    
    # 如果是FASTA内容
    if is_fasta_content(input_string):
        sequence = extract_sequence_from_fasta_content(input_string)
    # 如果是UniProt ID
    elif is_uniprot_id(input_string):
        sequence = get_uniprot_sequence(input_string)
    # 如果是纯氨基酸序列
    elif is_amino_acid_sequence(input_string):
        sequence = clean_sequence(input_string)
    else:
        raise ValueError(f"Invalid input: {input_string}")
    
    # 保存为FASTA文件
    os.makedirs(os.path.dirname(output_fasta_path), exist_ok=True)
    with open(output_fasta_path, 'w') as f:
        f.write(f">query\n{sequence}")
    
    return output_fasta_path


# ============== API 类 ==============

class EnzymeRecognitionRequest(BaseModel):
    """酶识别请求模型"""
    input_type: str  # 输入类型: fasta, sequence, uniprot
    query: str       # 查询字符串（氨基酸序列或UniProt ID或FASTA内容）


class EnzymeRecognitionResponse(BaseModel):
    is_enzyme: bool
    confidence: float


class EnzymeRecognitionAPI:
    """酶识别API类"""
    
    def __init__(
        self,
        model_weights_path: str = None,
        esm2_model_location: str = 'esm2_t33_650M_UR50D',
        nogpu: bool = False
    ):
        self.model_weights_path = model_weights_path
        self.esm2_model_location = esm2_model_location
        self.nogpu = nogpu
        self._predictor = None
    
    @property
    def predictor(self):
        """延迟加载预测器"""
        if self._predictor is None:
            from models.enzyme_predictor import EnzymePredictor
            self._predictor = EnzymePredictor(
                esm2_model_location=self.esm2_model_location,
                model_weights_path=self.model_weights_path,
                nogpu=self.nogpu
            )
        return self._predictor
    
    def run(self, query: str) -> dict:
        """运行酶识别预测"""
        fasta_path = str(FASTA_DIR / "enzy_recognize_query.fasta")
        
        try:
            fasta_path = classify_input_to_fasta(query.strip(), fasta_path)
            probabilities, labels = self.predictor.predict(fasta_path)
            return {
                "is_enzyme": bool(labels[0] == 1),
                "confidence": round(float(probabilities[0]), 4)  # 转换为Python原生float
            }
        except Exception as e:
            return {"error": f"Failed to process input: {str(e)}"}


# 全局API实例（延迟初始化）
_enzyme_recognize_api = None


def get_api():
    """获取API实例"""
    global _enzyme_recognize_api
    if _enzyme_recognize_api is None:
        # 从环境变量或配置文件读取模型路径
        model_weights_path = os.path.join(SERVICE_ROOT, "checkpoints", "best_model.pth")
        _enzyme_recognize_api = EnzymeRecognitionAPI(model_weights_path=model_weights_path)
    return _enzyme_recognize_api


# ============== API 端点 ==============

@app.post("/api/recognize/enzyme", response_model=dict)
async def recognize_enzyme(request: EnzymeRecognitionRequest):
    """
    酶识别API (JSON格式输入)
    
    请求体 (JSON):
    - **input_type**: 输入类型，可选值: fasta, sequence, uniprot
    - **query**: 查询字符串（氨基酸序列、UniProt ID 或 FASTA 格式内容）
    
    返回:
    - **is_enzyme**: 是否为酶
    - **confidence**: 预测置信度
    """
    try:
        input_type = request.input_type
        query = request.query
        
        # 验证输入类型
        if input_type not in ["fasta", "sequence", "uniprot"]:
            raise HTTPException(status_code=400, detail=f"Invalid input_type: {input_type}. Must be one of: fasta, sequence, uniprot")
        
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="Query is required and cannot be empty")
        
        api = get_api()
        result = api.run(query.strip())
        return {"result": result}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "enzy_recognize"}


@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "Enzyme Recognition Service",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/recognize/enzyme", "method": "POST", "description": "酶识别预测"},
            {"path": "/health", "method": "GET", "description": "健康检查"}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18901)
