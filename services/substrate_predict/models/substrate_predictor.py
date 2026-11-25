"""
Substrate Predictor Model
底物预测器 - 使用MEI模型预测酶-底物关系
"""
import os
import glob
import subprocess
import sys
import pickle
from typing import Tuple
from rdkit import Chem
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import dgl


# ============== LayerNormNet 模型 ==============

class LayerNormNet(nn.Module):
    """用于处理ESM嵌入的LayerNorm网络"""
    
    def __init__(self, hidden_dim: int = 512, out_dim: int = 128, device=None, dtype=None, drop_out: float = 0.1):
        super(LayerNormNet, self).__init__()
        if device is None:
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if dtype is None:
            dtype = torch.float32
        self.fc1 = nn.Linear(1280, hidden_dim, dtype=dtype, device=device)
        self.ln1 = nn.LayerNorm(hidden_dim, dtype=dtype, device=device)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim, dtype=dtype, device=device)
        self.ln2 = nn.LayerNorm(hidden_dim, dtype=dtype, device=device)
        self.fc3 = nn.Linear(hidden_dim, out_dim, dtype=dtype, device=device)
        self.dropout = nn.Dropout(p=drop_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.dropout(self.ln1(self.fc1(x)))
        x = torch.relu(x)
        x = self.dropout(self.ln2(self.fc2(x)))
        x = torch.relu(x)
        x = self.fc3(x)
        return x


# ============== MEI 模型组件 ==============

class SmiEncoder(nn.Module):
    """SMILES编码器"""
    
    def __init__(self, smi_dim: int, hid_dim: int, n_layers: int, kernel_size: int, dropout: float = 0.2):
        super().__init__()
        assert kernel_size % 2 == 1, "Kernel size must be odd."
        self.input_dim = 128
        self.hid_dim = hid_dim
        self.kernel_size = kernel_size
        self.n_layers = n_layers
        self.scale = torch.sqrt(torch.tensor(0.5))
        self.convs = nn.ModuleList(
            [nn.Conv1d(hid_dim, 2 * hid_dim, kernel_size, padding=(kernel_size - 1) // 2) for _ in range(self.n_layers)]
        )
        self.do = nn.Dropout(dropout)
        self.fc = nn.Linear(self.input_dim, self.hid_dim)
        self.gn = nn.GroupNorm(8, hid_dim * 2)
        self.ln = nn.LayerNorm(hid_dim)

    def forward(self, smi: torch.Tensor) -> torch.Tensor:
        smi = smi.permute(0, 2, 1)
        conv_input = self.fc(smi)
        conv_input = conv_input.permute(0, 2, 1)
        for conv in self.convs:
            conved = conv(self.do(conv_input))
            conved = F.glu(conved, dim=1)
            conved = conved + conv_input * self.scale.to(conved.device)
            conv_input = conved
        conved = conved.permute(0, 2, 1)
        conved = self.ln(conved)
        return conved


class AttentionBlock(nn.Module):
    """注意力块"""
    
    def __init__(self, hid_dim: int, n_heads: int, dropout: float):
        super().__init__()
        self.hid_dim = hid_dim
        self.n_heads = n_heads
        assert hid_dim % n_heads == 0
        self.f_q = nn.Linear(hid_dim, hid_dim)
        self.f_k = nn.Linear(hid_dim, hid_dim)
        self.f_v = nn.Linear(hid_dim, hid_dim)
        self.fc = nn.Linear(hid_dim, hid_dim)
        self.do = nn.Dropout(dropout)
        self.scale = torch.sqrt(torch.tensor(hid_dim // n_heads))

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, mask=None) -> torch.Tensor:
        batch_size = query.size(0)
        Q = self.f_q(query)
        K = self.f_k(key)
        V = self.f_v(value)
        Q = Q.view(batch_size, self.n_heads, self.hid_dim // self.n_heads).unsqueeze(3)
        K_T = K.view(batch_size, self.n_heads, self.hid_dim // self.n_heads).unsqueeze(3).transpose(2, 3)
        V = V.view(batch_size, self.n_heads, self.hid_dim // self.n_heads).unsqueeze(3)
        energy = torch.matmul(Q, K_T) / self.scale.to(Q.device)
        if mask is not None:
            energy = energy.masked_fill(mask == 0, -1e10)
        attention = self.do(F.softmax(energy, dim=-1))
        weighted = torch.matmul(attention, V)
        weighted = weighted.permute(0, 2, 1, 3).contiguous()
        weighted = weighted.view(batch_size, -1)
        weighted = self.do(self.fc(weighted))
        return weighted


class MEI(nn.Module):
    """MEI酶-底物预测模型"""
    
    def __init__(self, n_output: int = 2, projection_dim: int = 256, dropout: float = 0.2):
        super(MEI, self).__init__()
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
        self.n_output = n_output
        self.projection_dim = projection_dim
        
        self.mol_linear = nn.Linear(1024, projection_dim)
        self.enzyme_linear = nn.Linear(128, projection_dim)
        self.conv_x_1 = nn.Conv1d(in_channels=1024, out_channels=128, kernel_size=3, padding=1)
        self.smiencoder = SmiEncoder(smi_dim=128, hid_dim=64, n_layers=32, kernel_size=1)
        self.fc1_xt = nn.Linear(64, projection_dim)
        self.ln = nn.LayerNorm(projection_dim)
        self.att = AttentionBlock(projection_dim, 1, 0.2)
        self.enzyme_linear_proj = nn.Linear(128, projection_dim)
        self.att_block = AttentionBlock(projection_dim, 1, 0.2)
        self.ln2 = nn.LayerNorm(projection_dim)
        
        self.fc = nn.Sequential(
            nn.Linear(768, 2560),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(2560, 2560),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(2560, 1024),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(1024, 1024),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(1024, 256),
            nn.ReLU(),
            nn.Dropout(),
            nn.Linear(256, 2)
        )

    def forward(self, mol_embeddings: torch.Tensor, enzyme_embeddings: torch.Tensor) -> torch.Tensor:
        mol_projection = self.mol_linear(mol_embeddings)
        enzyme_projection = self.enzyme_linear(enzyme_embeddings)
        att = self.att(mol_projection, enzyme_projection, enzyme_projection)
        combined_embeddings = mol_projection + att
        combined_embeddings = self.ln2(combined_embeddings)
        feature = torch.cat((mol_projection, combined_embeddings, enzyme_projection), dim=1)
        output = self.fc(feature)
        return output


# ============== 分子图处理相关函数和类 ==============

# 节点属性名称
attribute_names = ['element', 'charge', 'aromatic', 'hcount']


def networkx_to_dgl(raw_graph, feature_encoder):
    """将NetworkX图转换为DGL图"""
    # add edges
    src = [s for (s, _) in raw_graph.edges]
    dst = [t for (_, t) in raw_graph.edges]
    graph = dgl.graph((src, dst), num_nodes=len(raw_graph.nodes))
    # add node features
    node_features = []
    for i in range(len(raw_graph.nodes)):
        raw_feature = raw_graph.nodes[i]
        numerical_feature = []
        for j in attribute_names:
            if raw_feature[j] in feature_encoder[j]:
                numerical_feature.append(feature_encoder[j][raw_feature[j]])
            else:
                numerical_feature.append(feature_encoder[j]['unknown'])
        node_features.append(numerical_feature)
    node_features = torch.tensor(node_features)
    graph.ndata['feature'] = node_features
    # transform to bi-directed graph with self-loops
    graph = dgl.to_bidirected(graph, copy_ndata=True)
    graph = dgl.add_self_loop(graph)
    return graph


def rdkit_to_networkx(smiles):
    """使用RDKit将SMILES转换为NetworkX图"""
    import networkx as nx
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("RDKit failed to parse SMILES")
    graph = nx.Graph()
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        graph.add_node(idx, element=atom.GetSymbol().lower(), charge=atom.GetFormalCharge(),
                       aromatic=atom.GetIsAromatic(), hcount=atom.GetTotalNumHs())
    for bond in mol.GetBonds():
        graph.add_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
    return graph


class GraphDataset(dgl.data.DGLDataset):
    """分子图数据集"""
    
    def __init__(self, path_to_model, smiles_list, gpu):
        self.path = path_to_model
        self.smiles_list = smiles_list
        self.gpu = gpu
        self.parsed = []
        self.graphs = []
        super().__init__(name='graph_dataset')

    def process(self):
        with open(self.path + '/feature_enc.pkl', 'rb') as f:
            feature_encoder = pickle.load(f)
        for i, smiles in enumerate(self.smiles_list):
            # try:
            #     # import pysmiles
            #     # raw_graph = pysmiles.read_smiles(smiles, zero_order_bonds=False)
            # except Exception:
            #     raw_graph = rdkit_to_networkx(smiles)
            raw_graph = rdkit_to_networkx(smiles)
            dgl_graph = networkx_to_dgl(raw_graph, feature_encoder)
            self.graphs.append(dgl_graph)
            self.parsed.append(i)
        if torch.cuda.is_available() and self.gpu is not None:
            self.graphs = [graph.to('cuda:' + str(self.gpu)) for graph in self.graphs]

    def __getitem__(self, i):
        return self.graphs[i]

    def __len__(self):
        return len(self.graphs)
    
class MolEFeaturizer:
    """分子嵌入特征提取器 - 使用GNN模型提取分子嵌入"""
    
    def __init__(self, path_to_model: str, gpu: int = 0):
        self.path_to_model = path_to_model
        self.gpu = gpu
        
        # 加载超参数
        with open(os.path.join(path_to_model, 'hparams.pkl'), 'rb') as f:
            hparams = pickle.load(f)
        
        self._hparams = hparams
        self._dim = hparams['dim']
        
        # 加载GNN模型
        from .mol_gnn import GNN
        self.mole = GNN(hparams['gnn'], hparams['layer'], hparams['feature_len'], hparams['dim'])
        
        model_path = os.path.join(path_to_model, 'model.pt')
        if torch.cuda.is_available() and gpu is not None:
            self.mole.load_state_dict(torch.load(model_path))
            self.mole = self.mole.cuda(gpu)
        else:
            self.mole.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    
    @property
    def dim(self):
        return self._dim
    
    def transform(self, smiles_list: list, batch_size: int = 1024) -> Tuple[np.ndarray, bool]:
        """转换SMILES列表为嵌入向量"""
        from dgl.dataloading import GraphDataLoader
        
        data = GraphDataset(self.path_to_model, smiles_list, self.gpu)
        dataloader = GraphDataLoader(data, batch_size=batch_size)
        all_embeddings = np.zeros((len(smiles_list), self.dim), dtype=float)
        res = []
        
        with torch.no_grad():
            self.mole.eval()
            for graphs in dataloader:
                res.append(self.mole(graphs))
            res = torch.cat(res, dim=0).cpu().numpy()
        
        all_embeddings[data.parsed, :] = res
        return all_embeddings, True


# ============== 底物预测器 ==============

class SubstratePredictor:
    """底物预测器"""
    
    def __init__(
        self,
        model_path: str = None,
        mol_model_path: str = None,
        esm_script_path: str = None,
        esm_out_dir: str = None,
        enzyme_embedding_model_path: str = None,
        gpu: int = 0
    ):
        self.model_path = model_path
        self.mol_model_path = mol_model_path
        self.esm_script_path = esm_script_path
        self.esm_out_dir = esm_out_dir
        self.enzyme_embedding_model_path = enzyme_embedding_model_path
        self.gpu = gpu
        
        # 设置设备
        if torch.cuda.is_available() and gpu is not None:
            self.device = torch.device(f"cuda:{gpu}")
        else:
            self.device = torch.device("cpu")
        
        # 延迟加载模型
        self._mei_model = None
        self._mol_featurizer = None
        self._enzyme_embedding_model = None
    
    @property
    def mei_model(self):
        """延迟加载MEI模型"""
        if self._mei_model is None and self.model_path:
            self._mei_model = MEI().to(self.device)
            self._mei_model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            self._mei_model.eval()
        return self._mei_model
    
    @property
    def mol_featurizer(self):
        """延迟加载分子特征提取器"""
        if self._mol_featurizer is None and self.mol_model_path:
            self._mol_featurizer = MolEFeaturizer(self.mol_model_path, self.gpu)
        return self._mol_featurizer
    
    @property
    def enzyme_embedding_model(self):
        """延迟加载酶嵌入处理模型"""
        if self._enzyme_embedding_model is None and self.enzyme_embedding_model_path:
            dtype = torch.float32
            self._enzyme_embedding_model = LayerNormNet(
                hidden_dim=512, out_dim=128, device=self.device, dtype=dtype
            )
            checkpoint = torch.load(self.enzyme_embedding_model_path, map_location=self.device)
            self._enzyme_embedding_model.load_state_dict(checkpoint)
            self._enzyme_embedding_model.eval()
        return self._enzyme_embedding_model
    
    def _format_esm(self, a):
        """格式化ESM输出"""
        if isinstance(a, dict):
            return a['mean_representations'][33]
        return a
    
    def _run_esm(self, uniprot_id: str, fasta_dir: str) -> torch.Tensor:
        """运行ESM提取嵌入（每次重新计算，不使用缓存）"""
        pt_path = os.path.join(self.esm_out_dir, f"{uniprot_id}.pt")
        
        # 如果存在旧的缓存文件，先删除
        if os.path.exists(pt_path):
            os.remove(pt_path)
        
        esm_type = "esm1b_t33_650M_UR50S"
        fasta_path = os.path.join(fasta_dir, f"{uniprot_id}.fasta")
        
        command = [
            sys.executable, self.esm_script_path, esm_type,
            fasta_path, self.esm_out_dir, "--include", "mean"
        ]
        subprocess.run(command, check=True)
        
        # 查找生成的文件并重命名
        generated_files = glob.glob(os.path.join(self.esm_out_dir, "*.pt"))
        for file in generated_files:
            if uniprot_id in file:
                os.rename(file, pt_path)
                break
        
        esm_tensor = self._format_esm(torch.load(pt_path, weights_only=True))
        return esm_tensor.unsqueeze(0).to(device=self.device)
    
    def _process_enzyme_embedding(self, esm_embedding: torch.Tensor) -> torch.Tensor:
        """处理酶ESM嵌入"""
        if self.enzyme_embedding_model is not None:
            return self.enzyme_embedding_model(esm_embedding)
        
        # 如果没有预训练模型，创建临时模型
        dtype = torch.float32
        model = LayerNormNet(hidden_dim=512, out_dim=128, device=self.device, dtype=dtype)
        if self.enzyme_embedding_model_path:
            checkpoint = torch.load(self.enzyme_embedding_model_path, map_location=self.device)
            model.load_state_dict(checkpoint)
        model.eval()
        return model(esm_embedding)
    
    def predict(self, uniprot_id: str, smiles: str, fasta_dir: str) -> Tuple[bool, float]:
        """
        预测酶-底物关系
        
        Args:
            uniprot_id: 蛋白质ID（对应FASTA文件名）
            smiles: 底物分子的SMILES字符串
            fasta_dir: FASTA文件目录
            
        Returns:
            is_substrate: 是否为底物
            confidence: 预测置信度
        """
        # 获取酶ESM嵌入
        esm_enzyme_emb = self._run_esm(uniprot_id, fasta_dir)
        
        # 处理酶嵌入
        clean_enzyme_emb = self._process_enzyme_embedding(esm_enzyme_emb)
        
        # 获取分子嵌入
        substrate_emb, _ = self.mol_featurizer.transform([smiles])
        
        # 转换为张量
        clean_enzyme_emb = clean_enzyme_emb.to(self.device)
        substrate_emb = torch.tensor(substrate_emb, dtype=torch.float32).to(self.device)
        
        # 预测
        with torch.no_grad():
            output = self.mei_model(substrate_emb, clean_enzyme_emb)
            prob = torch.sigmoid(output)[0][1].item()
        
        return (prob > 0.5), prob
    
    def predict_from_sequence(self, sequence: str, smiles: str, fasta_dir: str) -> Tuple[bool, float]:
        """
        从序列预测酶-底物关系
        
        Args:
            sequence: 蛋白质序列
            smiles: 底物分子的SMILES字符串
            fasta_dir: FASTA文件保存目录
            
        Returns:
            is_substrate: 是否为底物
            confidence: 预测置信度
        """
        # 保存序列为FASTA文件
        uniprot_id = "substrate_query"
        fasta_path = os.path.join(fasta_dir, f"{uniprot_id}.fasta")
        with open(fasta_path, 'w') as f:
            f.write(f">{uniprot_id}\n{sequence}\n")
        
        return self.predict(uniprot_id, smiles, fasta_dir)
