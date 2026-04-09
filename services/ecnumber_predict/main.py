"""
EC Number Prediction Service - FastAPI Main Application
EC号预测服务 - 预测蛋白质的EC分类号
"""
import os
import re
import shutil
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
ESM_DIR = FILES_DIR / "esm"

# 确保目录存在
FASTA_DIR.mkdir(parents=True, exist_ok=True)
ESM_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="EC Number Prediction Service",
    description="预测蛋白质的EC分类号",
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

class ECNumberPredictionRequest(BaseModel):
    """EC号预测请求模型"""
    input_type: str  # 输入类型: fasta, sequence, uniprot
    query: str       # 查询字符串（氨基酸序列或UniProt ID或FASTA内容）


class ECNumberPredictionResponse(BaseModel):
    ec_number: str


class ECNumberPredictionAPI:
    """EC号预测API类"""
    
    def __init__(
        self,
        train_data: str = 'split100',
        pretrained: bool = True,
        model_name: str = None,
        gmm_path: str = None,
        checkpoint_file: str = None,
        emb_train_file: str = None,
        train_csv_file: str = None,
        esm_data_dir: str = None,
        input_dir: str = None,
        esm_script: str = None,
        nogpu: bool = False
    ):
        """
        初始化EC号预测API
        
        Args:
            train_data: 训练数据类型
            pretrained: 是否使用预训练模型
            model_name: 模型名称
            gmm_path: GMM模型文件路径
            checkpoint_file: 检查点文件路径
            emb_train_file: 训练嵌入文件路径
            train_csv_file: 训练CSV文件路径
            esm_data_dir: ESM数据目录
            input_dir: 输入数据目录
            esm_script: ESM提取脚本路径
            nogpu: 是否禁用GPU
        """
        self.train_data = train_data
        self.pretrained = pretrained
        self.model_name = model_name
        self.gmm_path = gmm_path
        self.checkpoint_file = checkpoint_file
        self.emb_train_file = emb_train_file
        self.train_csv_file = train_csv_file
        self.esm_data_dir = esm_data_dir or str(ESM_DIR)
        self.input_dir = input_dir or str(FASTA_DIR)
        self.esm_script = esm_script
        self.nogpu = nogpu
        
        # 延迟加载
        self._predictor = None
    
    @property
    def predictor(self):
        """延迟加载预测器"""
        if self._predictor is None:
            from models.ecnumber_predictor import ECnumberPredictor
            self._predictor = ECnumberPredictor(
                train_data=self.train_data,
                gmm=self.gmm_path,
                checkpoint_file=self.checkpoint_file,
                emb_train_file=self.emb_train_file,
                train_csv_file=self.train_csv_file,
                esm_data_dir=self.esm_data_dir,
                input_dir=self.input_dir,
                esm_script=self.esm_script,
                nogpu=self.nogpu
            )
        return self._predictor
    
    def run(self, query: str) -> dict:
        """运行EC号预测"""
        fasta_dir = str(FASTA_DIR)
        os.makedirs(fasta_dir, exist_ok=True)
        fasta_path = os.path.join(fasta_dir, "ecnumber_query.fasta")
        
        try:
            # 如果是已经是文件路径，直接复制
            if os.path.isfile(query):
                shutil.copy(query, fasta_path)
            else:
                fasta_path = classify_input_to_fasta(query.strip(), fasta_path)
            
            query_id = os.path.basename(fasta_path).split('.')[0]
            result = self.predictor.predict(query_id)
            
            return {"ec_number": result}
            
        except Exception as e:
            return {"error": str(e)}


# 全局API实例（延迟初始化）
_ecnumber_predict_api = None


def get_api():
    """获取API实例"""
    global _ecnumber_predict_api
    if _ecnumber_predict_api is None:
        # 从环境变量读取配置
        gmm_path = os.path.join(SERVICE_ROOT, "checkpoints", "pretrained", "gmm_ensumble.pkl")
        checkpoint_file = os.path.join(SERVICE_ROOT, "checkpoints", "pretrained", "split100.pth")
        emb_train_file =  os.path.join(SERVICE_ROOT, "checkpoints", "pretrained", "100.pt") 
        train_csv_file = os.path.join(SERVICE_ROOT, "checkpoints", "split100.csv")

        esm_data_dir =  os.path.join(SERVICE_ROOT, "files", "esm_data")
        input_dir =  FASTA_DIR

        esm_script = os.path.join(SERVICE_ROOT, "script", "extract.py")

        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(esm_data_dir, exist_ok=True)
        
        _ecnumber_predict_api = ECNumberPredictionAPI(
            gmm_path=gmm_path,
            checkpoint_file=checkpoint_file,
            emb_train_file=emb_train_file,
            train_csv_file=train_csv_file,
            esm_data_dir=esm_data_dir,
            input_dir=input_dir,
            esm_script=esm_script
        )
    return _ecnumber_predict_api


# ============== API 端点 ==============

@app.post("/api/predict/ec", response_model=dict)
async def predict_ec_number(request: ECNumberPredictionRequest):
    """
    EC号预测API (JSON格式输入)
    
    请求体 (JSON):
    - **input_type**: 输入类型，可选值: fasta, sequence, uniprot
    - **query**: 查询字符串（氨基酸序列、UniProt ID 或 FASTA 格式内容）
    
    返回:
    - **ec_number**: 预测的EC号
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
    return {"status": "healthy", "service": "ecnumber_predict"}


@app.get("/")
async def root():
    """根端点"""
    return {
        "service": "EC Number Prediction Service",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/api/predict/ec", "method": "POST", "description": "EC号预测"},
            {"path": "/health", "method": "GET", "description": "健康检查"}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18902)
