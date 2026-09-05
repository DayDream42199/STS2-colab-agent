"""What the Status and Curse cards do."""

from typing import Callable, Dict, List, Optional, Union
import copy

from ...entities import HAND_LIMIT
from ...statuses import StatusType, DEBUFF_STATUSES
from ..model import Card, CardType, TargetMode, UNPLAYABLE
from .common import *  # noqa: F401,F403
from .common import _arm_power, _pick


def fx_enthralled(engine, caster, target, card, x_amount=0):
    engine.log.append(f"{caster.name} plays out {card.name}")


def _fx_slimed(engine, caster, target, card, x_amount=0):
    engine.draw_extra(caster, 1)
