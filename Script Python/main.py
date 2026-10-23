"""
main.py
Script principal para la resolución computacional del modelo de optimización de la
Planta de Compostaje Maitenlahue (Python 3.9.18 - Gurobi 10.0.3).
"""
from gurobipy import GRB, Model
from cargador_datos import cargar_todos_los_parametros
from estructura_modelo import DatosModelo, crear_variables
from restricciones_objetivo import agregar_restricciones, definir_objetivo
from resultados_graficos import extraer_y_exportar_resultados, generar_graficos_informe


def main():
    print("1. Cargando parámetros desde 'Instancias Excel/'...")
    datos_crudos = cargar_todos_los_parametros()
    data = DatosModelo(datos_crudos)

    # ----------------------- Generación del modelo ------------------------
    print("2. Inicializando modelo en Gurobi (TimeLimit = 1800 segundos)...")
    model = Model("Planta_Compostaje_Maitenlahue")
    model.setParam("TimeLimit", 1800)  # 30 minutos según requerimiento del enunciado

    # ---------------- Se instancian variables de decisión -----------------
    print("3. Creando variables de decisión (x_mpt, r_mt, y_pt, v_pt, a_pt)...")
    vars_dict = crear_variables(model, data)

    # ----------------------- Agregar Restricciones ------------------------
    print("4. Agregando restricciones operativas y agronómicas (R1 a R14)...")
    agregar_restricciones(model, data, vars_dict)

    # ------------------------- Función Objetivo ---------------------------
    print("5. Configurando Función Objetivo y ejecutando optimización...")
    definir_objetivo(model, data, vars_dict)
    model.optimize()

    # ------------------------ Manejo Soluciones ---------------------------
    if model.SolCount > 0:
        print(f"\nSolución encontrada (Estado Gurobi: {model.Status}). Exportando resultados...")
        tablas_res = extraer_y_exportar_resultados(model, data, vars_dict)
        generar_graficos_informe(tablas_res)
    else:
        print(f"\nEl modelo no encontró solución factible (Estado Gurobi: {model.Status}).")
        if model.Status == GRB.INFEASIBLE:
            print("Calculando IIS (Irreducible Inconsistent Subsystem) para diagnóstico...")
            model.computeIIS()
            model.write("diagnostico_infactibilidad.ilp")
            print("Archivo 'diagnostico_infactibilidad.ilp' generado.")


if __name__ == "__main__":
    main()
