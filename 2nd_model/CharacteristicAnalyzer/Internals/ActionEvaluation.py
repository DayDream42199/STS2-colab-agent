def clip(val, min_val, max_val):
    return max(min_val, min(val, max_val))


def getEvidence(dc):
    # Temp
    Aplus_denominator = dc["Aplus_avgoppdmg"] * dc["Aplus_totalcost"]
    Aplus_mapped = clip(dc["Aplus_useddmg"] / Aplus_denominator * 100 if Aplus_denominator > 0 else 0, 0, 100)
    Aminus_denominator = dc["Aminus_avgoppblock"] * dc["Aminus_totalcost"]
    Aminus_mapped = clip(dc["Aminus_usedblock"] / Aminus_denominator * 100 if Aminus_denominator > 0 else 0, 0, 100)

    Splus_denominator = dc["Splus_totalcost"]
    Splus_mapped = dc["Splus_usedcost"] / Splus_denominator * 100 if Splus_denominator > 0 else 0
    Sminus_denominator = dc["Sminus_totalcost"]
    Sminus_mapped = dc["Sminus_usedcost"] / Sminus_denominator * 100 if Sminus_denominator > 0 else 0

    Tplus_denominator = dc["Tplus_totalcost"]
    Tplus_mapped = dc["Tplus_usedcost"] / Tplus_denominator * 100 if Tplus_denominator > 0 else 0
    Tminus_denominator = dc["Tminus_totalcost"]
    Tminus_mapped = dc["Tminus_usedcost"] / Tminus_denominator * 100 if Tminus_denominator > 0 else 0


    # Calculate Evidence
    e_A = (Aplus_mapped - Aminus_mapped) / 100
    e_S = (Splus_mapped - Sminus_mapped) / 100
    e_T = (Tplus_mapped - Tminus_mapped) / 100

    return {
        "e_A": e_A,
        "e_S": e_S,
        "e_T": e_T,

        "Aplus_totalcost": dc["Aplus_totalcost"],
        "Aminus_totalcost": dc["Aminus_totalcost"],
        "Splus_totalcost": dc["Splus_totalcost"],
        "Sminus_totalcost": dc["Sminus_totalcost"],
        "Tplus_totalcost": dc["Tplus_totalcost"],
        "Tminus_totalcost": dc["Tminus_totalcost"],

        "E_total": dc["E_total"]
    }