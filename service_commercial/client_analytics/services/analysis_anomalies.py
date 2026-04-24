from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def _pick_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]) -> str | None:
    if df is None or df.empty:
        return None
    for col in candidates or []:
        if col in df.columns:
            return col
    return None


def _to_datetime(s: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(
            s, errors="coerce", dayfirst=True, infer_datetime_format=True
        )
    except Exception:
        return pd.to_datetime(s, errors="coerce")


@dataclass(frozen=True)
class _PeriodSpec:
    granularity: str
    window: int
    min_history: int


def _default_period_spec(time_granularity: str | None) -> _PeriodSpec:
    tg = str(time_granularity or "month").lower().strip()
    if tg in ["fiscal", "fiscal_year", "fiscale", "annuel", "annuelle"]:
        tg = "year"
    if tg not in ["month", "quarter", "year"]:
        tg = "month"

    if tg == "month":
        return _PeriodSpec(granularity="month", window=12, min_history=6)
    if tg == "quarter":
        return _PeriodSpec(granularity="quarter", window=8, min_history=5)
    return _PeriodSpec(granularity="year", window=5, min_history=3)


def _compute_fiscal_year(dt: pd.Series, fiscal_year_start_month: int = 4) -> pd.Series:
    month = dt.dt.month
    year = dt.dt.year
    return year + (month >= fiscal_year_start_month).astype(int)


def _compute_fiscal_quarter(
    dt: pd.Series, fiscal_year_start_month: int = 4
) -> pd.Series:
    # Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar
    month = dt.dt.month
    return (((month - fiscal_year_start_month) % 12) // 3 + 1).astype(int)


def _period_start_from_fy_q(fy: pd.Series, fq: pd.Series) -> pd.Series:
    start_month_map = {1: 4, 2: 7, 3: 10, 4: 1}
    start_month = fq.map(start_month_map).astype("Int64")
    # Q4 démarre en Jan de FY, les autres en FY-1
    start_year = (fy - (fq != 4).astype(int)).astype("Int64")
    return pd.to_datetime(
        {
            "year": start_year.astype(int),
            "month": start_month.astype(int),
            "day": 1,
        },
        errors="coerce",
    )


def _build_period_columns(
    df: pd.DataFrame,
    dt: pd.Series,
    time_granularity: str,
    fiscal_year_start_month: int = 4,
) -> pd.DataFrame:
    """Ajoute des colonnes techniques de période: _period_start (datetime) et _period_label (str)."""
    out = df.copy()

    if time_granularity == "month":
        out["_period_start"] = dt.dt.to_period("M").dt.to_timestamp()
        out["_period_label"] = dt.dt.to_period("M").astype(str)
        return out

    fy = _compute_fiscal_year(dt, fiscal_year_start_month=fiscal_year_start_month)
    out["_fy"] = fy

    if time_granularity == "quarter":
        fq = _compute_fiscal_quarter(
            dt, fiscal_year_start_month=fiscal_year_start_month
        )
        out["_fq"] = fq
        out["_period_start"] = _period_start_from_fy_q(fy, fq)
        out["_period_label"] = "Q" + fq.astype(str) + " FY" + fy.astype(str)
        if "Fiscal_Quarter" in out.columns:
            out["_period_label"] = (
                out["Fiscal_Quarter"]
                .astype(str)
                .where(out["Fiscal_Quarter"].notna(), out["_period_label"])
            )
        return out

    # year fiscal
    out["_period_start"] = pd.to_datetime(
        {"year": (fy - 1).astype(int), "month": fiscal_year_start_month, "day": 1},
        errors="coerce",
    )
    out["_period_label"] = "FY" + fy.astype(str)
    if "Fiscal_Year_Label" in out.columns:
        out["_period_label"] = (
            out["Fiscal_Year_Label"]
            .astype(str)
            .where(out["Fiscal_Year_Label"].notna(), out["_period_label"])
        )
    return out


def _robust_z_from_history(
    values: pd.Series,
    window: int,
    min_history: int,
) -> pd.Series:
    """Z-score robuste par rapport à l'historique (shift(1)), sans fuite."""
    hist = values.shift(1)
    med = hist.rolling(window=window, min_periods=min_history).median()
    abs_dev = (hist - med).abs()
    mad = abs_dev.rolling(window=window, min_periods=min_history).median()

    z = 0.6745 * (values - med) / mad
    valid = mad.notna() & (mad > 0) & med.notna()
    z = z.where(valid)

    # Cas particulier: MAD==0 (historique parfaitement constant)
    # Toute déviation par rapport à la médiane historique devient une anomalie évidente.
    mad0 = mad.notna() & (mad == 0) & med.notna()
    z = z.mask(mad0 & (values == med), 0.0)
    z = z.mask(mad0 & (values != med), np.sign(values - med) * 999.0)
    return z


def _detect_anomalies_ml(
    df: pd.DataFrame,
    feature_cols: list[str],
    contamination: float = 0.1,
    min_samples: int = 10,
) -> tuple[pd.Series, pd.Series]:
    """Détection d'anomalies multivariée avec Isolation Forest.

    Args:
        df: DataFrame avec les métriques
        feature_cols: Liste des colonnes à utiliser comme features (CA, Qty, Freq)
        contamination: Proportion attendue d'anomalies (0.1 = 10%)
        min_samples: Nombre minimum de points requis

    Returns:
        Tuple (is_anomaly: Series booléen, anomaly_score: Series de scores)
    """
    # Filtrer les colonnes disponibles et avec données valides
    valid_cols = [
        col for col in feature_cols if col in df.columns and df[col].notna().sum() > 0
    ]

    if len(valid_cols) < 2 or len(df) < min_samples:
        # Pas assez de données pour ML
        return pd.Series(False, index=df.index), pd.Series(0.0, index=df.index)

    # Préparer les données
    X = df[valid_cols].copy()

    # Remplir les NaN avec la médiane
    for col in valid_cols:
        X[col] = X[col].fillna(X[col].median())

    # Vérifier qu'il reste des données exploitables
    if X.isnull().all().all() or len(X.dropna()) < min_samples:
        return pd.Series(False, index=df.index), pd.Series(0.0, index=df.index)

    # Normalisation
    scaler = StandardScaler()
    try:
        X_scaled = scaler.fit_transform(X)
    except Exception:
        return pd.Series(False, index=df.index), pd.Series(0.0, index=df.index)

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
        is_anomaly = pd.Series(predictions == -1, index=df.index)
        anomaly_score = pd.Series(
            -scores, index=df.index
        )  # Scores positifs pour anomalies

        return is_anomaly, anomaly_score

    except Exception:
        return pd.Series(False, index=df.index), pd.Series(0.0, index=df.index)


def analyze_client_anomalies(
    df: pd.DataFrame,
    time_granularity: str = "month",
    z_thresh: float = 3.5,
    window: int | None = None,
    min_history: int | None = None,
    fiscal_year_start_month: int = 4,
    top_n: int = 20,
    include_scatter: bool = False,
) -> dict[str, Any]:
    """Analyse les anomalies de portefeuille client.

    Retourne un dict sérialisable (template-friendly).
    """

    base = {
        "meta": {
            "time_granularity": time_granularity,
            "z_thresh": float(z_thresh),
            "window": None,
            "min_history": None,
        },
        "kpis": {},
        "top_anomalies_latest": [],
        "top_anomalies_all": [],
        "graphs": {},
    }

    if df is None or df.empty:
        base["error"] = "DataFrame vide."
        return base

    spec = _default_period_spec(time_granularity)
    tg = spec.granularity
    win = int(window or spec.window)
    min_hist = int(min_history or spec.min_history)
    base["meta"]["time_granularity"] = tg
    base["meta"]["window"] = win
    base["meta"]["min_history"] = min_hist

    client_col = _pick_col(df, ["Cpt Client", "Compte Client", "Client", "Code Client"])
    date_col = _pick_col(
        df, ["Date Fact.", "Date_Ref", "Date", "Date facture", "Date Facture"]
    )
    amount_col = _pick_col(df, ["Montant", "CA", "CA Net", "Chiffre d'Affaires"])
    qty_col = _pick_col(df, ["Quantité", "Quantite", "Qty", "Qte", "Qté", "Quantity"])
    order_col = _pick_col(
        df,
        [
            "N° Bon",
            "No Bon",
            "N Bon",
            "Num Bon",
            "Numéro Bon",
            "Commande",
            "N° Commande",
            "Order",
        ],
    )

    base["meta"]["columns"] = {
        "client": client_col,
        "date": date_col,
        "amount": amount_col,
        "qty": qty_col,
        "order": order_col,
    }

    if not client_col or not date_col or not amount_col:
        base["error"] = "Colonnes requises manquantes (client/date/montant)."
        return base

    df2 = df[
        [
            c
            for c in [
                client_col,
                date_col,
                amount_col,
                qty_col,
                order_col,
                "Fiscal_Quarter",
                "Fiscal_Year_Label",
            ]
            if c and c in df.columns
        ]
    ].copy()
    df2[amount_col] = pd.to_numeric(df2[amount_col], errors="coerce")
    if qty_col and qty_col in df2.columns:
        df2[qty_col] = pd.to_numeric(df2[qty_col], errors="coerce")
    df2[date_col] = _to_datetime(df2[date_col])
    df2 = df2.dropna(subset=[client_col, date_col])
    if df2.empty:
        base["error"] = "Aucune ligne exploitable après nettoyage (client/date)."
        return base

    df2 = _build_period_columns(
        df2, df2[date_col], tg, fiscal_year_start_month=fiscal_year_start_month
    )

    agg_spec: dict[str, Any] = {
        amount_col: "sum",
    }
    if qty_col and qty_col in df2.columns:
        agg_spec[qty_col] = "sum"
    if order_col and order_col in df2.columns:
        agg_spec[order_col] = pd.Series.nunique
    else:
        # fallback: nb de lignes
        df2["_line_count"] = 1
        agg_spec["_line_count"] = "sum"

    grouped = (
        df2.groupby([client_col, "_period_start", "_period_label"], dropna=False)
        .agg(agg_spec)
        .reset_index()
    )

    grouped = grouped.rename(
        columns={
            client_col: "Client",
            amount_col: "CA",
        }
    )

    if qty_col and qty_col in grouped.columns:
        grouped = grouped.rename(columns={qty_col: "Qty"})
    else:
        grouped["Qty"] = np.nan

    if order_col and order_col in grouped.columns:
        grouped = grouped.rename(columns={order_col: "Freq"})
    else:
        grouped["Freq"] = grouped.get("_line_count")

    grouped["Freq"] = pd.to_numeric(grouped["Freq"], errors="coerce")
    grouped["CA"] = pd.to_numeric(grouped["CA"], errors="coerce")
    grouped["Qty"] = pd.to_numeric(grouped["Qty"], errors="coerce")
    grouped["Price"] = grouped["CA"] / grouped["Qty"].where(grouped["Qty"] > 0)
    grouped = grouped.drop(columns=[c for c in ["_line_count"] if c in grouped.columns])

    grouped = grouped.sort_values(
        ["Client", "_period_start"], kind="mergesort"
    ).reset_index(drop=True)

    metric_cols = ["CA", "Qty", "Freq", "Price"]
    present_metrics = [m for m in metric_cols if grouped[m].notna().any()]
    if not present_metrics:
        base["error"] = "Aucune métrique exploitable pour la détection."
        return base

    for m in present_metrics:
        grouped[f"z_{m.lower()}"] = grouped.groupby("Client", dropna=False)[
            m
        ].transform(
            lambda s: _robust_z_from_history(s, window=win, min_history=min_hist)
        )

    z_cols = [f"z_{m.lower()}" for m in present_metrics]
    grouped["_score"] = grouped[z_cols].abs().max(axis=1)
    grouped["_is_anomaly"] = grouped["_score"].notna() & (
        grouped["_score"] >= float(z_thresh)
    )

    # métrique principale + direction (vectorisé)
    z_mat = grouped[z_cols].to_numpy(dtype=float)
    abs_mat = np.abs(z_mat)
    abs_mat = np.where(np.isnan(abs_mat), -np.inf, abs_mat)
    main_pos = abs_mat.argmax(axis=1)
    main_metric = []
    main_z = []
    for i in range(len(grouped)):
        if abs_mat[i, main_pos[i]] == -np.inf:
            main_metric.append(None)
            main_z.append(np.nan)
        else:
            metric_name = present_metrics[main_pos[i]]
            main_metric.append(metric_name)
            main_z.append(z_mat[i, main_pos[i]])
    grouped["_main_metric"] = main_metric
    grouped["_direction"] = np.where(pd.Series(main_z) >= 0, "hausse", "baisse")
    grouped.loc[pd.isna(pd.Series(main_z)), "_direction"] = None

    latest_start = grouped["_period_start"].max()
    latest_label = None
    if pd.notna(latest_start):
        latest_label = (
            grouped.loc[grouped["_period_start"].eq(latest_start), "_period_label"]
            .dropna()
            .astype(str)
            .head(1)
            .tolist()
        )
        latest_label = latest_label[0] if latest_label else None

    latest = (
        grouped[grouped["_period_start"].eq(latest_start)].copy()
        if pd.notna(latest_start)
        else grouped.iloc[0:0].copy()
    )
    latest_anom = (
        latest[latest["_is_anomaly"]]
        .sort_values("_score", ascending=False)
        .head(int(top_n))
    )

    all_anom = (
        grouped[grouped["_is_anomaly"]]
        .sort_values("_score", ascending=False)
        .head(int(top_n))
    )

    def _safe_float(x):
        try:
            if x is None or pd.isna(x):
                return None
            return float(x)
        except Exception:
            return None

    top_rows: list[dict[str, Any]] = []
    for _, r in latest_anom.iterrows():
        # Raison: top 3 contributeurs en z (calculée uniquement pour les lignes affichées)
        parts = []
        for m in present_metrics:
            z = r.get(f"z_{m.lower()}")
            if z is None or (isinstance(z, float) and np.isnan(z)):
                continue
            parts.append((m, float(z)))
        parts.sort(key=lambda t: abs(t[1]), reverse=True)
        reason = (
            ", ".join([f"{m}: z={z:+.2f}" for m, z in parts[:3]]) if parts else None
        )

        top_rows.append(
            {
                "client": "" if pd.isna(r.get("Client")) else str(r.get("Client")),
                "period": (
                    None
                    if pd.isna(r.get("_period_label"))
                    else str(r.get("_period_label"))
                ),
                "score": _safe_float(r.get("_score")),
                "main_metric": (
                    None
                    if pd.isna(r.get("_main_metric"))
                    else str(r.get("_main_metric"))
                ),
                "direction": (
                    None if pd.isna(r.get("_direction")) else str(r.get("_direction"))
                ),
                "ca": _safe_float(r.get("CA")),
                "qty": _safe_float(r.get("Qty")),
                "freq": _safe_float(r.get("Freq")),
                "price": _safe_float(r.get("Price")),
                "reason": reason,
            }
        )

    base["top_anomalies_latest"] = top_rows

    top_all_rows: list[dict[str, Any]] = []
    for _, r in all_anom.iterrows():
        parts = []
        for m in present_metrics:
            z = r.get(f"z_{m.lower()}")
            if z is None or (isinstance(z, float) and np.isnan(z)):
                continue
            parts.append((m, float(z)))
        parts.sort(key=lambda t: abs(t[1]), reverse=True)
        reason = (
            ", ".join([f"{m}: z={z:+.2f}" for m, z in parts[:3]]) if parts else None
        )

        top_all_rows.append(
            {
                "client": "" if pd.isna(r.get("Client")) else str(r.get("Client")),
                "period": (
                    None
                    if pd.isna(r.get("_period_label"))
                    else str(r.get("_period_label"))
                ),
                "score": _safe_float(r.get("_score")),
                "main_metric": (
                    None
                    if pd.isna(r.get("_main_metric"))
                    else str(r.get("_main_metric"))
                ),
                "direction": (
                    None if pd.isna(r.get("_direction")) else str(r.get("_direction"))
                ),
                "ca": _safe_float(r.get("CA")),
                "qty": _safe_float(r.get("Qty")),
                "freq": _safe_float(r.get("Freq")),
                "price": _safe_float(r.get("Price")),
                "reason": reason,
            }
        )

    base["top_anomalies_all"] = top_all_rows
    base["kpis"] = {
        "latest_period": latest_label,
        "n_anomalies_latest": int(latest_anom.shape[0]),
        "n_clients_anomalous_latest": (
            int(latest_anom["Client"].nunique()) if latest_anom.shape[0] else 0
        ),
        "n_anomalies_total": int(grouped["_is_anomaly"].sum()),
        "n_clients_total": int(grouped["Client"].nunique()),
        "metrics_used": present_metrics,
    }

    if include_scatter:
        try:
            from .visualizations import viz_anomalies

            base["graphs"]["scatter_latest"] = (
                viz_anomalies.create_client_anomalies_scatter(
                    latest, z_thresh=float(z_thresh)
                )
            )
        except Exception:
            base["graphs"]["scatter_latest"] = None

    return base


def analyze_client_anomalies_for_client(
    df: pd.DataFrame,
    client_id: str,
    time_granularity: str = "month",
    z_thresh: float = 3.5,
    window: int | None = None,
    min_history: int | None = None,
    fiscal_year_start_month: int = 4,
    max_anomalies_per_metric: int = 20,
) -> dict[str, Any]:
    """Analyse les anomalies pour un client précis.

    Retourne un dict sérialisable contenant:
    - kpis
    - anomalies_by_metric: listes de périodes anormales par métrique
    - series: série agrégée par période avec valeurs et z-scores
    """

    out: dict[str, Any] = {
        "meta": {
            "time_granularity": time_granularity,
            "z_thresh": float(z_thresh),
            "window": None,
            "min_history": None,
        },
        "client": {"id": str(client_id) if client_id is not None else None},
        "kpis": {},
        "anomalies_by_metric": {},
        "series": [],
    }

    if not client_id:
        out["error"] = "Client non spécifié."
        return out

    if df is None or df.empty:
        out["error"] = "DataFrame vide."
        return out

    spec = _default_period_spec(time_granularity)
    tg = spec.granularity
    win = int(window or spec.window)
    min_hist = int(min_history or spec.min_history)
    out["meta"]["time_granularity"] = tg
    out["meta"]["window"] = win
    out["meta"]["min_history"] = min_hist

    client_col = _pick_col(df, ["Cpt Client", "Compte Client", "Client", "Code Client"])
    date_col = _pick_col(
        df, ["Date Fact.", "Date_Ref", "Date", "Date facture", "Date Facture"]
    )
    amount_col = _pick_col(df, ["Montant", "CA", "CA Net", "Chiffre d'Affaires"])
    qty_col = _pick_col(df, ["Quantité", "Quantite", "Qty", "Qte", "Qté", "Quantity"])
    order_col = _pick_col(
        df,
        [
            "N° Bon",
            "No Bon",
            "N Bon",
            "Num Bon",
            "Numéro Bon",
            "Commande",
            "N° Commande",
            "Order",
        ],
    )

    out["meta"]["columns"] = {
        "client": client_col,
        "date": date_col,
        "amount": amount_col,
        "qty": qty_col,
        "order": order_col,
    }

    if not client_col or not date_col or not amount_col:
        out["error"] = "Colonnes requises manquantes (client/date/montant)."
        return out

    # Filtrer sur le client
    df_client = df[df[client_col].astype(str) == str(client_id)].copy()
    if df_client.empty:
        out["error"] = f"Aucune ligne trouvée pour le client '{client_id}'."
        return out

    keep_cols = [
        c
        for c in [
            client_col,
            date_col,
            amount_col,
            qty_col,
            order_col,
            "Fiscal_Quarter",
            "Fiscal_Year_Label",
        ]
        if c and c in df_client.columns
    ]
    df2 = df_client[keep_cols].copy()
    df2[amount_col] = pd.to_numeric(df2[amount_col], errors="coerce")
    if qty_col and qty_col in df2.columns:
        df2[qty_col] = pd.to_numeric(df2[qty_col], errors="coerce")
    df2[date_col] = _to_datetime(df2[date_col])
    df2 = df2.dropna(subset=[date_col])
    if df2.empty:
        out["error"] = "Aucune ligne exploitable après nettoyage (date)."
        return out

    df2 = _build_period_columns(
        df2, df2[date_col], tg, fiscal_year_start_month=fiscal_year_start_month
    )

    agg_spec: dict[str, Any] = {amount_col: "sum"}
    if qty_col and qty_col in df2.columns:
        agg_spec[qty_col] = "sum"
    if order_col and order_col in df2.columns:
        agg_spec[order_col] = pd.Series.nunique
    else:
        df2["_line_count"] = 1
        agg_spec["_line_count"] = "sum"

    grouped = (
        df2.groupby(["_period_start", "_period_label"], dropna=False)
        .agg(agg_spec)
        .reset_index()
    )
    grouped = grouped.rename(columns={amount_col: "CA"})
    if qty_col and qty_col in grouped.columns:
        grouped = grouped.rename(columns={qty_col: "Qty"})
    else:
        grouped["Qty"] = np.nan
    if order_col and order_col in grouped.columns:
        grouped = grouped.rename(columns={order_col: "Freq"})
    else:
        grouped["Freq"] = grouped.get("_line_count")

    grouped["Freq"] = pd.to_numeric(grouped["Freq"], errors="coerce")
    grouped["CA"] = pd.to_numeric(grouped["CA"], errors="coerce")
    grouped["Qty"] = pd.to_numeric(grouped["Qty"], errors="coerce")
    grouped["Price"] = grouped["CA"] / grouped["Qty"].where(grouped["Qty"] > 0)
    grouped = grouped.drop(columns=[c for c in ["_line_count"] if c in grouped.columns])
    grouped = grouped.sort_values(["_period_start"], kind="mergesort").reset_index(
        drop=True
    )

    metric_cols = ["CA", "Qty", "Freq", "Price"]
    present_metrics = [m for m in metric_cols if grouped[m].notna().any()]
    if not present_metrics:
        out["error"] = "Aucune métrique exploitable pour la détection."
        return out

    # === DÉTECTION ML AVEC ISOLATION FOREST ===
    # On utilise CA, Qty, Freq comme features multivariées
    ml_features = ["CA", "Qty", "Freq"]
    ml_features_available = [f for f in ml_features if f in present_metrics]

    # Détection globale multivariée
    is_anomaly_ml, anomaly_score_ml = _detect_anomalies_ml(
        grouped,
        ml_features_available,
        contamination=min(0.15, max(0.05, 1.0 / max(len(grouped), 1))),  # Adaptatif
        min_samples=max(5, min_hist),
    )

    grouped["is_anomaly_ml"] = is_anomaly_ml
    grouped["anomaly_score_ml"] = anomaly_score_ml

    # Pour chaque métrique, on attribue l'anomalie ML et on calcule la direction
    for m in present_metrics:
        if m in ml_features_available:
            # Utiliser la détection ML
            grouped[f"is_anomaly_{m.lower()}"] = is_anomaly_ml
            grouped[f"anomaly_score_{m.lower()}"] = anomaly_score_ml

            # Direction basée sur la déviation par rapport à la médiane historique
            hist_median = (
                grouped[m].shift(1).rolling(window=win, min_periods=min_hist).median()
            )
            deviation = grouped[m] - hist_median
            grouped[f"direction_{m.lower()}"] = np.where(
                deviation >= 0, "hausse", "baisse"
            )
            grouped.loc[grouped[m].isna(), f"direction_{m.lower()}"] = None
        else:
            # Pour Price, utiliser l'ancienne méthode z-score
            z = _robust_z_from_history(grouped[m], window=win, min_history=min_hist)
            grouped[f"z_{m.lower()}"] = z
            grouped[f"is_anomaly_{m.lower()}"] = z.abs() >= float(z_thresh)
            grouped[f"anomaly_score_{m.lower()}"] = z.abs()
            grouped[f"direction_{m.lower()}"] = np.where(z >= 0, "hausse", "baisse")
            grouped.loc[z.isna(), f"direction_{m.lower()}"] = None
            grouped.loc[z.isna(), f"is_anomaly_{m.lower()}"] = False

    # Séries sérialisables
    def _safe_float(x):
        try:
            if x is None or pd.isna(x):
                return None
            return float(x)
        except Exception:
            return None

    series_rows: list[dict[str, Any]] = []
    for _, r in grouped.iterrows():
        row = {
            "period": (
                None if pd.isna(r.get("_period_label")) else str(r.get("_period_label"))
            ),
            "ca": _safe_float(r.get("CA")),
            "qty": _safe_float(r.get("Qty")),
            "freq": _safe_float(r.get("Freq")),
            "price": _safe_float(r.get("Price")),
            "anomaly_score_ca": _safe_float(r.get("anomaly_score_ca")),
            "anomaly_score_qty": _safe_float(r.get("anomaly_score_qty")),
            "anomaly_score_freq": _safe_float(r.get("anomaly_score_freq")),
            "anomaly_score_price": _safe_float(r.get("anomaly_score_price")),
            "is_anomaly_ca": bool(r.get("is_anomaly_ca", False)),
            "is_anomaly_qty": bool(r.get("is_anomaly_qty", False)),
            "is_anomaly_freq": bool(r.get("is_anomaly_freq", False)),
            "is_anomaly_price": bool(r.get("is_anomaly_price", False)),
            "is_anomaly_ml": bool(r.get("is_anomaly_ml", False)),
            "anomaly_score_ml": _safe_float(r.get("anomaly_score_ml")),
            "direction_ca": r.get("direction_ca"),
            "direction_qty": r.get("direction_qty"),
            "direction_freq": r.get("direction_freq"),
            "direction_price": r.get("direction_price"),
        }
        series_rows.append(row)
    out["series"] = series_rows

    # Anomalies par métrique
    anomalies_by_metric: dict[str, list[dict[str, Any]]] = {}
    for m in present_metrics:
        scorecol = f"anomaly_score_{m.lower()}"
        flagcol = f"is_anomaly_{m.lower()}"
        dcol = f"direction_{m.lower()}"
        subset = grouped[grouped[flagcol]].copy()
        if scorecol in subset.columns and subset[scorecol].notna().any():
            subset = subset.sort_values(scorecol, ascending=False).head(
                int(max_anomalies_per_metric)
            )
        rows = []
        for _, r in subset.iterrows():
            rows.append(
                {
                    "period": (
                        None
                        if pd.isna(r.get("_period_label"))
                        else str(r.get("_period_label"))
                    ),
                    "value": _safe_float(r.get(m)),
                    "anomaly_score": _safe_float(r.get(scorecol)),
                    "direction": r.get(dcol),
                }
            )
        anomalies_by_metric[m] = rows

    out["anomalies_by_metric"] = anomalies_by_metric

    latest_label = None
    if not grouped.empty:
        latest_label = grouped["_period_label"].dropna().astype(str).tail(1).tolist()
        latest_label = latest_label[0] if latest_label else None

    out["kpis"] = {
        "latest_period": latest_label,
        "metrics_used": present_metrics,
        "n_periods": int(grouped.shape[0]),
        "n_anomalies_ca": (
            int(grouped.get("is_anomaly_ca", pd.Series(False)).sum())
            if "is_anomaly_ca" in grouped.columns
            else 0
        ),
        "n_anomalies_qty": (
            int(grouped.get("is_anomaly_qty", pd.Series(False)).sum())
            if "is_anomaly_qty" in grouped.columns
            else 0
        ),
        "n_anomalies_freq": (
            int(grouped.get("is_anomaly_freq", pd.Series(False)).sum())
            if "is_anomaly_freq" in grouped.columns
            else 0
        ),
        "n_anomalies_price": (
            int(grouped.get("is_anomaly_price", pd.Series(False)).sum())
            if "is_anomaly_price" in grouped.columns
            else 0
        ),
    }

    return out
