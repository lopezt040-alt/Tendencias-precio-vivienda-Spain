"""
Carga el Excel del SERPAVI (Ministerio de Vivienda, 2011-2024) en SQLite.

El Excel es "ancho": una columna por métrica, tipología y año
(p. ej. ALQM2_LV_M_VC_24 = renta mediana €/m²·mes, vivienda colectiva, 2024).
Este script lo convierte a formato largo y lo guarda en:
  - tabla `serpavi`: todas las métricas (nº viviendas, renta €/m², renta €/mes, superficie)
  - tabla `precios`: la métrica elegida (por defecto renta mediana €/m²), lista para clasificar

Uso:
  python cargar_serpavi.py ARCHIVO.xlsx --hoja Municipios --tipologia VC
  python almacenar_clasificar.py clasificar --tipo alquiler_municipios --lag 1
  python almacenar_clasificar.py resumen --tipo alquiler_municipios
"""
import argparse
import pandas as pd
from almacenar_clasificar import conectar

# hoja -> (columna de código, columna de nombre)
HOJAS = {
    "CCAA": ("CCAA", "LITCCAA"),
    "Provincias": ("CPRO", "LITPRO"),
    "Municipios": ("CUMUN", "NMUN"),
    "Distritos": ("CUDIS", "LITMUN"),
    "Secciones censales": ("CUSEC", "LITMUN"),
}
BASES = {"ALQM2": "renta_m2", "ALQTBID12": "renta_mes", "SLVM2": "superficie_m2"}
ESTADISTICOS = {"M": "mediana", "25": "p25", "75": "p75"}


def parsear_columna(col: str):
    """'ALQM2_LV_M_VC_24' -> ('renta_m2_mediana', 'VC', 2024). None si no es métrica."""
    p = col.split("_")
    if not p[-1].isdigit():
        return None
    anio = 2000 + int(p[-1])
    if col.startswith("BI_ALVHEPCO_T"):
        return "n_viviendas", p[-2][1:], anio  # TVC -> VC
    if p[0] in BASES and p[-3] in ESTADISTICOS:
        return f"{BASES[p[0]]}_{ESTADISTICOS[p[-3]]}", p[-2], anio
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--hoja", default="Municipios", choices=list(HOJAS))
    ap.add_argument("--tipologia", default="VC", choices=["VC", "VU"],
                    help="VC = vivienda colectiva (pisos), VU = unifamiliar/rural")
    ap.add_argument("--metrica", default="renta_m2_mediana",
                    help="métrica que va a la tabla `precios` para clasificar")
    args = ap.parse_args()

    col_cod, col_nom = HOJAS[args.hoja]
    print(f"Leyendo hoja '{args.hoja}' (puede tardar un poco)...")
    df = pd.read_excel(args.archivo, sheet_name=args.hoja, dtype={col_cod: str})

    meta = {c: parsear_columna(c) for c in df.columns}
    meta = {c: m for c, m in meta.items() if m}
    largo = df.melt(id_vars=[col_cod, col_nom], value_vars=list(meta), value_name="valor")
    largo = largo.dropna(subset=["valor"])
    largo[["metrica", "tipologia", "anio"]] = pd.DataFrame(
        largo["variable"].map(meta).tolist(), index=largo.index)
    largo = largo.rename(columns={col_cod: "codigo", col_nom: "nombre"})
    largo["nivel"] = args.hoja
    largo = largo[["nivel", "codigo", "nombre", "anio", "tipologia", "metrica", "valor"]]

    con = conectar()
    con.execute("""CREATE TABLE IF NOT EXISTS serpavi (
        nivel TEXT, codigo TEXT, nombre TEXT, anio INTEGER,
        tipologia TEXT, metrica TEXT, valor REAL)""")
    con.execute("DELETE FROM serpavi WHERE nivel = ?", (args.hoja,))
    largo.to_sql("serpavi", con, if_exists="append", index=False, chunksize=50000)

    # Subconjunto listo para clasificar
    sel = largo[(largo["tipologia"] == args.tipologia) & (largo["metrica"] == args.metrica)]
    tipo = f"alquiler_{args.hoja.lower().replace(' ', '_')}"
    con.execute("DELETE FROM precios WHERE fuente = 'SERPAVI' AND tipo = ?", (tipo,))
    con.executemany(
        "INSERT OR REPLACE INTO precios VALUES (?,?,?,?,?)",
        [("SERPAVI", tipo, f"{r.codigo} {r.nombre}", str(r.anio), r.valor)
         for r in sel.itertuples()])
    con.commit()

    print(f"[OK] tabla serpavi: {len(largo):,} filas ({args.hoja})")
    print(f"[OK] tabla precios: {len(sel):,} filas, tipo='{tipo}' "
          f"({args.metrica}, {args.tipologia})")
    print(f"\nSiguiente paso:\n  python almacenar_clasificar.py clasificar --tipo {tipo} --lag 1")


if __name__ == "__main__":
    main()
