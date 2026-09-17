"""
Genera la pagina web del producto (docs/index.html) a partir de los CSV
que deja 05_prediccion_diaria.py en dashboard_data/. Se ejecuta como
ultimo paso del workflow diario, para que GitHub Pages sirva siempre la
version mas reciente.
"""
import json
import math
import os

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "dashboard_data")
TEMPLATE_PATH = os.path.join(REPO_ROOT, "web", "template.html")
OUT_DIR = os.path.join(REPO_ROOT, "docs")
OUT_PATH = os.path.join(OUT_DIR, "index.html")

# El ticker "GLD" (SPDR Gold Shares, usado en 00_descargas.ipynb como proxy
# del oro internacional) no representa una onza troy completa: cada accion
# equivale a una fraccion de onza que se reduce lentamente por la comision
# de administracion del fondo desde su lanzamiento en 2004. Este factor
# corrige SOLO la cifra que se muestra al usuario (precio en pantalla y
# simuladores), calibrado el 17-sep-2026 contra el futuro de oro COMEX
# (GC=F, que si cotiza en USD por onza troy completa): promedio de la razon
# GC=F/GLD de los ultimos 8 dias bursatiles = 11,08. No afecta ninguna
# metrica del modelo (RMSE, precision direccional, correlaciones), que se
# calculan sobre retornos porcentuales y son invariantes a la escala.
FACTOR_ONZA_COMPLETA = 11.08


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, float) and math.isnan(o):
        return None
    return o


def construir_datos():
    hist = pd.read_csv(os.path.join(DATA_DIR, "historico.csv"))
    hist["DATE"] = pd.to_datetime(hist["DATE"])
    resumen = pd.read_csv(os.path.join(DATA_DIR, "resumen.csv")).iloc[0].to_dict()
    pred_log = pd.read_csv(os.path.join(DATA_DIR, "prediccion.csv")).to_dict("records")
    modelos = pd.read_csv(os.path.join(DATA_DIR, "metricas_modelos.csv")).to_dict("records")

    serie_precio = hist[["DATE", "oro_cop"]].dropna().copy()
    serie_precio["oro_cop"] = serie_precio["oro_cop"] * FACTOR_ONZA_COMPLETA
    serie_precio["DATE"] = serie_precio["DATE"].dt.strftime("%Y-%m-%d")
    serie_usd = hist[["DATE", "usd_cop_Close"]].dropna().copy()
    serie_usd["DATE"] = serie_usd["DATE"].dt.strftime("%Y-%m-%d")
    serie_xau = hist[["DATE", "oro_xauusd_Close"]].dropna().copy()
    serie_xau["oro_xauusd_Close"] = serie_xau["oro_xauusd_Close"] * FACTOR_ONZA_COMPLETA
    serie_xau["DATE"] = serie_xau["DATE"].dt.strftime("%Y-%m-%d")

    h = hist.set_index("DATE")
    h["retorno_oro_cop"] = h["oro_cop"].pct_change(fill_method=None)
    h["retorno_usd_cop"] = h["usd_cop_Close"].pct_change(fill_method=None)
    h["retorno_dxy"] = h["dxy_Close"].pct_change(fill_method=None)
    h["retorno_vix"] = h["vix_Close"].pct_change(fill_method=None)
    h["retorno_wti"] = h["wti_crudo_Close"].pct_change(fill_method=None)
    h["retorno_bono_10y"] = h["bono_10y_Close"].pct_change(fill_method=None)
    for lag in range(1, 11):
        h[f"usd_cop_lag_{lag}"] = h["retorno_usd_cop"].shift(lag)
    h["retorno_dxy_lag1"] = h["retorno_dxy"].shift(1)
    h["retorno_vix_lag1"] = h["retorno_vix"].shift(1)
    h["retorno_wti_lag1"] = h["retorno_wti"].shift(1)
    h["retorno_bono_10y_lag1"] = h["retorno_bono_10y"].shift(1)

    corrs_lag = [
        {"lag": lag, "corr": round(float(h[f"usd_cop_lag_{lag}"].corr(h["retorno_oro_cop"])), 4)}
        for lag in range(1, 11)
    ]
    corrs_macro = [
        {"nombre": "DXY (indice dolar)", "corr": round(float(h["retorno_dxy_lag1"].corr(h["retorno_oro_cop"])), 4)},
        {"nombre": "VIX (volatilidad)", "corr": round(float(h["retorno_vix_lag1"].corr(h["retorno_oro_cop"])), 4)},
        {"nombre": "WTI (petroleo)", "corr": round(float(h["retorno_wti_lag1"].corr(h["retorno_oro_cop"])), 4)},
        {"nombre": "Bono 10Y (tasa)", "corr": round(float(h["retorno_bono_10y_lag1"].corr(h["retorno_oro_cop"])), 4)},
    ]

    h2 = h.reset_index()
    h2["DATE"] = pd.to_datetime(h2["DATE"])
    h2["dia_semana"] = h2["DATE"].dt.day_name()
    orden = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    nombres_es = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles", "Thursday": "Jueves", "Friday": "Viernes"}
    h2["dia_semana"] = pd.Categorical(h2["dia_semana"], categories=orden, ordered=True)
    por_dia = h2.groupby("dia_semana", observed=True)["retorno_usd_cop"].mean()
    por_dia_list = [{"dia": nombres_es[d], "retorno_pct": round(float(v) * 100, 4)} for d, v in por_dia.items()]

    # Se corrige la escala de los precios en pesos que ve el usuario final
    # (resumen y bitacora de predicciones). Los campos en porcentaje
    # (retorno_predicho_manana_pct, error_pct) y el booleano
    # acierto_direccion no se tocan: son invariantes a la escala.
    resumen["precio_oro_cop_hoy"] = resumen["precio_oro_cop_hoy"] * FACTOR_ONZA_COMPLETA
    resumen["precio_oro_cop_predicho_manana"] = resumen["precio_oro_cop_predicho_manana"] * FACTOR_ONZA_COMPLETA
    for fila in pred_log:
        for campo in ("precio_hoy", "precio_predicho", "precio_real", "error_COP"):
            fila[campo] = fila[campo] * FACTOR_ONZA_COMPLETA

    return clean({
        "serie_precio": serie_precio.values.tolist(),
        "serie_usd": serie_usd.values.tolist(),
        "serie_xau": serie_xau.values.tolist(),
        "corrs_lag": corrs_lag,
        "corrs_macro": corrs_macro,
        "por_dia_semana": por_dia_list,
        "resumen": resumen,
        "predicciones": pred_log,
        "modelos": modelos,
    })


def main():
    datos = construir_datos()
    template = open(TEMPLATE_PATH, encoding="utf-8").read()
    salida = template.replace("__DATA_JSON__", json.dumps(datos, separators=(",", ":")))
    os.makedirs(OUT_DIR, exist_ok=True)
    open(OUT_PATH, "w", encoding="utf-8").write(salida)
    print(f"Pagina generada: {OUT_PATH} ({len(salida.encode('utf-8')):,} bytes)")


if __name__ == "__main__":
    main()
