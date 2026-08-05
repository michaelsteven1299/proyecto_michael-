"""
Pipeline de produccion: descarga los datos mas recientes, reentrena el modelo
campeon (Regresion Lineal, seleccionado en 04_modelo.ipynb) sobre todo el
historico disponible y predice el retorno y precio del oro en pesos
colombianos para el siguiente dia habil.

Pensado para ejecutarse una vez al dia desde GitHub Actions. Escribe sus
salidas en dashboard_data/, que es la fuente que consume el dashboard
(Google Sheets -> Looker Studio via IMPORTDATA sobre el CSV crudo de GitHub).
"""
import os
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.linear_model import LinearRegression

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "dashboard_data")
os.makedirs(OUT_DIR, exist_ok=True)

TICKERS = {
    "GLD": "oro_xauusd",
    "COP=X": "usd_cop",
    "DX-Y.NYB": "dxy",
    "^VIX": "vix",
    "CL=F": "wti_crudo",
    "^TNX": "bono_10y",
}

FEATURES = [
    "usd_cop_lag_5", "usd_cop_lag_8", "usd_cop_lag_10", "usd_cop_lag_16",
    "dia_1", "dia_2", "dia_3", "dia_4",
    "retorno_dxy_lag1", "retorno_vix_lag1", "retorno_wti_lag1", "retorno_bono_10y_lag1",
]
TARGET = "retorno_oro_cop"


def descargar_series():
    series = {}
    for ticker, nombre in TICKERS.items():
        df = yf.download(ticker, start="2021-01-01", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        series[nombre] = df["Close"]
    return series


def consolidar(series):
    df = pd.DataFrame(index=series["oro_xauusd"].index)
    df["oro_xauusd_Close"] = series["oro_xauusd"]
    df = df.join(series["usd_cop"].rename("usd_cop_Close"), how="inner")
    df["oro_cop"] = df["oro_xauusd_Close"] * df["usd_cop_Close"]
    for nombre in ["dxy", "vix", "wti_crudo", "bono_10y"]:
        df[f"{nombre}_Close"] = series[nombre]
    df.index.name = "DATE"
    df = df.dropna(subset=["oro_xauusd_Close", "usd_cop_Close", "oro_cop"])
    return df


def construir_features(df):
    df = df.copy()
    df["retorno_oro_cop"] = df["oro_cop"].pct_change(fill_method=None)
    df["retorno_usd_cop"] = df["usd_cop_Close"].pct_change(fill_method=None)
    df["retorno_dxy"] = df["dxy_Close"].pct_change(fill_method=None)
    df["retorno_vix"] = df["vix_Close"].pct_change(fill_method=None)
    df["retorno_wti"] = df["wti_crudo_Close"].pct_change(fill_method=None)
    df["retorno_bono_10y"] = df["bono_10y_Close"].pct_change(fill_method=None)

    for lag in [5, 8, 10, 16]:
        df[f"usd_cop_lag_{lag}"] = df["retorno_usd_cop"].shift(lag)

    df["retorno_dxy_lag1"] = df["retorno_dxy"].shift(1)
    df["retorno_vix_lag1"] = df["retorno_vix"].shift(1)
    df["retorno_wti_lag1"] = df["retorno_wti"].shift(1)
    df["retorno_bono_10y_lag1"] = df["retorno_bono_10y"].shift(1)

    dummies_dia = pd.get_dummies(df.index.dayofweek, prefix="dia", drop_first=True)
    dummies_dia.index = df.index
    for col in ["dia_1", "dia_2", "dia_3", "dia_4"]:
        if col not in dummies_dia.columns:
            dummies_dia[col] = False
    df = pd.concat([df, dummies_dia[["dia_1", "dia_2", "dia_3", "dia_4"]]], axis=1)
    return df


def agregar_fila_manana(df):
    ultimo_dia = df.index[-1]
    manana = ultimo_dia + pd.tseries.offsets.BDay(1)
    fila_vacia = pd.DataFrame(np.nan, index=[manana], columns=df.columns)
    extendido = pd.concat([df, fila_vacia])
    extendido.index.name = "DATE"
    return construir_features(extendido[["oro_xauusd_Close", "usd_cop_Close", "oro_cop",
                                          "dxy_Close", "vix_Close", "wti_crudo_Close",
                                          "bono_10y_Close"]])


def predecir_manana(df_features):
    df_modelo = df_features.dropna(subset=FEATURES + [TARGET])
    X_train = df_modelo[FEATURES]
    y_train = df_modelo[TARGET]

    modelo = LinearRegression()
    modelo.fit(X_train, y_train)

    fila_manana = df_features.iloc[[-1]]
    X_manana = fila_manana[FEATURES]
    retorno_predicho = float(modelo.predict(X_manana)[0])

    precio_hoy = float(df_features["oro_cop"].dropna().iloc[-1])
    precio_predicho = precio_hoy * (1 + retorno_predicho)

    return {
        "fecha_prediccion": df_features.index[-2].strftime("%Y-%m-%d"),
        "fecha_objetivo": df_features.index[-1].strftime("%Y-%m-%d"),
        "precio_hoy": precio_hoy,
        "retorno_predicho": retorno_predicho,
        "precio_predicho": precio_predicho,
    }


def actualizar_historico(df):
    cols = ["oro_xauusd_Close", "usd_cop_Close", "oro_cop", "dxy_Close",
            "vix_Close", "wti_crudo_Close", "bono_10y_Close"]
    hist = df[cols].copy()
    hist["retorno_oro_cop"] = hist["oro_cop"].pct_change()
    hist = hist.reset_index()
    hist["DATE"] = hist["DATE"].dt.strftime("%Y-%m-%d")
    hist.to_csv(os.path.join(OUT_DIR, "historico.csv"), index=False)
    return hist


def actualizar_predicciones(nueva_prediccion, hist):
    path = os.path.join(OUT_DIR, "prediccion.csv")
    columnas = ["fecha_prediccion", "fecha_objetivo", "precio_hoy", "retorno_predicho",
                "precio_predicho", "precio_real", "error_COP", "error_pct", "acierto_direccion"]

    if os.path.exists(path):
        log = pd.read_csv(path)
    else:
        log = pd.DataFrame(columns=columnas)

    fila = {c: None for c in columnas}
    fila.update(nueva_prediccion)
    log = log[log["fecha_objetivo"] != fila["fecha_objetivo"]]
    fila_df = pd.DataFrame([fila])
    log = fila_df if log.empty else pd.concat([log, fila_df], ignore_index=True)

    precios_reales = hist.set_index("DATE")["oro_cop"]
    for i, row in log.iterrows():
        objetivo = row["fecha_objetivo"]
        if objetivo in precios_reales.index and pd.notna(precios_reales[objetivo]):
            real = float(precios_reales[objetivo])
            predicho = float(row["precio_predicho"])
            hoy = float(row["precio_hoy"])
            log.at[i, "precio_real"] = real
            log.at[i, "error_COP"] = real - predicho
            log.at[i, "error_pct"] = (real - predicho) / real * 100
            log.at[i, "acierto_direccion"] = (predicho - hoy) * (real - hoy) > 0

    log = log.sort_values("fecha_objetivo").reset_index(drop=True)
    log.to_csv(path, index=False)
    return log


def actualizar_resumen(nueva_prediccion, log):
    validas = log.dropna(subset=["error_pct"])
    kpis = {
        "fecha_actualizacion": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "precio_oro_cop_hoy": nueva_prediccion["precio_hoy"],
        "precio_oro_cop_predicho_manana": nueva_prediccion["precio_predicho"],
        "retorno_predicho_manana_pct": nueva_prediccion["retorno_predicho"] * 100,
        "fecha_objetivo": nueva_prediccion["fecha_objetivo"],
        "error_abs_promedio_pct": validas["error_pct"].abs().mean() if len(validas) else None,
        "aciertos_direccion_pct": validas["acierto_direccion"].mean() * 100 if len(validas) else None,
        "predicciones_evaluadas": len(validas),
        "modelo_campeon": "Regresion Lineal",
        "mejora_rmse_vs_referencia_pct": 4.16,
    }
    pd.DataFrame([kpis]).to_csv(os.path.join(OUT_DIR, "resumen.csv"), index=False)


def escribir_metricas_modelos():
    """Ranking de los 15 modelos evaluados en 04_modelo.ipynb (validacion con
    TimeSeriesSplit de 6 ventanas). Tabla de referencia estatica: la
    comparacion de modelos es un resultado de la fase de analisis, no se
    recalcula en cada corrida de produccion."""
    ranking = [
        ("Linear Regression", 0.014564, 4.163935, 6),
        ("Huber Regressor", 0.014669, 3.468624, 5),
        ("Bayesian Ridge", 0.014836, 2.372132, 6),
        ("Extra Trees", 0.014847, 2.301467, 5),
        ("Ridge", 0.014893, 1.997537, 5),
        ("Random Forest", 0.014946, 1.648443, 5),
        ("AdaBoost", 0.014992, 1.340920, 4),
        ("LightGBM", 0.015124, 0.473861, 4),
        ("K-Nearest Neighbors", 0.015131, 0.427588, 5),
        ("ElasticNet", 0.015172, 0.161685, 5),
        ("Lasso", 0.015186, 0.068660, 4),
        ("Gradient Boosting", 0.015381, -1.214669, 5),
        ("SVR (RBF)", 0.015613, -2.745050, 2),
        ("Decision Tree", 0.015687, -3.231746, 1),
        ("XGBoost", 0.015893, -4.585363, 1),
    ]
    df = pd.DataFrame(ranking, columns=["modelo", "rmse_promedio", "mejora_pct", "ventanas_ganadas"])
    df.to_csv(os.path.join(OUT_DIR, "metricas_modelos.csv"), index=False)


def main():
    series = descargar_series()
    consolidado = consolidar(series)
    df_features = agregar_fila_manana(consolidado)

    prediccion = predecir_manana(df_features)
    hist = actualizar_historico(consolidado)
    log = actualizar_predicciones(prediccion, hist)
    actualizar_resumen(prediccion, log)
    escribir_metricas_modelos()

    print(f"Prediccion para {prediccion['fecha_objetivo']}: "
          f"retorno {prediccion['retorno_predicho']*100:.3f}% -> "
          f"precio {prediccion['precio_predicho']:,.0f} COP "
          f"(hoy: {prediccion['precio_hoy']:,.0f} COP)")


if __name__ == "__main__":
    main()
