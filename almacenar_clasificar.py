"""
Carga datos de precios de vivienda (CSV/Excel), los guarda en SQLite y los clasifica.

Ejemplos:
  # 1) Cargar el CSV del INE generado por tendencias_vivienda.py
  python almacenar_clasificar.py cargar precios_venta.csv --fuente INE --tipo venta \
      --territorio serie --periodo fecha --valor valor

  # 2) Cargar un fichero del Ministerio (SERPAVI) descargado a mano
  python almacenar_clasificar.py cargar serpavi.xlsx --fuente SERPAVI --tipo alquiler \
      --territorio "Municipio" --periodo "Año" --valor "Precio"

  # 3) Clasificar (lag = periodos para comparar: 4 si es trimestral, 1 si es anual)
  python almacenar_clasificar.py clasificar --tipo venta --lag 4

  # 4) Ver resultados
  python almacenar_clasificar.py resumen --tipo venta
"""
import argparse
import sqlite3
import pandas as pd

DB = "vivienda.db"

# Umbrales de variación % para clasificar la tendencia (ajústalos a tu gusto)
UMBRAL_BAJADA = -1.0
UMBRAL_ESTABLE = 1.0
UMBRAL_MODERADA = 5.0


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS precios (
            fuente TEXT, tipo TEXT, territorio TEXT, periodo TEXT, valor REAL,
            PRIMARY KEY (fuente, tipo, territorio, periodo)
        );
        CREATE TABLE IF NOT EXISTS clasificacion (
            tipo TEXT, territorio TEXT, periodo TEXT, valor REAL,
            var_pct REAL, nivel TEXT, tendencia TEXT,
            PRIMARY KEY (tipo, territorio)
        );
    """)
    return con


def leer_archivo(ruta: str) -> pd.DataFrame:
    if ruta.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(ruta)
    return pd.read_csv(ruta, sep=None, engine="python")  # detecta ; o ,


def cargar(args):
    df = leer_archivo(args.archivo)
    df = df.rename(columns={
        args.territorio: "territorio", args.periodo: "periodo", args.valor: "valor"
    })[["territorio", "periodo", "valor"]]
    # Normaliza: decimales con coma, periodos como texto, sin filas vacías
    df["valor"] = pd.to_numeric(
        df["valor"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    df["periodo"] = df["periodo"].astype(str).str[:10]
    df = df.dropna(subset=["territorio", "periodo", "valor"])
    df.insert(0, "tipo", args.tipo)
    df.insert(0, "fuente", args.fuente)

    con = conectar()
    con.executemany(
        "INSERT OR REPLACE INTO precios VALUES (?,?,?,?,?)",
        df[["fuente", "tipo", "territorio", "periodo", "valor"]].values.tolist())
    con.commit()
    print(f"[OK] {len(df)} filas guardadas en {DB} ({args.fuente}/{args.tipo})")


def tendencia(v: float) -> str:
    if pd.isna(v):
        return "sin datos"
    if v < UMBRAL_BAJADA:
        return "bajada"
    if v <= UMBRAL_ESTABLE:
        return "estable"
    if v <= UMBRAL_MODERADA:
        return "subida moderada"
    return "subida fuerte"


def clasificar(args):
    con = conectar()
    df = pd.read_sql("SELECT territorio, periodo, valor FROM precios WHERE tipo = ?",
                     con, params=(args.tipo,))
    if df.empty:
        print("No hay datos de ese tipo. Usa primero el comando 'cargar'.")
        return

    # Tabla territorio x periodo: los huecos quedan como NaN y no desalinean la comparación
    piv = df.pivot_table(index="territorio", columns="periodo",
                         values="valor", aggfunc="last").sort_index(axis=1)
    if piv.shape[1] <= args.lag:
        print(f"Solo hay {piv.shape[1]} periodos y --lag es {args.lag}: reduce el lag.")
        return

    actual, anterior = piv.iloc[:, -1], piv.iloc[:, -1 - args.lag]
    res = pd.DataFrame({
        "tipo": args.tipo, "territorio": piv.index,
        "periodo": piv.columns[-1], "valor": actual.values,
        "var_pct": ((actual / anterior - 1) * 100).values,
    })
    res["tendencia"] = res["var_pct"].apply(tendencia)

    # Nivel de precio por cuartiles dentro del conjunto cargado
    res["nivel"] = "sin datos"
    ok = res["valor"].notna()
    try:
        res.loc[ok, "nivel"] = pd.qcut(
            res.loc[ok, "valor"], 4,
            labels=["bajo", "medio", "alto", "muy alto"]).astype(str)
    except ValueError:  # pocos territorios o valores repetidos
        res.loc[ok, "nivel"] = "n/d"

    filas = res[["tipo", "territorio", "periodo", "valor",
                 "var_pct", "nivel", "tendencia"]]
    con.execute("DELETE FROM clasificacion WHERE tipo = ?", (args.tipo,))
    con.executemany("INSERT OR REPLACE INTO clasificacion VALUES (?,?,?,?,?,?,?)",
                    filas.astype(object).where(filas.notna(), None).values.tolist())
    con.commit()
    print(f"[OK] {len(filas)} territorios clasificados (periodo {piv.columns[-1]} "
          f"vs {piv.columns[-1 - args.lag]})")
    print(filas["tendencia"].value_counts().to_string())


def resumen(args):
    con = conectar()
    df = pd.read_sql(
        "SELECT * FROM clasificacion WHERE tipo = ? ORDER BY var_pct DESC",
        con, params=(args.tipo,))
    print(df.round(2).to_string(index=False) if not df.empty else "Sin clasificar aún.")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cargar")
    c.add_argument("archivo")
    c.add_argument("--fuente", required=True)
    c.add_argument("--tipo", required=True, help="p. ej. venta, alquiler")
    c.add_argument("--territorio", required=True, help="nombre de la columna")
    c.add_argument("--periodo", required=True, help="nombre de la columna")
    c.add_argument("--valor", required=True, help="nombre de la columna")
    c.set_defaults(fn=cargar)

    k = sub.add_parser("clasificar")
    k.add_argument("--tipo", required=True)
    k.add_argument("--lag", type=int, default=4)
    k.set_defaults(fn=clasificar)

    r = sub.add_parser("resumen")
    r.add_argument("--tipo", required=True)
    r.set_defaults(fn=resumen)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
