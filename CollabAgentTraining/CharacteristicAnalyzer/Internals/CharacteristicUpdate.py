beta = 20

def getNewProfile(U, OP):
    # Temp
    n_A = min(beta * OP["c_A"] + U["w_A"], beta)
    n_S = min(beta * OP["c_S"] + U["w_S"], beta)
    n_T = min(beta * OP["c_T"] + U["w_T"], beta)


    # Calculate New Profile
    A_new = OP["A"] + (U["w_A"] / n_A) * (U["e_A"] - OP["A"]) if U["w_A"] > 0 else OP["A"]
    d_A_new = OP["d_A"] + (U["w_A"] / n_A) * (U["e_A"] - OP["A"] - OP["d_A"]) if U["w_A"] > 0 else OP["d_A"]
    c_A_new = (n_A / beta) * (1 - (abs(d_A_new / 2))) if U["w_A"] > 0 else OP["c_A"]

    S_new = OP["S"] + (U["w_S"] / n_S) * (U["e_S"] - OP["S"]) if U["w_S"] > 0 else OP["S"]
    d_S_new = OP["d_S"] + (U["w_S"] / n_S) * (U["e_S"] - OP["S"] - OP["d_S"]) if U["w_S"] > 0 else OP["d_S"]
    c_S_new = (n_S / beta) * (1 - (abs(d_S_new / 2))) if U["w_S"] > 0 else OP["c_S"]

    T_new = OP["T"] + (U["w_T"] / n_T) * (U["e_T"] - OP["T"]) if U["w_T"] > 0 else OP["T"]
    d_T_new = OP["d_T"] + (U["w_T"] / n_T) * (U["e_T"] - OP["T"] - OP["d_T"]) if U["w_T"] > 0 else OP["d_T"]
    c_T_new = (n_T / beta) * (1 - (abs(d_T_new / 2))) if U["w_T"] > 0 else OP["c_T"]

    return {
        "A": A_new,
        "S": S_new,
        "T": T_new,

        "d_A": d_A_new,
        "d_S": d_S_new,
        "d_T": d_T_new,

        "c_A": c_A_new,
        "c_S": c_S_new,
        "c_T": c_T_new,
    }