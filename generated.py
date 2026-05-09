# filename: switch_transformer.py
"""
Switch Transformer implementation for 12 trillion parameter models.
Uses tensor and pipeline parallelism for distributed training.
"""

import torch
import torch.nn as nn
from megatron.core import mpu
from megatron.model import TransformerLayer, ParallelTransformer
from typing import Optional, Tuple

class SwitchTransformer(ParallelTransformer):
    """
    Switch Transformer architecture with Mixture-of-Experts (MoE) layers.
    Implements tensor and pipeline parallelism for 12 trillion parameters.
    """

    def __init__(self, config: dict):
        """
        Initialize the Switch Transformer model.

        Args:
            config: Dictionary containing model configuration parameters
        """
        super().__init__(config)
        self.moe = True
        self.num_experts = config.get("num_experts", 128)
        self.top_k = config.get("top_k", 2)
        self.hidden_size = config["hidden_size"]

        # Initialize expert layers
        self.experts = nn.ModuleList([
            nn.Linear(self.hidden_size, self.hidden_size)
            for _ in range(self.num_experts)
        ])

        # Initialize router
        self.router = nn.Linear(self.hidden_size, self.num_experts)

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Forward pass of the Switch Transformer.

        Args:
            hidden_states: Input tensor of shape (batch_size, seq_len, hidden_size)
            attention_mask: Optional attention mask tensor

        Returns:
            Output tensor of shape (batch_size, seq_len, hidden_size)
        """
        # Standard transformer forward pass
        hidden_states = super().forward(hidden_states, attention_mask)

        # MoE routing
        hidden_states = self._moe_forward(hidden_states)

        return hidden_states

    def _moe_forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Mixture-of-Experts forward pass.

        Args:
            x: Input tensor of shape (batch_size, seq_len, hidden_size)

        Returns:
            Output tensor of shape (batch_size, seq_len, hidden_size)
        """
        batch_size, seq_len, hidden_size = x.shape

        # Flatten for routing
        x_flat = x.view(-1, hidden_size)

        # Route to experts
        router_logits = self.router(x_flat)
        router_probs = torch.softmax(router_logits, dim=-1)

        # Select top-k experts
        top_k_probs, top_k_indices = torch.topk(router_probs, self.top_k, dim=-1)

        # Normalize probabilities
        top_k_probs = top_k_probs / top_k_probs.sum(dim=-1, keepdim=True)

        # Initialize output
        output = torch.zeros_like(x_flat)

        # Process each expert
        for i in range(self.top_k):
            # Get expert indices
            expert_indices = top_k_indices[:, i]

            # Gather inputs for this expert
            expert_input = x_flat.gather(
                0,
                expert_indices.unsqueeze(-1).expand(-1, hidden_size)
            )

            # Apply expert
            expert_output = self.experts[expert_indices](expert_input)

            # Weight by router probability
            output.scatter_add_(
                0,
                expert_indices.unsqueeze(-1).expand(-1, hidden_size),
                expert_output * top_k_probs[:, i].unsqueeze(-1)
            )

        # Reshape output
        output = output.view(batch_size, seq_len, hidden_size)

        return output

def init_12t_model() -> SwitchTransformer:
    """
    Initialize a 12 trillion parameter Switch Transformer model.

    Returns:
        Initialized SwitchTransformer model
    """
    config = {
        "hidden_size": 24576,    # 24k dimension
        "num_layers": 128,       # 128 layers
        "num_attention_heads": 192,
        "ffn_hidden_size": 98304, # 4x hidden_size (MoE)
        "vocab_size": 128000,
        "max_position_embeddings": 4096,
        "num_experts": 128,      # 128 experts per MoE layer
        "top_k": 2,             # Route to top-2 experts
    }

    model = SwitchTransformer(config)

    # Custom weight initialization
    for name, param in model.named_parameters():
        if "weight" in name:
            torch.nn.init.normal_(param, mean=0.0, std=0.006)
        elif "bias" in name:
            torch.nn.init.zeros_(param)

    return model