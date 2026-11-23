"""The policy behind --network pair: one small network scores every card-and-target pair.

The action numbers, the masks and MaskablePPO stay as they are. What changes is how the 106 scores are made:

    each card    -> card reader (one network)
    each player  -> player reader (one network: their numbers, profile, piles and the cards in hand)
    each enemy   -> enemy reader (one network)
    all of them  -> situation: teammates and enemies are added up by mean and max, so seats don't matter

    score of "play card h on target t" = scorer(card h, target t, kind of target, situation)
    score of "choose option k"         = chooser(option k, situation)
    end turn, stop choosing, wait      = read from the situation

So one example of a card teaches every hand slot and every teammate, and a target's own HP and profile go straight
into that target's score. Two teammates swapped in the input swap their scores: a seat alone can't be preferred.
"""
from functools import partial

import numpy as np
import torch as th
from torch import nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy

from .config import (OFF_PLAYERS, OFF_ENEMIES, OFF_CARDS, OFF_PILES, N_PLAYERS, N_ENEMIES, PLAYER_SIZE, ENEMY_SIZE,
                     CARD_SIZE, N_CARD_SLOTS, HAND_SIZE, N_CHOICE, N_PILES, PILE_SIZE, N_TARGETS, OBS_SIZE, EFFECT_SIZE,
                     ENEMY_EXTRA_SIZE)

SUMMARY = 64          # a card's or a unit's summary
SITUATION = 256       # the summary of the whole situation
LATENT = (HAND_SIZE + N_CHOICE + N_TARGETS) * SUMMARY + SITUATION


def _layers(*sizes):
    """Linear layers with ReLU between them, none after the last."""
    layers = []
    for a, b in zip(sizes, sizes[1:]):
        layers += [nn.Linear(a, b), nn.ReLU()]
    return nn.Sequential(*layers[:-1])


def _reader(*sizes):
    """A reader's output is never below 0, so an empty slot (all zeros) can't win the max."""
    return nn.Sequential(_layers(*sizes), nn.ReLU())


class PairExtractor(BaseFeaturesExtractor):
    """Output: the agent's hand, the choice slots, the 10 targets (the agent, 3 teammates, 6 enemies), the situation."""

    def __init__(self, observation_space):
        super().__init__(observation_space, LATENT)
        extra = observation_space.shape[0] - OBS_SIZE
        effects, foes = N_CARD_SLOTS * EFFECT_SIZE, N_ENEMIES * ENEMY_EXTRA_SIZE
        if extra not in (0, effects, foes, effects + foes):
            raise ValueError(f"an input of {observation_space.shape[0]} numbers is {OBS_SIZE} with neither, either or both "
                             "card effects and enemy statuses")
        self.with_effects = extra in (effects, effects + foes)   # EnvConfig.card_effects: each card's effects join its reading
        self.with_foes = extra in (foes, effects + foes)          # EnvConfig.enemy_statuses: each enemy's join its reading
        self.foes_at = OBS_SIZE + (effects if self.with_effects else 0)
        self.card_reader = _reader(CARD_SIZE + (EFFECT_SIZE if self.with_effects else 0), 128, SUMMARY)
        self.player_reader = _reader(PLAYER_SIZE + N_PILES * PILE_SIZE + SUMMARY, 128, SUMMARY)
        self.enemy_reader = _reader(ENEMY_SIZE + (ENEMY_EXTRA_SIZE if self.with_foes else 0), 128, SUMMARY)
        self.trunk = _reader(OFF_PLAYERS + 6 * SUMMARY, 512, SITUATION)

    def forward(self, obs):
        players = obs[:, OFF_PLAYERS:OFF_ENEMIES].reshape(-1, N_PLAYERS, PLAYER_SIZE)
        enemies = obs[:, OFF_ENEMIES:OFF_CARDS].reshape(-1, N_ENEMIES, ENEMY_SIZE)
        if self.with_foes:
            at = self.foes_at
            enemies = th.cat([enemies, obs[:, at:at + N_ENEMIES * ENEMY_EXTRA_SIZE].reshape(-1, N_ENEMIES, ENEMY_EXTRA_SIZE)], -1)
        cards = obs[:, OFF_CARDS:OFF_PILES].reshape(-1, N_CARD_SLOTS, CARD_SIZE)
        if self.with_effects:
            cards = th.cat([cards, obs[:, OBS_SIZE:OBS_SIZE + N_CARD_SLOTS * EFFECT_SIZE].reshape(-1, N_CARD_SLOTS, EFFECT_SIZE)], -1)
        piles = obs[:, OFF_PILES:OBS_SIZE].reshape(-1, N_PLAYERS, N_PILES * PILE_SIZE)
        here = (cards.abs().sum(-1, keepdim=True) > 0).float()              # empty slots stay all zeros
        read = self.card_reader(cards) * here
        hands = read[:, :N_PLAYERS * HAND_SIZE].reshape(-1, N_PLAYERS, HAND_SIZE, SUMMARY)
        held = here[:, :N_PLAYERS * HAND_SIZE].reshape(-1, N_PLAYERS, HAND_SIZE, 1)
        hand_mean = hands.sum(2) / held.sum(2).clamp(min=1)
        # the first number of a player's or an enemy's block says the slot is in use
        team = self.player_reader(th.cat([players, piles, hand_mean], -1)) * players[:, :, :1]
        foes = self.enemy_reader(enemies) * enemies[:, :, :1]
        me, mates = team[:, 0], team[:, 1:]
        mean = lambda units, used: units.sum(1) / used.sum(1).clamp(min=1)
        situation = self.trunk(th.cat([obs[:, :OFF_PLAYERS], me, mean(mates, players[:, 1:, :1]), mates.max(1).values,
                                       mean(foes, enemies[:, :, :1]), foes.max(1).values, hand_mean[:, 0]], -1))
        targets = th.cat([me[:, None], mates, foes], 1)
        return th.cat([hands[:, 0].flatten(1), read[:, N_PLAYERS * HAND_SIZE:].flatten(1), targets.flatten(1), situation], -1)


class PairLatent(nn.Module):
    """In place of SB3's mlp_extractor: the actor gets the extractor's output as it is, the critic a small net on the situation."""

    def __init__(self):
        super().__init__()
        self.latent_dim_pi = LATENT
        self.latent_dim_vf = SITUATION
        self.critic = nn.Sequential(nn.Linear(SITUATION, SITUATION), nn.Tanh())

    def forward_actor(self, features):
        return features

    def forward_critic(self, features):
        return self.critic(features[:, -SITUATION:])

    def forward(self, features):
        return self.forward_actor(features), self.forward_critic(features)


class PairHead(nn.Module):
    """In place of SB3's action_net: the 106 scores, in the env's action order."""

    def __init__(self):
        super().__init__()
        self.situation = nn.Sequential(nn.Linear(SITUATION, SUMMARY), nn.ReLU())
        self.scorer = _layers(3 * SUMMARY + 3, 128, 1)
        self.chooser = _layers(2 * SUMMARY, 64, 1)
        self.rest = nn.Linear(SITUATION, 3)                                 # end turn, stop choosing, wait
        kind = th.zeros(N_TARGETS, 3)
        kind[0, 0], kind[1:N_PLAYERS, 1], kind[N_PLAYERS:, 2] = 1, 1, 1     # the agent, a teammate, an enemy
        self.register_buffer("kind", kind)

    def forward(self, latent):
        n = latent.shape[0]
        hand = latent[:, :HAND_SIZE * SUMMARY].reshape(n, HAND_SIZE, SUMMARY)
        at = HAND_SIZE * SUMMARY
        choice = latent[:, at:at + N_CHOICE * SUMMARY].reshape(n, N_CHOICE, SUMMARY)
        at += N_CHOICE * SUMMARY
        target = latent[:, at:at + N_TARGETS * SUMMARY].reshape(n, N_TARGETS, SUMMARY)
        situation = latent[:, -SITUATION:]
        short = self.situation(situation)
        pairs = th.cat([hand[:, :, None].expand(-1, -1, N_TARGETS, -1),
                        target[:, None].expand(-1, HAND_SIZE, -1, -1),
                        self.kind[None, None].expand(n, HAND_SIZE, -1, -1),
                        short[:, None, None].expand(-1, HAND_SIZE, N_TARGETS, -1)], -1)
        play = self.scorer(pairs).squeeze(-1)                               # (n, 10, 10): action 1 + 10 h + t
        choose = self.chooser(th.cat([choice, short[:, None].expand(-1, N_CHOICE, -1)], -1)).squeeze(-1)
        rest = self.rest(situation)
        return th.cat([rest[:, :1], play.flatten(1), choose, rest[:, 1:]], 1)


class PairPolicy(MaskableActorCriticPolicy):
    def _build_mlp_extractor(self):
        self.mlp_extractor = PairLatent()

    def _build(self, lr_schedule):
        super()._build(lr_schedule)
        # SB3 has just built a plain action_net and an optimizer holding it: swap in the head, then the optimizer
        self.action_net = PairHead()
        if self.ortho_init:                                                 # as SB3 sets its own: small last layers
            self.action_net.apply(partial(self.init_weights, gain=np.sqrt(2)))
            for last in (self.action_net.scorer[-1], self.action_net.chooser[-1], self.action_net.rest):
                nn.init.orthogonal_(last.weight, gain=0.01)
        self.optimizer = self.optimizer_class(self.parameters(), lr=lr_schedule(1), **self.optimizer_kwargs)

    def action_logits(self, obs):
        """The 106 scores before the mask."""
        return self.action_net(self.mlp_extractor.forward_actor(self.extract_features(obs)))
