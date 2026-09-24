"""
Tendencias de vivienda en España:
  1) Precios de venta y alquiler -> API oficial del INE (datos abiertos)
  2) Características más buscadas -> Google Trends (pytrends)

Instalación:  pip install requests pandas pytrends
Uso:          python tendencias_vivienda.py
"""
import time
import requests
import pandas as pd
from pytrends.request import TrendReq

# --- CONFIGURACIÓN -----------------------------------------------------------
# IDs de tablas del INE. VERIFÍCALOS en https://www.ine.es (buscar
# "Índice de Precios de Vivienda" e "Índice de Precios de Vivienda en Alquiler",
# el ID aparece en la URL de la tabla en tempus3.ine.es).
INE_TABLAS = {
    "venta": 25171,     # IPV (compraventa) por comunidades autónomas
    "alquiler": 59058,  # IPVA (alquiler) -> comprueba el ID
}
N_ULTIMOS_PERIODOS = 20  # trimestres

# Características a comparar (Google Trends admite máx. 5 por consulta)
CARACTERISTICAS = [
    "piso con terraza",
    "piso con ascensor",
    "piso con garaje",
    "piso con piscina",
    "piso reformado",
    "piso amueblado",
]
GEO = "ES"  # o "ES-VC" para la Comunidad Valenciana, etc.
# -----------------------------------------------------------------------------


def descargar_ine(tabla_id: int, n: int = N_ULTIMOS_PERIODOS) -> pd.DataFrame:
    url = f"https://servicio.ine.es/wstempus/js/ES/DATOS_TABLA/{tabla_id}"
    r = requests.get(url, params={"nult": n}, timeout=30)
    r.raise_for_status()
    filas = []
    for serie in r.json():
        for d in serie.get("Data", []):
            filas.append({
                "serie": serie["Nombre"],
                "fecha": pd.to_datetime(d["Fecha"], unit="ms"),
                "valor": d["Valor"],
            })
    return pd.DataFrame(filas)


def variacion_anual(df: pd.DataFrame) -> pd.DataFrame:
    """Añade la variación % interanual (4 trimestres) por serie."""
    df = df.sort_values(["serie", "fecha"]).copy()
    df["var_anual_%"] = df.groupby("serie")["valor"].pct_change(4) * 100
    return df


def tendencias_busqueda(palabras: list[str], geo: str = GEO) -> pd.DataFrame:
    pt = TrendReq(hl="es-ES", tz=60)
    partes = []
    # Se trocea en grupos de 5, con una palabra ancla común para poder
    # comparar entre grupos.
    ancla = palabras[0]
    resto = palabras[1:]
    for i in range(0, len(resto), 4):
        grupo = [ancla] + resto[i:i + 4]
        pt.build_payload(grupo, geo=geo, timeframe="today 5-y")
        partes.append(pt.interest_over_time().drop(columns="isPartial"))
        time.sleep(5)  # evitar bloqueos por exceso de peticiones
    df = pd.concat(partes, axis=1)
    return df.loc[:, ~df.columns.duplicated()]


def main():
    for tipo, tabla in INE_TABLAS.items():
        try:
            df = variacion_anual(descargar_ine(tabla))
            df.to_csv(f"precios_{tipo}.csv", index=False)
            print(f"[OK] precios_{tipo}.csv ({len(df)} filas)")
        except Exception as e:
            print(f"[ERROR] {tipo}: {e}")

    try:
        trends = tendencias_busqueda(CARACTERISTICAS)
        trends.to_csv("busquedas_caracteristicas.csv")
        print("\nInterés medio de búsqueda (0-100, últimos 5 años):")
        print(trends.mean().sort_values(ascending=False).round(1))
    except Exception as e:
        print(f"[ERROR] Google Trends: {e}")


if __name__ == "__main__":
    main()
