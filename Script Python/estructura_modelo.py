"""
estructura_modelo.py
Módulo encargado de instanciar los conjuntos, parámetros del modelo y las variables de decisión en Gurobi.
"""
from gurobipy import GRB


class DatosModelo:
    """Contenedor estructurado de conjuntos y parámetros para fácil acceso en el modelo."""

    def __init__(self, datos_crudos):
        # Conjuntos
        self.M = datos_crudos["conjuntos"]["M"]  # {1, 2, 3, 4} Materias primas
        self.P = datos_crudos["conjuntos"]["P"]  # {1, ..., P} Posiciones en cancha
        self.T = datos_crudos["conjuntos"]["T"]  # {1, ..., 52} Semanas
        self.S = datos_crudos["conjuntos"]["S"]  # {1, 2, 3, 4} Etapas biológicas

        # Nombres descriptivos para reportes y gráficos
        self.nombres_M = {
            1: "Lodos de purines",
            2: "Guano de pollo",
            3: "Aserrín",
            4: "Viruta"
        }
        self.nombres_S = {
            1: "Latencia",
            2: "Fermentación",
            3: "Enfriamiento",
            4: "Maduración"
        }

        # Escalares principales del modelo matemático
        esc = datos_crudos["escalares"]
        self.eV = esc["eV"]
        self.eC = esc["eC"]
        self.eF = esc["eF"]
        self.cn_min = esc["cn_min"]
        self.cn_max = esc["cn_max"]
        self.h_min = esc["h_min"]
        self.h_max = esc["h_max"]
        self.q_min = esc["q_min"]
        self.q_max = esc["q_max"]
        self.a_c = esc["a_c"]
        self.o_max = esc["o_max"]
        self.alpha = esc.get("alpha", len(self.T) / 52.0)
        self.v_max = esc["v_max"]

        # Parámetros indexados por Material (m in M)
        mat = datos_crudos["material"]
        self.gamma_m = mat["gamma_m"]
        self.eT_m = mat["eT_m"]
        self.eA_m = mat["eA_m"]
        self.h_m = mat["h_m"]
        self.s_m = mat["s_m"]
        self.c_m = mat["c_m"]
        self.n_m = mat["n_m"]
        self.beta_min = mat["beta_min"]
        self.beta_max = mat["beta_max"]
        self.rho_m = mat["rho_m"]

        # Parámetros indexados por Etapa (s in S)
        eta = datos_crudos["etapa"]
        self.v_min_s = eta["v_min_s"]
        self.dur_s = eta["dur_s"]

        # Parámetros indexados por Semana (t in T)
        sem = datos_crudos["semanal"]
        self.cE_t = sem["cE_t"]
        self.cv_t = sem["cv_t"]
        self.l_t = sem["l_t"]

        # Parámetros Especiales Multidimensionales
        esp = datos_crudos["especial"]
        self.d_mt = esp["d_mt"]              # d_mt[m, t]
        self.phi_ms = esp["phi_ms"]          # phi_ms[m, s]
        self.delta = esp["delta_taust"]      # delta[tau, s, t]


def crear_variables(model, data: DatosModelo):
    """
    Instancia las variables de decisión y auxiliares en el objeto Model de Gurobi,
    siguiendo la plantilla oficial del curso.
    """
    M, P, T = data.M, data.P, data.T

    # x_mpt >= 0 (Continua): Toneladas de materia prima m en posición p en semana t
    x = model.addVars(M, P, T, vtype=GRB.CONTINUOUS, lb=0.0, name="x")

    # r_mt >= 0 (Continua): Toneladas de material m no incorporadas al compostaje en semana t
    r = model.addVars(M, T, vtype=GRB.CONTINUOUS, lb=0.0, name="r")

    # y_pt in {0, 1} (Binaria): 1 si se forma una nueva pila en posición p en semana t
    y = model.addVars(P, T, vtype=GRB.BINARY, name="y")

    # v_pt in Z+ (Entera no negativa): Número de volteos mecánicos a la pila en p durante t
    v = model.addVars(P, T, vtype=GRB.INTEGER, lb=0.0, name="v")

    # a_pt in {0, 1} (Binaria auxiliar): 1 si la posición p está ocupada por una pila activa en t
    a = model.addVars(P, T, vtype=GRB.BINARY, name="a")

    model.update()

    return {"x": x, "r": r, "y": y, "v": v, "a": a}
