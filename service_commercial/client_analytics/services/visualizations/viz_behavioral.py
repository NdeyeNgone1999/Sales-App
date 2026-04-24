"""
Visualisations Plotly pour le monitoring comportemental client.
"""
from __future__ import annotations
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

logger = logging.getLogger(__name__)

# Consistent colors
C_OBSERVED  = "#2E86AB"
C_BASELINE  = "#F18F01"
C_BAND      = "rgba(241,143,1,0.12)"
C_ALERT     = "#E84855"
C_GREEN     = "#2dc653"
C_ORANGE    = "#F18F01"
C_RED       = "#E84855"
C_CUSUM_POS = "#E84855"
C_CUSUM_NEG = "#9B5DE5"


def _plotly_html(fig) -> str:
    return pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False, "responsive": True},
    )


def create_client_timeline_chart(client_data: dict) -> str | None:
    """
    Create a 4-panel Plotly chart for client deep-dive:
    Row 1: CA with baseline band + ±2σ
    Row 2: Quantity + Unit Price (dual axis)
    Row 3: nb_families + HHI (product diversity)
    Row 4: Alert Score over time with threshold lines
    """
    try:
        periods = client_data.get("periods", [])
        signals = client_data.get("signals_data", {})
        alert_scores = client_data.get("alert_score_history", [])
        cusum = client_data.get("cusum", {})

        if not periods:
            return None

        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            subplot_titles=(
                "Chiffre d'Affaires vs Baseline",
                "Quantité & Prix Unitaire",
                "Diversité Produits",
                "Score d'Alerte",
            ),
            vertical_spacing=0.07,
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": True}],
                [{"secondary_y": True}],
                [{"secondary_y": False}],
            ],
        )

        # ── Row 1: CA with baseline band ────────────────────────────────────
        ca = signals.get("ca", {})
        if ca.get("values"):
            # Band ±2σ
            upper = ca.get("base_upper", [None]*len(periods))
            lower = ca.get("base_lower", [None]*len(periods))
            valid_upper = [v for v in upper if v is not None]
            valid_lower = [v for v in lower if v is not None]
            if valid_upper:
                fig.add_trace(go.Scatter(
                    x=periods, y=upper, mode="lines",
                    line=dict(width=0), showlegend=False, hoverinfo="skip",
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=periods, y=lower, mode="lines",
                    fill="tonexty", fillcolor=C_BAND,
                    line=dict(width=0), showlegend=False, hoverinfo="skip",
                    name="Bande ±2σ",
                ), row=1, col=1)

            # Baseline mean
            if ca.get("base_mean"):
                fig.add_trace(go.Scatter(
                    x=periods, y=ca["base_mean"], mode="lines",
                    name="Baseline (moy. 6M)", line=dict(color=C_BASELINE, width=1.5, dash="dash"),
                ), row=1, col=1)

            # Actual CA
            fig.add_trace(go.Scatter(
                x=periods, y=ca["values"], mode="lines+markers",
                name="CA réel", line=dict(color=C_OBSERVED, width=2),
                marker=dict(size=5),
            ), row=1, col=1)

        # ── Row 2: Qty + PU ─────────────────────────────────────────────────
        qty = signals.get("qty", {})
        pu  = signals.get("pu", {})
        if qty.get("values"):
            fig.add_trace(go.Bar(
                x=periods, y=qty["values"],
                name="Quantité", marker_color="rgba(46,134,171,0.5)",
            ), row=2, col=1)
        if pu.get("values"):
            fig.add_trace(go.Scatter(
                x=periods, y=pu["values"], mode="lines+markers",
                name="Prix unitaire (€)", line=dict(color=C_ORANGE, width=1.5),
                marker=dict(size=4),
            ), row=2, col=1, secondary_y=True)

        # ── Row 3: nb_families + HHI ─────────────────────────────────────────
        fam = signals.get("nb_families", {})
        hhi = signals.get("hhi", {})
        if fam.get("values"):
            fig.add_trace(go.Scatter(
                x=periods, y=fam["values"], mode="lines+markers",
                name="Nb familles", line=dict(color="#00BBF9", width=1.8),
                marker=dict(size=5),
            ), row=3, col=1)
        if hhi.get("values"):
            fig.add_trace(go.Scatter(
                x=periods, y=hhi["values"], mode="lines",
                name="HHI concentration", line=dict(color="#9B5DE5", width=1.5, dash="dot"),
            ), row=3, col=1, secondary_y=True)

        # ── Row 4: Alert Score ───────────────────────────────────────────────
        if alert_scores:
            # Color each bar based on classification
            bar_colors = [
                C_RED if v >= 60 else (C_ORANGE if v >= 30 else C_GREEN)
                for v in alert_scores
            ]
            fig.add_trace(go.Bar(
                x=periods, y=alert_scores,
                name="Score d'alerte", marker_color=bar_colors, showlegend=False,
            ), row=4, col=1)
            # Threshold lines
            fig.add_hline(y=30, line_dash="dash", line_color=C_ORANGE, line_width=1, row=4, col=1)
            fig.add_hline(y=60, line_dash="dash", line_color=C_RED, line_width=1, row=4, col=1)

        fig.update_layout(
            height=850,
            margin=dict(l=50, r=30, t=80, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="CA (€)", row=1, col=1)
        fig.update_yaxes(title_text="Quantité", row=2, col=1)
        fig.update_yaxes(title_text="Prix (€)", row=2, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Nb familles", row=3, col=1)
        fig.update_yaxes(title_text="HHI", row=3, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Score (0-100)", row=4, col=1, range=[0, 105])

        return _plotly_html(fig)

    except Exception:
        logger.exception("create_client_timeline_chart failed")
        return None


def create_cusum_chart(client_data: dict) -> str | None:
    """CUSUM bilateral chart for CA anomaly detection."""
    try:
        periods = client_data.get("periods", [])
        cusum   = client_data.get("cusum", {})
        if not periods or not cusum:
            return None

        s_pos = cusum.get("s_pos", [])
        s_neg = cusum.get("s_neg", [])
        h     = cusum.get("threshold", 4.0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=periods, y=s_pos, mode="lines+markers",
            name="CUSUM+ (hausse anormale)", line=dict(color=C_CUSUM_POS, width=2),
            marker=dict(size=4),
        ))
        fig.add_trace(go.Scatter(
            x=periods, y=s_neg, mode="lines+markers",
            name="CUSUM− (baisse anormale)", line=dict(color=C_CUSUM_NEG, width=2),
            marker=dict(size=4),
        ))
        fig.add_hline(y=h, line_dash="dash", line_color="#888", annotation_text=f"Seuil h={h}")

        fig.update_layout(
            title="CUSUM — Détection de changement structurel (CA)",
            height=320,
            margin=dict(l=50, r=20, t=50, b=40),
            hovermode="x unified",
        )
        return _plotly_html(fig)

    except Exception:
        logger.exception("create_cusum_chart failed")
        return None


def create_radar_chart(client_data: dict) -> str | None:
    """Radar chart: current month vs baseline for key signals."""
    try:
        latest  = client_data.get("latest_values", {})
        baseline = client_data.get("baseline_values", {})

        radar_signals = ["ca", "qty", "nb_orders", "nb_families", "active_days"]
        labels = ["CA", "Quantité", "Commandes", "Familles", "Activité"]

        def _normalize(vals: list[float | None], refs: list[float | None]) -> list[float]:
            out = []
            for v, r in zip(vals, refs):
                if v is None or r is None or r == 0:
                    out.append(0.0)
                else:
                    out.append(round(v / r * 100, 1))
            return out

        cur_vals = [latest.get(s) for s in radar_signals]
        bas_vals = [baseline.get(s) for s in radar_signals]
        cur_norm = _normalize(cur_vals, bas_vals)
        bas_norm = [100.0] * len(radar_signals)

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=bas_norm + [bas_norm[0]],
            theta=labels + [labels[0]],
            mode="lines",
            name="Baseline (100%)",
            line=dict(color=C_BASELINE, dash="dash", width=2),
            fill="toself",
            fillcolor="rgba(241,143,1,0.05)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=cur_norm + [cur_norm[0]],
            theta=labels + [labels[0]],
            mode="lines+markers",
            name="Mois actuel",
            line=dict(color=C_OBSERVED, width=2),
            fill="toself",
            fillcolor="rgba(46,134,171,0.15)",
            marker=dict(size=6),
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max(max(cur_norm + [0]), 150)])),
            title="Profil actuel vs Baseline",
            height=400,
            margin=dict(l=50, r=50, t=60, b=40),
            legend=dict(orientation="h", y=-0.15),
        )
        return _plotly_html(fig)

    except Exception:
        logger.exception("create_radar_chart failed")
        return None
