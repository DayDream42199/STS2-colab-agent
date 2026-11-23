def getUpdate(e):
    # Calculate Weight
    w_A = (max(0, e["Aplus_totalcost"] + e["Aminus_totalcost"] - e["E_total"])) / e["E_total"] if e["E_total"] > 0 else 0
    w_S = (max(0, e["Splus_totalcost"] + e["Sminus_totalcost"] - e["E_total"])) / e["E_total"] if e["E_total"] > 0 else 0
    w_T = (max(0, e["Tplus_totalcost"] + e["Tminus_totalcost"] - e["E_total"])) / e["E_total"] if e["E_total"] > 0 else 0

    return {
        "e_A": e["e_A"],
        "e_S": e["e_S"],
        "e_T": e["e_T"],

        "w_A": w_A,
        "w_S": w_S,
        "w_T": w_T
    }