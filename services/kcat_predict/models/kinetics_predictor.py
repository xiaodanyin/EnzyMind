"""
Kinetics Predictor Models (Kcat & Km)
动力学参数预测模型
"""
import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import Data, Batch
from torch_geometric.utils import softmax, degree
from torch_geometric.nn import global_add_pool

try:
    import esm
    from rdkit import Chem
    from rdkit.Chem import MACCSkeys
except ImportError:
    esm = None
    Chem = None
    MACCSkeys = None


class AttentionAgg(nn.Module):
    def __init__(self, hidden_dim):
        super(AttentionAgg, self).__init__()
        self.q = nn.Linear(hidden_dim, hidden_dim)
        self.k = nn.Linear(hidden_dim, hidden_dim, bias=False)
    
    def forward(self, x, y):
        q = F.relu(self.q(x.mean(dim=1)))
        k = F.relu(self.k(y))
        score = F.softmax(torch.matmul(q.unsqueeze(1), k.transpose(-1, -2)), dim=-1)
        out = torch.matmul(score, y).squeeze(1)
        return out


class MultiHeadAttenAgg(nn.Module):
    def __init__(self, hidden_dim, att_layer, dropout):
        super().__init__()
        self.seq_m = nn.ModuleList(AttentionAgg(hidden_dim) for _ in range(att_layer))
        self.seq_o = nn.Sequential(
            nn.Linear(hidden_dim * att_layer, 4 * hidden_dim * att_layer),
            nn.ReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(4 * hidden_dim * att_layer, hidden_dim)
        )
    
    def forward(self, x, y):
        return self.seq_o(torch.cat([m(x, y) for m in self.seq_m], dim=-1))


class Resnet(nn.Module):
    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.lin1 = nn.Linear(in_dim, out_dim)
        self.lin2 = nn.Linear(out_dim, out_dim)
        self.lin3 = nn.Linear(out_dim, out_dim)
        self.lin4 = nn.Linear(out_dim, out_dim)
    
    def forward(self, x):
        x = F.relu(self.lin1(x))
        x = x + F.relu(self.lin2(x))
        x = x + F.relu(self.lin3(x))
        x = x + F.relu(self.lin4(x))
        return x


class ProMolAtt(nn.Module):
    def __init__(self, hidden_dim):
        super(ProMolAtt, self).__init__()
        self.q = nn.Linear(hidden_dim, hidden_dim)
        self.merge = nn.Linear(2 * hidden_dim, 1, bias=False)
        self.k = nn.Linear(hidden_dim, hidden_dim)
    
    def forward(self, mol, prot, batch):
        q = F.relu(self.q(mol))
        r = q.repeat_interleave(degree(batch, dtype=batch.dtype), dim=0)
        k = F.relu(self.k(prot))
        score = self.merge(torch.cat([k, r], dim=-1))
        score = softmax(score, batch, dim=0)
        o = global_add_pool(k * score, batch)
        return o, q


class EitlemKcatPredictor(nn.Module):
    """Kcat预测模型"""
    
    def __init__(self, mol_in_dim, hidden_dim=128, protein_dim=1280, layer=10, dropout=0.2, att_layer=10):
        super(EitlemKcatPredictor, self).__init__()
        self.prej1 = Resnet(mol_in_dim, hidden_dim)
        self.prej2 = nn.Linear(protein_dim, hidden_dim, bias=False)
        self.pro_extrac = nn.ModuleList([ProMolAtt(hidden_dim) for _ in range(layer)])
        self.att1 = MultiHeadAttenAgg(hidden_dim, att_layer, dropout)
        self.att2 = MultiHeadAttenAgg(hidden_dim, att_layer, dropout)
        self.out = nn.Sequential(
            nn.Linear(2 * hidden_dim, 4 * hidden_dim),
            nn.PReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(4 * hidden_dim, hidden_dim),
            nn.PReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_dim, 1)
        )
    
    def final_stage(self, mol, pro):
        pro_out = self.att1(mol, pro)
        mol_out = self.att2(pro, mol)
        return self.out(torch.cat([mol_out, pro_out], dim=-1)).squeeze(dim=-1)
    
    def forward(self, data):
        mol = F.relu(self.prej1(data.x))
        prot = F.relu(self.prej2(data.pro_emb))
        att_pro = []
        att_mol = []
        for m in self.pro_extrac:
            o, q = m(mol, prot, data.pro_emb_batch)
            att_pro.append(o)
            att_mol.append(q)
        att_mol = torch.stack(att_mol, dim=1)
        att_pro = torch.stack(att_pro, dim=1)
        return self.final_stage(att_mol, att_pro)


class EitlemKmPredictor(nn.Module):
    """Km预测模型"""
    
    def __init__(self, mol_in_dim, hidden_dim=128, protein_dim=1280, layer=10, dropout=0.2, att_layer=10):
        super(EitlemKmPredictor, self).__init__()
        self.prej1 = Resnet(mol_in_dim, hidden_dim)
        self.prej2 = nn.Linear(protein_dim, hidden_dim, bias=False)
        self.pro_extrac = nn.ModuleList([ProMolAtt(hidden_dim) for _ in range(layer)])
        self.att1 = MultiHeadAttenAgg(hidden_dim, att_layer, dropout)
        self.att2 = MultiHeadAttenAgg(hidden_dim, att_layer, dropout)
        self.out = nn.Sequential(
            nn.Linear(2 * hidden_dim, 4 * hidden_dim),
            nn.PReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(4 * hidden_dim, hidden_dim),
            nn.PReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_dim, 1)
        )
    
    def final_stage(self, mol, pro):
        pro_out = self.att1(mol, pro)
        mol_out = self.att2(pro, mol)
        return self.out(torch.cat([mol_out, pro_out], dim=-1)).squeeze(dim=-1)
    
    def forward(self, data):
        mol = F.relu(self.prej1(data.x))
        prot = F.relu(self.prej2(data.pro_emb))
        att_pro = []
        att_mol = []
        for m in self.pro_extrac:
            o, q = m(mol, prot, data.pro_emb_batch)
            att_pro.append(o)
            att_mol.append(q)
        att_mol = torch.stack(att_mol, dim=1)
        att_pro = torch.stack(att_pro, dim=1)
        return self.final_stage(att_mol, att_pro)


class BaseKineticsPredictor:
    """基础动力学预测器"""
    
    def __init__(self, model_class, weight_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        
        if esm is None:
            raise RuntimeError("ESM library not available")
        
        self.model, self.alphabet = esm.pretrained.esm1v_t33_650M_UR90S_1()
        self.model.eval().to(self.device)
        self.batch_converter = self.alphabet.get_batch_converter()
        
        self.predictor = model_class(167, 512, 1280, 10, 0.5, 10).to(self.device)
        if weight_path and os.path.exists(weight_path):
            self.predictor.load_state_dict(torch.load(weight_path, map_location=self.device))
        self.predictor.eval()
    
    def prepare_data(self, sequence: str, smiles: str):
        data = [("protein1", sequence)]
        _, _, batch_tokens = self.batch_converter(data)
        batch_tokens = batch_tokens.to(self.device)
        batch_lens = (batch_tokens != self.alphabet.padding_idx).sum(1)
        
        with torch.no_grad():
            results = self.model(batch_tokens, repr_layers=[33], return_contacts=False)
        token_representations = results["representations"][33]
        sequence_rep = token_representations[0, 1:batch_lens[0] - 1]
        
        mol = Chem.MolFromSmiles(smiles)
        mol_feature = MACCSkeys.GenMACCSKeys(mol).ToList()
        
        sample = Data(x=torch.FloatTensor(mol_feature).unsqueeze(0), pro_emb=sequence_rep)
        batch = Batch.from_data_list([sample], follow_batch=["pro_emb"])
        return batch.to(self.device)
    
    def predict(self, sequence: str, smiles: str) -> float:
        data = self.prepare_data(sequence, smiles)
        with torch.no_grad():
            output = self.predictor(data)
        return round(math.pow(10, output[0].item()), 4)
