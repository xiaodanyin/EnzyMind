"""
配置文件，包含项目路径和服务配置
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Files目录配置
FILES_DIR = PROJECT_ROOT / "files"
FASTA_DIR = FILES_DIR / "fasta"
PDB_DIR = FILES_DIR / "pdb"
ESM_DIR = FILES_DIR / "esm"
TEMP_DIR = FILES_DIR / "temp"

# 确保目录存在
for dir_path in [FILES_DIR, FASTA_DIR, PDB_DIR, ESM_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 服务端口配置
SERVICE_PORTS = {
    "gateway": 8000,
    "enzy_recognize": 18901,
    "ecnumber_predict": 18902,
    "substrate_predict": 18903,
    "kcat_predict": 18904,
    "km_predict": 18905,
    "structure_predict": 18906,
    "active_sites": 18907,
    "enzyme_check": 18908,
    "ec_reaction_info": 18909,
    "kinetic_params": 18910,
    "functional_site": 18911,
    "sequence_info": 18912,
    "enzyme_subclass": 18913,
    "enzyme_type": 18914,
    "enzyme_full_info": 18915,
    "function_get": 18916,
    "protparam": 18917,
    "sequence_alignment": 18918,
    "frontend": 8501,
    "agent": 8080,
}

# 服务URL配置
def get_service_url(service_name: str, host: str = "localhost") -> str:
    """获取服务URL"""
    port = SERVICE_PORTS.get(service_name)
    if port is None:
        raise ValueError(f"Unknown service: {service_name}")
    return f"http://{host}:{port}"

# 模型权重路径配置（需要根据实际情况修改）
MODEL_WEIGHTS = {
    "enzyme_recognition": "/path/to/enzyme_recognition_model/best_model.pth",
    "ecnumber_predictor": {
        "checkpoint": "/path/to/clean_data/pretrained/split100.pth",
        "gmm": "/path/to/clean_data/pretrained/gmm_ensumble.pkl",
        "emb_train": "/path/to/clean_data/pretrained/100.pt",
    },
    "kcat_predictor": "/path/to/eitlem_weights/KCAT/model_weights",
    "km_predictor": "/path/to/eitlem_weights/KM/model_weights",
    "esmfold": {
        "script_path": "/path/to/esmfold.py",
        "python_exec": "/path/to/python",
    },
    "substrate_predictor": {
        "script_path": "/path/to/mei_enzyme_substrate_predictor.py",
        "model_path": "/path/to/mei/model.pt",
    }
}

# ESM模型配置
ESM_CONFIG = {
    "model_location": "esm2_t33_650M_UR50D",
    "toks_per_batch": 4096,
    "repr_layers": [-1],
    "include": "mean",
    "truncation_seq_length": 1022,
}

# CUDA配置
CUDA_DEVICE = "cuda:0"  # 根据实际情况修改
