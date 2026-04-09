"""
Enzyme Predictor Model
酶识别预测器 - 使用ESM2特征进行酶/非酶分类
"""
import os
import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, List


class SimpleMLP(nn.Module):
    """简单的多层感知机分类器"""
    
    def __init__(
        self,
        input_dim: int = 1280,
        hidden_dim: int = 256,
        output_dim: int = 2,
        dropout: float = 0.1
    ):
        super(SimpleMLP, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class EnzymePredictor:
    """酶识别预测器"""
    
    def __init__(
        self,
        esm2_model_location: str = 'esm2_t33_650M_UR50D',
        model_weights_path: str = None,
        nogpu: bool = False
    ):
        """
        初始化预测器
        
        Args:
            esm2_model_location: ESM2模型名称或路径
            model_weights_path: 分类器模型权重路径
            nogpu: 是否禁用GPU
        """
        self.esm2_model_location = esm2_model_location
        self.model_weights_path = model_weights_path
        self.nogpu = nogpu
        
        # 设置设备
        if torch.cuda.is_available() and not nogpu:
            self.device = torch.device('cuda')
        else:
            self.device = torch.device('cpu')
        
        # 延迟加载模型
        self._esm_model = None
        self._esm_alphabet = None
        self._batch_converter = None
        self._classifier = None
    
    def _load_esm_model(self):
        """加载ESM2模型"""
        if self._esm_model is None:
            import esm
            
            # 加载ESM2模型
            if os.path.isfile(self.esm2_model_location):
                # 从本地文件加载
                model_data = torch.load(self.esm2_model_location, map_location='cpu')
                model, alphabet = esm.pretrained.load_model_and_alphabet_core(
                    self.esm2_model_location, model_data, None
                )
            else:
                # 从torch hub加载预训练模型
                model, alphabet = getattr(esm.pretrained, self.esm2_model_location)()
            
            self._esm_model = model.eval().to(self.device)
            self._esm_alphabet = alphabet
            self._batch_converter = alphabet.get_batch_converter()
    
    def _load_classifier(self):
        """加载分类器模型"""
        if self._classifier is None:
            self._classifier = SimpleMLP(
                input_dim=1280,
                hidden_dim=2560,
                output_dim=2,
                dropout=0.1
            )
            
            if self.model_weights_path and os.path.exists(self.model_weights_path):
                state_dict = torch.load(self.model_weights_path, map_location=self.device)
                self._classifier.load_state_dict(state_dict)
            
            self._classifier = self._classifier.eval().to(self.device)
    
    def _parse_fasta(self, fasta_path: str) -> List[Tuple[str, str]]:
        """解析FASTA文件"""
        sequences = []
        current_header = None
        current_sequence = []
        
        with open(fasta_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    if current_header is not None:
                        sequences.append((current_header, ''.join(current_sequence)))
                    current_header = line[1:].split()[0]  # 取第一个词作为ID
                    current_sequence = []
                else:
                    current_sequence.append(line)
            
            # 添加最后一条序列
            if current_header is not None:
                sequences.append((current_header, ''.join(current_sequence)))
        
        return sequences
    
    def _extract_esm_features(self, sequences: List[Tuple[str, str]]) -> np.ndarray:
        """提取ESM2特征"""
        self._load_esm_model()
        
        # 转换为batch格式
        batch_labels, batch_strs, batch_tokens = self._batch_converter(sequences)
        batch_tokens = batch_tokens.to(self.device)
        
        # 获取ESM2表示
        with torch.no_grad():
            results = self._esm_model(batch_tokens, repr_layers=[33], return_contacts=False)
            token_representations = results["representations"][33]
        
        # 计算序列级别的平均表示
        sequence_representations = []
        for i, (_, seq) in enumerate(sequences):
            # 排除特殊token (BOS和EOS)
            seq_repr = token_representations[i, 1:len(seq)+1].mean(dim=0)
            sequence_representations.append(seq_repr.cpu().numpy())
        
        return np.array(sequence_representations)
    
    def predict(self, fasta_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测FASTA文件中的序列是否为酶
        
        Args:
            fasta_path: FASTA文件路径
            
        Returns:
            probabilities: 预测概率
            labels: 预测标签 (0: 非酶, 1: 酶)
        """
        # 解析FASTA文件
        sequences = self._parse_fasta(fasta_path)
        
        if not sequences:
            raise ValueError("No sequences found in FASTA file")
        
        # 提取ESM2特征
        features = self._extract_esm_features(sequences)
        
        # 加载分类器
        self._load_classifier()
        
        # 进行预测
        with torch.no_grad():
            features_tensor = torch.tensor(features, dtype=torch.float32).to(self.device)
            logits = self._classifier(features_tensor)
            probabilities = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()  # 取酶类别的概率
            labels = (probabilities >= 0.5).astype(int)
        
        return probabilities, labels
    
    def predict_sequence(self, sequence: str, seq_id: str = "query") -> Tuple[float, int]:
        """
        预测单条序列是否为酶
        
        Args:
            sequence: 氨基酸序列
            seq_id: 序列ID
            
        Returns:
            probability: 预测概率
            label: 预测标签 (0: 非酶, 1: 酶)
        """
        sequences = [(seq_id, sequence)]
        
        # 提取ESM2特征
        features = self._extract_esm_features(sequences)
        
        # 加载分类器
        self._load_classifier()
        
        # 进行预测
        with torch.no_grad():
            features_tensor = torch.tensor(features, dtype=torch.float32).to(self.device)
            logits = self._classifier(features_tensor)
            probability = torch.softmax(logits, dim=1)[0, 1].item()  # 取酶类别的概率
            label = 1 if probability >= 0.5 else 0
        
        return probability, label
