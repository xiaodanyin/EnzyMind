"""
Molecular GNN Model
分子图神经网络模型 - 与原始MEI实现一致
"""
import math
import torch
import torch.nn as nn
from torch.nn import ModuleList
from torch.nn.functional import one_hot
from dgl.nn import GraphConv, TAGConv
from dgl.nn.pytorch.glob import SumPooling


class GNN(nn.Module):
    """图神经网络模型 - 用于提取分子嵌入"""
    
    def __init__(self, gnn: str, n_layer: int, feature_len: int, dim: int):
        super(GNN, self).__init__()
        self.gnn = gnn
        self.n_layer = n_layer
        self.feature_len = feature_len
        self.dim = dim
        self.gnn_layers = ModuleList([])
        
        if gnn in ['gcn', 'tag']:
            for i in range(n_layer):
                if gnn == 'gcn':
                    self.gnn_layers.append(GraphConv(
                        in_feats=feature_len if i == 0 else dim,
                        out_feats=dim,
                        activation=None if i == n_layer - 1 else torch.relu
                    ))
                elif gnn == 'tag':
                    hops = 2
                    self.gnn_layers.append(TAGConv(
                        in_feats=feature_len if i == 0 else dim,
                        out_feats=dim,
                        activation=None if i == n_layer - 1 else torch.relu,
                        k=hops
                    ))
        else:
            raise ValueError(f'unknown GNN model: {gnn}')

        self.pooling_layer = SumPooling()
        self.factor = None

    def forward(self, graph) -> torch.Tensor:
        """前向传播"""
        feature = graph.ndata['feature']
        h = one_hot(feature, num_classes=self.feature_len)
        h = torch.sum(h, dim=1, dtype=torch.float)
        
        for layer in self.gnn_layers:
            h = layer(graph, h)
            if self.gnn == 'gat':
                h = torch.reshape(h, [h.size()[0], -1])
        
        if self.factor is None:
            self.factor = math.sqrt(self.dim) / float(torch.mean(torch.linalg.norm(h, dim=1)))
        h *= self.factor
        
        graph_embedding = self.pooling_layer(graph, h)
        return graph_embedding
