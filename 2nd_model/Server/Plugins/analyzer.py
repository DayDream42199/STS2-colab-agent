"""The Characteristic Analyzer's arithmetic: one teammate's turn in, three
pieces of evidence out, and the profile they update. The spec's section 3.1.1,
steps 2-6, as plain functions on plain data, so they can be checked by hand
and run on a recorded game as well as a live one. aura.py gathers the turns.

A turn (step 1, Behavioral History) is a dict:
    energy      E_total: all the energy the player had this turn
    used        the cards they played, each {cost, dmg, block, groups}
    opp         every card that was in their hand this turn, the same shape
    incoming    D: the intent damage aimed at them
    block       B: their Block when they ended the turn

A card's `cost` is energy (an X-cost card: what it spent, or would spend);
`dmg` is all the damage it deals, every hit; `block` the Block it gives them;
`groups` from card_groups.py. Unplayable cards cost 0.
"""

TRAITS = ("A", "S", "T")       # Aggression, Scaling, Teamwork
# Memory size: how many full-weight turns a profile is built from before
# new evidence starts to move it slowly. The spec leaves it open; 20, as the
# teammate's CharacteristicAnalyzer package has it (the user's choice,
# 2026-10-31). Until a profile reaches it, it sets only the confidence: A, S
# and T come out the same at any beta.
BETA = 20


def _sum(cards, key, where=lambda c: True):
    return sum(c[key] for c in cards if where(c))


def _ratio(top, bottom):
    return top / bottom if bottom else 0.0


def _clip(value, low, high):
    return max(low, min(high, value))


def context(turn):
    """Step 2, Context Analysis: what each side of each trait could have taken
    (totalcost) and what it did (used), in the spec's names."""
    E, used, opp = turn["energy"], turn["used"], turn["opp"]
    attack = lambda c: c["dmg"] > 0
    guard = lambda c: c["block"] > 0
    blockless = lambda c: c["block"] == 0
    has = lambda group: (lambda c: group in c["groups"])

    # The hit still to be blocked: their own cards' Block is added back, so
    # Block a teammate gave them does lower it.
    I = max(0, turn["incoming"] - (turn["block"] - _sum(used, "block")))

    a = {}
    a["A+useddmg"] = _sum(used, "dmg")
    a["A+avgoppdmg"] = _ratio(_sum(opp, "dmg", attack), _sum(opp, "cost", attack))
    a["A+totalcost"] = min(_sum(opp, "cost", attack), E)
    a["A-usedblock"] = _sum(used, "block")
    a["A-avgoppblock"] = _ratio(_sum(opp, "block", guard), _sum(opp, "cost", guard))
    # "If teammate i holds no Block cards, A-totalcost = 0."
    a["A-totalcost"] = (min(_sum(opp, "cost", guard), I / a["A-avgoppblock"], E)
                        if a["A-avgoppblock"] > 0 else 0)
    block_side = a["A-totalcost"]

    a["S+usedcost"] = _sum(used, "cost", has("scale"))
    a["S+totalcost"] = min(_sum(opp, "cost", has("scale")), E)
    a["S-usedcost"] = (min(_sum(used, "cost", lambda c: has("now")(c) and guard(c)), block_side)
                       + _sum(used, "cost", lambda c: has("now")(c) and blockless(c)))
    a["S-totalcost"] = min(block_side + _sum(opp, "cost", lambda c: has("now")(c) and blockless(c)), E)

    a["T+usedcost"] = _sum(used, "cost", has("team"))
    a["T+totalcost"] = min(_sum(opp, "cost", has("team")), E)
    a["T-usedcost"] = (min(_sum(used, "cost", lambda c: has("self")(c) and guard(c)), block_side)
                       + _sum(used, "cost", lambda c: has("self")(c) and blockless(c)))
    a["T-totalcost"] = min(block_side + _sum(opp, "cost", lambda c: has("self")(c) and blockless(c)), E)
    a["I"] = I
    a["E"] = E
    return a


def mapped(a):
    """Step 3, Action Evaluation: each side as 0-100, the share of what was
    possible that the player used."""
    m = {}
    m["A+"] = _clip(_ratio(a["A+useddmg"], a["A+avgoppdmg"] * a["A+totalcost"]) * 100, 0, 100)
    m["A-"] = _clip(_ratio(a["A-usedblock"], a["A-avgoppblock"] * a["A-totalcost"]) * 100, 0, 100)
    for trait in ("S", "T"):
        for side in "+-":
            # The spec's sums keep these within 100. A cost that changed
            # between being seen in hand and being played (Corruption) could
            # push one over, so it is held there, as A's are: e stays in [-1, 1].
            m[trait + side] = _clip(_ratio(a[trait + side + "usedcost"],
                                           a[trait + side + "totalcost"]) * 100, 0, 100)
    return m


def evidence(turn):
    """Steps 2-4: per trait, the evidence e in [-1, 1] and its weight w in
    [0, 1]. A weight of 0 - both sides affordable in full, or one side not
    possible at all - means the turn says nothing about that trait."""
    a = context(turn)
    m = mapped(a)
    E = a["E"]
    out = {}
    for trait in TRAITS:
        plus = a[trait + "+totalcost"]
        minus = a[trait + "-totalcost"]
        e = 0.0 if plus == 0 or minus == 0 else (m[trait + "+"] - m[trait + "-"]) / 100
        w = max(0, plus + minus - E) / E if E > 0 else 0.0
        out[trait] = {"e": e, "w": w}
    return out, a, m


def new_profile():
    """Step 6: per trait the value X, the deviation d and the confidence c,
    all starting at 0."""
    return {trait: {"X": 0.0, "d": 0.0, "c": 0.0} for trait in TRAITS}


def update(profile, found, beta=BETA):
    """Step 5, Characteristic Update, each trait on its own. A trait whose
    weight is 0 is left as it was."""
    for trait in TRAITS:
        e, w = found[trait]["e"], found[trait]["w"]
        if w <= 0:
            continue
        p = profile[trait]
        n = min(beta * p["c"] + w, beta)
        step = w / n
        surprise = e - p["X"]
        p["X"] = p["X"] + step * surprise
        p["d"] = p["d"] + step * (surprise - p["d"])
        p["c"] = (n / beta) * (1 - abs(p["d"]) / 2)
    return profile


def values(profile):
    """What the agent is given: CV = {A, S, T, cA, cS, cT}."""
    out = {trait: profile[trait]["X"] for trait in TRAITS}
    out.update({"c" + trait: profile[trait]["c"] for trait in TRAITS})
    return out
