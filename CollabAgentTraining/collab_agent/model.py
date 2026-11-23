"""Policy network input: the shared card reader + everything else."""
import torch
from torch import nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from .config import OFF_CARDS, OFF_PILES, OBS_SIZE, N_CARD_SLOTS, CARD_SIZE


class CardReaderExtractor(BaseFeaturesExtractor):
    """All 43 card slots go through the SAME small network (the card reader),
    then the card summaries are joined with the global, player, enemy and pile numbers."""

    def __init__(self, observation_space, card_dim=64, features_dim=256):
        super().__init__(observation_space, features_dim)
        self.card_reader = nn.Sequential(
            nn.Linear(CARD_SIZE, 128), nn.ReLU(),
            nn.Linear(128, card_dim), nn.ReLU(),
        )
        other = OFF_CARDS + (OBS_SIZE - OFF_PILES)          # 877 + 108 = 985
        self.trunk = nn.Sequential(
            nn.Linear(other + N_CARD_SLOTS * card_dim, 512), nn.ReLU(),
            nn.Linear(512, features_dim), nn.ReLU(),
        )

    def forward(self, obs):
        cards = obs[:, OFF_CARDS:OFF_PILES].reshape(-1, N_CARD_SLOTS, CARD_SIZE)
        empty = (cards.abs().sum(-1, keepdim=True) == 0).float()
        summaries = self.card_reader(cards) * (1 - empty)    # empty slots stay all zeros
        rest = torch.cat([obs[:, :OFF_CARDS], obs[:, OFF_PILES:]], dim=1)
        return self.trunk(torch.cat([rest, summaries.flatten(1)], dim=1))
