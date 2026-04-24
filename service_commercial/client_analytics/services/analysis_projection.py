"""
Moteur de Projection de Portefeuille Client — Mensuel
=====================================================
Méthode : Ensemble STL-Trend + GlobalGBM Quantile (sklearn HistGradientBoosting)

Pour chaque client ayant >= MIN_HISTORY mois de données :
  1. Feature engineering : lags, rolling stats, trend linéaire, saisonnalité (sin/cos),
     signaux comportementaux (alert_score, CUSUM, z-scores).
  2. GlobalGBM Quantile : un seul modèle entraîné sur TOUS les clients (cross-learning).
     → q10 (pessimiste), q50 (base), q90 (optimiste) × horizon (3, 6, 12 mois).
  3. STL Projection : pour les clients ≥ STL_MIN_HISTORY mois, décompose trend + seasonal
     et extrapole la tendance avec régression linéaire sur la queue STL.
  4. Ensemble : blend pondéré GBM + STL (60 / 40) quand STL disponible.
  5. P(churn) : score basé sur risque comportemental + recency + pente de tendance.
  6. Agrégation portefeuille + 3 scénarios (pessimiste / base / optimiste).

Granularité : mensuelle uniquement.
Horizons    : 3, 6, 12 mois.
"""
from __future__ import annotations

import logging
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

logger = logging.getLogger(__name__)

# ─── Paramètres globaux ──────────────────────────────────────────────────────
HORIZONS          = [3, 6, 12]          # mois à projeter
MIN_HISTORY       = 6                   # mois minimum pour intégrer un client
STL_MIN_HISTORY   = 18                  # mois minimum pour la branche STL
GBM_WEIGHT        = 0.60                # poids du modèle GBM dans l'ensemble
STL_WEIGHT        = 0.40                # poids du modèle STL dans l'ensemble
QUANTILES         = [0.10, 0.50, 0.90]  # pessimiste / base / optimiste
GBM_PARAMS        = dict(
    max_iter=200, max_depth=5, learning_rate=0.05,
    min_samples_leaf=5, random_state=42,
)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _to_month(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", dayfirst=True).dt.to_period("M")


def _safe(x, default=None):
    try:
        v = float(x)
        return default if np.isnan(v) or np.isinf(v) else v
    except Exception:
        return default


def _lin_slope(series: pd.Series) -> float:
    """Pente de régression linéaire (unités/mois). Retourne 0 si impossible."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return 0.0
    x = np.arange(len(s), dtype=float)
    try:
        return float(np.polyfit(x, s.values, 1)[0])
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def _build_monthly_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Agrège les données brutes en matrice (client × mois) avec tous les signaux."""
    col = {
        "client":  _pick_col(df, ["Cpt Client", "Compte Client", "Client", "Code Client"]),
        "date":    _pick_col(df, ["Date Fact.", "Date_Ref", "Date", "Date facture", "Date Facture"]),
        "amount":  _pick_col(df, ["Montant", "CA", "CA Net", "Chiffre d'Affaires"]),
        "qty":     _pick_col(df, ["Quantité", "Quantite", "Qty", "Qte", "Qté", "Quantity"]),
        "order":   _pick_col(df, ["N° Bon", "No Bon", "N Bon", "Num Bon", "Numéro Bon",
                                  "Commande", "N° Commande", "Order"]),
        "family":  _pick_col(df, ["Famille Produits", "Famille", "Famille Prod.",
                                  "Categorie", "Category"]),
        "product": _pick_col(df, ["Ref Produit", "Article", "Produit", "Product",
                                  "Réf. Produit"]),
    }

    if not col["client"] or not col["date"] or not col["amount"]:
        return pd.DataFrame(), col

    w = df.copy()
    w["_month"] = _to_month(w[col["date"]])
    w[col["amount"]] = pd.to_numeric(w[col["amount"]], errors="coerce")
    w = w.dropna(subset=["_month", col["amount"], col["client"]])

    cc, am = col["client"], col["amount"]

    # Agrégations de base
    grp = w.groupby([cc, "_month"])
    feat = grp[am].sum().rename("ca").to_frame()

    if col["qty"]:
        w[col["qty"]] = pd.to_numeric(w[col["qty"]], errors="coerce")
        feat["qty"]    = grp[col["qty"]].sum()
        feat["pu"]     = feat["ca"] / feat["qty"].replace(0, np.nan)
    else:
        feat["qty"] = np.nan
        feat["pu"]  = np.nan

    order_col = col["order"] or am
    feat["freq"] = grp[order_col].nunique() if col["order"] else grp[am].count()

    if col["family"]:
        feat["nb_families"] = grp[col["family"]].nunique()
        # HHI concentration
        fam_ca = w.groupby([cc, "_month", col["family"]])[am].sum().reset_index()
        fam_ca.columns = ["_c", "_m", "_f", "_fca"]
        tot = fam_ca.groupby(["_c", "_m"])["_fca"].transform("sum")
        fam_ca["_share"] = fam_ca["_fca"] / tot.replace(0, np.nan)
        hhi = fam_ca.groupby(["_c", "_m"])["_share"].apply(
            lambda s: float((s ** 2).sum() * 10_000)
        )
        hhi.index.names = [cc, "_month"]
        feat["hhi"] = hhi
    else:
        feat["nb_families"] = np.nan
        feat["hhi"]         = np.nan

    return feat, col


def _engineer_features(client_feat: pd.DataFrame,
                        behavioral_score: float = 0.0,
                        horizon: int = 3,
                        month_period: Any = None) -> dict:
    """
    Construit le vecteur de features pour la PRÉDICTION d'un client
    à un horizon donné, à partir de son historique mensuel.
    """
    ca   = pd.to_numeric(client_feat["ca"],   errors="coerce")
    qty  = pd.to_numeric(client_feat.get("qty", pd.Series(dtype=float)), errors="coerce")
    freq = pd.to_numeric(client_feat.get("freq", pd.Series(dtype=float)), errors="coerce")
    pu   = pd.to_numeric(client_feat.get("pu",  pd.Series(dtype=float)), errors="coerce")

    def lag(s, k):    return _safe(s.iloc[-k] if len(s) >= k else np.nan)
    def roll(s, w):   return _safe(s.tail(w).mean())
    def rollstd(s, w):return _safe(s.tail(w).std())
    def slope(s, w):  return _safe(_lin_slope(s.tail(w)))

    # Saisonnalité du mois à prédire
    if month_period is not None:
        try:
            future_month = (month_period + horizon).month
        except Exception:
            future_month = 1
    else:
        future_month = 1

    month_sin = np.sin(2 * np.pi * future_month / 12)
    month_cos = np.cos(2 * np.pi * future_month / 12)

    return {
        # CA lags
        "ca_lag1":       lag(ca, 1),
        "ca_lag2":       lag(ca, 2),
        "ca_lag3":       lag(ca, 3),
        "ca_lag6":       lag(ca, 6),
        "ca_lag12":      lag(ca, 12) if len(ca) >= 12 else np.nan,
        # CA rolling
        "ca_roll3":      roll(ca, 3),
        "ca_roll6":      roll(ca, 6),
        "ca_roll12":     roll(ca, 12),
        "ca_roll3_std":  rollstd(ca, 3),
        "ca_roll6_std":  rollstd(ca, 6),
        # CA trend (slope)
        "ca_slope3":     slope(ca, 3),
        "ca_slope6":     slope(ca, 6),
        "ca_slope12":    slope(ca, 12),
        # Qty
        "qty_lag1":      lag(qty, 1),
        "qty_roll3":     roll(qty, 3),
        "qty_slope3":    slope(qty, 3),
        # Freq
        "freq_lag1":     lag(freq, 1),
        "freq_roll3":    roll(freq, 3),
        "freq_slope3":   slope(freq, 3),
        # PU
        "pu_lag1":       lag(pu, 1),
        "pu_roll3":      roll(pu, 3),
        # Saisonnalité
        "month_sin":     month_sin,
        "month_cos":     month_cos,
        # Risque comportemental
        "alert_score":   behavioral_score,
        # Horizon
        "horizon":       float(horizon),
    }


def _build_training_samples(
    feat_matrix: pd.DataFrame,
    behavioral_scores: dict,
    horizons: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Génère les échantillons d'entraînement pour le modèle global.
    Pour chaque (client, mois t) : features à t, cibles CA à t+h pour chaque horizon.
    """
    rows_X, rows_y = [], []

    clients = feat_matrix.index.get_level_values(0).unique()

    for client_id in clients:
        try:
            cf = feat_matrix.xs(client_id, level=0).sort_index()
        except KeyError:
            continue
        if len(cf) < MIN_HISTORY:
            continue

        score = behavioral_scores.get(str(client_id), 0.0)
        ca    = pd.to_numeric(cf["ca"], errors="coerce")

        for t_idx in range(MIN_HISTORY - 1, len(cf)):
            slice_t = cf.iloc[: t_idx + 1]
            period_t = cf.index[t_idx]

            for h in horizons:
                target_idx = t_idx + h
                if target_idx >= len(cf):
                    continue  # cible non disponible
                target_ca = _safe(ca.iloc[target_idx])
                if target_ca is None or target_ca < 0:
                    continue

                feats = _engineer_features(
                    slice_t, behavioral_score=score,
                    horizon=h, month_period=period_t,
                )
                rows_X.append(feats)
                rows_y.append({"target_ca": target_ca, "horizon": h})

    if not rows_X:
        return pd.DataFrame(), pd.DataFrame()

    return pd.DataFrame(rows_X), pd.DataFrame(rows_y)


# ─────────────────────────────────────────────────────────────────────────────
# STL PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

def _stl_project(ca_series: pd.Series, horizon: int) -> tuple[float | None, float]:
    """
    Projection STL : décompose trend + seasonal, extrapole trend linéairement.
    Retourne (point_estimate, résidu_std) ou (None, 0) si insuffisant.
    """
    try:
        from statsmodels.tsa.seasonal import STL
    except ImportError:
        return None, 0.0

    s = pd.to_numeric(ca_series, errors="coerce").dropna()
    if len(s) < STL_MIN_HISTORY:
        return None, 0.0

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            stl_res = STL(s, period=12, robust=True).fit()
        except Exception:
            return None, 0.0

    # Extrapole tendance sur les 6 derniers points STL
    trend = stl_res.trend[-6:]
    x     = np.arange(len(trend), dtype=float)
    try:
        slope, intercept = np.polyfit(x, trend.values, 1)
    except Exception:
        return None, 0.0

    proj_trend    = intercept + slope * (len(trend) - 1 + horizon)
    proj_seasonal = stl_res.seasonal.iloc[-(12 - horizon % 12) or -12]
    point         = max(0.0, float(proj_trend + proj_seasonal))
    resid_std     = float(stl_res.resid.std()) * np.sqrt(horizon)

    return point, resid_std


# ─────────────────────────────────────────────────────────────────────────────
# CHURN PROBABILITY
# ─────────────────────────────────────────────────────────────────────────────

def _churn_prob(alert_score: float, recency_months: int, slope_6m: float) -> float:
    """
    Probabilité de churn dans les 6 prochains mois.
    Combinaison linéaire : risque comportemental + recency + tendance.
    """
    p = (alert_score / 100.0) * 0.55
    if recency_months >= 2:
        p += min((recency_months - 1) * 0.07, 0.25)
    if slope_6m < 0:
        p += min(abs(slope_6m) / max(1.0, abs(slope_6m) + 1) * 0.20, 0.20)
    return round(float(np.clip(p, 0.01, 0.97)), 3)


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

def _train_quantile_models(X: pd.DataFrame, y: pd.DataFrame, horizons: list[int]):
    """
    Entraîne 3 modèles quantiles (q10, q50, q90) par horizon.
    Retourne dict {horizon: {q: model}}.
    """
    FEATURE_COLS = [c for c in X.columns if c != "horizon"]
    models = {}

    for h in horizons:
        mask  = y["horizon"] == h
        X_h   = X.loc[mask, FEATURE_COLS].copy()
        y_h   = y.loc[mask, "target_ca"].copy()
        if len(X_h) < 20:
            models[h] = None
            continue

        # Remplacer NaN par la médiane colonne (HistGBM les gère nativement mais sécurité)
        X_h = X_h.fillna(X_h.median(numeric_only=True))

        h_models = {}
        for q in QUANTILES:
            m = HistGradientBoostingRegressor(
                loss="quantile", quantile=q, **GBM_PARAMS
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m.fit(X_h, y_h)
            h_models[q] = m
        models[h] = h_models

    return models, FEATURE_COLS


# ─────────────────────────────────────────────────────────────────────────────
# PROJECTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_portfolio_projection(
    df: pd.DataFrame,
    min_history: int = MIN_HISTORY,
    horizons: list[int] | None = None,
) -> dict[str, Any]:
    """
    Point d'entrée principal : projette l'ensemble du portefeuille.

    Retourne un dict sérialisable JSON contenant :
    - portfolio  : projections agrégées + scénarios
    - clients    : liste triée par at-risk CA
    - model_info : métadonnées du modèle
    """
    if horizons is None:
        horizons = HORIZONS

    base: dict[str, Any] = {
        "portfolio": {},
        "clients": [],
        "model_info": {"method": "STL + HistGBM Quantile Ensemble"},
        "error": None,
    }

    # ── 1. Matrice mensuelle ─────────────────────────────────────────────────
    try:
        feat_matrix, col_map = _build_monthly_matrix(df)
    except Exception:
        logger.exception("[projection] _build_monthly_matrix failed")
        base["error"] = "Erreur lors du calcul de la matrice mensuelle."
        return base

    if feat_matrix.empty:
        base["error"] = "Colonnes requises manquantes (client / date / montant)."
        return base

    # ── 2. Scores comportementaux (réutilise le moteur existant) ────────────
    behavioral_scores: dict[str, float] = {}
    behavioral_classes: dict[str, str]  = {}
    try:
        from .analysis_behavioral_monitoring import analyze_portfolio as _bm_portfolio
        bm = _bm_portfolio(df)
        for row in bm.get("portfolio", []):
            cid = str(row["client_id"])
            behavioral_scores[cid]  = row.get("alert_score", 0.0)
            behavioral_classes[cid] = row.get("classification", "green")
    except Exception:
        logger.debug("[projection] behavioral scores unavailable", exc_info=True)

    # ── 3. Échantillons d'entraînement ───────────────────────────────────────
    X_train, y_train = _build_training_samples(
        feat_matrix, behavioral_scores, horizons
    )
    n_samples = len(X_train)
    base["model_info"]["training_samples"] = n_samples

    if n_samples < 50:
        base["error"] = (
            f"Historique insuffisant pour entraîner le modèle "
            f"({n_samples} échantillons < 50 requis)."
        )
        return base

    # ── 4. Entraînement des modèles quantiles ────────────────────────────────
    try:
        models, feature_cols = _train_quantile_models(X_train, y_train, horizons)
    except Exception:
        logger.exception("[projection] training failed")
        base["error"] = "Erreur lors de l'entraînement du modèle."
        return base

    base["model_info"]["feature_cols"] = feature_cols

    # ── 5. Projection par client ─────────────────────────────────────────────
    clients_list = feat_matrix.index.get_level_values(0).unique()
    client_results = []
    n_projected = 0

    for client_id in clients_list:
        try:
            cf = feat_matrix.xs(client_id, level=0).sort_index()
        except KeyError:
            continue
        if len(cf) < min_history:
            continue

        cid        = str(client_id)
        score      = behavioral_scores.get(cid, 0.0)
        risk_class = behavioral_classes.get(cid, "green")
        ca         = pd.to_numeric(cf["ca"], errors="coerce")
        last_period= cf.index[-1]

        # Recency (mois depuis dernier achat réel)
        latest_ca  = _safe(ca.iloc[-1], 0.0)
        recency    = 0  # par définition le dernier mois est t=0
        slope_6m   = _safe(_lin_slope(ca.tail(6)), 0.0)

        # Features à t (dernier mois connu) pour prédiction
        proj: dict[int, dict] = {}

        for h in horizons:
            h_models = models.get(h)

            # ── GBM ──────────────────────────────────────────────────────────
            gbm_q: dict[float, float] = {}
            if h_models:
                feat_vec = _engineer_features(
                    cf, behavioral_score=score,
                    horizon=h, month_period=last_period,
                )
                row_df = pd.DataFrame([feat_vec])[feature_cols].fillna(
                    X_train[feature_cols].median()
                )
                for q, m in h_models.items():
                    try:
                        val = float(m.predict(row_df)[0])
                        gbm_q[q] = max(0.0, val)
                    except Exception:
                        gbm_q[q] = max(0.0, float(ca.tail(3).mean() or 0))

            # ── STL ──────────────────────────────────────────────────────────
            stl_point, stl_std = _stl_project(ca, h)

            # ── Ensemble ─────────────────────────────────────────────────────
            if stl_point is not None and gbm_q:
                q50_gbm = gbm_q.get(0.50, stl_point)
                q50_ens = GBM_WEIGHT * q50_gbm + STL_WEIGHT * stl_point
                # Intervalles : blend GBM spread + STL spread
                q10_ens = max(0.0, GBM_WEIGHT * gbm_q.get(0.10, q50_gbm * 0.8)
                              + STL_WEIGHT * max(0.0, stl_point - 1.28 * stl_std))
                q90_ens = (GBM_WEIGHT * gbm_q.get(0.90, q50_gbm * 1.2)
                           + STL_WEIGHT * (stl_point + 1.28 * stl_std))
            elif gbm_q:
                q50_ens = gbm_q.get(0.50, 0.0)
                q10_ens = gbm_q.get(0.10, q50_ens * 0.8)
                q90_ens = gbm_q.get(0.90, q50_ens * 1.2)
            else:
                # Fallback : extrapolation naïve
                mean6 = _safe(ca.tail(6).mean(), 0.0)
                q50_ens = mean6
                q10_ens = mean6 * 0.75
                q90_ens = mean6 * 1.25

            proj[h] = {
                "q10": round(q10_ens, 0),
                "q50": round(q50_ens, 0),
                "q90": round(q90_ens, 0),
                "delta_pct": round(
                    (q50_ens - latest_ca) / latest_ca * 100, 1
                ) if latest_ca and latest_ca > 0 else None,
                "stl_available": stl_point is not None,
            }

        if not proj:
            continue

        churn_p = _churn_prob(score, recency, slope_6m)

        # Historique CA des 18 derniers mois pour sparkline
        ca_history = [
            {"period": str(p), "ca": round(_safe(v, 0), 0)}
            for p, v in ca.tail(18).items()
        ]

        client_results.append({
            "client_id":    cid,
            "current_ca":   round(latest_ca or 0, 0),
            "nb_months":    int(len(cf)),
            "risk_class":   risk_class,
            "alert_score":  round(score, 1),
            "churn_prob":   churn_p,
            "slope_6m":     round(slope_6m, 1),
            "trend":        "hausse" if slope_6m > 0 else ("baisse" if slope_6m < 0 else "stable"),
            "proj":         proj,
            "ca_history":   ca_history,
        })
        n_projected += 1

    base["model_info"]["n_clients_projected"] = n_projected
    base["model_info"]["n_clients_total"]     = int(len(clients_list))

    if not client_results:
        base["error"] = "Aucun client avec suffisamment d'historique."
        return base

    # Trier : clients à risque d'abord (score desc)
    client_results.sort(key=lambda r: r["alert_score"], reverse=True)

    # ── 6. Agrégation portefeuille ───────────────────────────────────────────
    total_current = sum(r["current_ca"] for r in client_results)
    portfolio_proj: dict[int, dict] = {}
    for h in horizons:
        q10 = sum(r["proj"][h]["q10"] for r in client_results if h in r["proj"])
        q50 = sum(r["proj"][h]["q50"] for r in client_results if h in r["proj"])
        q90 = sum(r["proj"][h]["q90"] for r in client_results if h in r["proj"])
        portfolio_proj[h] = {
            "pessimistic": round(q10, 0),
            "base":        round(q50, 0),
            "optimistic":  round(q90, 0),
            "delta_pct_base": round(
                (q50 - total_current) / total_current * 100, 1
            ) if total_current else None,
        }

    # At-risk CA : CA des clients rouges × leur P(churn) + orange × 0.3 × P(churn)
    at_risk_ca = sum(
        r["current_ca"] * r["churn_prob"]
        for r in client_results
        if r["risk_class"] in ("red", "orange")
    )

    # Clients à fort risque de churn
    n_churn_risk = sum(1 for r in client_results if r["churn_prob"] > 0.50)

    # Timeline portefeuille : dernier 12 mois historique + 12 mois projeté (q50 interp.)
    timeline_hist = _portfolio_history_timeline(feat_matrix, last_n=18)
    timeline_proj = _portfolio_forecast_timeline(client_results, horizons)

    base["portfolio"] = {
        "current_ca":  round(total_current, 0),
        "at_risk_ca":  round(at_risk_ca, 0),
        "n_churn_risk": n_churn_risk,
        "n_clients":   n_projected,
        "by_horizon":  portfolio_proj,
        "timeline_history": timeline_hist,
        "timeline_forecast": timeline_proj,
    }
    base["clients"] = client_results

    return base


def _portfolio_history_timeline(
    feat_matrix: pd.DataFrame, last_n: int = 18
) -> list[dict]:
    """Historique mensuel agrégé (tous clients) pour les last_n derniers mois."""
    if feat_matrix.empty:
        return []
    ca_col = pd.to_numeric(feat_matrix["ca"], errors="coerce")
    monthly = ca_col.groupby(level=1).sum().sort_index()
    monthly = monthly.tail(last_n)
    return [
        {"period": str(p), "ca": round(float(v), 0)}
        for p, v in monthly.items()
    ]


def _portfolio_forecast_timeline(
    client_results: list[dict], horizons: list[int]
) -> list[dict]:
    """
    Construit une timeline forward pour le portefeuille.
    Points aux horizons 3, 6, 12 (q10, q50, q90).
    """
    result = []
    for h in sorted(horizons):
        q10 = sum(r["proj"][h]["q10"] for r in client_results if h in r.get("proj", {}))
        q50 = sum(r["proj"][h]["q50"] for r in client_results if h in r.get("proj", {}))
        q90 = sum(r["proj"][h]["q90"] for r in client_results if h in r.get("proj", {}))
        result.append({
            "horizon": h,
            "label":   f"+{h}M",
            "q10":     round(q10, 0),
            "q50":     round(q50, 0),
            "q90":     round(q90, 0),
        })
    return result


def analyze_client_projection(
    df: pd.DataFrame,
    client_id: str,
    horizons: list[int] | None = None,
) -> dict[str, Any]:
    """
    Deep-dive : projection détaillée pour un client unique.
    Retourne les courbes CA, Qty, Freq sur tout l'historique + les 3 horizons.
    """
    if horizons is None:
        horizons = HORIZONS

    out: dict[str, Any] = {
        "client_id": client_id,
        "error": None,
        "metrics": {},
        "proj": {},
    }

    try:
        feat_matrix, col_map = _build_monthly_matrix(df)
    except Exception:
        out["error"] = "Erreur matrice."
        return out

    try:
        cf = feat_matrix.xs(client_id, level=0).sort_index()
    except KeyError:
        out["error"] = f"Client '{client_id}' introuvable."
        return out

    if len(cf) < MIN_HISTORY:
        out["error"] = f"Historique insuffisant ({len(cf)} mois < {MIN_HISTORY})."
        return out

    periods = [str(p) for p in cf.index.tolist()]

    # Courbe historique par métrique
    for metric in ["ca", "qty", "freq", "pu"]:
        if metric not in cf.columns:
            continue
        vals = pd.to_numeric(cf[metric], errors="coerce")
        out["metrics"][metric] = {
            "periods": periods,
            "values":  [round(_safe(v, 0) or 0, 1) for v in vals],
        }

    # Projection CA aux 3 horizons avec STL + fallback
    ca = pd.to_numeric(cf["ca"], errors="coerce")
    latest_ca = _safe(ca.iloc[-1], 0.0) or 0.0
    last_period = cf.index[-1]

    for h in horizons:
        stl_pt, stl_std = _stl_project(ca, h)
        slope_h = _safe(_lin_slope(ca.tail(max(h, 3))), 0.0)
        mean_6  = _safe(ca.tail(6).mean(), latest_ca)

        if stl_pt is not None:
            q50 = stl_pt
            q10 = max(0.0, stl_pt - 1.28 * stl_std)
            q90 = stl_pt + 1.28 * stl_std
        else:
            # Extrapolation linéaire simple
            q50 = max(0.0, latest_ca + slope_h * h)
            q10 = q50 * 0.80
            q90 = q50 * 1.20

        out["proj"][h] = {
            "q10":        round(q10, 0),
            "q50":        round(q50, 0),
            "q90":        round(q90, 0),
            "delta_pct":  round((q50 - latest_ca) / latest_ca * 100, 1)
                          if latest_ca > 0 else None,
            "stl":        stl_pt is not None,
        }

    out["current_ca"]   = round(latest_ca, 0)
    out["nb_months"]    = int(len(cf))
    out["latest_period"]= str(last_period)
    out["slope_6m"]     = round(_safe(_lin_slope(ca.tail(6)), 0.0), 1)

    return out
