"""Détection d’anomalies robustes pour séries temporelles.

Méthode: Machine Learning avec Isolation Forest (détection multivariée).

- Entrée principale: DataFrame journalier (DatetimeIndex) avec métriques CA_Total, Qty_Total, Nb_Clients.
- Sortie: DataFrame par métrique avec observed/anomaly_score/is_anomaly/direction.

Cette implémentation utilise:
- Isolation Forest: algorithme state-of-the-art pour la détection d'anomalies
- Approche multivariée: analyse simultanée de plusieurs métriques
- Robustesse aux outliers et aux cas limites
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

try:
    from statsmodels.tsa.seasonal import STL
except Exception:  # pragma: no cover
    STL = None


@dataclass(frozen=True)
class AnomalyParams:
    method: str = "isolation_forest"
    contamination: float = 0.1
    basis: str = "daily"
    min_points: int = 30


def _safe_datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    if isinstance(index, pd.DatetimeIndex):
        return index
    dt = pd.to_datetime(index, errors="coerce")
    return pd.DatetimeIndex(dt)


def _resolve_stl_period(n_points: int, stl_period: int | None) -> int:
    """Détermine la période STL selon le nombre de points."""
    if stl_period is not None:
        return int(stl_period)
    # Règle métier demandée
    return 365 if n_points >= 2 * 365 else 7


def detect_anomalies_ml(
    df: pd.DataFrame,
    value_cols: list[str],
    contamination: float = 0.1,
    min_points: int = 30,
) -> dict[str, pd.DataFrame]:
    """Détecte les anomalies multivariées avec Isolation Forest.

    Args:
        df: DataFrame avec DatetimeIndex et colonnes de métriques
        value_cols: Liste des colonnes à analyser (CA_Total, Qty_Total, Nb_Clients)
        contamination: Proportion attendue d'anomalies (0.05 à 0.15)
        min_points: Nombre minimum de points requis

    Returns:
        Dict {col_name: DataFrame avec observed/anomaly_score/is_anomaly/direction}
    """
    if df is None or df.empty or len(df) < min_points:
        return {
            col: pd.DataFrame(
                {"observed": [], "anomaly_score": [], "is_anomaly": [], "direction": []}
            )
            for col in value_cols
        }

    df_work = df.copy()
    if not isinstance(df_work.index, pd.DatetimeIndex):
        df_work.index = pd.to_datetime(df_work.index, errors="coerce")
    df_work = df_work.sort_index()

    # Filtrer les colonnes disponibles
    available_cols = [
        col
        for col in value_cols
        if col in df_work.columns and df_work[col].notna().sum() > 0
    ]

    if len(available_cols) < 2:
        # Pas assez de métriques pour ML multivariée, fallback
        return {
            col: pd.DataFrame(
                {
                    "observed": df_work[col] if col in df_work.columns else [],
                    "anomaly_score": 0.0,
                    "is_anomaly": False,
                    "direction": "",
                },
                index=df_work.index,
            )
            for col in value_cols
        }

    # Préparer les features
    X = df_work[available_cols].copy()

    # Remplir les NaN avec la médiane
    for col in available_cols:
        X[col] = pd.to_numeric(X[col], errors="coerce")
        median_val = X[col].median()
        X[col] = X[col].fillna(median_val if pd.notna(median_val) else 0)

    # Vérifier qu'il reste des données exploitables
    if X.isnull().all().all() or len(X.dropna()) < min_points:
        return {
            col: pd.DataFrame(
                {
                    "observed": df_work[col] if col in df_work.columns else [],
                    "anomaly_score": 0.0,
                    "is_anomaly": False,
                    "direction": "",
                },
                index=df_work.index,
            )
            for col in value_cols
        }

    # Normalisation
    scaler = StandardScaler()
    try:
        X_scaled = scaler.fit_transform(X)
    except Exception:
        return {
            col: pd.DataFrame(
                {
                    "observed": df_work[col] if col in df_work.columns else [],
                    "anomaly_score": 0.0,
                    "is_anomaly": False,
                    "direction": "",
                },
                index=df_work.index,
            )
            for col in value_cols
        }

    # Isolation Forest
    iso_forest = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        max_samples="auto",
        bootstrap=False,
    )

    try:
        # Prédiction: -1 pour anomalies, 1 pour normaux
        predictions = iso_forest.fit_predict(X_scaled)

        # Score d'anomalie (plus négatif = plus anormal)
        scores = iso_forest.score_samples(X_scaled)

        # Convertir en booléen et normaliser le score
        is_anomaly = pd.Series(predictions == -1, index=df_work.index)
        anomaly_score = pd.Series(
            -scores, index=df_work.index
        )  # Scores positifs pour anomalies

    except Exception:
        is_anomaly = pd.Series(False, index=df_work.index)
        anomaly_score = pd.Series(0.0, index=df_work.index)

    # Créer les résultats par métrique
    results = {}
    for col in value_cols:
        if col not in df_work.columns:
            results[col] = pd.DataFrame(
                {"observed": [], "anomaly_score": [], "is_anomaly": [], "direction": []}
            )
            continue

        obs = df_work[col].copy()

        # Direction basée sur déviation par rapport à la médiane mobile
        rolling_median = obs.rolling(window=min(30, len(obs)), min_periods=1).median()
        deviation = obs - rolling_median
        direction = pd.Series("", index=df_work.index, dtype=str)
        direction.loc[is_anomaly & (deviation >= 0)] = "spike"
        direction.loc[is_anomaly & (deviation < 0)] = "drop"

        results[col] = pd.DataFrame(
            {
                "observed": obs,
                "anomaly_score": anomaly_score,
                "is_anomaly": is_anomaly,
                "direction": direction,
            },
            index=df_work.index,
        )

    return results


def detect_anomalies_stl_mad(
    series: pd.Series,
    stl_period: int | None = None,
    z_thresh: float = 3.5,
    min_points: int = 30,
) -> pd.DataFrame:
    """Détecte les anomalies d’une série via STL + MAD.

    Args:
        series: Série temporelle (index datetime recommandé).
        stl_period: Période STL. Si None, applique la règle 7/365 selon longueur.
        z_thresh: Seuil |z| au-delà duquel on marque une anomalie.
        min_points: Nombre minimal de points valides requis.

    Returns:
        DataFrame index datetime avec colonnes:
            observed, expected, resid, z, is_anomaly, direction
    """
    if series is None:
        series = pd.Series(dtype=float)

    s = pd.to_numeric(series, errors="coerce")
    if s.index is None:
        s.index = pd.RangeIndex(len(s))

    dt_index = _safe_datetime_index(s.index)
    s = pd.Series(s.values, index=dt_index, name="observed").sort_index()

    n_total = int(len(s))
    stl_period_resolved = _resolve_stl_period(n_total, stl_period)

    out = pd.DataFrame(index=s.index)
    out["observed"] = s.astype(float)

    valid = out["observed"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < min_points or valid.nunique(dropna=True) <= 1:
        out["expected"] = np.nan
        out["resid"] = np.nan
        out["z"] = np.nan
        out["is_anomaly"] = False
        out["direction"] = ""
        return out

    # STL nécessite une série sans NaN -> on interpole légèrement si besoin
    y = out["observed"].copy()
    if y.isna().any():
        y = y.interpolate(limit_direction="both")

    expected: pd.Series
    resid: pd.Series

    can_stl = (
        STL is not None
        and len(y) >= max(14, 2 * stl_period_resolved)
        and y.nunique(dropna=True) > 1
    )

    if can_stl:
        try:
            stl = STL(y, period=stl_period_resolved, robust=True)
            stl_res = stl.fit()
            expected = (stl_res.trend + stl_res.seasonal).rename("expected")
            resid = (y - expected).rename("resid")
        except Exception:
            can_stl = False

    if not can_stl:
        window = 7 if len(y) >= 7 else max(2, int(min(len(y), 7)))
        expected = y.rolling(window=window, min_periods=1).mean().rename("expected")
        resid = (y - expected).rename("resid")

    out["expected"] = expected
    out["resid"] = resid

    resid_valid = (
        pd.to_numeric(out["resid"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    med = float(resid_valid.median())
    mad = float((resid_valid.sub(med).abs()).median())

    if mad <= 0 or not np.isfinite(mad):
        out["z"] = np.nan
        out["is_anomaly"] = False
        out["direction"] = ""
        return out

    z = 0.6745 * (out["resid"] - med) / mad
    out["z"] = z

    is_anom = z.abs() > float(z_thresh)
    is_anom = is_anom.fillna(False)
    out["is_anomaly"] = is_anom.astype(bool)

    direction = pd.Series("", index=out.index, dtype=str)
    direction.loc[is_anom & (out["resid"] > 0)] = "spike"
    direction.loc[is_anom & (out["resid"] < 0)] = "drop"
    out["direction"] = direction

    return out


def build_anomaly_report(
    df_daily: pd.DataFrame,
    value_cols: list[str] | None = None,
    contamination: float = 0.1,
) -> dict[str, Any]:
    """Construit un rapport multi-métriques + score joint (>=2 métriques anormales).

    Note: Le rapport retourné est destiné à être injecté dans `results['anomalies']`.

    Args:
        df_daily: DataFrame journalier (DatetimeIndex) avec colonnes métriques.
        value_cols: Colonnes à analyser.
        contamination: Proportion attendue d'anomalies (0.05 à 0.15).

    Returns:
        dict conforme à la structure demandée (params/by_metric/joint),
        + un champ interne `_anom_map` (DataFrames) pour la génération du dashboard.
    """
    if value_cols is None:
        value_cols = ["CA_Total", "Qty_Total", "Nb_Clients"]

    if df_daily is None or df_daily.empty:
        params = AnomalyParams(contamination=float(contamination))
        return {
            "params": {
                "method": params.method,
                "contamination": params.contamination,
                "basis": params.basis,
            },
            "by_metric": {},
            "joint": {"n_joint_ge_2": 0, "top_joint": []},
            "_anom_map": {},
        }

    df = df_daily.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.sort_index()

    # Adapter le contamination rate selon la taille de l'échantillon
    adaptive_contamination = min(0.15, max(0.05, contamination))
    params = AnomalyParams(contamination=float(adaptive_contamination))

    by_metric: dict[str, Any] = {}
    anom_map: dict[str, pd.DataFrame] = {}

    # Détection ML multivariée
    ml_results = detect_anomalies_ml(
        df,
        value_cols=value_cols,
        contamination=adaptive_contamination,
        min_points=params.min_points,
    )

    for col in value_cols:
        if col not in ml_results:
            continue

        anom_df = ml_results[col]
        anom_map[col] = anom_df

        if anom_df.empty:
            by_metric[col] = {"n_anomalies": 0, "top": []}
            continue

        anoms_only = anom_df.loc[anom_df["is_anomaly"]].copy()
        if not anoms_only.empty and "anomaly_score" in anoms_only.columns:
            anoms_only = anoms_only.sort_values("anomaly_score", ascending=False)

        top = []
        for idx, row in anoms_only.head(10).iterrows():
            date_str = pd.Timestamp(idx).date().isoformat() if pd.notna(idx) else ""
            top.append(
                {
                    "date": date_str,
                    "observed": (
                        float(row.get("observed", np.nan))
                        if pd.notna(row.get("observed", np.nan))
                        else None
                    ),
                    "anomaly_score": (
                        float(row.get("anomaly_score", np.nan))
                        if pd.notna(row.get("anomaly_score", np.nan))
                        else None
                    ),
                    "direction": str(row.get("direction", "")),
                }
            )

        by_metric[col] = {
            "n_anomalies": (
                int(anom_df["is_anomaly"].sum())
                if "is_anomaly" in anom_df.columns
                else 0
            ),
            "top": top,
        }

    # Joint score
    joint = {"n_joint_ge_2": 0, "top_joint": []}
    if anom_map:
        idx = next(iter(anom_map.values())).index
        flags = pd.DataFrame(index=idx)
        for metric, frame in anom_map.items():
            flags[metric] = frame.get("is_anomaly", False).astype(int)
        flags = flags.fillna(0).astype(int)

        joint_score = flags.sum(axis=1)
        joint_mask = joint_score >= 2
        joint["n_joint_ge_2"] = int(joint_mask.sum())

        if int(joint_mask.sum()) > 0:
            rows = []
            for dt, score in (
                joint_score.loc[joint_mask]
                .sort_values(ascending=False)
                .head(10)
                .items()
            ):
                metrics_hit = [m for m in flags.columns if int(flags.loc[dt, m]) == 1]
                parts = []
                for m in metrics_hit:
                    d = (
                        anom_map[m].loc[dt, "direction"]
                        if dt in anom_map[m].index
                        else ""
                    )
                    if d:
                        parts.append(f"{m}: {d}")
                    else:
                        parts.append(m)
                rows.append(
                    {
                        "date": pd.Timestamp(dt).date().isoformat(),
                        "joint_score": int(score),
                        "metrics": metrics_hit,
                        "summary": "; ".join(parts),
                    }
                )
            joint["top_joint"] = rows

    return {
        "params": {
            "method": params.method,
            "contamination": params.contamination,
            "basis": params.basis,
        },
        "by_metric": by_metric,
        "joint": joint,
        "_anom_map": anom_map,
    }
