"""
generar_instancia_dmt.py  –  Grupo 12, ICS1113 E3 (Planta de Compostaje Maitenlahue)

Construye la disponibilidad semanal d_mt [ton] y el balance de estructurantes, y los
escribe en la planilla de instancia que lee main.py.

  Paso 1  h, c, n por componente (Adenda N°1 DIA, lab. Agrosuper; aserrín: Rynk 1992)
  Paso 2  rangos de la mezcla (NCh2880, DIA/RCA, Rynk 1992)
  Paso 3  balance de estructurante por humedad y por C:N
  Paso 4  reparto aserrín/viruta según oferta vendida V + VI región (INFOR 2025)
  Paso 5  estacionalidad mensual de la madera (INE IPMan div. 16, Los Ríos)
  Paso 6  series semanales con semilla fija:
            - lodo + guano de cerdo: AR(1), phi = 0,6, CV objetivo 8 %, total 64.400 t
            - guano de pollo: base 40 t/sem + lote cada 8 semanas (≈ 280 t), total 4.043,5 t
            - aserrín y viruta: total del balance × factor mensual INE × ruido 10 %

Uso (desde la carpeta 'Script Python/'):
    python generar_instancia_dmt.py              # imprime el balance y escribe d_mt
    python generar_instancia_dmt.py --no-write   # solo imprime

Solo usa pandas y numpy. pandas escribe el .xlsx con su motor openpyxl.
IMPORTANTE: después de escribir, abra la planilla en Excel y guárdela (o recalcule)
para que las fórmulas tengan valores; main.py lee los valores guardados.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

RUTA = Path(__file__).resolve().parent.parent / "Instancias Excel" / "Parametros_E3_G12_v3.xlsx"
SEMILLA = 12

# ---------- Paso 1: h, c, n (fracción; c y n en base seca) ----------
P = {  # nombre: (t/año, h, c, n)
    "lodo":        (28_000, 0.78,    0.26,    0.05),      # Adenda N°1, Tablas 2-3, punto medio
    "guano_cerdo": (36_400, 0.575,   0.515,   0.018),     # Adenda N°1, Tablas 2-3, punto medio
    "guano_pollo": (None,   0.2943,  0.2972,  0.0309),    # Adenda N°1, Tabla 5
    "aserrin":     (None,   0.39,    0.50,    0.50 / 442),# Rynk et al. 1992, Ap. B (C:N 442)
    "viruta":      (None,   0.31795, 0.49665, 0.00095),   # Adenda N°1, Tabla 6 (promedio 2 muestras)
}
# Fila 1 = lodo + guano de cerdo (28.000 m3 × 1,0 + 52.000 m3 × 0,7 t/m3)
T1 = P["lodo"][0] + P["guano_cerdo"][0]
MS = {k: P[k][0] * (1 - P[k][1]) for k in ("lodo", "guano_cerdo")}
H1 = sum(P[k][0] * P[k][1] for k in MS) / T1                      # ponderado por masa húmeda
C1 = sum(MS[k] * P[k][2] for k in MS) / sum(MS.values())          # ponderado por masa seca
N1 = sum(MS[k] * P[k][3] for k in MS) / sum(MS.values())

# ---------- Paso 2: rangos de la mezcla ----------
CN_MIN, CN_MAX, H_MIN, H_MAX = 25, 35, 0.50, 0.60

# ---------- Paso 4: oferta regional (INFOR 2025, V + VI, vendido) ----------
RHO_AS, RHO_VI = 0.237, 0.144                  # t/m3 aparente
OFERTA_AS = (9_923 + 468 + 77_626 + 3_392) * RHO_AS
CAP_VI = (443 + 3_319) * RHO_VI                # todo lo vendido de viruta en V y VI


# ---------- Paso 3: balance por tonelada húmeda de residuo ----------
def balance(f_vi):
    """f_vi = fracción (masa húmeda) de viruta dentro del estructurante."""
    hA, cA, nA = P["aserrin"][1:]
    hV, cV, nV = P["viruta"][1:]
    he = (1 - f_vi) * hA + f_vi * hV
    msA, msV = (1 - f_vi) * (1 - hA), f_vi * (1 - hV)
    ce = (msA * cA + msV * cV) / (msA + msV)
    ne = (msA * nA + msV * nV) / (msA + msV)
    C0, N0 = (1 - H1) * C1, (1 - H1) * N1
    x_ms = (CN_MIN * N0 - C0) / (ce - CN_MIN * ne)      # t MS / t residuo
    x_cn = x_ms / (1 - he)                               # t húmeda / t residuo
    x_h = max(0.0, (H1 - H_MAX) / (H_MAX - he))          # t húmeda / t residuo
    return dict(he=he, ce=ce, ne=ne, x_ms=x_ms, x_cn=x_cn, x_h=x_h, x=max(x_cn, x_h))


def mezcla(x, f_vi):
    """C:N y humedad de 1 t de residuo + x t de estructurante."""
    hA, cA, nA = P["aserrin"][1:]
    hV, cV, nV = P["viruta"][1:]
    xa, xv = x * (1 - f_vi), x * f_vi
    C = (1 - H1) * C1 + xa * (1 - hA) * cA + xv * (1 - hV) * cV
    N = (1 - H1) * N1 + xa * (1 - hA) * nA + xv * (1 - hV) * nV
    H = (H1 + xa * hA + xv * hV) / (1 + x)
    return C / N, H


req0 = balance(0.03)["x"] * T1                 # primera pasada para fijar f_vi
F_VI = min(CAP_VI, req0) / req0
B = balance(F_VI)
REQ = B["x"] * T1
MARGEN = 1.15
D_VI = round(CAP_VI)                           # tope físico, sin margen
D_AS = round(REQ * MARGEN - D_VI)
# Balance final con el reparto efectivamente cargado (igual a la hoja Balance_estructurante)
F_VI_CARGADO = D_VI / (D_AS + D_VI)
B_FIN = balance(F_VI_CARGADO)
REQ_FIN = B_FIN["x"] * T1

# ---------- Paso 5: estacionalidad INE (IPMan div. 16, Los Ríos, jul-2023 a jul-2026) ----------
INE = [80.4, 85.5, 78.3, 69.2, 72.5, 68.9, 79.0, 72.3, 90.5, 99.4, 89.5, 80.5,
       82.1, 90.4, 98.3, 112.9, 95.8, 81.9, 99.0, 93.0, 110.9, 107.6, 105.3, 102.6,
       102.6, 95.4, 98.2, 97.7, 108.9, 108.3, 109.2, 95.5, 107.4, 91.9, 92.0, 94.8, 92.6]
s = pd.Series(INE, pd.period_range("2023-07", periods=len(INE), freq="M"))
ma = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)   # media móvil 2×12
ratio = (s / ma).dropna()
FMES = ratio.groupby(ratio.index.month).mean()
FMES /= FMES.mean()
CAIDA_INV = 1 - FMES.loc[[6, 7, 8, 9]].mean()

# ---------- Paso 6: series semanales ----------
rng = np.random.default_rng(SEMILLA)
SEM = np.arange(1, 53)
MES = np.array([(pd.Timestamp("2026-01-01") + pd.Timedelta(days=7 * (t - 1) + 3)).month for t in SEM])


def redondear(v, total):
    """Redondea a 0,1 t y ajusta la semana con mayor residuo para cerrar el total exacto."""
    r = np.round(v, 1)
    dif = round(total - r.sum(), 1)
    if dif:
        i = int(np.argmax(np.abs(v - r)))
        r[i] = round(r[i] + dif, 1)
    return r


# lodo + guano de cerdo: AR(1) estacionario con CV objetivo 8 %
PHI, CV = 0.6, 0.08
e = np.zeros(52)
e[0] = rng.normal(0, CV)
for t in range(1, 52):
    e[t] = PHI * e[t - 1] + rng.normal(0, CV * np.sqrt(1 - PHI ** 2))
purin = redondear((1 + e) / (1 + e).sum() * T1, T1)

# guano de pollo: base 40 t/sem + lote cada 8 semanas (42 d crianza + 14 d vacío sanitario)
TOTAL_POLLO, BASE = 4_043.5, 40.0
lotes = np.arange(4, 53, 8)                     # semanas 4, 12, ..., 52
tam = rng.normal(1.0, 0.12, len(lotes))
pollo = np.full(52, BASE)
pollo[lotes - 1] += tam / tam.sum() * (TOTAL_POLLO - BASE * 52)
pollo = redondear(pollo, TOTAL_POLLO)

# estructurantes: total del balance × factor mensual × ruido 10 %
def serie(total):
    v = FMES.loc[MES].to_numpy() * (1 + rng.normal(0, 0.10, 52))
    return redondear(v / v.sum() * total, total)

asr, vir = serie(D_AS), serie(D_VI)
DMT = pd.DataFrame({"t": SEM, "Lodos de purines": purin, "Guano de pollo": pollo,
                    "Aserrín": asr, "Viruta": vir})


def resumen():
    print(f"Fila 1: {T1} t/año, h={H1:.4f}, c={C1:.4f}, n={N1:.5f}, C:N={C1 / N1:.2f}")
    print(f"Oferta V+VI vendida: aserrín {OFERTA_AS:.0f} t, viruta {CAP_VI:.0f} t; f_vi={F_VI:.4f}")
    print(f"Requerimiento: C:N {B_FIN['x_cn']:.3f} t/t, humedad {B_FIN['x_h']:.3f} t/t -> "
          f"{'HUMEDAD' if B_FIN['x_h'] > B_FIN['x_cn'] else 'C:N'} ; {REQ_FIN:.0f} t/año")
    print(f"Cargado (×{MARGEN}): aserrín {D_AS} t, viruta {D_VI} t")
    print("Mezcla con lo cargado: C:N={:.1f}, h={:.3f}".format(*mezcla((D_AS + D_VI) / T1, F_VI_CARGADO)))
    print("Factores mensuales:", FMES.round(3).to_dict(), f"caída jun-sep = {CAIDA_INV:.1%}")
    print("Totales d_mt:", DMT.iloc[:, 1:].sum().round(1).to_dict())
    print(f"CV lodos observado: {purin.std() / purin.mean():.1%}")


def escribir(ruta=RUTA):
    with pd.ExcelWriter(ruta, engine="openpyxl", mode="a", if_sheet_exists="overlay") as w:
        DMT.iloc[:, 1:].to_excel(w, sheet_name="d_mt", startrow=1, startcol=1, header=False, index=False)
        pd.DataFrame({"mes": FMES.index, "f": FMES.round(3).values}).to_excel(
            w, sheet_name="Semanal", startrow=2, startcol=10, header=False, index=False)
    print(f"d_mt escrito en {ruta}. Abra y guarde la planilla en Excel antes de correr main.py.")


if __name__ == "__main__":
    resumen()
    if "--no-write" not in sys.argv:
        escribir(Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else RUTA)
