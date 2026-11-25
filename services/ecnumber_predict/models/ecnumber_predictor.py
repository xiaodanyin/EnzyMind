"""
EC Number Predictor Model
EC号预测器 - 使用ESM嵌入和MaxSep方法预测EC分类号
"""
import os
import csv
import pickle
import random
import subprocess
import sys
from typing import Dict, Tuple, List, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm


def seed_everything(seed: int = 1234):
    """设置随机种子"""
    random.seed(seed)
    np.random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True


def ensure_dirs(path: str):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)


class LayerNormNet(nn.Module):
    def __init__(self, hidden_dim, out_dim, device, dtype, drop_out=0.1):
        super(LayerNormNet, self).__init__()
        self.hidden_dim1 = hidden_dim
        self.out_dim = out_dim
        self.drop_out = drop_out
        self.device = device
        self.dtype = dtype

        self.fc1 = nn.Linear(1280, hidden_dim, dtype=dtype, device=device)
        self.ln1 = nn.LayerNorm(hidden_dim, dtype=dtype, device=device)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim,
                             dtype=dtype, device=device)
        self.ln2 = nn.LayerNorm(hidden_dim, dtype=dtype, device=device)
        self.fc3 = nn.Linear(hidden_dim, out_dim, dtype=dtype, device=device)
        self.dropout = nn.Dropout(p=drop_out)

    def forward(self, x):
        x = self.dropout(self.ln1(self.fc1(x)))
        x = torch.relu(x)
        x = self.dropout(self.ln2(self.fc2(x)))
        x = torch.relu(x)
        x = self.fc3(x)
        return x


def get_ec_id_dict(csv_name: str) -> Tuple[Dict, Dict]:
    """
    从CSV文件获取EC ID字典
    
    Args:
        csv_name: CSV文件路径
        
    Returns:
        id_ec: ID到EC号的映射
        ec_id: EC号到ID集合的映射
    """
    csv_file = open(csv_name)
    csvreader = csv.reader(csv_file, delimiter='\t')
    id_ec = {}
    ec_id = {}
    
    for i, rows in enumerate(csvreader):
        if i > 0:
            id_ec[rows[0]] = rows[1].split(';')
            for ec in rows[1].split(';'):
                if ec not in ec_id.keys():
                    ec_id[ec] = set()
                    ec_id[ec].add(rows[0])
                else:
                    ec_id[ec].add(rows[0])
    return id_ec, ec_id


def maximum_separation(lst: List[float], first_grad: bool = True, use_max_grad: bool = False) -> int:
    """
    计算最大分离点
    
    Args:
        lst: 距离列表
        first_grad: 是否使用一阶梯度
        use_max_grad: 是否使用最大梯度
        
    Returns:
        最大分离点索引
    """
    lst = np.array(lst)
    
    if use_max_grad:
        if first_grad:
            sep_lst = np.diff(lst)
            sep_lst = np.insert(sep_lst, 0, 0)
        else:
            sep_lst = np.diff(np.diff(lst))
            sep_lst = np.insert(sep_lst, 0, 0)
            sep_lst = np.insert(sep_lst, 0, 0)
        return np.argmax(sep_lst)
    
    if first_grad:
        sep_lst = np.diff(lst)
        sep_lst = np.insert(sep_lst, 0, 0)
    else:
        sep_lst = np.diff(np.diff(lst))
        sep_lst = np.insert(sep_lst, 0, 0)
        sep_lst = np.insert(sep_lst, 0, 0)
    
    return np.argmax(sep_lst)


def infer_confidence_gmm(distance: float, gmm_lst: List) -> float:
    """
    使用GMM推断置信度
    
    Args:
        distance: 距离值
        gmm_lst: GMM模型列表
        
    Returns:
        置信度
    """
    confidence = []
    for j in range(len(gmm_lst)):
        main_GMM = gmm_lst[j]
        a, b = main_GMM.means_
        true_model_index = 0 if a[0] < b[0] else 1
        certainty = main_GMM.predict_proba([[distance]])[0][true_model_index]
        confidence.append(certainty)
    return np.mean(confidence)


def get_dist_map_test(
    model_emb_train: torch.Tensor,
    model_emb_test: torch.Tensor,
    ec_id_dict_train: Dict,
    id_ec_test: Dict,
    device,
    dtype,
    dot: bool = False
) -> Dict:
    """
    获取测试查询与训练EC聚类中心的距离映射
    
    Args:
        model_emb_train: 训练嵌入
        model_emb_test: 测试嵌入
        ec_id_dict_train: 训练EC ID字典
        id_ec_test: 测试ID到EC映射
        device: 计算设备
        dtype: 数据类型
        dot: 是否使用点积距离
        
    Returns:
        距离映射字典
    """
    # 计算聚类中心
    cluster_center_model = {}
    id_counter = 0
    with torch.no_grad():
        for ec in list(ec_id_dict_train.keys()):
            ids_for_query = list(ec_id_dict_train[ec])
            id_counter_prime = id_counter + len(ids_for_query)
            emb_cluster = model_emb_train[id_counter: id_counter_prime]
            cluster_center = emb_cluster.mean(dim=0)
            cluster_center_model[ec] = cluster_center.detach().cpu()
            id_counter = id_counter_prime
    
    # 构建查找表
    total_ec_n, out_dim = len(ec_id_dict_train.keys()), model_emb_train.size(1)
    model_lookup = torch.zeros(total_ec_n, out_dim, device=device, dtype=dtype)
    ecs = list(cluster_center_model.keys())
    for i, ec in enumerate(ecs):
        model_lookup[i] = cluster_center_model[ec]
    model_lookup = model_lookup.to(device=device, dtype=dtype)
    
    # 计算距离
    ids = list(id_ec_test.keys())
    dist = {}
    
    if dot:
        lookup1 = F.normalize(model_emb_test, dim=-1, p=2)
        lookup2 = F.normalize(model_lookup, dim=-1, p=2)
        for i, key1 in enumerate(ids):
            current = lookup1[i].unsqueeze(0)
            dist_norm = (current - lookup2).norm(dim=1, p=2)
            dist_norm = dist_norm**2
            dist_norm = dist_norm.detach().cpu().numpy()
            dist[key1] = {}
            for j, key2 in enumerate(ecs):
                dist[key1][key2] = dist_norm[j]
    else:
        for i, key1 in enumerate(ids):
            current = model_emb_test[i].unsqueeze(0)
            dist_norm = (current - model_lookup).norm(dim=1, p=2)
            dist_norm = dist_norm.detach().cpu().numpy()
            dist[key1] = {}
            for j, key2 in enumerate(ecs):
                dist[key1][key2] = dist_norm[j]
    
    return dist


def write_max_sep_choices(
    df: pd.DataFrame,
    csv_name: str,
    first_grad: bool = True,
    use_max_grad: bool = False,
    gmm: Optional[str] = None
) -> str:
    """
    使用最大分离方法写入预测结果
    
    Args:
        df: 距离数据框
        csv_name: 输出文件名
        first_grad: 是否使用一阶梯度
        use_max_grad: 是否使用最大梯度
        gmm: GMM模型路径
        
    Returns:
        预测的EC号字符串
    """
    gmm_lst = pickle.load(open(gmm, 'rb')) if gmm is not None else None
    best_ec_predictions = []
    for col in df.columns:
        smallest_10_dist_df = df[col].nsmallest(10)
        dist_lst = list(smallest_10_dist_df)
        max_sep_i = maximum_separation(dist_lst, first_grad, use_max_grad)
        candidates = []
        for i in range(max_sep_i + 1):
            EC_i = smallest_10_dist_df.index[i]
            dist_i = float(smallest_10_dist_df.iloc[i])
            score = infer_confidence_gmm(dist_i, gmm_lst) if gmm_lst is not None else -dist_i
            candidates.append((score, EC_i))

        if not candidates:
            fallback_ec = smallest_10_dist_df.index[0]
            best_ec_predictions.append('EC:' + str(fallback_ec))
            continue

        _, best_ec = max(candidates, key=lambda item: item[0])
        best_ec_predictions.append('EC:' + str(best_ec))

    return f"{', '.join(best_ec_predictions)}"


class ECnumberPredictor:
    """EC号预测器类"""
    
    def __init__(
        self,
        train_data: str = 'split100',
        gmm: str = None,
        checkpoint_file: str = None,
        emb_train_file: str = None,
        train_csv_file: str = None,
        esm_data_dir: str = None,
        input_dir: str = None,
        esm_script: str = None,
        nogpu: bool = False
    ):
        """
        初始化EC号预测器
        
        Args:
            train_data: 训练数据类型
            gmm: GMM模型路径
            checkpoint_file: 检查点文件路径
            emb_train_file: 训练嵌入文件路径
            train_csv_file: 训练CSV文件路径
            esm_data_dir: ESM数据目录
            input_dir: 输入数据目录
            esm_script: ESM提取脚本路径
            nogpu: 是否禁用GPU
        """
        self.train_data = train_data
        self.gmm = gmm
        self.nogpu = nogpu
        
        # 设置设备
        if torch.cuda.is_available() and not nogpu:
            self.device = torch.device('cuda')
        else:
            self.device = torch.device('cpu')
        self.dtype = torch.float32
        
        # 路径配置
        self.esm_data_dir = esm_data_dir
        self.input_dir = input_dir
        self.esm_script = esm_script
        self.train_csv_file = train_csv_file
        
        # 加载模型和数据
        self.checkpoint_file = checkpoint_file
        self.emb_train_file = emb_train_file
        
        self._checkpoint = None
        self._emb_train = None
        self._model = None
    
    @property
    def checkpoint(self):
        """延迟加载检查点"""
        if self._checkpoint is None and self.checkpoint_file:
            self._checkpoint = torch.load(
                self.checkpoint_file,
                map_location=self.device,
                weights_only=True
            )
        return self._checkpoint
    
    @property
    def emb_train(self):
        """延迟加载训练嵌入"""
        if self._emb_train is None and self.emb_train_file:
            self._emb_train = torch.load(
                self.emb_train_file,
                map_location=self.device,
                weights_only=True
            )
        return self._emb_train
    
    @property
    def model(self):
        """延迟加载模型"""
        if self._model is None:
            self._model = LayerNormNet(512, 128, self.device, self.dtype)
            if self.checkpoint is not None:
                self._model.load_state_dict(self.checkpoint)
            self._model.eval()
        return self._model
    
    def format_esm(self, a):
        """格式化ESM嵌入"""
        if isinstance(a, dict):
            a = a['mean_representations'][33]
        return a
    
    def load_esm(self, lookup: str) -> torch.Tensor:
        """加载ESM嵌入"""
        esm_path = os.path.join(self.esm_data_dir, lookup + '.pt')
        esm = self.format_esm(torch.load(esm_path, weights_only=True))
        return esm.unsqueeze(0)
    
    def model_embedding_test(self, id_ec_test: Dict, model: nn.Module) -> torch.Tensor:
        """
        获取测试序列的模型嵌入
        
        Args:
            id_ec_test: ID到EC映射
            model: 嵌入模型
            
        Returns:
            模型嵌入张量
        """
        ids_for_query = list(id_ec_test.keys())
        esm_to_cat = [self.load_esm(id) for id in ids_for_query]
        esm_emb = torch.cat(esm_to_cat).to(device=self.device, dtype=self.dtype)
        model_emb = model(esm_emb)
        return model_emb
    
    def prepare_infer_fasta(self, fasta_name: str):
        """
        准备推断所需的FASTA和CSV文件
        
        Args:
            fasta_name: FASTA文件名（不含扩展名）
        """
        # 提取ESM嵌入
        self.retrieve_esm_embedding(fasta_name)
        
        # 创建CSV文件
        csv_path = os.path.join(self.input_dir, fasta_name + '.csv')
        fasta_path = os.path.join(self.input_dir, fasta_name + '.fasta')
        
        with open(csv_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter='\t')
            csvwriter.writerow(['Entry', 'EC number', 'Sequence'])
            with open(fasta_path, 'r') as fastafile:
                for line in fastafile.readlines():
                    if line[0] == '>':
                        csvwriter.writerow([line.strip()[1:], ' ', ' '])
    
    def retrieve_esm_embedding(self, fasta_name: str):
        """
        提取ESM嵌入
        
        Args:
            fasta_name: FASTA文件名
        """
        if self.esm_script is None:
            raise ValueError("ESM script path is not configured")
        
        fasta_path = os.path.join(self.input_dir, fasta_name + ".fasta")
        esm_type = "esm1b_t33_650M_UR50S"
        command = [
            sys.executable, self.esm_script, esm_type,
            fasta_path, self.esm_data_dir, "--include", "mean"
        ]
        subprocess.run(command, check=True)
    
    def infer_maxsep(self, fasta_file: str) -> str:
        """
        使用MaxSep方法进行EC号推断
        
        Args:
            fasta_file: FASTA文件名（不含扩展名）
            
        Returns:
            预测的EC号
        """
        # 准备推断文件
        self.prepare_infer_fasta(fasta_file)
        
        # 获取EC ID字典
        id_ec_train, ec_id_dict_train = get_ec_id_dict(self.train_csv_file)
        csv_path = os.path.join(self.input_dir, fasta_file + '.csv')
        id_ec_test, _ = get_ec_id_dict(csv_path)
        
        # 获取模型嵌入
        emb_test = self.model_embedding_test(id_ec_test, self.model)
        
        # 计算距离
        eval_dist = get_dist_map_test(
            self.emb_train, emb_test,
            ec_id_dict_train, id_ec_test,
            self.device, self.dtype
        )
        
        # 设置随机种子
        seed_everything()
        
        # 生成结果
        eval_df = pd.DataFrame.from_dict(eval_dist)
        ensure_dirs("./results")
        out_filename = "results/" + fasta_file
        results = write_max_sep_choices(eval_df, out_filename, gmm=self.gmm)
        
        return results
    
    def predict(self, test_file: str) -> str:
        """
        预测EC号
        
        Args:
            test_file: 测试文件名（不含扩展名）
            
        Returns:
            预测的EC号
        """
        return self.infer_maxsep(test_file)
