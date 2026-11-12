import pandas as pd
import copy
from gurobipy import GRB, Model
from cargador_datos import cargar_todos_los_parametros, DIR_ANALISIS
from estructura_modelo import DatosModelo, crear_variables
from restricciones_objetivo import agregar_restricciones, definir_objetivo

def resolver_instancia(data_modificada, nombre_escenario):
    """Construye y resuelve el modelo para un set de datos específico."""
    model = Model(f"Modelo_{nombre_escenario}")
    model.setParam("OutputFlag", 0) # Silencia la salida en consola de Gurobi para no saturar
    model.setParam("TimeLimit", 10) # Límite de 5 minutos por iteración para agilizar el análisis
    
    vars_dict = crear_variables(model, data_modificada)
    agregar_restricciones(model, data_modificada, vars_dict)
    definir_objetivo(model, data_modificada, vars_dict)
    
    model.optimize()
    
    if model.SolCount > 0:
        # Extraer métricas clave si hay solución factible
        M, P, T = data_modificada.M, data_modificada.P, data_modificada.T
        x, r = vars_dict["x"], vars_dict["r"]
        
        obj_val = model.ObjVal
        ton_compostadas = sum(x[m, p, t].X for m in M for p in P for t in T)
        ton_rechazadas = sum(r[m, t].X for m in M for t in T)
        estado = "Óptimo/Factible"
    else:
        # Manejo de error si la variación hace que el modelo sea infactible
        obj_val = None
        ton_compostadas = None
        ton_rechazadas = None
        estado = "Infactible"
        
    return {
        "Escenario": nombre_escenario,
        "Estado": estado,
        "Función Objetivo (ton CO2eq)": obj_val,
        "Total Compostado (ton)": ton_compostadas,
        "Total Rechazado (ton)": ton_rechazadas,
        "Gap (%)": model.MIPGap * 100 if model.SolCount > 0 else None
    }

def main():
    print("Cargando datos base...")
    datos_crudos = cargar_todos_los_parametros()
    resultados = []
    
    # Lista de variaciones porcentuales sugeridas: -10%, -5%, Base, +5%, +10%
    variaciones = [-0.10, -0.05, 0.0, 0.05, 0.10]
    
    # 1. Sensibilidad: Capacidad Volumétrica de la Cancha (cE_t)
    print("Iniciando análisis: Capacidad de Cancha (cE_t)...")
    for var in variaciones:
        data_sens = DatosModelo(copy.deepcopy(datos_crudos))
        # Aplicar variación al parámetro
        for t in data_sens.T:
            data_sens.cE_t[t] = data_sens.cE_t[t] * (1 + var)
            
        res = resolver_instancia(data_sens, f"Capacidad Cancha {var*100:+.0f}%")
        res["Parámetro Alterado"] = "Capacidad Cancha"
        res["Variación"] = f"{var*100:+.0f}%"
        resultados.append(res)

    # 2. Sensibilidad: Disponibilidad de Aserrín (d_mt)
    print("Iniciando análisis: Disponibilidad de Aserrín (d_mt)...")
    indice_aserrin = 3 # Según el orden de tu conjunto M
    for var in variaciones:
        data_sens = DatosModelo(copy.deepcopy(datos_crudos))
        for t in data_sens.T:
            data_sens.d_mt[indice_aserrin, t] = data_sens.d_mt[indice_aserrin, t] * (1 + var)
            
        res = resolver_instancia(data_sens, f"Disponibilidad Aserrín {var*100:+.0f}%")
        res["Parámetro Alterado"] = "Disponibilidad Aserrín"
        res["Variación"] = f"{var*100:+.0f}%"
        resultados.append(res)

    # 3. Sensibilidad: Capacidad Volteadora (cv_t)
    print("Iniciando análisis: Capacidad Volteadora (cv_t)...")
    for var in variaciones:
        data_sens = DatosModelo(copy.deepcopy(datos_crudos))
        for t in data_sens.T:
            data_sens.cv_t[t] = data_sens.cv_t[t] * (1 + var)
            
        res = resolver_instancia(data_sens, f"Capacidad Volteadora {var*100:+.0f}%")
        res["Parámetro Alterado"] = "Capacidad Volteadora"
        res["Variación"] = f"{var*100:+.0f}%"
        resultados.append(res)

    # Exportar DataFrame consolidado a Excel
    df_resultados = pd.DataFrame(resultados)
    DIR_ANALISIS.mkdir(parents=True, exist_ok=True)
    ruta_exportacion = DIR_ANALISIS / "Resultados_Sensibilidad.xlsx"
    df_resultados.to_excel(ruta_exportacion, index=False)
    print(f"\nAnálisis finalizado. Resultados exportados en: {ruta_exportacion}")
    print(df_resultados.to_string(index=False))

if __name__ == "__main__":
    main()