def calcCost(history, mode, group=""):
    SumCost = 0
    SumCost_nodmg = 0
    SumCost_dmg = 0
    SumCost_noblock = 0
    SumCost_block = 0

    SumCost_group = 0
    SumCost_groupnodmg = 0
    SumCost_groupdmg = 0
    SumCost_groupnoblock = 0
    SumCost_groupblock = 0

    pile = history[1] if mode == 0 else history[2]

    for card in pile:
        cost = card[0]
        damage = card[1]
        block = card[2]
        groups = card[3]

        SumCost += cost

        if damage > 0:
            SumCost_dmg += cost
        else:
            SumCost_nodmg += cost

        if block > 0:
            SumCost_block += cost
        else:
            SumCost_noblock += cost

        if groups and group in groups:
            SumCost_group += cost

            if damage > 0:
                SumCost_groupdmg += cost
            else:
                SumCost_groupnodmg += cost

            if block > 0:
                SumCost_groupblock += cost
            else:
                SumCost_groupnoblock += cost

    return {
        "total": SumCost,
        "nodmg": SumCost_nodmg,
        "dmg": SumCost_dmg,
        "noblock": SumCost_noblock,
        "block": SumCost_block,

        "group": SumCost_group,
        "groupnodmg": SumCost_groupnodmg,
        "groupdmg": SumCost_groupdmg,
        "groupnoblock": SumCost_groupnoblock,
        "groupblock": SumCost_groupblock
    }


def calcDamage(history, mode, group=""):
    SumDamage = 0
    SumDamage_nodmg = 0
    SumDamage_dmg = 0
    SumDamage_noblock = 0
    SumDamage_block = 0

    SumDamage_group = 0
    SumDamage_groupnodmg = 0
    SumDamage_groupdmg = 0
    SumDamage_groupnoblock = 0
    SumDamage_groupblock = 0

    pile = history[1] if mode == 0 else history[2]

    for card in pile:
        cost = card[0]
        damage = card[1]
        block = card[2]
        groups = card[3]

        SumDamage += damage

        if damage > 0:
            SumDamage_dmg += damage
        else:
            SumDamage_nodmg += damage

        if block > 0:
            SumDamage_block += damage
        else:
            SumDamage_noblock += damage

        if groups and group in groups:
            SumDamage_group += damage

            if damage > 0:
                SumDamage_groupdmg += damage
            else:
                SumDamage_groupnodmg += damage

            if block > 0:
                SumDamage_groupblock += damage
            else:
                SumDamage_groupnoblock += damage

    return {
        "total": SumDamage,
        "nodmg": SumDamage_nodmg,
        "dmg": SumDamage_dmg,
        "noblock": SumDamage_noblock,
        "block": SumDamage_block,

        "group": SumDamage_group,
        "groupnodmg": SumDamage_groupnodmg,
        "groupdmg": SumDamage_groupdmg,
        "groupnoblock": SumDamage_groupnoblock,
        "groupblock": SumDamage_groupblock
    }


def calcBlock(history, mode, group=""):
    SumBlock = 0
    SumBlock_nodmg = 0
    SumBlock_dmg = 0
    SumBlock_noblock = 0
    SumBlock_block = 0

    SumBlock_group = 0
    SumBlock_groupnodmg = 0
    SumBlock_groupdmg = 0
    SumBlock_groupnoblock = 0
    SumBlock_groupblock = 0

    pile = history[1] if mode == 0 else history[2]

    for card in pile:
        cost = card[0]
        damage = card[1]
        block = card[2]
        groups = card[3]

        SumBlock += block

        if damage > 0:
            SumBlock_dmg += block
        else:
            SumBlock_nodmg += block

        if block > 0:
            SumBlock_block += block
        else:
            SumBlock_noblock += block

        if groups and group in groups:
            SumBlock_group += block

            if damage > 0:
                SumBlock_groupdmg += block
            else:
                SumBlock_groupnodmg += block

            if block > 0:
                SumBlock_groupblock += block
            else:
                SumBlock_groupnoblock += block

    return {
        "total": SumBlock,
        "nodmg": SumBlock_nodmg,
        "dmg": SumBlock_dmg,
        "noblock": SumBlock_noblock,
        "block": SumBlock_block,

        "group": SumBlock_group,
        "groupnodmg": SumBlock_groupnodmg,
        "groupdmg": SumBlock_groupdmg,
        "groupnoblock": SumBlock_groupnoblock,
        "groupblock": SumBlock_groupblock
    }


def getDecisionContext(history):
    # Variables
    E_total = history[0]
    # B = Block when the turn ended (5th entry). Without it, take the Block of
    # the used cards: no Block from anywhere else, so I is the whole intent.
    B = history[4] if len(history) > 4 else calcBlock(history, 0)["total"]
    I = max(0, history[3] - (B - calcBlock(history, 0)["total"]))


    # Aggression
    Aplus_useddmg = calcDamage(history, 0)["total"]
    Aplus_avgoppdmg = calcDamage(history, 1)["dmg"] / calcCost(history, 1)["dmg"] if calcCost(history, 1)["dmg"] > 0 else 0
    Aplus_totalcost = min(calcCost(history, 1)["dmg"], E_total)

    Aminus_usedblock = calcBlock(history, 0)["total"]
    Aminus_avgoppblock = calcBlock(history, 1)["block"] / calcCost(history, 1)["block"] if calcCost(history, 1)["block"] > 0 else 0
    Aminus_totalcost = min(calcCost(history, 1)["block"], I / Aminus_avgoppblock if Aminus_avgoppblock > 0 else 0, E_total)

    # Scaling
    Splus_usedcost = calcCost(history, 0, "scale")["group"]
    Splus_totalcost = min(calcCost(history, 1, "scale")["group"], E_total)
    Sminus_usedcost = min(calcCost(history, 0, "now")["groupblock"], Aminus_totalcost) + calcCost(history, 0, "now")["groupnoblock"]
    Sminus_totalcost = min(Aminus_totalcost + calcCost(history, 1, "now")["groupnoblock"], E_total)

    # Teamwork
    Tplus_usedcost = calcCost(history, 0, "team")["group"]
    Tplus_totalcost = min(calcCost(history, 1, "team")["group"], E_total)
    Tminus_usedcost = min(calcCost(history, 0, "self")["groupblock"], Aminus_totalcost) + calcCost(history, 0, "self")["groupnoblock"]
    Tminus_totalcost = min(Aminus_totalcost + calcCost(history, 1, "self")["groupnoblock"], E_total)

    return {
        "E_total": E_total,
        "Aplus_useddmg": Aplus_useddmg,
        "Aplus_avgoppdmg": Aplus_avgoppdmg,
        "Aplus_totalcost": Aplus_totalcost,
        "Aminus_usedblock": Aminus_usedblock,
        "Aminus_avgoppblock": Aminus_avgoppblock,
        "Aminus_totalcost": Aminus_totalcost,
        "Splus_usedcost": Splus_usedcost,
        "Splus_totalcost": Splus_totalcost,
        "Sminus_usedcost": Sminus_usedcost,
        "Sminus_totalcost": Sminus_totalcost,
        "Tplus_usedcost": Tplus_usedcost,
        "Tplus_totalcost": Tplus_totalcost,
        "Tminus_usedcost": Tminus_usedcost,
        "Tminus_totalcost": Tminus_totalcost
    }