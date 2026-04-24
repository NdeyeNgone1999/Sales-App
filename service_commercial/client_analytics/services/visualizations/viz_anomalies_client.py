import base64
from io import BytesIO

import numpy as np
import pandas as pd


def _fig_to_base64_png(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def plot_client_timeline(
    series: list[dict], client_id: str, granularity: str
) -> str | None:
    """Graph 2x2 des métriques (valeurs) + points rouges sur périodes anormales détectées par ML."""
    if not series:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    df = pd.DataFrame(series).copy()
    if df.empty or "period" not in df.columns:
        return None

    df["period"] = df["period"].astype(str)

    metrics = [
        ("ca", "is_anomaly_ca", "CA (Montant)"),
        ("freq", "is_anomaly_freq", "Fréquence d'achat"),
        ("qty", "is_anomaly_qty", "Quantité"),
        ("price", "is_anomaly_price", "Prix moyen"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    axes = axes.ravel()

    x = np.arange(len(df))
    xlabels = df["period"].tolist()

    for ax, (val_col, flag_col, title) in zip(axes, metrics, strict=False):
        if val_col not in df.columns:
            ax.axis("off")
            continue

        y = pd.to_numeric(df[val_col], errors="coerce")

        # Ligne normale en bleu
        ax.plot(x, y, linewidth=2, color="#2E86AB", alpha=0.7, label="Valeurs")

        # Points rouges pour anomalies
        if flag_col in df.columns:
            mask = df[flag_col].fillna(False).astype(bool) & y.notna()
            if mask.any():
                ax.scatter(
                    x[mask.to_numpy()],
                    y[mask],
                    color="#E63946",
                    s=80,
                    zorder=3,
                    label="Anomalies ML",
                    edgecolors="darkred",
                    linewidth=1.5,
                )

        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(loc="best", fontsize=8)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=9)

    fig.suptitle(
        f"Détection d'anomalies ML (Isolation Forest) — Client {client_id}\nGranularité: {granularity}",
        y=0.98,
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()

    png = _fig_to_base64_png(fig)
    plt.close(fig)
    return png


def plot_anomaly_scores_timeline(
    series: list[dict], client_id: str, granularity: str
) -> str | None:
    """Graphique des scores d'anomalie ML au fil du temps."""
    if not series:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    df = pd.DataFrame(series).copy()
    if df.empty or "period" not in df.columns or "anomaly_score_ml" not in df.columns:
        return None

    df["period"] = df["period"].astype(str)
    df["anomaly_score_ml"] = pd.to_numeric(df["anomaly_score_ml"], errors="coerce")
    df["is_anomaly_ml"] = df.get("is_anomaly_ml", False).fillna(False)

    if df["anomaly_score_ml"].isna().all():
        return None

    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(df))
    scores = df["anomaly_score_ml"].to_numpy()

    # Barres de score
    colors = ["#E63946" if is_anom else "#A8DADC" for is_anom in df["is_anomaly_ml"]]
    ax.bar(x, scores, color=colors, alpha=0.7, edgecolor="black", linewidth=0.5)

    # Ligne de seuil (indicative)
    if df["is_anomaly_ml"].any():
        threshold = df[df["is_anomaly_ml"]]["anomaly_score_ml"].min()
        ax.axhline(
            y=threshold,
            color="red",
            linestyle="--",
            linewidth=1.5,
            label=f"Seuil détection (~{threshold:.2f})",
            alpha=0.7,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(df["period"].tolist(), rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Score d'anomalie", fontsize=11)
    ax.set_title(
        f"Évolution des scores d'anomalie ML — Client {client_id}\nGranularité: {granularity}",
        fontsize=12,
        fontweight="bold",
    )
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    ax.legend(loc="best", fontsize=9)

    fig.tight_layout()
    png = _fig_to_base64_png(fig)
    plt.close(fig)
    return png


def plot_multi_clients_anomaly_counts(
    reports: list[dict], granularity: str
) -> str | None:
    """Barres empilées: nb d'anomalies par métrique et par client."""
    if not reports:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    rows = []
    for rep in reports:
        client_id = ((rep.get("client") or {}).get("id")) or "—"
        kpis = rep.get("kpis") or {}
        rows.append(
            {
                "client": str(client_id),
                "CA": int(kpis.get("n_anomalies_ca") or 0),
                "Freq": int(kpis.get("n_anomalies_freq") or 0),
                "Qty": int(kpis.get("n_anomalies_qty") or 0),
                "Price": int(kpis.get("n_anomalies_price") or 0),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return None

    df = df.sort_values(["CA", "Freq", "Qty", "Price"], ascending=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(df))

    bottom = np.zeros(len(df))
    for col, label in [
        ("CA", "CA"),
        ("Freq", "Fréq."),
        ("Qty", "Qté"),
        ("Price", "Prix"),
    ]:
        vals = df[col].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, label=label)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(df["client"].tolist(), rotation=45, ha="right")
    ax.set_ylabel("Nombre d'anomalies")
    ax.set_title(f"Anomalies détectées — clients sélectionnés ({granularity})")
    ax.grid(True, axis="y", alpha=0.2)
    ax.legend(ncol=4, fontsize=9)

    fig.tight_layout()
    png = _fig_to_base64_png(fig)
    plt.close(fig)
    return png


def plot_top_anomalies(rows: list[dict], granularity: str, title: str) -> str | None:
    """Barres horizontales: score des top anomalies (global)."""
    if not rows:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    labels = []
    scores = []
    for r in rows:
        client = r.get("client")
        period = r.get("period")
        score = r.get("score")
        if score is None or (isinstance(score, float) and np.isnan(score)):
            continue
        labels.append(f"{client} — {period}")
        scores.append(float(score))

    if not scores:
        return None

    # Limiter le nombre de barres
    labels = labels[:20]
    scores = scores[:20]

    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(scores))
    ax.barh(y, scores)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Score (z robuste)")
    ax.set_title(f"{title} ({granularity})")
    ax.grid(True, axis="x", alpha=0.2)

    fig.tight_layout()
    png = _fig_to_base64_png(fig)
    plt.close(fig)
    return png
