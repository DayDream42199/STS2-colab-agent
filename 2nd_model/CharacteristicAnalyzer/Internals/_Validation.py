import math


def _isNumber(v, minValue=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return False
    return minValue is None or v >= minValue


def checkHistory(history):
    if not isinstance(history, (list, tuple)) or len(history) not in (4, 5):
        raise ValueError("history must be [E_total, Used, Opp, incomingDamage] "
                         "or [E_total, Used, Opp, incomingDamage, blockAtTurnEnd]")
    energy, used, opp, damage = history[:4]
    numbers = [("E_total", energy), ("incomingDamage", damage)]
    if len(history) == 5:
        numbers.append(("blockAtTurnEnd", history[4]))
    for name, v in numbers:
        if not _isNumber(v, 0):
            raise ValueError(f"{name} must be a number >= 0, got {v!r}")
    for name, cards in (("Used", used), ("Opp", opp)):
        if not isinstance(cards, (list, tuple)):
            raise ValueError(f"{name} must be a list of cards")
        for c in cards:
            if not isinstance(c, (list, tuple)) or len(c) != 4:
                raise ValueError(f"every card must be [cost, damage, block, groups]; got {c!r} in {name}")
            if not all(_isNumber(v, 0) for v in c[:3]):
                raise ValueError(f"card cost/damage/block must be numbers >= 0; got {c!r} in {name}")


def checkProfile(data, keys):
    profile = {}
    for k in keys:
        if k not in data:
            raise ValueError(f"missing {k!r}")
        if not _isNumber(data[k]):
            raise ValueError(f"{k!r} is not a finite number: {data[k]!r}")
        profile[k] = data[k]
    return profile


def checkFinite(profile):
    for k, v in profile.items():
        if not math.isfinite(v):
            raise ArithmeticError(f"pipeline produced a non-finite value for {k}: {v!r}")
