"""
Graph Dataset for Molecule Feature Extraction
分子图数据集
"""
import pickle
import networkx as nx

import torch
import dgl
from rdkit import Chem


def rdkit_to_networkx(smiles: str) -> nx.Graph:
    """将SMILES转换为NetworkX图"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit failed to parse SMILES: {smiles}")
    
    graph = nx.Graph()
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        graph.add_node(
            idx,
            element=atom.GetSymbol().lower(),
            charge=atom.GetFormalCharge(),
            aromatic=atom.GetIsAromatic(),
            hcount=atom.GetTotalNumHs()
        )
    
    for bond in mol.GetBonds():
        graph.add_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
    
    return graph


def networkx_to_dgl(raw_graph: nx.Graph, feature_encoder: dict) -> dgl.DGLGraph:
    """将NetworkX图转换为DGL图"""
    # 获取节点特征
    node_features = []
    for node in raw_graph.nodes():
        node_data = raw_graph.nodes[node]
        features = []
        for key in ['element', 'charge', 'aromatic', 'hcount']:
            if key in node_data:
                value = node_data[key]
                if key in feature_encoder:
                    if value in feature_encoder[key]:
                        features.append(feature_encoder[key][value])
                    else:
                        features.append(0)
                else:
                    features.append(int(value) if isinstance(value, bool) else value)
        node_features.append(features)
    
    # 创建DGL图
    src_nodes = []
    dst_nodes = []
    for edge in raw_graph.edges():
        src_nodes.append(edge[0])
        dst_nodes.append(edge[1])
        # 添加反向边（无向图）
        src_nodes.append(edge[1])
        dst_nodes.append(edge[0])
    
    dgl_graph = dgl.graph((src_nodes, dst_nodes), num_nodes=len(raw_graph.nodes()))
    dgl_graph.ndata['x'] = torch.tensor(node_features, dtype=torch.float32)
    
    return dgl_graph


class GraphDataset(dgl.data.DGLDataset):
    """分子图数据集"""
    
    def __init__(self, path_to_model: str, smiles_list: list, gpu: int = None):
        self.path = path_to_model
        self.smiles_list = smiles_list
        self.gpu = gpu
        self.parsed = []
        self.graphs = []
        super().__init__(name='graph_dataset')

    def process(self):
        """处理SMILES列表为DGL图"""
        with open(self.path + '/feature_enc.pkl', 'rb') as f:
            feature_encoder = pickle.load(f)
        
        for i, smiles in enumerate(self.smiles_list):
            try:
                # 尝试使用pysmiles解析
                try:
                    import pysmiles
                    raw_graph = pysmiles.read_smiles(smiles, zero_order_bonds=False)
                except Exception:
                    # 回退到RDKit
                    raw_graph = rdkit_to_networkx(smiles)
                
                dgl_graph = networkx_to_dgl(raw_graph, feature_encoder)
                self.graphs.append(dgl_graph)
                self.parsed.append(i)
            except Exception as e:
                print(f"Warning: Failed to parse SMILES at index {i}: {e}")
                continue
        
        # 移动到GPU（如果可用）
        if torch.cuda.is_available() and self.gpu is not None:
            self.graphs = [graph.to(f'cuda:{self.gpu}') for graph in self.graphs]

    def __getitem__(self, i: int) -> dgl.DGLGraph:
        return self.graphs[i]

    def __len__(self) -> int:
        return len(self.graphs)
