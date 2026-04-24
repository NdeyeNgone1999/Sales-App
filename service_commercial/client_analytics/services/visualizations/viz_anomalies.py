"""Visualisations pour les anomalies de portefeuille client."""

from __future__ import annotations

import pandas as pd


def create_client_anomalies_scatter(df_latest: pd.DataFrame, z_thresh: float = 3.5) -> str | None:
    """Scatter Plotly: Score vs CA (dernière période).

    Retourne un HTML Plotly (str) ou None.
    """
    if df_latest is None or df_latest.empty:
        return None

    if '_score' not in df_latest.columns or 'CA' not in df_latest.columns or 'Client' not in df_latest.columns:
        return None

    try:
        import plotly.express as px

        d = df_latest.copy()
        d['_is_anomaly'] = d.get('_is_anomaly', False)
        d['_label'] = d['_is_anomaly'].map({True: f"Anomalie (≥ {z_thresh})", False: 'Normal'})
        fig = px.scatter(
            d,
            x='CA',
            y='_score',
            color='_label',
            hover_name='Client',
            hover_data={'_period_label': True, 'CA': ':.0f', '_score': ':.2f'},
            title='Anomalies portefeuille client — Dernière période',
        )
        fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=20))
        return fig.to_html(full_html=False, include_plotlyjs=False)
    except Exception:
        return None
