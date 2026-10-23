"""
cargador_datos.py
Módulo encargado de gestionar las rutas relativas y leer los parámetros desde 'Instancias Excel/'.
"""
from pathlib import Path
import pandas as pd
import numpy as np

# Rutas relativas basadas en la ubicación de este script
DIR_SCRIPT = Path(__file__).resolve().parent
DIR_INSTANCIAS = DIR_SCRIPT.parent / "Instancias Excel"
DIR_ANALISIS = DIR_SCRIPT.parent / "Análisis de Excels"

# Clasificación oficial de parámetros según parametros.csv
PARAMETROS_ESCALARES = [
    "T", "P", "M", "S", "eV", "eC", "eF", "cn_min", "cn_max",
    "h_min", "h_max", "q_min", "q_max", "a_c", "o_max", "alpha",
    "v_max", "cE_base", "cv_base", "FE_diesel", "L_volteo", "L_conf",
    "FE_camion", "ef_CH4", "ef_N2O", "GWP_CH4", "GWP_N2O", "D_total",
    "kW_volt", "cons_esp", "f_carga", "L_pila", "cap_volt", "ef_volt",
    "A_pila", "V_pila", "t_volteo", "h_volt_sem"
]

PARAMETROS_MATERIAL = [
    "d_anual_m", "gamma_m", "dist_m", "eT_m", "eA_m",
    "h_m", "s_m", "c_m", "n_m", "β_min", "β_max", "rho_m"
]

PARAMETROS_ETAPA = ["f_s", "v_min_s", "dur_s"]

PARAMETROS_SEMANAL = ["w_t", "factor_cE_t", "cE_t", "factor_cv_t", "cv_t", "l_t"]


def asegurar_directorios():
    """Verifica que exista la carpeta de salida 'Análisis de Excels/'."""
    DIR_ANALISIS.mkdir(parents=True, exist_ok=True)


def _buscar_archivo_parametro(nombre_param):
    """
    Busca <nombre_param>.xlsx en 'Instancias Excel/'.
    Maneja variantes de nombre como beta_min / β_min o delta_taust / delta_(tau)st.
    """
    variantes = [
        f"{nombre_param}.xlsx",
        f"{nombre_param.replace('β', 'beta')}.xlsx",
        f"{nombre_param.replace('(tau)', 'tau')}.xlsx",
    ]
    for var in variantes:
        ruta = DIR_INSTANCIAS / var
        if ruta.exists():
            return ruta
    return DIR_INSTANCIAS / f"{nombre_param}.xlsx"


def _extraer_numeros_df(df):
    """Extrae todos los valores numéricos válidos de un DataFrame en orden fila-columna."""
    df_num = df.apply(pd.to_numeric, errors="coerce")
    valores = df_num.to_numpy().flatten()
    return valores[~np.isnan(valores)]


def leer_escalar(nombre_param):
    """Lee un parámetro escalar (1 dato) desde su archivo .xlsx."""
    ruta = _buscar_archivo_parametro(nombre_param)
    df = pd.read_excel(ruta, header=None)
    valores = _extraer_numeros_df(df)
    if len(valores) == 0:
        raise ValueError(f"No se encontraron valores numéricos en {ruta}")
    # El último valor numérico suele ser el dato cuando hay índices o cabeceras numéricas
    return float(valores[-1]) if len(valores) == 1 else float(valores[0])


def leer_vector(nombre_param, llaves):
    """
    Lee un parámetro 1D (material=4, etapa=4, semanal=52) y lo retorna
    como diccionario indexado por las llaves del conjunto respectivo (1..K).
    """
    ruta = _buscar_archivo_parametro(nombre_param)
    df = pd.read_excel(ruta)
    k = len(llaves)

    # Si tiene 2 o más columnas, tomamos la última columna numérica (asumiendo que la 1ra es el índice/nombre)
    cols_num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if len(df) == k and len(cols_num) >= 1:
        serie = df[cols_num[-1]].to_numpy(dtype=float)
    else:
        # Si no tiene cabecera o viene en formato fila/celdas
        df_raw = pd.read_excel(ruta, header=None)
        nums = _extraer_numeros_df(df_raw)
        # Si vienen pares (indice, valor), tomamos los últimos k o los impares
        if len(nums) == 2 * k:
            serie = nums[1::2]
        else:
            serie = nums[-k:]

    return {llave: float(val) for llave, val in zip(llaves, serie)}


def leer_d_mt(M_set, T_set):
    """
    Obtiene el parámetro d_mt (208 datos = 4 materiales x 52 semanas).
    Prioridad 1: Lee 'Instancias Excel/d_mt.xlsx' si existe.
    Prioridad 2: Importa DMT directamente desde 'generar_instancia_dmt.py'.
    """
    ruta_dmt = _buscar_archivo_parametro("d_mt")
    d_mt = {}

    if ruta_dmt.exists():
        df = pd.read_excel(ruta_dmt)
        # Removemos columna 't' o índice semanal si está presente
        if "t" in df.columns:
            df = df.drop(columns=["t"])
        elif df.shape[1] == len(M_set) + 1:
            df = df.iloc[:, 1:]

        matriz = df.to_numpy(dtype=float)
        # Soportar orientación (52 x 4) o (4 x 52)
        if matriz.shape == (len(T_set), len(M_set)):
            for idx_t, t in enumerate(T_set):
                for idx_m, m in enumerate(M_set):
                    d_mt[m, t] = float(matriz[idx_t, idx_m])
        elif matriz.shape == (len(M_set), len(T_set)):
            for idx_m, m in enumerate(M_set):
                for idx_t, t in enumerate(T_set):
                    d_mt[m, t] = float(matriz[idx_m, idx_t])
        else:
            raise ValueError(f"Dimensiones inesperadas en d_mt.xlsx: {matriz.shape}")
    else:
        # Ejecuta/importa la generación oficial del equipo desde generar_instancia_dmt.py
        import generar_instancia_dmt as gen_dmt
        df_dmt = gen_dmt.DMT
        cols_mat = [c for c in df_dmt.columns if c != "t"]
        for idx_t, t in enumerate(T_set):
            for idx_m, m in enumerate(M_set):
                col = cols_mat[idx_m]
                d_mt[m, t] = float(df_dmt.iloc[idx_t][col])

    return d_mt


def leer_phi_ms(M_set, S_set):
    """
    Lee phi_ms (16 datos = 4 materiales x 4 etapas) desde 'phi_ms.xlsx'.
    Retorna diccionario phi_ms[m, s].
    """
    ruta = _buscar_archivo_parametro("phi_ms")
    df = pd.read_excel(ruta)
    if df.shape[1] == len(S_set) + 1:
        df = df.iloc[:, 1:]
    matriz = df.to_numpy(dtype=float)

    phi_ms = {}
    for idx_m, m in enumerate(M_set):
        for idx_s, s in enumerate(S_set):
            phi_ms[m, s] = float(matriz[idx_m, idx_s])
    return phi_ms


def leer_delta_taust(T_set, S_set, dur_s=None):
    """
    Construye el parámetro binario delta[tau, s, t] (10.816 datos = 52 x 4 x 52).
    Soporta:
      1. Matriz E (52 x 52) en 'delta_(tau)st.xlsx' donde celda (tau, t) = s en {0, 1, 2, 3, 4},
         aplicando la regla del equipo: delta[tau, s, t] = int(E.loc[tau, t] == s).
      2. Tabla larga de 10.816 filas con columnas (tau, s, t, valor).
      3. Cálculo directo desde dur_s si se requiere validación.
    """
    ruta = _buscar_archivo_parametro("delta_(tau)st")
    delta = {}

    if ruta.exists():
        df = pd.read_excel(ruta)
        # Caso 1: Matriz 52 x 52 (con o sin columna de índice tau)
        if df.shape[0] == len(T_set) and df.shape[1] in (len(T_set), len(T_set) + 1):
            if df.shape[1] == len(T_set) + 1:
                df = df.iloc[:, 1:]
            E = df.to_numpy(dtype=int)
            for idx_tau, tau in enumerate(T_set):
                for idx_t, t in enumerate(T_set):
                    etapa_actual = int(E[idx_tau, idx_t])
                    for s in S_set:
                        delta[tau, s, t] = int(etapa_actual == s)
            return delta

        # Caso 2: Tabla larga de 10.816 filas
        if len(df) == len(T_set) * len(S_set) * len(T_set):
            for row in df.itertuples(index=False):
                tau, s, t, val = int(row[0]), int(row[1]), int(row[2]), int(row[3])
                delta[tau, s, t] = val
            return delta

    # Caso 3 (Respaldo analítico exacto a partir de dur_s)
    if dur_s is None:
        raise FileNotFoundError(f"No se pudo leer {ruta} ni se entregó dur_s.")
    for tau in T_set:
        for t in T_set:
            if t < tau:
                for s in S_set:
                    delta[tau, s, t] = 0
            else:
                edad = t - tau  # semanas transcurridas desde conformación (0 en t == tau)
                acum = 0
                etapa_activa = 0
                for s in S_set:
                    if acum <= edad < acum + int(round(dur_s[s])):
                        etapa_activa = s
                        break
                    acum += int(round(dur_s[s]))
                for s in S_set:
                    delta[tau, s, t] = int(etapa_activa == s)
    return delta


def cargar_todos_los_parametros():
    """
    Lee todos los archivos .xlsx desde 'Instancias Excel/' y retorna un diccionario
    con los conjuntos (M, P, T, S) y todos los parámetros listos para Gurobi.
    """
    datos = {"escalares": {}, "material": {}, "etapa": {}, "semanal": {}, "especial": {}}

    # 1. Leer escalares (incluyendo tamaños de conjuntos T, P, M, S)
    for nombre in PARAMETROS_ESCALARES:
        ruta = _buscar_archivo_parametro(nombre)
        if ruta.exists():
            datos["escalares"][nombre] = leer_escalar(nombre)

    # Dimensiones de los conjuntos (por defecto M=4, P=posiciones, T=52, S=4 si no están aún)
    n_M = int(round(datos["escalares"].get("M", 4)))
    n_P = int(round(datos["escalares"].get("P", 20)))
    n_T = int(round(datos["escalares"].get("T", 52)))
    n_S = int(round(datos["escalares"].get("S", 4)))

    M_set = list(range(1, n_M + 1))
    P_set = list(range(1, n_P + 1))
    T_set = list(range(1, n_T + 1))
    S_set = list(range(1, n_S + 1))

    datos["conjuntos"] = {"M": M_set, "P": P_set, "T": T_set, "S": S_set}

    # 2. Leer parámetros por material (4 datos c/u)
    for nombre in PARAMETROS_MATERIAL:
        datos["material"][nombre] = leer_vector(nombre, M_set)

    # Si s_m no viene explícito o requiere verificación: s_m = 1 - h_m
    if "s_m" not in datos["material"] and "h_m" in datos["material"]:
        datos["material"]["s_m"] = {m: 1.0 - datos["material"]["h_m"][m] for m in M_set}

    # 3. Leer parámetros por etapa (4 datos c/u)
    for nombre in PARAMETROS_ETAPA:
        datos["etapa"][nombre] = leer_vector(nombre, S_set)

    # 4. Leer parámetros semanales (52 datos c/u)
    for nombre in PARAMETROS_SEMANAL:
        datos["semanal"][nombre] = leer_vector(nombre, T_set)

    # 5. Leer parámetros especiales: d_mt (208), phi_ms (16), delta_(tau)st (10.816)
    datos["especial"]["d_mt"] = leer_d_mt(M_set, T_set)
    datos["especial"]["phi_ms"] = leer_phi_ms(M_set, S_set)
    datos["especial"]["delta_taust"] = leer_delta_taust(
        T_set, S_set, dur_s=datos["etapa"].get("dur_s")
    )

    return datos
