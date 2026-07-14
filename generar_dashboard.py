#!/usr/bin/env python3
"""Genera un dashboard estático de distancia al promedio para GitHub Pages."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "configuracion.json"
DEFAULT_OUTPUT = ROOT / "index.html"


@dataclass
class AssetResult:
    ticker: str
    nombre: str
    color: str
    df: pd.DataFrame | None = None
    promedio: float | None = None
    precio_actual: float | None = None
    desviacion: float | None = None
    fecha_precio: pd.Timestamp | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Archivo JSON con la configuración del dashboard.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ruta donde se guardará el HTML generado.",
    )
    return parser.parse_args()


def cargar_configuracion(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as archivo:
        config = json.load(archivo)

    if not config.get("activos"):
        raise ValueError("La configuración debe incluir al menos un activo.")

    tickers: set[str] = set()
    for activo in config["activos"]:
        for campo in ("ticker", "nombre", "color"):
            if not activo.get(campo):
                raise ValueError(f"Falta '{campo}' en uno de los activos.")
        ticker = activo["ticker"].strip().upper()
        if ticker in tickers:
            raise ValueError(f"El ticker '{ticker}' está repetido.")
        tickers.add(ticker)

    return config


def normalizar_cierres(df: pd.DataFrame, ema_periodo: int) -> pd.DataFrame:
    """Limpia un bloque de Yahoo Finance y calcula su EMA."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(columna[0]) for columna in df.columns]

    if df.empty or "Close" not in df:
        raise ValueError("Yahoo Finance no devolvió precios.")

    cierre = pd.to_numeric(df["Close"], errors="coerce")
    limpio = pd.DataFrame({"Close": cierre}).dropna()
    limpio = limpio[limpio["Close"] > 0].copy()
    limpio = limpio[~limpio.index.duplicated(keep="last")].sort_index()

    if getattr(limpio.index, "tz", None) is not None:
        limpio.index = limpio.index.tz_localize(None)

    if len(limpio) < 20:
        raise ValueError("No hay suficientes cierres diarios para mostrar el activo.")

    limpio["EMA"] = limpio["Close"].ewm(span=ema_periodo, adjust=False).mean()
    return limpio


def descargar_datos(
    tickers: list[str], anos: int, ema_periodo: int
) -> dict[str, pd.DataFrame]:
    """Descarga todos los activos en una sola solicitud para evitar bloqueos."""
    fin = datetime.now(timezone.utc).date() + timedelta(days=1)
    inicio = fin - timedelta(days=anos * 365 + 3)
    descarga = yf.download(
        tickers,
        start=inicio.isoformat(),
        end=fin.isoformat(),
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
        timeout=30,
    )

    if descarga.empty:
        raise ValueError("Yahoo Finance no devolvió precios.")

    datos: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1 and not isinstance(descarga.columns, pd.MultiIndex):
                bloque = descarga.copy()
            elif ticker in descarga.columns.get_level_values(0):
                bloque = descarga[ticker].copy()
            elif ticker in descarga.columns.get_level_values(1):
                bloque = descarga.xs(ticker, axis=1, level=1).copy()
            else:
                continue
            datos[ticker] = normalizar_cierres(bloque, ema_periodo)
        except (KeyError, ValueError):
            continue
    return datos


def procesar_activo(
    activo: dict[str, str], datos: dict[str, pd.DataFrame]
) -> AssetResult:
    resultado = AssetResult(
        ticker=activo["ticker"].strip().upper(),
        nombre=activo["nombre"].strip(),
        color=activo["color"].strip(),
    )
    try:
        if resultado.ticker not in datos:
            raise ValueError("Yahoo Finance no devolvió precios.")
        df = datos[resultado.ticker]
        promedio = float(df["Close"].mean())
        precio_actual = float(df["Close"].iloc[-1])
        resultado.df = df
        resultado.promedio = promedio
        resultado.precio_actual = precio_actual
        resultado.desviacion = ((precio_actual - promedio) / promedio) * 100
        resultado.fecha_precio = pd.Timestamp(df.index[-1])
    except Exception as exc:  # Cada activo falla por separado para no romper todo.
        resultado.error = str(exc)
    return resultado


def clasificar_salud(
    desviacion: float, umbral_cerca: float, umbral_moderado: float
) -> tuple[str, str]:
    distancia = abs(desviacion)
    if distancia <= umbral_cerca:
        return "Cerca del promedio", "cerca"
    if distancia <= umbral_moderado:
        return "Distancia moderada", "moderada"
    return "Muy alejado", "alejada"


def formato_precio(valor: float) -> str:
    if valor >= 1_000:
        return f"${valor:,.0f}"
    if valor >= 1:
        return f"${valor:,.2f}"
    return f"${valor:,.4f}"


def crear_figura(resultado: AssetResult, ema_periodo: int) -> str:
    assert resultado.df is not None
    df = resultado.df
    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"],
            mode="lines",
            name="Precio",
            line={"color": resultado.color, "width": 1.8},
            hovertemplate="%{x|%d/%m/%Y}<br><b>$%{y:,.2f}</b><extra>Precio</extra>",
        )
    )
    figura.add_trace(
        go.Scatter(
            x=df.index,
            y=df["EMA"],
            mode="lines",
            name=f"EMA {ema_periodo}",
            line={"color": "#f2f0e9", "width": 1.35, "dash": "dot"},
            opacity=0.82,
            hovertemplate=(
                f"%{{x|%d/%m/%Y}}<br><b>$%{{y:,.2f}}</b><extra>EMA {ema_periodo}</extra>"
            ),
        )
    )
    figura.update_layout(
        autosize=True,
        height=330,
        margin={"l": 56, "r": 18, "t": 18, "b": 42},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, ui-sans-serif, system-ui, sans-serif", "color": "#a6ada8"},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#151a18", "bordercolor": "#303834"},
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.08,
            "xanchor": "left",
            "yanchor": "bottom",
            "font": {"size": 11, "color": "#a6ada8"},
        },
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showline": False,
            "tickfont": {"size": 10, "color": "#747d78"},
            "fixedrange": True,
        },
        yaxis={
            "showgrid": True,
            "gridcolor": "#252b28",
            "gridwidth": 1,
            "zeroline": False,
            "tickprefix": "$",
            "tickformat": ",.2s",
            "tickfont": {"size": 10, "color": "#747d78"},
            "fixedrange": True,
        },
    )
    return figura.to_json().replace("</", "<\\/")


def tarjeta_activo(
    resultado: AssetResult,
    indice: int,
    ema_periodo: int,
    umbral_cerca: float,
    umbral_moderado: float,
) -> tuple[str, str | None]:
    ticker = html.escape(resultado.ticker)
    nombre = html.escape(resultado.nombre)
    color = html.escape(resultado.color, quote=True)

    if resultado.error:
        tarjeta = f"""
        <article class="asset-card asset-card--error">
          <div class="asset-heading">
            <div><span class="ticker">{ticker}</span><h2>{nombre}</h2></div>
            <span class="status-pill status-pill--error">Sin datos</span>
          </div>
          <p class="error-copy">No se pudo actualizar este activo. El resto del tablero sigue disponible.</p>
        </article>
        """
        return tarjeta, None

    assert resultado.desviacion is not None
    assert resultado.precio_actual is not None
    assert resultado.promedio is not None
    assert resultado.fecha_precio is not None

    desviacion = resultado.desviacion
    direccion = "arriba" if desviacion >= 0 else "abajo"
    direccion_texto = "por encima" if desviacion >= 0 else "por debajo"
    flecha = "↑" if desviacion >= 0 else "↓"
    salud, clase_salud = clasificar_salud(
        desviacion, umbral_cerca, umbral_moderado
    )
    altura = min(48.0, max(5.0, abs(desviacion) / max(umbral_moderado, 1) * 32.0))
    chart_id = f"chart-{indice}"
    fecha = resultado.fecha_precio.strftime("%d/%m/%Y")

    tarjeta = f"""
    <article class="asset-card" style="--asset-color: {color};">
      <div class="asset-heading">
        <div>
          <span class="ticker">{ticker}</span>
          <h2>{nombre}</h2>
        </div>
        <span class="status-pill status-pill--{clase_salud}">{salud}</span>
      </div>

      <div class="asset-reading">
        <div>
          <span class="eyebrow">Precio actual</span>
          <strong class="current-price">{formato_precio(resultado.precio_actual)}</strong>
          <span class="price-date">Cierre del {fecha}</span>
        </div>
        <div class="distance-block">
          <div class="deviation deviation--{direccion}">{flecha} {desviacion:+.1f}%</div>
          <span>{direccion_texto} de su promedio</span>
        </div>
        <div class="distance-meter" aria-label="Distancia {desviacion:+.1f}%">
          <span class="meter-zero"></span>
          <span class="meter-bar meter-bar--{direccion}" style="--bar-size: {altura:.1f}%;"></span>
        </div>
      </div>

      <div id="{chart_id}" class="chart" role="img" aria-label="Precio diario y EMA {ema_periodo} de {nombre}"></div>
      <div class="card-foot">
        <span>Promedio simple oculto</span>
        <strong>{formato_precio(resultado.promedio)}</strong>
        <span>·</span>
        <span>{len(resultado.df):,} cierres</span>
      </div>
    </article>
    """
    return tarjeta, crear_figura(resultado, ema_periodo)


def construir_html(config: dict[str, Any], resultados: list[AssetResult]) -> str:
    anos = int(config.get("anos_historia", 10))
    ema_periodo = int(config.get("ema_periodo", 200))
    umbrales = config.get("umbrales_distancia", {})
    umbral_cerca = float(umbrales.get("cerca", 15))
    umbral_moderado = float(umbrales.get("moderada", 35))
    titulo = html.escape(config.get("titulo", "Mi radar de mercado"))

    tarjetas: list[str] = []
    figuras: list[str] = []
    disponibles = [resultado for resultado in resultados if resultado.error is None]
    for indice, resultado in enumerate(resultados):
        tarjeta, figura = tarjeta_activo(
            resultado,
            indice,
            ema_periodo,
            umbral_cerca,
            umbral_moderado,
        )
        tarjetas.append(tarjeta)
        if figura is not None:
            figuras.append(f'"chart-{indice}":{figura}')

    if disponibles:
        cercano = min(disponibles, key=lambda item: abs(item.desviacion or 0))
        alejado = max(disponibles, key=lambda item: abs(item.desviacion or 0))
        arriba = sum(1 for item in disponibles if (item.desviacion or 0) >= 0)
        resumen = f"""
          <div class="summary-item"><span>Más cerca</span><strong>{html.escape(cercano.ticker)}</strong><em>{cercano.desviacion:+.1f}%</em></div>
          <div class="summary-item"><span>Más alejado</span><strong>{html.escape(alejado.ticker)}</strong><em>{alejado.desviacion:+.1f}%</em></div>
          <div class="summary-item"><span>Sobre el promedio</span><strong>{arriba} de {len(disponibles)}</strong><em>activos</em></div>
        """
    else:
        resumen = "<p>No fue posible descargar datos en esta ejecución.</p>"

    actualizado = datetime.now(timezone.utc).strftime("%d/%m/%Y · %H:%M UTC")
    tarjetas_html = "\n".join(tarjetas)
    figuras_json = "{" + ",".join(figuras) + "}"

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="description" content="Dashboard personal de precio diario, EMA {ema_periodo} y distancia al promedio.">
  <title>{titulo}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
  <style>
    :root {{
      --bg: #0b0e0d;
      --surface: #121614;
      --surface-raised: #171c19;
      --line: #28302c;
      --text: #f2f0e9;
      --muted: #98a19c;
      --faint: #68716c;
      --positive: #36d48d;
      --negative: #ff6b6b;
      --amber: #f4b95f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at 8% -10%, rgba(54, 212, 141, .08), transparent 30rem),
        var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    .shell {{ width: min(1440px, calc(100% - 40px)); margin: 0 auto; }}
    .topbar {{
      min-height: 74px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; font-size: 14px; font-weight: 720; letter-spacing: .02em; }}
    .brand-mark {{ width: 11px; height: 11px; border-radius: 50%; background: var(--positive); box-shadow: 0 0 0 6px rgba(54, 212, 141, .10); }}
    .updated {{ color: var(--faint); font-size: 12px; }}
    .hero {{ padding: 68px 0 36px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, .72fr); gap: 70px; align-items: end; }}
    .kicker, .eyebrow {{ display: block; color: var(--muted); font-size: 11px; font-weight: 750; text-transform: uppercase; letter-spacing: .13em; }}
    h1 {{ margin: 13px 0 18px; max-width: 780px; font-size: clamp(42px, 6vw, 78px); line-height: .96; letter-spacing: -.055em; font-weight: 740; }}
    .intro {{ max-width: 670px; margin: 0; color: var(--muted); font-size: 16px; line-height: 1.65; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--line); border-radius: 18px; overflow: hidden; background: rgba(18,22,20,.72); }}
    .summary-item {{ padding: 20px; min-width: 0; }}
    .summary-item + .summary-item {{ border-left: 1px solid var(--line); }}
    .summary-item span, .summary-item em {{ display: block; color: var(--faint); font-size: 10px; font-style: normal; text-transform: uppercase; letter-spacing: .08em; }}
    .summary-item strong {{ display: block; margin: 12px 0 5px; font-size: 19px; letter-spacing: -.03em; }}
    .section-head {{ margin: 24px 0 18px; display: flex; align-items: end; justify-content: space-between; gap: 24px; }}
    .section-head h2 {{ margin: 0; font-size: 22px; letter-spacing: -.03em; }}
    .legend {{ display: flex; align-items: center; gap: 18px; color: var(--faint); font-size: 11px; }}
    .legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
    .legend i {{ width: 18px; height: 2px; background: var(--positive); }}
    .legend .ema-key {{ background: var(--text); opacity: .8; border-top: 1px dotted var(--bg); }}
    .asset-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; padding-bottom: 72px; }}
    .asset-card {{ position: relative; min-width: 0; padding: 24px 24px 17px; border: 1px solid var(--line); border-radius: 20px; background: linear-gradient(145deg, rgba(24,29,26,.98), rgba(16,20,18,.98)); overflow: hidden; }}
    .asset-card::before {{ content: ""; position: absolute; inset: 0 auto 0 0; width: 2px; background: var(--asset-color); opacity: .75; }}
    .asset-heading {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }}
    .ticker {{ color: var(--asset-color, var(--muted)); font-size: 12px; font-weight: 800; letter-spacing: .12em; }}
    .asset-heading h2 {{ margin: 5px 0 0; font-size: 19px; letter-spacing: -.03em; font-weight: 650; }}
    .status-pill {{ padding: 7px 10px; border: 1px solid; border-radius: 999px; font-size: 10px; font-weight: 750; white-space: nowrap; }}
    .status-pill--cerca {{ color: var(--positive); border-color: rgba(54,212,141,.28); background: rgba(54,212,141,.08); }}
    .status-pill--moderada {{ color: var(--amber); border-color: rgba(244,185,95,.28); background: rgba(244,185,95,.08); }}
    .status-pill--alejada, .status-pill--error {{ color: #ff8c78; border-color: rgba(255,107,107,.28); background: rgba(255,107,107,.08); }}
    .asset-reading {{ display: grid; grid-template-columns: 1fr auto 34px; gap: 20px; align-items: center; margin: 30px 0 8px; padding: 0 8px 24px 0; border-bottom: 1px solid var(--line); }}
    .current-price {{ display: block; margin-top: 6px; font-size: 27px; letter-spacing: -.045em; }}
    .price-date {{ display: block; margin-top: 4px; color: var(--faint); font-size: 10px; }}
    .distance-block {{ text-align: right; }}
    .distance-block > span {{ color: var(--faint); font-size: 10px; }}
    .deviation {{ font-size: 22px; font-weight: 760; letter-spacing: -.04em; }}
    .deviation--arriba {{ color: var(--positive); }}
    .deviation--abajo {{ color: var(--negative); }}
    .distance-meter {{ position: relative; width: 28px; height: 68px; border: 1px solid var(--line); border-radius: 7px; background: #0d100f; overflow: hidden; }}
    .meter-zero {{ position: absolute; left: 4px; right: 4px; top: 50%; height: 1px; background: #59625d; }}
    .meter-bar {{ position: absolute; left: 7px; right: 7px; min-height: 4px; }}
    .meter-bar--arriba {{ bottom: 50%; height: var(--bar-size); background: var(--positive); border-radius: 3px 3px 0 0; }}
    .meter-bar--abajo {{ top: 50%; height: var(--bar-size); background: var(--negative); border-radius: 0 0 3px 3px; }}
    .chart {{ width: 100%; height: 330px; }}
    .card-foot {{ display: flex; gap: 8px; align-items: center; padding-top: 10px; border-top: 1px solid var(--line); color: var(--faint); font-size: 10px; }}
    .card-foot strong {{ color: var(--muted); font-weight: 650; }}
    .asset-card--error {{ min-height: 180px; }}
    .error-copy {{ color: var(--muted); max-width: 400px; line-height: 1.6; }}
    .method {{ padding: 34px 0 72px; border-top: 1px solid var(--line); display: grid; grid-template-columns: .65fr 1.35fr; gap: 70px; }}
    .method h2 {{ margin: 0; font-size: 27px; letter-spacing: -.04em; }}
    .method p {{ margin: 0; color: var(--muted); line-height: 1.7; }}
    .method strong {{ color: var(--text); }}
    footer {{ padding: 25px 0 36px; border-top: 1px solid var(--line); color: var(--faint); font-size: 11px; display: flex; justify-content: space-between; gap: 20px; }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; gap: 34px; padding-top: 48px; }}
      .asset-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .shell {{ width: min(100% - 24px, 1440px); }}
      .topbar {{ min-height: 64px; }}
      .updated {{ max-width: 150px; text-align: right; }}
      .hero {{ padding-top: 42px; }}
      h1 {{ font-size: 46px; }}
      .summary {{ grid-template-columns: 1fr; }}
      .summary-item + .summary-item {{ border-left: 0; border-top: 1px solid var(--line); }}
      .section-head {{ align-items: flex-start; flex-direction: column; }}
      .asset-card {{ padding: 20px 16px 15px; border-radius: 16px; }}
      .asset-reading {{ grid-template-columns: 1fr 34px; }}
      .distance-block {{ grid-row: 2; grid-column: 1; text-align: left; }}
      .distance-meter {{ grid-column: 2; grid-row: 1 / span 2; }}
      .method {{ grid-template-columns: 1fr; gap: 18px; }}
      footer {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header class="shell topbar">
    <div class="brand"><span class="brand-mark"></span>{titulo}</div>
    <div class="updated">Actualizado {actualizado}</div>
  </header>

  <main class="shell">
    <section class="hero">
      <div>
        <span class="kicker">Lectura personal · sin ruido</span>
        <h1>Distancia al promedio, de un vistazo.</h1>
        <p class="intro">Cada activo muestra hasta {anos} años de cierres diarios y su EMA {ema_periodo}. La barra indica cuánto se separa el precio actual de su promedio simple: verde arriba, rojo abajo.</p>
      </div>
      <div class="summary" aria-label="Resumen del dashboard">{resumen}</div>
    </section>

    <div class="section-head">
      <h2>{len(disponibles)} activos actualizados</h2>
      <div class="legend"><span><i></i> Precio diario</span><span><i class="ema-key"></i> EMA {ema_periodo}</span></div>
    </div>

    <section class="asset-grid">{tarjetas_html}</section>

    <section class="method">
      <h2>Una regla, nada más.</h2>
      <p>El promedio se calcula sumando todos los cierres diarios disponibles dentro de los últimos {anos} años y dividiéndolos por el número de cierres. Ese promedio <strong>no aparece como línea</strong>: solo alimenta el porcentaje de distancia. Una distancia alta significa que el precio está más estirado respecto de su propia historia; no es una recomendación de compra o venta.</p>
    </section>
  </main>

  <footer class="shell">
    <span>Datos de mercado provistos por Yahoo Finance.</span>
    <span>Uso personal · La información puede tener retrasos.</span>
  </footer>

  <noscript>Necesitas activar JavaScript para ver los gráficos.</noscript>
  <script>
    const figures = {figuras_json};
    const plotConfig = {{ responsive: true, displayModeBar: false, scrollZoom: false }};
    for (const [id, figure] of Object.entries(figures)) {{
      Plotly.newPlot(id, figure.data, figure.layout, plotConfig);
    }}
  </script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    try:
        config = cargar_configuracion(args.config.resolve())
        anos = int(config.get("anos_historia", 10))
        ema_periodo = int(config.get("ema_periodo", 200))
        tickers = [activo["ticker"].strip().upper() for activo in config["activos"]]
        print(f"Descargando {len(tickers)} activos en un solo lote...")
        datos = descargar_datos(tickers, anos, ema_periodo)
        resultados = []

        print("Construyendo tarjetas...")
        for activo in config["activos"]:
            ticker = activo["ticker"].strip().upper()
            print(f"  - {ticker}...", end=" ", flush=True)
            resultado = procesar_activo(activo, datos)
            resultados.append(resultado)
            print("listo" if resultado.error is None else f"sin datos ({resultado.error})")

        if not any(resultado.error is None for resultado in resultados):
            print("Error: ningún activo pudo actualizarse.")
            return 1

        salida = args.output.resolve()
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(construir_html(config, resultados), encoding="utf-8")
        print(f"Dashboard generado: {salida}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error de configuración: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
