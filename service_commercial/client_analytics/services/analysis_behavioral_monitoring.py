"""
Moteur de Monitoring Comportemental Client
==========================================
Détecte les changements de comportement d'achat client via signaux multi-dimensionnels:
  - Z-scores robustes (MAD) par rapport à une baseline glissante de 6 mois
  - CUSUM bilatéral sur le CA normalisé
  - Score d'alerte composite pondéré (0-100)
  - Attribution automatique (explanation du signal déclencheur)

Granularité: MENSUELLE uniquement.
"""

from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from typing import Any

logger = logging.getLogger(__name__)

# ─── Signal definitions (key → (short_label, long_label, weight, higher_is_bad)) ─
# higher_is_bad: True means a positive z-score is BAD (e.g., HHI concentration)
SIGNALS: dict[str, tuple[str, str, float, bool]] = {
    "ca":          ("CA",          "Chiffre d'affaires",       0.30, False),
    "qty":         ("Qté",         "Quantité achetée",         0.15, False),
    "pu":          ("PU",          "Prix unitaire moyen",      0.08, False),
    "nb_orders":   ("Commandes",   "Fréquence de commandes",   0.15, False),
    "nb_families": ("Familles",    "Diversité familles",       0.15, False),
    "hhi":         ("Concentr.",   "Concentration produits",   0.12, True),
    "active_days": ("Activité",    "Jours d'activité",         0.05, False),
}

CUSUM_K = 0.5   # slack factor
CUSUM_H = 4.0   # decision threshold
BASELINE_WINDOW = 6   # months used for rolling baseline

# Alert score thresholds
THRESH_GREEN  = 30
THRESH_ORANGE = 60


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _to_period_month(date_series: pd.Series) -> pd.Series:
    return pd.to_datetime(date_series, errors="coerce", dayfirst=True).dt.to_period("M")


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def _build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Build (client × month) feature matrix. Returns (features_df, col_map)."""
    col_map = {
        "client":  _pick_col(df, ["Cpt Client", "Compte Client", "Client", "Code Client"]),
        "date":    _pick_col(df, ["Date Fact.", "Date_Ref", "Date", "Date facture", "Date Facture"]),
        "amount":  _pick_col(df, ["Montant", "CA", "CA Net", "Chiffre d'Affaires"]),
        "qty":     _pick_col(df, ["Quantité", "Quantite", "Qty", "Qte", "Qté", "Quantity"]),
        "order":   _pick_col(df, ["N° Bon", "No Bon", "N Bon", "Num Bon", "Numéro Bon", "Commande", "N° Commande", "Order"]),
        "family":  _pick_col(df, ["Famille Produits", "Famille", "Famille Prod.", "Categorie", "Category"]),
        "product": _pick_col(df, ["Ref Produit", "Article", "Produit", "Product", "Réf. Produit"]),
    }

    if not col_map["client"] or not col_map["date"] or not col_map["amount"]:
        return pd.DataFrame(), col_map

    work = df.copy()
    work["_month"] = _to_period_month(work[col_map["date"]])
    work["_date_dt"] = pd.to_datetime(work[col_map["date"]], errors="coerce", dayfirst=True).dt.normalize()
    work[col_map["amount"]] = pd.to_numeric(work[col_map["amount"]], errors="coerce")
    work = work.dropna(subset=["_month", col_map["amount"], col_map["client"]])

    cc = col_map["client"]
    grp = work.groupby([cc, "_month"])

    # Basic aggregations
    feat = grp[col_map["amount"]].sum().rename("ca").to_frame()

    if col_map["qty"]:
        work[col_map["qty"]] = pd.to_numeric(work[col_map["qty"]], errors="coerce")
        feat["qty"] = grp[col_map["qty"]].sum()
        feat["pu"] = feat["ca"] / feat["qty"].replace(0, np.nan)
    else:
        feat["qty"] = np.nan
        feat["pu"] = np.nan

    order_col = col_map["order"] if col_map["order"] else col_map["amount"]
    feat["nb_orders"] = grp[order_col].nunique() if col_map["order"] else grp[col_map["amount"]].count()

    feat["active_days"] = work.groupby([cc, "_month"])["_date_dt"].nunique()

    if col_map["family"]:
        feat["nb_families"] = grp[col_map["family"]].nunique()
        # HHI of product families
        fam_ca = work.groupby([cc, "_month", col_map["family"]])[col_map["amount"]].sum().reset_index()
        fam_ca.columns = ["_client", "_month", "_fam", "_fam_ca"]
        total_ca = fam_ca.groupby(["_client", "_month"])["_fam_ca"].transform("sum")
        fam_ca["_share"] = fam_ca["_fam_ca"] / total_ca.replace(0, np.nan)
        hhi_series = (
            fam_ca.groupby(["_client", "_month"])["_share"]
            .apply(lambda s: float((s ** 2).sum() * 10000))
        )
        hhi_series.index.names = [cc, "_month"]
        feat["hhi"] = hhi_series
    else:
        feat["nb_families"] = np.nan
        feat["hhi"] = np.nan

    return feat, col_map


# ─────────────────────────────────────────────────────────────────────────────
# Z-SCORES (ROBUST MAD-BASED)
# ─────────────────────────────────────────────────────────────────────────────

def _robust_zscore_series(s: pd.Series, window: int = BASELINE_WINDOW, min_periods: int = 3) -> pd.Series:
    """MAD-based z-score vs rolling shifted baseline (no leakage)."""
    hist = s.shift(1)
    median = hist.rolling(window=window, min_periods=min_periods).median()
    mad = (hist - median).abs().rolling(window=window, min_periods=min_periods).median()
    z = 0.6745 * (s - median) / mad.replace(0, np.nan)
    # MAD==0 edge case
    z = z.where(mad != 0).fillna(
        (s - median).apply(lambda v: 0.0 if v == 0 else (999.0 if v > 0 else -999.0))
    )
    return z


def _compute_zscores(client_feat: pd.DataFrame) -> pd.DataFrame:
    """Compute per-signal z-scores for a single client's feature history."""
    zscores = pd.DataFrame(index=client_feat.index)
    for sig in SIGNALS:
        if sig not in client_feat.columns:
            zscores[sig] = np.nan
            continue
        s = pd.to_numeric(client_feat[sig], errors="coerce")
        # For HHI: higher = more concentrated = bad = positive z_bad
        z = _robust_zscore_series(s)
        if SIGNALS[sig][3]:  # higher_is_bad → negate so positive z = bad
            pass  # keep sign; positive z on HHI means more concentrated (bad)
        else:
            pass  # negative z on CA means lower revenue (bad)
        zscores[sig] = z
    return zscores


# ─────────────────────────────────────────────────────────────────────────────
# CUSUM
# ─────────────────────────────────────────────────────────────────────────────

def _cusum(z_series: pd.Series, k: float = CUSUM_K) -> tuple[pd.Series, pd.Series]:
    """Bilateral CUSUM on z-scores. Returns (s_pos, s_neg)."""
    vals = pd.to_numeric(z_series, errors="coerce").fillna(0).values
    s_pos = np.zeros(len(vals))
    s_neg = np.zeros(len(vals))
    for i in range(1, len(vals)):
        s_pos[i] = max(0.0, s_pos[i - 1] + vals[i] - k)
        s_neg[i] = max(0.0, s_neg[i - 1] - vals[i] - k)
    return pd.Series(s_pos, index=z_series.index), pd.Series(s_neg, index=z_series.index)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT SCORE & CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def _alert_score(zscores_row: dict[str, float], cusum_s_neg: float, cusum_s_pos: float) -> float:
    """Compute alert score 0-100 from z-scores and CUSUM.

    Orientation: NEGATIVE z on CA/qty/nb_orders/nb_families/active_days → bad (revenue drop, disengagement)
                 POSITIVE z on HHI → bad (product concentration)
    """
    raw = 0.0
    for sig, (_, _, weight, higher_is_bad) in SIGNALS.items():
        z = zscores_row.get(sig)
        if z is None or np.isnan(z):
            continue
        if higher_is_bad:
            bad_z = max(0.0, z)        # positive z on HHI = bad
        else:
            bad_z = max(0.0, -z)       # negative z on CA etc. = bad
        raw += weight * min(bad_z, 3.0) / 3.0

    # CUSUM bonus: accumulation indicates sustained trend
    max_cusum = max(float(cusum_s_neg), float(cusum_s_pos), 0.0)
    cusum_ratio = min(max_cusum / (CUSUM_H * 2), 1.0)

    # 70% from z-scores, 30% from CUSUM
    score = raw * 70.0 + cusum_ratio * 30.0
    return round(min(100.0, score), 1)


def _classify(score: float) -> str:
    if score >= THRESH_ORANGE:
        return "red"
    if score >= THRESH_GREEN:
        return "orange"
    return "green"


# ─────────────────────────────────────────────────────────────────────────────
# ATTRIBUTION (natural language)
# ─────────────────────────────────────────────────────────────────────────────

_SIGNAL_TEMPLATES = {
    "ca": {
        "neg": "baisse significative du chiffre d'affaires ({pct:+.0f}% vs baseline)",
        "pos": "hausse du chiffre d'affaires ({pct:+.0f}% vs baseline)",
    },
    "qty": {
        "neg": "réduction des volumes achetés ({pct:+.0f}%)",
        "pos": "augmentation des volumes achetés ({pct:+.0f}%)",
    },
    "pu": {
        "neg": "baisse du prix unitaire moyen ({pct:+.0f}%)",
        "pos": "hausse du prix unitaire moyen ({pct:+.0f}%)",
    },
    "nb_orders": {
        "neg": "diminution de la fréquence de commandes ({pct:+.0f}%)",
        "pos": "augmentation de la fréquence de commandes ({pct:+.0f}%)",
    },
    "nb_families": {
        "neg": "rétrécissement du portefeuille produits — perte de familles ({pct:+.0f}%)",
        "pos": "élargissement du portefeuille produits ({pct:+.0f}%)",
    },
    "hhi": {
        "pos": "concentration croissante sur peu de familles produits ({pct:+.0f}%)",
        "neg": "diversification du mix produits ({pct:+.0f}%)",
    },
    "active_days": {
        "neg": "baisse des jours d'activité ({pct:+.0f}%)",
        "pos": "hausse des jours d'activité ({pct:+.0f}%)",
    },
}

def _generate_attribution(
    zscores: dict[str, float],
    current: dict[str, float],
    baseline: dict[str, float],
    cusum_breached: bool,
) -> str:
    """Generate a natural language explanation of the alert signals."""
    # Compute "badness" per signal
    bad_items = []
    for sig, (_, _, _, higher_is_bad) in SIGNALS.items():
        z = zscores.get(sig)
        if z is None or np.isnan(z):
            continue
        if higher_is_bad:
            bad_z = z        # positive z on HHI is bad
        else:
            bad_z = -z       # negative z on others is bad
        if bad_z > 1.0:
            bad_items.append((bad_z, sig))

    if not bad_items:
        return "Aucun signal d'alerte significatif détecté. Comportement conforme à l'historique."

    bad_items.sort(reverse=True)
    top = bad_items[:3]

    parts = []
    for _, sig in top:
        z = zscores.get(sig, 0)
        cur_val = current.get(sig)
        bas_val = baseline.get(sig)
        if cur_val is not None and bas_val and abs(bas_val) > 0:
            pct = (cur_val - bas_val) / abs(bas_val) * 100
        else:
            pct = 0.0

        tmpl = _SIGNAL_TEMPLATES.get(sig, {})
        if z < 0:
            msg = tmpl.get("neg", f"{sig} anormalement bas").format(pct=pct)
        else:
            msg = tmpl.get("pos", f"{sig} anormalement haut").format(pct=pct)
        parts.append(f"• {msg}")

    prefix = "⚠️ CUSUM déclenché — changement structurel détecté. " if cusum_breached else ""
    return prefix + "Signaux détectés :\n" + "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze_portfolio(df: pd.DataFrame) -> dict[str, Any]:
    """Compute alert scores for all clients. Returns portfolio summary dict."""
    if df is None or df.empty:
        return {"error": "DataFrame vide", "portfolio": [], "counts": {}}

    try:
        feat, col_map = _build_feature_matrix(df)
    except Exception:
        logger.exception("_build_feature_matrix failed")
        return {"error": "Erreur lors du calcul des features", "portfolio": [], "counts": {}}

    if feat.empty:
        missing = [k for k, v in col_map.items() if v is None and k in ("client", "date", "amount")]
        return {"error": f"Colonnes requises manquantes: {missing}", "portfolio": [], "counts": {}}

    client_col = col_map["client"]
    clients = feat.index.get_level_values(0).unique()
    results = []

    for client_id in clients:
        try:
            row = _compute_single_client(feat, client_id)
            if row:
                results.append(row)
        except Exception:
            logger.debug("Skipping client %s", client_id, exc_info=True)

    results.sort(key=lambda r: r["alert_score"], reverse=True)
    counts = {"red": 0, "orange": 0, "green": 0}
    for r in results:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1

    latest_period = str(feat.index.get_level_values(1).max()) if not feat.empty else ""

    return {
        "portfolio": results,
        "counts": counts,
        "latest_period": latest_period,
        "col_map": col_map,
    }


def _compute_single_client(feat: pd.DataFrame, client_id) -> dict | None:
    """Compute alert score for one client (latest available month)."""
    try:
        client_feat = feat.xs(client_id, level=0).sort_index()
    except KeyError:
        return None
    if len(client_feat) < 2:
        return None

    zscores_df = _compute_zscores(client_feat)
    ca_z = zscores_df.get("ca", pd.Series(dtype=float))
    s_pos, s_neg = _cusum(ca_z)

    latest_z = zscores_df.iloc[-1].to_dict()
    latest_vals = client_feat.iloc[-1].to_dict()
    cusum_s_pos_latest = float(s_pos.iloc[-1])
    cusum_s_neg_latest = float(s_neg.iloc[-1])
    cusum_breached = max(cusum_s_pos_latest, cusum_s_neg_latest) >= CUSUM_H

    score = _alert_score(latest_z, cusum_s_neg_latest, cusum_s_pos_latest)
    classification = _classify(score)

    # Top signal
    best_sig = max(
        [sig for sig in SIGNALS if latest_z.get(sig) is not None and not np.isnan(latest_z.get(sig, np.nan))],
        key=lambda s: abs(latest_z.get(s, 0) or 0),
        default=None,
    )

    # CA baseline (mean of previous months)
    ca_hist = pd.to_numeric(client_feat["ca"], errors="coerce")
    baseline_ca = float(ca_hist.iloc[:-1].tail(BASELINE_WINDOW).mean()) if len(ca_hist) > 1 else None
    latest_ca = float(ca_hist.iloc[-1]) if not pd.isna(ca_hist.iloc[-1]) else None
    ca_pct_change = None
    if baseline_ca and baseline_ca > 0 and latest_ca is not None:
        ca_pct_change = round((latest_ca - baseline_ca) / baseline_ca * 100, 1)

    # 6-month CA sparkline
    ca_trend = [
        round(float(v), 0) if not pd.isna(v) else 0
        for v in ca_hist.tail(6).values
    ]

    return {
        "client_id": str(client_id),
        "alert_score": score,
        "classification": classification,
        "latest_month": str(client_feat.index[-1]),
        "latest_ca": round(latest_ca, 0) if latest_ca is not None else None,
        "baseline_ca": round(baseline_ca, 0) if baseline_ca is not None else None,
        "ca_pct_change": ca_pct_change,
        "top_signal": SIGNALS[best_sig][0] if best_sig else None,
        "top_signal_z": round(float(latest_z.get(best_sig, 0) or 0), 2) if best_sig else None,
        "cusum_alert": cusum_breached,
        "ca_trend": ca_trend,
        "nb_months": len(client_feat),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT DEEP-DIVE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_client(df: pd.DataFrame, client_id: str) -> dict[str, Any]:
    """Full behavioral profile for one client."""
    if df is None or df.empty:
        return {"error": "DataFrame vide"}

    try:
        feat, col_map = _build_feature_matrix(df)
    except Exception:
        logger.exception("_build_feature_matrix failed")
        return {"error": "Erreur lors du calcul des features"}

    if feat.empty:
        return {"error": "Colonnes requises manquantes"}

    try:
        client_feat = feat.xs(client_id, level=0).sort_index()
    except KeyError:
        return {"error": f"Client '{client_id}' non trouvé"}

    if len(client_feat) < 2:
        return {"error": "Historique insuffisant (minimum 2 mois requis)"}

    zscores_df = _compute_zscores(client_feat)
    ca_z = zscores_df.get("ca", pd.Series(dtype=float))
    s_pos, s_neg = _cusum(ca_z)

    latest_z = zscores_df.iloc[-1].to_dict()
    latest_vals = client_feat.iloc[-1].to_dict()

    # Baseline: mean of shifted rolling window
    baseline_vals = {}
    for sig in SIGNALS:
        if sig in client_feat.columns:
            s = pd.to_numeric(client_feat[sig], errors="coerce")
            baseline_vals[sig] = float(s.shift(1).tail(BASELINE_WINDOW).mean())

    cusum_s_pos_latest = float(s_pos.iloc[-1])
    cusum_s_neg_latest = float(s_neg.iloc[-1])
    cusum_breached = max(cusum_s_pos_latest, cusum_s_neg_latest) >= CUSUM_H

    score = _alert_score(latest_z, cusum_s_neg_latest, cusum_s_pos_latest)
    classification = _classify(score)
    attribution = _generate_attribution(latest_z, latest_vals, baseline_vals, cusum_breached)

    # Periods for chart x-axis
    periods = [str(p) for p in client_feat.index.tolist()]

    # Build series dicts for each signal (for charting)
    signals_data = {}
    for sig in SIGNALS:
        if sig in client_feat.columns:
            vals = pd.to_numeric(client_feat[sig], errors="coerce")
            z_vals = pd.to_numeric(zscores_df.get(sig, pd.Series()), errors="coerce")
            # Rolling baseline mean for band
            base_mean = vals.shift(1).rolling(BASELINE_WINDOW, min_periods=2).mean()
            base_std  = vals.shift(1).rolling(BASELINE_WINDOW, min_periods=2).std()
            signals_data[sig] = {
                "values":     [round(float(v), 2) if not pd.isna(v) else None for v in vals],
                "z_scores":   [round(float(z), 2) if not pd.isna(z) else None for z in z_vals],
                "base_mean":  [round(float(v), 2) if not pd.isna(v) else None for v in base_mean],
                "base_upper": [round(float(m + 2*s), 2) if not (pd.isna(m) or pd.isna(s)) else None for m, s in zip(base_mean, base_std)],
                "base_lower": [round(float(m - 2*s), 2) if not (pd.isna(m) or pd.isna(s)) else None for m, s in zip(base_mean, base_std)],
            }

    # Alert score history
    alert_score_history = []
    for i in range(len(client_feat)):
        z_row = {sig: float(zscores_df[sig].iloc[i]) if sig in zscores_df.columns and not pd.isna(zscores_df[sig].iloc[i]) else None for sig in SIGNALS}
        sp = float(s_pos.iloc[i])
        sn = float(s_neg.iloc[i])
        alert_score_history.append(_alert_score(z_row, sn, sp))

    return {
        "client_id": str(client_id),
        "alert_score": score,
        "classification": classification,
        "attribution": attribution,
        "cusum_alert": cusum_breached,
        "latest_month": periods[-1] if periods else "",
        "nb_months": len(client_feat),
        "periods": periods,
        "signals_data": signals_data,
        "cusum": {
            "s_pos": [round(float(v), 2) for v in s_pos],
            "s_neg": [round(float(v), 2) for v in s_neg],
            "threshold": CUSUM_H,
        },
        "alert_score_history": [round(v, 1) for v in alert_score_history],
        "latest_values": {k: round(float(v), 2) if v is not None and not np.isnan(float(v)) else None for k, v in latest_vals.items()},
        "baseline_values": {k: round(float(v), 2) if v is not None and not np.isnan(float(v)) else None for k, v in baseline_vals.items()},
    }
