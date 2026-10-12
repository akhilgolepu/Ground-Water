"""
Phase 3: Temporal Fusion Transformer (TFT) Engine
Constructs Variable Selection Networks (VSNs), Multi-Head Self-Attention,
and Quantile Loss head for probabilistic groundwater forecasting.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class GatedResidualNetwork(nn.Module):
    """Gated Residual Network (GRN) for nonlinear feature processing."""
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.gate = nn.Linear(input_dim, output_dim)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(output_dim)
        self.skip_projection = nn.Linear(input_dim, output_dim) if input_dim != output_dim else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.skip_projection(x) if self.skip_projection is not None else x
        h = F.elu(self.fc1(x))
        h = self.dropout(self.fc2(h))
        g = torch.sigmoid(self.gate(x))
        return self.layer_norm(residual + g * h)


class VariableSelectionNetwork(nn.Module):
    """Variable Selection Network (VSN) to dynamically weight top environmental features."""
    def __init__(self, num_features: int, hidden_dim: int, dropout: float = 0.1):
        super().__init__()
        self.num_features = num_features
        self.single_feature_grns = nn.ModuleList([
            GatedResidualNetwork(1, hidden_dim, hidden_dim, dropout)
            for _ in range(num_features)
        ])
        self.weight_grn = GatedResidualNetwork(num_features, hidden_dim, num_features, dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        weights = F.softmax(self.weight_grn(x), dim=-1)
        
        processed_feats = []
        for i in range(self.num_features):
            feat_i = x[:, i:i+1]
            processed_i = self.single_feature_grns[i](feat_i)
            processed_feats.append(processed_i.unsqueeze(1))
            
        processed_feats = torch.cat(processed_feats, dim=1)
        selected = torch.sum(weights.unsqueeze(-1) * processed_feats, dim=1)
        return selected


class TemporalFusionTransformer(nn.Module):
    """Temporal Fusion Transformer (TFT) Architecture for Multi-Horizon Forecasting."""
    def __init__(self, num_features: int, hidden_dim: int = 64, quantiles: list = [0.1, 0.5, 0.9], dropout: float = 0.1):
        super().__init__()
        self.num_features = num_features
        self.quantiles = quantiles
        self.vsn = VariableSelectionNetwork(num_features, hidden_dim, dropout)
        self.lstm_encoder = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)
        self.self_attention = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=4, batch_first=True)
        self.post_attention_grn = GatedResidualNetwork(hidden_dim, hidden_dim, hidden_dim, dropout)
        self.quantile_head = nn.Linear(hidden_dim, len(quantiles))

    def forward(self, x: torch.Tensor):
        vsn_out = self.vsn(x).unsqueeze(1)
        lstm_out, _ = self.lstm_encoder(vsn_out)
        attn_out, _ = self.self_attention(lstm_out, lstm_out, lstm_out)
        fused = self.post_attention_grn(attn_out.squeeze(1))
        preds = self.quantile_head(fused)
        return preds, None


class QuantileLoss(nn.Module):
    """Pinball / Quantile Loss Function for probabilistic intervals."""
    def __init__(self, quantiles: list = [0.1, 0.5, 0.9]):
        super().__init__()
        self.quantiles = quantiles

    def forward(self, preds: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        losses = []
        for i, q in enumerate(self.quantiles):
            errors = target - preds[:, i]
            loss = torch.max((q - 1) * errors, q * errors)
            losses.append(loss.unsqueeze(-1))
        return torch.mean(torch.sum(torch.cat(losses, dim=-1), dim=-1))


def calculate_picp(y_true: np.ndarray, q_lower: np.ndarray, q_upper: np.ndarray) -> float:
    """Calculates Prediction Interval Coverage Probability (PICP)."""
    covered = (y_true >= q_lower) & (y_true <= q_upper)
    return float(np.mean(covered) * 100.0)