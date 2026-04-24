"""
Visualisations pour le sous-onglet SÉRIE TEMPORELLE
"""

from __future__ import annotations

import logging

import pandas as pd
import numpy as np

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

logger = logging.getLogger(__name__)

try:
    from statsmodels.tsa.seasonal import STL
except Exception:
    STL = None


def _compute_strength(component: pd.Series, resid: pd.Series) -> float | None:
    """Force Cleveland (trend/seasonal).

    var_resid = Var(resid)
    strength = max(0, 1 - var_resid / Var(component + resid))
    """
    try:
        resid_v = pd.to_numeric(resid, errors="coerce").dropna().values
        comp_v = pd.to_numeric(component, errors="coerce").dropna().values
        if len(resid_v) < 10 or len(comp_v) < 10:
            return None
        n = min(len(resid_v), len(comp_v))
        resid_v = resid_v[-n:]
        comp_v = comp_v[-n:]
        var_resid = float(pd.Series(resid_v).var(ddof=0))
        var_denom = float(pd.Series(comp_v + resid_v).var(ddof=0))
        if var_denom <= 0:
            return None
        strength = max(0.0, 1.0 - (var_resid / var_denom))
        return round(strength, 3)
    except Exception:
        return None


def create_stl_decomposition_plot(
    df_daily: pd.DataFrame, df_display: pd.DataFrame, display_granularity: str = "month"
):
    """
    Décomposition STL calculée TOUJOURS sur la granularité choisie (df_display).
    df_daily n'est jamais utilisé — conservé pour compatibilité de signature.

    - month   → STL sur données mensuelles, period=12
    - quarter → STL sur données trimestrielles, period=4
    - year    → graphique en barres (trop peu de points pour STL)

    Si df_display n'a pas assez de points pour STL, affiche un graphique
    linéaire + moyenne mobile à la même granularité (jamais de retour au journalier).

    Returns:
        tuple[str|None, dict]: (html_plotly, metrics_dict)
    """
    metrics = {}

    # df_display a un index string ("YYYY-MM", "2024Q1", "FY2024") — on garde les labels tels quels
    if df_display is None or df_display.empty or "CA_Total" not in df_display.columns:
        return None, metrics

    y = pd.to_numeric(df_display["CA_Total"], errors="coerce").fillna(0)
    x_labels = df_display.index.astype(str).tolist()
    n = len(y)

    if n < 2:
        return None, metrics

    try:
        # ── Année fiscale : barres simples ─────────────────────────────────────
        if display_granularity == "year":
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=x_labels, y=y.tolist(),
                name="CA annuel", marker_color="#2E86AB",
            ))
            fig.update_layout(
                title="CA annuel (granularité annuelle — STL non applicable)",
                height=350,
                margin=dict(l=50, r=20, t=60, b=40),
            )
            html = pio.to_html(
                fig, full_html=False, include_plotlyjs="cdn",
                config={"displayModeBar": False, "responsive": True},
            )
            return html, metrics

        # ── Mensuel / Trimestriel : STL ou fallback linéaire ──────────────────
        stl_period = 12 if display_granularity == "month" else 4
        gran_label = "mensuelle" if display_granularity == "month" else "trimestrielle"

        # statsmodels STL minimum : period + 1 pour les filtres saisonniers
        can_stl = (
            STL is not None
            and n >= stl_period + 1
            and y.nunique(dropna=True) > 1
        )

        if can_stl:
            stl = STL(y, period=stl_period, robust=True)
            stl_res = stl.fit()

            metrics["stl_period"] = stl_period
            metrics["stl_trend_strength"] = _compute_strength(stl_res.trend, stl_res.resid)
            metrics["stl_seasonal_strength"] = _compute_strength(stl_res.seasonal, stl_res.resid)

            fig = make_subplots(
                rows=4, cols=1,
                shared_xaxes=True,
                subplot_titles=(
                    f"Observé ({gran_label})",
                    f"Tendance ({gran_label})",
                    f"Saisonnalité ({gran_label})",
                    f"Résidu ({gran_label})",
                ),
                vertical_spacing=0.06,
            )
            fig.add_trace(go.Scatter(
                x=x_labels, y=stl_res.observed.values.tolist(),
                name="Observé", line=dict(color="#2E86AB", width=1.2), showlegend=False,
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=x_labels, y=stl_res.trend.values.tolist(),
                name="Tendance", line=dict(color="#F18F01", width=1.5), showlegend=False,
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=x_labels, y=stl_res.seasonal.values.tolist(),
                name="Saisonnalité", line=dict(color="#9B5DE5", width=1.0), showlegend=False,
            ), row=3, col=1)
            fig.add_trace(go.Scatter(
                x=x_labels, y=stl_res.resid.values.tolist(),
                name="Résidu", line=dict(color="#00BBF9", width=0.9), showlegend=False,
            ), row=4, col=1)
            fig.update_layout(height=700, margin=dict(l=50, r=20, t=60, b=40))

        else:
            # Pas assez de points pour STL — ligne + moyenne mobile, même granularité
            rolling_w = max(2, min(stl_period // 2, n // 2))
            y_ma = y.rolling(window=rolling_w, min_periods=1).mean()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x_labels, y=y.tolist(),
                name=f"CA {gran_label}", line=dict(color="#2E86AB", width=1.3),
            ))
            fig.add_trace(go.Scatter(
                x=x_labels, y=y_ma.tolist(),
                name="Moyenne mobile", line=dict(color="#F18F01", width=1.1, dash="dash"),
            ))
            fig.update_layout(
                title=f"CA {gran_label} (données insuffisantes pour STL complet)",
                height=350,
                margin=dict(l=50, r=20, t=60, b=40),
            )

        html = pio.to_html(
            fig, full_html=False, include_plotlyjs="cdn",
            config={"displayModeBar": False, "responsive": True},
        )
        return html, metrics

    except Exception:
        logger.exception("Erreur lors de la création du graphique STL")
        return None, {}


def create_anomaly_dashboard_plot(anom_map, title: str = "Détection d'anomalies") -> None:
    """Stub — anomaly detection section removed from template."""
    return None
