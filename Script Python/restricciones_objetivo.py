"""
restricciones_objetivo.py
Módulo que agrega las 14 familias de restricciones y la Función Objetivo al modelo Gurobi.
"""
from gurobipy import GRB, quicksum
from estructura_modelo import DatosModelo


def agregar_restricciones(model, data: DatosModelo, vars_dict):
    """
    Agrega las restricciones (1) a (14) de acuerdo con la formulación matemática del Informe 2.
    """
    M, P, T, S = data.M, data.P, data.T, data.S
    x = vars_dict["x"]
    r = vars_dict["r"]
    y = vars_dict["y"]
    v = vars_dict["v"]
    a = vars_dict["a"]

    # (1) Balance disponibilidad [m, t]
    model.addConstrs(
        (quicksum(x[m, p, t] for p in P) + r[m, t] == data.d_mt[m, t]
         for m in M for t in T),
        name="R01_balance_disp"
    )

    # (2) Compromiso anual [m]
    model.addConstrs(
        (quicksum(x[m, p, t] for t in T for p in P) >= data.gamma_m[m] * quicksum(data.d_mt[m, t] for t in T)
         for m in M),
        name="R02_compromiso_anual"
    )

    # (3) Tamaño de pila (2 lados) [p, t]
    model.addConstrs(
        (quicksum(x[m, p, t] for m in M) >= data.q_min * y[p, t]
         for p in P for t in T),
        name="R03a_tamano_pila_min"
    )
    model.addConstrs(
        (quicksum(x[m, p, t] for m in M) <= data.q_max * y[p, t]
         for p in P for t in T),
        name="R03b_tamano_pila_max"
    )

    # (4) Una pila por posición [p, t]
    model.addConstrs(
        (quicksum(data.delta[tau, s, t] * y[p, tau] for tau in T if tau <= t for s in S) <= 1
         for p in P for t in T),
        name="R04_una_pila_posicion"
    )

    # (5) Activación ocupación [p, t]
    model.addConstrs(
        (a[p, t] == quicksum(data.delta[tau, s, t] * y[p, tau] for tau in T if tau <= t for s in S)
         for p in P for t in T),
        name="R05_activacion_ocupacion"
    )

    # (6) Proporciones beta (2 lados) [m, p, t]
    model.addConstrs(
        (x[m, p, t] >= data.beta_min[m] * quicksum(x[j, p, t] for j in M)
         for m in M for p in P for t in T),
        name="R06a_prop_beta_min"
    )
    model.addConstrs(
        (x[m, p, t] <= data.beta_max[m] * quicksum(x[j, p, t] for j in M)
         for m in M for p in P for t in T),
        name="R06b_prop_beta_max"
    )

    # (7) Humedad (2 lados) [p, t]
    model.addConstrs(
        (quicksum(data.h_m[m] * x[m, p, t] for m in M) >= data.h_min * quicksum(x[m, p, t] for m in M)
         for p in P for t in T),
        name="R07a_humedad_min"
    )
    model.addConstrs(
        (quicksum(data.h_m[m] * x[m, p, t] for m in M) <= data.h_max * quicksum(x[m, p, t] for m in M)
         for p in P for t in T),
        name="R07b_humedad_max"
    )

    # (8) Relación C:N (2 lados) [p, t]
    model.addConstrs(
        (quicksum(data.c_m[m] * data.s_m[m] * x[m, p, t] for m in M)
         >= data.cn_min * quicksum(data.n_m[m] * data.s_m[m] * x[m, p, t] for m in M)
         for p in P for t in T),
        name="R08a_CN_min"
    )
    model.addConstrs(
        (quicksum(data.c_m[m] * data.s_m[m] * x[m, p, t] for m in M)
         <= data.cn_max * quicksum(data.n_m[m] * data.s_m[m] * x[m, p, t] for m in M)
         for p in P for t in T),
        name="R08b_CN_max"
    )

    # (9) Volumen anual de ingreso [—] (Restricción única escalar)
    model.addConstr(
        quicksum(x[m, p, t] / data.rho_m[m] for m in M for p in P for t in T)
        <= data.alpha * data.a_c * data.o_max,
        name="R09_volumen_anual_ingreso"
    )

    # (10) Capacidad volumétrica cancha [t]
    model.addConstrs(
        (quicksum(
            data.phi_ms[m, s] * data.delta[tau, s, t] * x[m, p, tau]
            for p in P for m in M for tau in T if tau <= t for s in S
        ) <= data.cE_t[t]
         for t in T),
        name="R10_cap_volumetrica_cancha"
    )

    # (11) Volteo solo si activa [p, t]
    model.addConstrs(
        (v[p, t] <= data.v_max * a[p, t]
         for p in P for t in T),
        name="R11_volteo_si_activa"
    )

    # (12) Volteos mínimos [p, t]
    model.addConstrs(
        (v[p, t] >= quicksum(
            data.v_min_s[s] * data.delta[tau, s, t] * y[p, tau]
            for tau in T if tau <= t for s in S
        )
         for p in P for t in T),
        name="R12_volteos_minimos"
    )

    # (13) Capacidad volteadora [t]
    model.addConstrs(
        (quicksum(v[p, t] for p in P) <= data.cv_t[t]
         for t in T),
        name="R13_cap_volteadora"
    )

    # (14) Final del horizonte [p, t]
    model.addConstrs(
        (y[p, t] <= data.l_t[t]
         for p in P for t in T),
        name="R14_final_horizonte"
    )


def definir_objetivo(model, data: DatosModelo, vars_dict):
    """
    Define la Función Objetivo: Minimizar las emisiones totales de GEI [ton CO2eq].
    """
    M, P, T = data.M, data.P, data.T
    x = vars_dict["x"]
    r = vars_dict["r"]
    y = vars_dict["y"]
    v = vars_dict["v"]

    emisiones_transporte_y_bio = quicksum(
        (data.eT_m[m] + data.eC) * x[m, p, t]
        for m in M for p in P for t in T
    )
    emisiones_operacion_maquinaria = quicksum(
        data.eF * y[p, t] + data.eV * v[p, t]
        for p in P for t in T
    )
    emisiones_gestion_alternativa = quicksum(
        data.eA_m[m] * r[m, t]
        for m in M for t in T
    )

    funcion_objetivo = (
        emisiones_transporte_y_bio
        + emisiones_operacion_maquinaria
        + emisiones_gestion_alternativa
    )

    model.setObjective(funcion_objetivo, GRB.MINIMIZE)
