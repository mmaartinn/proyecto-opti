import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from gurobipy import GRB, Model, quicksum

# =============================================================================
# 1. CONFIGURACIÓN DE RUTAS RELATIVAS Y DIRECTORIOS
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Detecta si main.py está dentro de "Script Python/" o en la raíz del proyecto
if os.path.basename(BASE_DIR) == "Script Python":
    ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
else:
    ROOT_DIR = BASE_DIR

DIR_INSTANCIAS = os.path.join(ROOT_DIR, "Instancias Excel")
DIR_ANALISIS = os.path.join(ROOT_DIR, "Análisis de Excels")

# Crear la carpeta de salida automáticamente si no existe
os.makedirs(DIR_ANALISIS, exist_ok=True)

# =============================================================================
# 2. LECTURA DE INSTANCIAS EXCEL (PARÁMETROS DE ENTRADA)
# =============================================================================
print("Leyendo archivos de entrada desde 'Instancias Excel/'...")

ruta_mp = os.path.join(DIR_INSTANCIAS, "MateriasPrimas.xlsx")
ruta_disp = os.path.join(DIR_INSTANCIAS, "Disponibilidad.xlsx")
ruta_glob = os.path.join(DIR_INSTANCIAS, "ParametrosGlobales.xlsx")

df_mp = pd.read_excel(ruta_mp)
df_disp = pd.read_excel(ruta_disp)
df_glob = pd.read_excel(ruta_glob)

# Limpieza de nombres de columnas por posibles espacios en blanco
df_mp.columns = df_mp.columns.str.strip()
df_disp.columns = df_disp.columns.str.strip()
df_glob.columns = df_glob.columns.str.strip()

# =============================================================================
# 3. DEFINICIÓN DE CONJUNTOS Y ESTRUCTURA DE PARÁMETROS
# =============================================================================
# Conjunto M: Materias primas
col_mat_mp = df_mp.columns[0]
df_mp[col_mat_mp] = df_mp[col_mat_mp].astype(str).str.strip()
M = df_mp[col_mat_mp].tolist()
df_mp.set_index(col_mat_mp, inplace=True)

# Conjunto T: Períodos de planificación (Semanas 1 a 52)
col_mat_disp = df_disp.columns[0]
df_disp[col_mat_disp] = df_disp[col_mat_disp].astype(str).str.strip()
df_disp.set_index(col_mat_disp, inplace=True)

cols_tiempo = list(df_disp.columns)
T = list(range(1, len(cols_tiempo) + 1))

# Diccionario de disponibilidad d_{m,t}
d = {}
for m in M:
    for idx, t in enumerate(T):
        d[(m, t)] = float(df_disp.loc[m, cols_tiempo[idx]])

# Función auxiliar para mapear columnas de MateriasPrimas sin importar formato LaTeX
def extraer_parametro_mp(df, posibles_nombres):
    for col in df.columns:
        col_clean = col.replace("$", "").replace("_", "").replace("^", "").replace("{", "").replace("}", "").replace("\\", "").lower()
        for nombre in posibles_nombres:
            if nombre.lower() in col_clean:
                return df[col].to_dict()
    raise KeyError(f"No se encontró ninguna columna asociada a {posibles_nombres} en MateriasPrimas.xlsx")

h = extraer_parametro_mp(df_mp, ["hm", "h_m", "humedad"])
c = extraer_parametro_mp(df_mp, ["cm", "c_m", "carbono"])
n = extraer_parametro_mp(df_mp, ["nm", "n_m", "nitrogeno"])
beta_min = extraer_parametro_mp(df_mp, ["betamin", "beta_m^min", "min"])
beta_max = extraer_parametro_mp(df_mp, ["betamax", "beta_m^max", "max"])
rho = extraer_parametro_mp(df_mp, ["rhom", "rho", "densidad", "ρ"])
gamma = extraer_parametro_mp(df_mp, ["gamma", "gamma_m", "γ"])
e_T = extraer_parametro_mp(df_mp, ["et", "e^t_m", "transporte"])
e_A = extraer_parametro_mp(df_mp, ["ea", "e^a_m", "alternativa"])

# Fracción de materia seca s_m = 1 - h_m
s_sec = {m: 1.0 - h[m] for m in M}

# Extracción de Parámetros Globales
col_param = df_glob.columns[0]
col_valor = df_glob.columns[1]
dict_glob_raw = dict(zip(df_glob[col_param].astype(str).str.strip(), df_glob[col_valor]))

def obtener_global(posibles_llaves, valor_por_defecto=None):
    for k, val in dict_glob_raw.items():
        k_clean = k.replace("$", "").replace("_", "").replace("^", "").replace("{", "").replace("}", "").replace("\\", "").lower()
        for llave in posibles_llaves:
            if llave.lower() == k_clean or llave.lower() in k_clean:
                return float(val)
    if valor_por_defecto is not None:
        return float(valor_por_defecto)
    raise KeyError(f"Parámetro global {posibles_llaves} no encontrado en ParametrosGlobales.xlsx")

e_V = obtener_global(["ev", "e^v"])
e_C = obtener_global(["ec", "e^c"])
e_F = obtener_global(["ef", "e^f"])
cn_min = obtener_global(["cnmin", "c_n^min"])
cn_max = obtener_global(["cnmax", "c_n^max"])
h_min = obtener_global(["hmin", "h^min"])
h_max = obtener_global(["hmax", "h^max"])
q_min = obtener_global(["qmin", "q^min"])
q_max = obtener_global(["qmax", "q^max"])
a_c = obtener_global(["ac", "a^c"])
o_max = obtener_global(["omax", "o^max"])
v_max = obtener_global(["vmax", "v^max"])

# Escala temporal alpha = |T| / 52
alpha = len(T) / 52.0

# Conjunto P (Sectores de cancha) y Conjunto S (Etapas biológicas: 1:Latencia, 2:Fermentación, 3:Enfriamiento, 4:Maduración)
num_posiciones = int(obtener_global(["p_max", "posiciones", "sectores"], valor_por_defecto=25))
P = list(range(1, num_posiciones + 1))
S = [1, 2, 3, 4]

# Capacidades operativas semanales (c^E_t y c^v_t)
cap_espacial_base = obtener_global(["ce", "c^e", "cap_espacial"], valor_por_defecto=15000.0)
cap_volteos_base = obtener_global(["cv", "c^v", "cap_volteos"], valor_por_defecto=80.0)
c_E = {t: cap_espacial_base for t in T}
c_v = {t: cap_volteos_base for t in T}

# Volteos mínimos exigidos por etapa biológica (v_s^min)
v_min = {
    1: obtener_global(["vmin1", "v_1^min"], valor_por_defecto=2.0),
    2: obtener_global(["vmin2", "v_2^min"], valor_por_defecto=3.0),
    3: obtener_global(["vmin3", "v_3^min"], valor_por_defecto=1.0),
    4: obtener_global(["vmin4", "v_4^min"], valor_por_defecto=1.0)
}

# Duración en semanas de cada etapa biológica para precomputar delta_{tau,t}^s y l_t
duracion_etapas = {
    1: int(obtener_global(["dur1", "dur_latencia"], valor_por_defecto=1)),
    2: int(obtener_global(["dur2", "dur_fermentacion"], valor_por_defecto=3)),
    3: int(obtener_global(["dur3", "dur_enfriamiento"], valor_por_defecto=2)),
    4: int(obtener_global(["dur4", "dur_maduracion"], valor_por_defecto=2))
}
duracion_total_ciclo = sum(duracion_etapas.values())

# Coeficiente de ocupación volumétrica phi_{m,s} [m^3 / ton] considerando contracción por etapa
factor_contraccion = {1: 1.00, 2: 0.85, 3: 0.75, 4: 0.65}
phi = {(m, s): (1.0 / rho[m]) * factor_contraccion[s] for m in M for s in S}

# Precomputación de parámetros binarios delta_{tau, t}^s y l_t
delta = {}
for tau in T:
    for t in T:
        for s in S:
            delta[(tau, t, s)] = 0
        if t >= tau:
            edad_pila = t - tau # Semanas transcurridas desde su conformación
            acum = 0
            for s in S:
                if acum <= edad_pila < acum + duracion_etapas[s]:
                    delta[(tau, t, s)] = 1
                acum += duracion_etapas[s]

# l_t vale 1 si una pila iniciada en t alcanza a completar su ciclo dentro del horizonte |T|
l = {t: (1 if (t + duracion_total_ciclo - 1) <= len(T) else 0) for t in T}


# =============================================================================
# 4. GENERACIÓN DEL MODELO EN GUROBI
# =============================================================================
print("Construyendo el modelo matemático en Gurobi...")
model = Model("Planta_Compostaje_Maitenlahue")

# Tiempo límite obligatorio de 30 minutos (1800 segundos)
model.setParam("TimeLimit", 1800)

# ---------------- Se instancian variables de decisión -----------------
x = model.addVars(M, P, T, vtype=GRB.CONTINUOUS, lb=0.0, name="x")
r = model.addVars(M, T, vtype=GRB.CONTINUOUS, lb=0.0, name="r")
y = model.addVars(P, T, vtype=GRB.BINARY, name="y")
v = model.addVars(P, T, vtype=GRB.INTEGER, lb=0.0, name="v")
a = model.addVars(P, T, vtype=GRB.BINARY, name="a")

# ------------------ Agregar las variables al modelo -------------------
model.update()

# ----------------------- Agregar Restricciones ------------------------

# 1. Disponibilidad y Compromiso
# Balance de masa semanal (incorporación al compostaje vs alternativa de gestión autorizada)
model.addConstrs(
    (quicksum(x[m, p, t] for p in P) + r[m, t] == d[m, t] for m in M for t in T),
    name="R1a_BalanceDisponibilidad"
)

# Compromiso anual mínimo de valorización
model.addConstrs(
    (quicksum(x[m, p, t] for p in P for t in T) >= gamma[m] * quicksum(d[m, t] for t in T) for m in M),
    name="R1b_CompromisoValorizacion"
)

# 2. Conformación y Tamaño Operable de Pilas
model.addConstrs(
    (quicksum(x[m, p, t] for m in M) >= q_min * y[p, t] for p in P for t in T),
    name="R2a_MasaMinimaPila"
)
model.addConstrs(
    (quicksum(x[m, p, t] for m in M) <= q_max * y[p, t] for p in P for t in T),
    name="R2b_MasaMaximaPila"
)

# Ocupación simultánea máxima de cada posición y activación de la variable auxiliar a_{p,t}
model.addConstrs(
    (a[p, t] == quicksum(delta[tau, t, s] * y[p, tau] for tau in T if tau <= t for s in S) for p in P for t in T),
    name="R2c_ActivacionOcupacion"
)
model.addConstrs(
    (quicksum(delta[tau, t, s] * y[p, tau] for tau in T if tau <= t for s in S) <= 1 for p in P for t in T),
    name="R2d_LimiteSimultaneoCancha"
)

# 3. Proporciones y Compatibilidad Agronómica de Mezcla
# Proporciones estructurales mínimas y máximas por materia prima
model.addConstrs(
    (x[m, p, t] >= beta_min[m] * quicksum(x[j, p, t] for j in M) for m in M for p in P for t in T),
    name="R3a_ProporcionMin"
)
model.addConstrs(
    (x[m, p, t] <= beta_max[m] * quicksum(x[j, p, t] for j in M) for m in M for p in P for t in T),
    name="R3b_ProporcionMax"
)

# Rango de humedad inicial sobre base húmeda
model.addConstrs(
    (quicksum(h[m] * x[m, p, t] for m in M) >= h_min * quicksum(x[m, p, t] for m in M) for p in P for t in T),
    name="R3c_HumedadMin"
)
model.addConstrs(
    (quicksum(h[m] * x[m, p, t] for m in M) <= h_max * quicksum(x[m, p, t] for m in M) for p in P for t in T),
    name="R3d_HumedadMax"
)

# Balance de relación Carbono:Nitrógeno (C:N) sobre base seca
model.addConstrs(
    (quicksum(c[m] * s_sec[m] * x[m, p, t] for m in M) >= cn_min * quicksum(n[m] * s_sec[m] * x[m, p, t] for m in M) for p in P for t in T),
    name="R3e_RelacionCN_Min"
)
model.addConstrs(
    (quicksum(c[m] * s_sec[m] * x[m, p, t] for m in M) <= cn_max * quicksum(n[m] * s_sec[m] * x[m, p, t] for m in M) for p in P for t in T),
    name="R3f_RelacionCN_Max"
)

# 4. Capacidades Físicas y Cumplimiento Ambiental
# Límite volumétrico anual de ingreso de materias primas
model.addConstr(
    quicksum(x[m, p, t] / rho[m] for m in M for p in P for t in T) <= alpha * a_c * o_max,
    name="R4a_TasaMaximaIngresoAnual"
)

# Capacidad volumétrica simultánea de cancha por período
model.addConstrs(
    (quicksum(phi[m, s] * delta[tau, t, s] * x[m, p, tau] for p in P for m in M for tau in T if tau <= t for s in S) <= c_E[t] for t in T),
    name="R4b_CapacidadVolumetricaCancha"
)

# 5. Régimen de Volteos y Capacidad de Maquinaria
model.addConstrs(
    (v[p, t] <= v_max * a[p, t] for p in P for t in T),
    name="R5a_VolteoMaximoPilaActiva"
)
model.addConstrs(
    (v[p, t] >= quicksum(v_min[s] * delta[tau, t, s] * y[p, tau] for tau in T if tau <= t for s in S) for p in P for t in T),
    name="R5b_FrecuenciaMinimaVolteos"
)
model.addConstrs(
    (quicksum(v[p, t] for p in P) <= c_v[t] for t in T),
    name="R5c_CapacidadMaquinaVolteadora"
)

# 6. Final del horizonte
model.addConstrs(
    (y[p, t] <= l[t] for p in P for t in T),
    name="R6_CierreHorizonte"
)

# ------------------------- Función Objetivo ---------------------------
emisiones_transporte_y_bio = quicksum((e_T[m] + e_C) * x[m, p, t] for m in M for p in P for t in T)
emisiones_operacion_cancha = quicksum(e_F * y[p, t] + e_V * v[p, t] for p in P for t in T)
emisiones_alternativa = quicksum(e_A[m] * r[m, t] for m in M for t in T)

funcion_objetivo = emisiones_transporte_y_bio + emisiones_operacion_cancha + emisiones_alternativa
model.setObjective(funcion_objetivo, GRB.MINIMIZE)

# Optimizar modelo
print("Iniciando optimización en Gurobi...")
model.optimize()


# =============================================================================
# 5. MANEJO DE SOLUCIONES Y EXPORTACIÓN AUTOMÁTICA A 'Análisis de Excels/'
# =============================================================================
if model.SolCount > 0:
    tiempo_ejecucion = model.Runtime
    valor_objetivo = model.ObjVal

    print("\n" + "=" * 60)
    print(f" OPTIMIZACIÓN FINALIZADA CON ÉXITO")
    print(f" Tiempo de ejecución : {tiempo_ejecucion:.2f} segundos")
    print(f" Valor Objetivo (Z)  : {valor_objetivo:,.2f} ton CO2eq")
    print("=" * 60)

    # 1. Extraer variables óptimas en DataFrames
    registros_x = []
    for m in M:
        for p in P:
            for t in T:
                val = x[m, p, t].X
                if val > 1e-4:
                    registros_x.append({"Material (m)": m, "Posición (p)": p, "Semana (t)": t, "Toneladas Incorporadas (x_mpt)": val})
    df_sol_x = pd.DataFrame(registros_x)

    registros_r = []
    for m in M:
        for t in T:
            val_r = r[m, t].X
            val_x = sum(x[m, p, t].X for p in P)
            registros_r.append({
                "Material (m)": m,
                "Semana (t)": t,
                "Disponible (d_mt)": d[m, t],
                "Compostado (ton)": val_x,
                "No Incorporado / Rechazo (r_mt)": val_r
            })
    df_sol_r = pd.DataFrame(registros_r)

    registros_cancha = []
    for p in P:
        for t in T:
            registros_cancha.append({
                "Posición (p)": p,
                "Semana (t)": t,
                "Inicio Nueva Pila (y_pt)": int(round(y[p, t].X)),
                "Posición Activa (a_pt)": int(round(a[p, t].X)),
                "Volteos Aplicados (v_pt)": int(round(v[p, t].X))
            })
    df_sol_cancha = pd.DataFrame(registros_cancha)

    # Desglose de emisiones para tablas de análisis del informe
    em_trans_val = sum((e_T[m] + e_C) * x[m, p, t].X for m in M for p in P for t in T)
    em_form_val = sum(e_F * y[p, t].X for p in P for t in T)
    em_volt_val = sum(e_V * v[p, t].X for p in P for t in T)
    em_alt_val = sum(e_A[m] * r[m, t].X for m in M for t in T)

    df_resumen = pd.DataFrame([
        {"Fuente de Emisión": "Transporte y Biológicas Directas (e^T + e^C)", "Emisiones [ton CO2eq]": em_trans_val},
        {"Fuente de Emisión": "Conformación de Pilas (e^F)", "Emisiones [ton CO2eq]": em_form_val},
        {"Fuente de Emisión": "Volteos Mecánicos (e^V)", "Emisiones [ton CO2eq]": em_volt_val},
        {"Fuente de Emisión": "Gestión Alternativa / Rechazo (e^A)", "Emisiones [ton CO2eq]": em_alt_val},
        {"Fuente de Emisión": "TOTAL HUELLA DE CARBONO (Z*)", "Emisiones [ton CO2eq]": valor_objetivo}
    ])

    # Exportar resultados a Excel en 'Análisis de Excels/'
    ruta_excel_resultados = os.path.join(DIR_ANALISIS, "Resultados_Optimos_Maitenlahue.xlsx")
    with pd.ExcelWriter(ruta_excel_resultados) as writer:
        df_resumen.to_excel(writer, sheet_name="Resumen_Ejecutivo", index=False)
        df_sol_x.to_excel(writer, sheet_name="Mezclas_Pilas_x", index=False)
        df_sol_r.to_excel(writer, sheet_name="Balance_Materiales_r", index=False)
        df_sol_cancha.to_excel(writer, sheet_name="Operacion_Cancha_y_v_a", index=False)

    print(f"-> Planilla de resultados exportada en: {ruta_excel_resultados}")

    # 2. Generación de Gráficos para el Informe en 'Análisis de Excels/'
    sns.set_theme(style="whitegrid")

    # Gráfico 1: Evolución semanal de ocupación de cancha y volteos
    df_sem = df_sol_cancha.groupby("Semana (t)")[["Posición Activa (a_pt)", "Volteos Aplicados (v_pt)"]].sum().reset_index()
    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.plot(df_sem["Semana (t)"], df_sem["Posición Activa (a_pt)"], color="#2b5c8f", marker="o", label="Pilas Activas en Cancha")
    ax1.set_xlabel("Semana de Planificación (t)")
    ax1.set_ylabel("Número de Posiciones Ocupadas", color="#2b5c8f")
    ax2 = ax1.twinx()
    ax2.bar(df_sem["Semana (t)"], df_sem["Volteos Aplicados (v_pt)"], alpha=0.3, color="#d95f02", label="Volteos Mecánicos")
    ax2.set_ylabel("Volteos Semanales", color="#d95f02")
    plt.title("Ocupación de Cancha y Régimen de Volteos Semanal - Planta Maitenlahue")
    fig.tight_layout()
    plt.savefig(os.path.join(DIR_ANALISIS, "Grafico_Ocupacion_y_Volteos.png"), dpi=300)
    plt.close()

    # Gráfico 2: Proporción de Material Compostado vs Gestión Alternativa
    df_mat_tot = df_sol_r.groupby("Material (m)")[["Compostado (ton)", "No Incorporado / Rechazo (r_mt)"]].sum()
    ax = df_mat_tot.plot(kind="bar", stacked=True, figsize=(9, 5), color=["#2ca02c", "#d62728"])
    plt.title("Destino Anual de Materias Primas (Compostaje vs Gestión Alternativa)")
    plt.xlabel("Materia Prima (m)")
    plt.ylabel("Toneladas Anuales [ton]")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(os.path.join(DIR_ANALISIS, "Grafico_Balance_Materiales.png"), dpi=300)
    plt.close()

    print(f"-> Gráficos generados y guardados en: {DIR_ANALISIS}")

else:
    print("El modelo no encontró una solución factible. Calculando IIS para diagnóstico...")
    model.computeIIS()
    model.write(os.path.join(DIR_ANALISIS, "diagnostico_infactibilidad.ilp"))