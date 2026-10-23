"""
resultados_graficos.py
Módulo encargado de procesar la solución óptima de Gurobi, exportar las planillas
de resultados y generar los gráficos en la carpeta 'Análisis de Excels/'.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from cargador_datos import DIR_ANALISIS, asegurar_directorios
from estructura_modelo import DatosModelo


def extraer_y_exportar_resultados(model, data: DatosModelo, vars_dict):
    """
    Extrae los valores óptimos de las variables, imprime el resumen por consola y
    exporta las planillas completas a 'Análisis de Excels/'.
    """
    asegurar_directorios()
    M, P, T, S = data.M, data.P, data.T, data.S
    x, r, y, v, a = vars_dict["x"], vars_dict["r"], vars_dict["y"], vars_dict["v"], vars_dict["a"]

    # 1. Desglose de la Función Objetivo (Emisiones en ton CO2eq)
    em_transporte = sum(data.eT_m[m] * x[m, p, t].X for m in M for p in P for t in T)
    em_biologica = sum(data.eC * x[m, p, t].X for m in M for p in P for t in T)
    em_conformacion = sum(data.eF * y[p, t].X for p in P for t in T)
    em_volteo = sum(data.eV * v[p, t].X for p in P for t in T)
    em_alternativa = sum(data.eA_m[m] * r[m, t].X for m in M for t in T)

    df_resumen_kpi = pd.DataFrame([
        {"Indicador": "Valor Objetivo Total (ton CO2eq)", "Valor": model.ObjVal},
        {"Indicador": "Emisiones Transporte a Planta (ton CO2eq)", "Valor": em_transporte},
        {"Indicador": "Emisiones Biológicas Compostaje (ton CO2eq)", "Valor": em_biologica},
        {"Indicador": "Emisiones Conformación de Pilas (ton CO2eq)", "Valor": em_conformacion},
        {"Indicador": "Emisiones Volteo Mecánico (ton CO2eq)", "Valor": em_volteo},
        {"Indicador": "Emisiones Gestión Alternativa / Rechazo (ton CO2eq)", "Valor": em_alternativa},
        {"Indicador": "Total Biomasa Compostada (ton)", "Valor": sum(x[m, p, t].X for m in M for p in P for t in T)},
        {"Indicador": "Total Biomasa No Compostada (ton)", "Valor": sum(r[m, t].X for m in M for t in T)},
        {"Indicador": "Total Pilas Conformadas en el Año (pilas)", "Valor": sum(y[p, t].X for p in P for t in T)},
        {"Indicador": "Total Volteos Realizados en el Año (volteos)", "Valor": sum(v[p, t].X for p in P for t in T)},
        {"Indicador": "Tiempo de Ejecución Gurobi (s)", "Valor": model.Runtime},
        {"Indicador": "Gap de Optimalidad (%)", "Valor": model.MIPGap * 100.0 if hasattr(model, "MIPGap") else 0.0},
    ])

    # 2. Tabla de Variables x_mpt (solo valores > 1e-4 para claridad, más matriz agregada m x t)
    filas_x = []
    for m in M:
        for p in P:
            for t in T:
                val = x[m, p, t].X
                if val > 1e-4:
                    filas_x.append({
                        "m": m,
                        "Material": data.nombres_M.get(m, f"M{m}"),
                        "p": p,
                        "t": t,
                        "Toneladas_x_mpt": round(val, 4)
                    })
    df_x_detalle = pd.DataFrame(filas_x)

    # 3. Tabla semanal de compostaje vs rechazo por material
    filas_balance_mat = []
    for t in T:
        for m in M:
            comp_mt = sum(x[m, p, t].X for p in P)
            rech_mt = r[m, t].X
            disp_mt = data.d_mt[m, t]
            filas_balance_mat.append({
                "t": t,
                "m": m,
                "Material": data.nombres_M.get(m, f"M{m}"),
                "Disponible_d_mt": round(disp_mt, 3),
                "Compostado_sum_x": round(comp_mt, 3),
                "No_Compostado_r_mt": round(rech_mt, 3),
                "Fraccion_Valorizada": round(comp_mt / disp_mt, 4) if disp_mt > 0 else 0.0
            })
    df_balance_semanal = pd.DataFrame(filas_balance_mat)

    # 4. Resumen anual por material (Cumplimiento de compromiso gamma_m)
    filas_anual_mat = []
    for m in M:
        disp_anual = sum(data.d_mt[m, t] for t in T)
        comp_anual = sum(x[m, p, t].X for p in P for t in T)
        rech_anual = sum(r[m, t].X for t in T)
        filas_anual_mat.append({
            "m": m,
            "Material": data.nombres_M.get(m, f"M{m}"),
            "Disponibilidad_Anual_ton": round(disp_anual, 2),
            "Compostado_Anual_ton": round(comp_anual, 2),
            "Rechazado_Anual_ton": round(rech_anual, 2),
            "Porcentaje_Compostado_%": round(100.0 * comp_anual / disp_anual, 2) if disp_anual > 0 else 0.0,
            "Compromiso_Minimo_gamma_%": round(100.0 * data.gamma_m[m], 2)
        })
    df_resumen_material = pd.DataFrame(filas_anual_mat)

    # 5. Estado semanal de la cancha (Ocupación, Conformación, Volteos y Volumen)
    filas_operacion_sem = []
    for t in T:
        vol_usado_t = sum(
            data.phi_ms[m, s] * data.delta[tau, s, t] * x[m, p, tau].X
            for p in P for m in M for tau in T if tau <= t for s in S
        )
        pilas_nuevas_t = sum(round(y[p, t].X) for p in P)
        pilas_activas_t = sum(round(a[p, t].X) for p in P)
        volteos_t = sum(round(v[p, t].X) for p in P)

        filas_operacion_sem.append({
            "t": t,
            "Pilas_Iniciadas_y": pilas_nuevas_t,
            "Posiciones_Ocupadas_a": pilas_activas_t,
            "Capacidad_Posiciones_P": len(P),
            "Volumen_Cancha_m3": round(vol_usado_t, 2),
            "Capacidad_Volumetrica_cE_m3": round(data.cE_t[t], 2),
            "Uso_Volumetrico_%": round(100.0 * vol_usado_t / data.cE_t[t], 2) if data.cE_t[t] > 0 else 0.0,
            "Volteos_Realizados_v": volteos_t,
            "Capacidad_Volteadora_cv": round(data.cv_t[t], 2)
        })
    df_operacion_semanal = pd.DataFrame(filas_operacion_sem)

    # 6. Matrices completas P x T para y_pt, a_pt y v_pt
    df_y_pt = pd.DataFrame(
        [[round(y[p, t].X) for t in T] for p in P],
        index=[f"P{p}" for p in P], columns=[f"T{t}" for t in T]
    )
    df_a_pt = pd.DataFrame(
        [[round(a[p, t].X) for t in T] for p in P],
        index=[f"P{p}" for p in P], columns=[f"T{t}" for t in T]
    )
    df_v_pt = pd.DataFrame(
        [[round(v[p, t].X) for t in T] for p in P],
        index=[f"P{p}" for p in P], columns=[f"T{t}" for t in T]
    )

    # Exportar todo a Excel en 'Análisis de Excels/'
    ruta_excel_resultados = DIR_ANALISIS / "Resultados_Optimizacion_Maitenlahue.xlsx"
    with pd.ExcelWriter(ruta_excel_resultados, engine="openpyxl") as writer:
        df_resumen_kpi.to_excel(writer, sheet_name="Resumen_KPIs", index=False)
        df_resumen_material.to_excel(writer, sheet_name="Resumen_Materiales", index=False)
        df_operacion_semanal.to_excel(writer, sheet_name="Operacion_Semanal", index=False)
        df_balance_semanal.to_excel(writer, sheet_name="Balance_Material_Semanal", index=False)
        df_x_detalle.to_excel(writer, sheet_name="Variables_x_mpt", index=False)
        df_y_pt.to_excel(writer, sheet_name="Matriz_Conformacion_y_pt")
        df_a_pt.to_excel(writer, sheet_name="Matriz_Ocupacion_a_pt")
        df_v_pt.to_excel(writer, sheet_name="Matriz_Volteos_v_pt")

    print("\n" + "=" * 65)
    print("RESUMEN EJECUTIVO DE LA SOLUCIÓN ÓPTIMA - PLANTA MAITENLAHUE")
    print("=" * 65)
    print(df_resumen_kpi.to_string(index=False))
    print("-" * 65)
    print(df_resumen_material.to_string(index=False))
    print("=" * 65)
    print(f"Planilla exportada exitosamente en: {ruta_excel_resultados}")

    return {
        "kpi": df_resumen_kpi,
        "anual_mat": df_resumen_material,
        "operacion_sem": df_operacion_semanal,
        "balance_sem": df_balance_semanal,
        "a_pt": df_a_pt,
        "v_pt": df_v_pt
    }


def generar_graficos_informe(tablas_res):
    """
    Genera y guarda en 'Análisis de Excels/' las figuras de análisis para el informe.
    """
    asegurar_directorios()
    sns.set_theme(style="whitegrid")

    df_op = tablas_res["operacion_sem"]
    df_mat = tablas_res["anual_mat"]
    df_a = tablas_res["a_pt"]

    # Gráfico 1: Ocupación Volumétrica de Cancha y Volteos Semanales
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(df_op["t"], df_op["Volumen_Cancha_m3"], label="Volumen Ocupado ($m^3$)", color="#1f77b4", lw=2)
    axes[0].plot(df_op["t"], df_op["Capacidad_Volumetrica_cE_m3"], label="Capacidad Máxima $c_t^E$ ($m^3$)", color="#d62728", ls="--")
    axes[0].set_ylabel("Volumen en Cancha ($m^3$)")
    axes[0].set_title("Evolución Semanal de Ocupación Volumétrica y Uso de Volteadora")
    axes[0].legend(loc="upper right")

    axes[1].bar(df_op["t"], df_op["Volteos_Realizados_v"], label="Volteos Realizados ($v_{pt}$)", color="#2ca02c", alpha=0.8)
    axes[1].plot(df_op["t"], df_op["Capacidad_Volteadora_cv"], label="Capacidad Volteadora $c_t^v$", color="#d62728", ls="--")
    axes[1].set_xlabel("Semana de Planificación ($t$)")
    axes[1].set_ylabel("N° de Volteos Semanales")
    axes[1].legend(loc="upper right")

    plt.tight_layout()
    fig.savefig(DIR_ANALISIS / "Grafico_1_Operacion_Cancha_y_Volteos.png", dpi=300)
    plt.close(fig)

    # Gráfico 2: Material Compostado vs Rechazado Anual por Tipo de Residuo
    fig, ax = plt.subplots(figsize=(9, 5))
    x_pos = np.arange(len(df_mat))
    ancho = 0.38

    ax.bar(x_pos - ancho / 2, df_mat["Compostado_Anual_ton"], ancho, label="Incorporado a Compostaje", color="#2b8cbe")
    ax.bar(x_pos + ancho / 2, df_mat["Rechazado_Anual_ton"], ancho, label="Gestión Alternativa ($r_{mt}$)", color="#e34a33")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(df_mat["Material"])
    ax.set_ylabel("Masa Anual (toneladas)")
    ax.set_title("Balance Anual de Materias Primas: Compostaje vs. Gestión Alternativa")
    ax.legend()

    plt.tight_layout()
    fig.savefig(DIR_ANALISIS / "Grafico_2_Balance_Anual_Materiales.png", dpi=300)
    plt.close(fig)

    # Gráfico 3: Mapa de Calor de Ocupación de Sectores en Cancha (a_pt)
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(df_a, cmap="YlGnBu", cbar_kws={"label": "Estado de Ocupación ($a_{pt}$)"}, linewidths=0.3, ax=ax)
    ax.set_title("Cronograma de Ocupación de Sectores en Cancha de Compostaje ($a_{pt}$)")
    ax.set_xlabel("Semana ($t$)")
    ax.set_ylabel("Sector de Cancha ($p$)")

    plt.tight_layout()
    fig.savefig(DIR_ANALISIS / "Grafico_3_Heatmap_Ocupacion_Cancha.png", dpi=300)
    plt.close(fig)

    print(f"Gráficos exportados exitosamente en: {DIR_ANALISIS}")
