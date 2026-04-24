"""
Service pour l'onglet CLUSTERING
Clustering K-Means automatique avec feature engineering avancé
Adapté du notebook week_1_clean.ipynb
"""
import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score,
    calinski_harabasz_score,
)
from django.conf import settings

from .visualizations.viz_clustering import (
    create_clustering_pca_plot,
    create_elbow_silhouette_plot,
    create_cluster_distribution_plot,
)

# ─── Constants ────────────────────────────────────────────────────────
TOP_N_FAMILLES = 30
K_RANGE = range(2, 11)
RANDOM_STATE = 42


# ─── Helpers ──────────────────────────────────────────────────────────
def _safe_div(a, b):
    """Division robuste : renvoie 0 si b == 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    out = np.zeros_like(a, dtype=float)
    m = b != 0
    out[m] = a[m] / b[m]
    return out


def _open_business_days(start, end):
    """Nombre de jours ouvrés entre deux dates."""
    days = pd.bdate_range(start=start, end=end, freq="B")
    return max(int(len(days)), 1)


# ─── Feature engineering ─────────────────────────────────────────────
def build_client_features(df):
    """
    Construit un DataFrame client-level avec features riches
    (intensités/jour ouvert, logs, ratios, PU Net, CA et parts par famille,
    temps entre commandes, country, diversité).

    Returns
    -------
    (df_client, top_familles)
    """
    df = df.dropna(subset=["Date Cde"]).copy()

    # Top familles par CA
    top_familles = []
    if "Famille" in df.columns:
        top_familles = (
            df.groupby("Famille")["Montant"]
            .sum()
            .sort_values(ascending=False)
            .head(TOP_N_FAMILLES)
            .index.tolist()
        )

    # Jours ouvrés dans la période
    open_days = _open_business_days(df["Date Cde"].min(), df["Date Cde"].max())

    # ── 1) Agrégats client ────────────────────────────────────────────
    agg_dict = {"Montant": ["sum", "mean"], "Quantité": "sum"}
    if "N° Bon" in df.columns:
        agg_dict["N° Bon"] = "nunique"
    if "Delai_Prev_Days" in df.columns:
        agg_dict["Delai_Prev_Days"] = "mean"

    df_client = df.groupby("Cpt Client").agg(agg_dict).reset_index()

    # Flatten multi-index columns
    new_cols = []
    for col in df_client.columns:
        if isinstance(col, tuple):
            new_cols.append("_".join(str(c) for c in col if c).strip("_"))
        else:
            new_cols.append(col)
    df_client.columns = new_cols

    rename_map = {
        "Montant_sum": "CA_Total",
        "Montant_mean": "CA_Moyen",
        "Quantité_sum": "Qty_Total",
    }
    if "N° Bon_nunique" in df_client.columns:
        rename_map["N° Bon_nunique"] = "Nb_Commandes"
    if "Delai_Prev_Days_mean" in df_client.columns:
        rename_map["Delai_Prev_Days_mean"] = "Delai_Moyen"
    df_client = df_client.rename(columns=rename_map)

    if "Nb_Commandes" not in df_client.columns:
        df_client["Nb_Commandes"] = df.groupby("Cpt Client").size().values
    if "Delai_Moyen" not in df_client.columns:
        df_client["Delai_Moyen"] = 0

    # ── 2) Intensités par jour ouvert ─────────────────────────────────
    df_client["CA_par_jour_ouvert"] = df_client["CA_Total"] / open_days
    df_client["Qty_par_jour_ouvert"] = df_client["Qty_Total"] / open_days
    df_client["Cmd_par_jour_ouvert"] = df_client["Nb_Commandes"] / open_days

    # ── 3) Ratios comportementaux ─────────────────────────────────────
    df_client["Panier_moyen"] = _safe_div(
        df_client["CA_Total"].values, df_client["Nb_Commandes"].values
    )
    df_client["Qty_par_commande"] = _safe_div(
        df_client["Qty_Total"].values, df_client["Nb_Commandes"].values
    )
    df_client["CA_par_qty"] = _safe_div(
        df_client["CA_Total"].values, df_client["Qty_Total"].values
    )

    # ── 4) Log transforms ────────────────────────────────────────────
    for col in [
        "CA_par_jour_ouvert",
        "Qty_par_jour_ouvert",
        "Cmd_par_jour_ouvert",
        "CA_Moyen",
        "Panier_moyen",
        "Qty_par_commande",
        "CA_par_qty",
    ]:
        df_client[f"log_{col}"] = np.log1p(
            df_client[col].astype(float).clip(lower=0)
        )

    # ── 5) PU Net moyen par famille ───────────────────────────────────
    if "Famille" in df.columns and "PU Net" in df.columns:
        mat_punet = df.pivot_table(
            index="Cpt Client", columns="Famille", values="PU Net", aggfunc="mean"
        )
        for fam in top_familles:
            if fam in mat_punet.columns:
                col_name = f"PU_Net_{fam}"
                df_client = df_client.merge(
                    mat_punet[[fam]].rename(columns={fam: col_name}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col_name] = df_client[col_name].fillna(0)

    # ── 6) CA par famille + parts de CA ───────────────────────────────
    if "Famille" in df.columns:
        mat_ca = df.pivot_table(
            index="Cpt Client", columns="Famille", values="Montant", aggfunc="sum"
        )
        for fam in top_familles:
            if fam in mat_ca.columns:
                col_name = f"CA_{fam}"
                df_client = df_client.merge(
                    mat_ca[[fam]].rename(columns={fam: col_name}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col_name] = df_client[col_name].fillna(0)
                df_client[f"Part_CA_{fam}"] = _safe_div(
                    df_client[col_name].values, df_client["CA_Total"].values
                )

    # ── 7) Temps entre commandes par famille ──────────────────────────
    if "Famille" in df.columns:
        df_sorted = df.sort_values(["Cpt Client", "Famille", "Date Cde"])
        df_sorted["Date_Suivante"] = df_sorted.groupby(
            ["Cpt Client", "Famille"]
        )["Date Cde"].shift(-1)
        df_sorted["Jours_Entre_Cmd"] = (
            df_sorted["Date_Suivante"] - df_sorted["Date Cde"]
        ).dt.days

        temp = (
            df_sorted.groupby(["Cpt Client", "Famille"])["Jours_Entre_Cmd"]
            .mean()
            .reset_index()
        )
        mat_temps = temp.pivot_table(
            index="Cpt Client",
            columns="Famille",
            values="Jours_Entre_Cmd",
            aggfunc="mean",
        )
        for fam in top_familles:
            if fam in mat_temps.columns:
                col_name = f"Temps_Entre_Cmd_{fam}"
                df_client = df_client.merge(
                    mat_temps[[fam]].rename(columns={fam: col_name}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col_name] = df_client[col_name].fillna(0)

    # ── 8) Country + encoding ─────────────────────────────────────────
    if "Country" in df.columns:
        country_map = df.groupby("Cpt Client")["Country"].first().to_dict()
        df_client["Country"] = (
            df_client["Cpt Client"].map(country_map).fillna("UNKNOWN")
        )
        le = LabelEncoder()
        df_client["Country_Encoded"] = le.fit_transform(
            df_client["Country"].astype(str)
        )
    else:
        df_client["Country"] = "UNKNOWN"
        df_client["Country_Encoded"] = 0

    # ── 9) Diversité produit ──────────────────────────────────────────
    if "Famille" in df.columns:
        nb_fam = df.groupby("Cpt Client")["Famille"].nunique().to_dict()
        df_client["Nb_Familles_Distinctes"] = (
            df_client["Cpt Client"].map(nb_fam).fillna(0)
        )
    else:
        df_client["Nb_Familles_Distinctes"] = 0

    # Fill remaining NaN
    num_cols = df_client.select_dtypes(include=[np.number]).columns
    df_client[num_cols] = df_client[num_cols].fillna(0)

    return df_client, top_familles


def get_features_list(df_client, top_familles):
    """Retourne la liste des features à utiliser pour le clustering."""
    feats = [
        "log_CA_par_jour_ouvert",
        "log_Qty_par_jour_ouvert",
        "log_Cmd_par_jour_ouvert",
        "log_CA_Moyen",
        "log_Panier_moyen",
        "log_Qty_par_commande",
        "log_CA_par_qty",
        "Country_Encoded",
        "Nb_Familles_Distinctes",
        "Delai_Moyen",
    ]
    for fam in top_familles:
        feats.append(f"PU_Net_{fam}")
    for fam in top_familles:
        feats.append(f"Part_CA_{fam}")
    for fam in top_familles:
        feats.append(f"Temps_Entre_Cmd_{fam}")

    return [f for f in feats if f in df_client.columns]


# ─── Optimal K selection ─────────────────────────────────────────────
def find_optimal_k(X_scaled):
    """Teste K=2..10, retourne le K optimal (silhouette) et les métriques."""
    results = []
    for k in K_RANGE:
        if X_scaled.shape[0] <= k:
            break
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10, max_iter=300)
        labels = km.fit_predict(X_scaled)
        if len(np.unique(labels)) < 2:
            continue
        results.append(
            {
                "k": k,
                "inertia": float(km.inertia_),
                "silhouette": float(silhouette_score(X_scaled, labels)),
                "davies_bouldin": float(davies_bouldin_score(X_scaled, labels)),
                "calinski_harabasz": float(
                    calinski_harabasz_score(X_scaled, labels)
                ),
            }
        )

    if not results:
        return {"optimal_k": 2, "metrics": []}

    best = max(results, key=lambda r: r["silhouette"])
    return {"optimal_k": best["k"], "metrics": results}


# ─── Cluster profiling ───────────────────────────────────────────────
def build_cluster_profiles(df_client, top_familles, n_clusters):
    """Construit le profil détaillé de chaque cluster."""
    profiles = []
    ca_fam_cols = [
        f"CA_{fam}" for fam in top_familles if f"CA_{fam}" in df_client.columns
    ]

    for cluster_id in range(n_clusters):
        cluster_data = df_client[df_client["Cluster"] == cluster_id]
        n = len(cluster_data)
        if n == 0:
            continue

        profile = {
            "id": cluster_id,
            "nb_clients": n,
            "pct": round(n / len(df_client) * 100, 1),
            "ca_total_moyen": round(float(cluster_data["CA_Total"].mean()), 2),
            "ca_total_sum": round(float(cluster_data["CA_Total"].sum()), 2),
            "qty_total_moyen": round(float(cluster_data["Qty_Total"].mean()), 2),
            "nb_commandes_moyen": round(
                float(cluster_data["Nb_Commandes"].mean()), 1
            ),
            "panier_moyen": round(
                float(cluster_data["Panier_moyen"].mean()), 2
            ),
            "delai_moyen": round(
                float(cluster_data["Delai_Moyen"].mean()), 1
            ),
            "nb_familles_moyen": round(
                float(cluster_data["Nb_Familles_Distinctes"].mean()), 1
            ),
        }

        # Top 5 familles par CA moyen
        if ca_fam_cols:
            fam_ca = {}
            for col in ca_fam_cols:
                fam_name = col.replace("CA_", "")
                ca_mean = float(cluster_data[col].mean())
                if ca_mean > 0:
                    fam_ca[fam_name] = round(ca_mean, 2)
            top_fam = sorted(fam_ca.items(), key=lambda x: x[1], reverse=True)[
                :5
            ]
            profile["top_familles"] = [
                {"nom": f, "ca_moyen": v} for f, v in top_fam
            ]
        else:
            profile["top_familles"] = []

        # Top 3 pays
        if "Country" in cluster_data.columns:
            top_pays = cluster_data["Country"].value_counts().head(3)
            profile["top_pays"] = [
                {
                    "pays": pays,
                    "count": int(count),
                    "pct": round(count / n * 100, 1),
                }
                for pays, count in top_pays.items()
            ]
        else:
            profile["top_pays"] = []

        profiles.append(profile)

    return profiles


# ─── Main entry point ────────────────────────────────────────────────
def generate_clustering_analysis(df):
    """
    Génère l'analyse de clustering complète automatique.

    Args:
        df: DataFrame des transactions brutes (post-processing)

    Returns:
        dict avec 'results', 'graphs', 'kpis'
    """
    try:
        if df is None or df.empty:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": "Aucune donnee disponible pour lancer le clustering.",
            }

        # 1) Feature engineering
        df_client, top_familles = build_client_features(df)
        if len(df_client) < 3:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": (
                    "Le clustering requiert au moins 3 clients distincts "
                    "sur le perimetre analyse."
                ),
            }

        features = get_features_list(df_client, top_familles)

        if len(features) < 2:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": "Pas assez de features pour le clustering",
            }

        X = df_client[features].fillna(0)

        # 2) Scaling
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 3) Optimal K
        k_result = find_optimal_k(X_scaled)
        optimal_k = k_result["optimal_k"]

        # 4) Final clustering
        kmeans = KMeans(
            n_clusters=optimal_k, random_state=RANDOM_STATE, n_init=20, max_iter=500
        )
        df_client["Cluster"] = kmeans.fit_predict(X_scaled)

        sil = float(silhouette_score(X_scaled, df_client["Cluster"]))
        db = float(davies_bouldin_score(X_scaled, df_client["Cluster"]))
        ch = float(calinski_harabasz_score(X_scaled, df_client["Cluster"]))

        # 5) Profiles
        profiles = build_cluster_profiles(df_client, top_familles, optimal_k)

        # 6) Graphs
        graphs = {}
        pca_plot = create_clustering_pca_plot(df_client, X_scaled)
        if pca_plot:
            graphs["clustering_pca"] = pca_plot

        elbow_plot = create_elbow_silhouette_plot(k_result["metrics"], optimal_k)
        if elbow_plot:
            graphs["elbow_silhouette"] = elbow_plot

        distrib_plot = create_cluster_distribution_plot(profiles)
        if distrib_plot:
            graphs["cluster_distribution"] = distrib_plot

        # 7) Pack results
        kpis = {
            "nb_clusters": optimal_k,
            "silhouette_score": round(sil, 4),
            "davies_bouldin_score": round(db, 4),
            "calinski_harabasz_score": round(ch, 2),
            "nb_clients": len(df_client),
            "nb_features": len(features),
            "inertia": round(float(kmeans.inertia_), 2),
        }

        results = {
            "profiles": profiles,
            "k_metrics": k_result["metrics"],
            "features_used": features,
            "top_familles": top_familles,
        }

        return {"results": results, "graphs": graphs, "kpis": kpis}

    except Exception as e:
        return {"results": {}, "graphs": {}, "kpis": {}, "error": str(e)}


def get_quarterly_clustering_available_years(df):
    """Liste les annees calendaires disponibles pour le clustering notebook."""
    if df is None or df.empty or "Date Cde" not in df.columns:
        return []

    date_series = df["Date Cde"]
    if not np.issubdtype(date_series.dtype, np.datetime64):
        date_series = pd.to_datetime(date_series, errors="coerce")

    return sorted(date_series.dt.year.dropna().astype(int).unique().tolist())


def get_notebook_closed_periods_by_year():
    """Retourne la configuration des periodes fermees definie dans settings."""
    return getattr(
        settings,
        "CLUSTERING_NOTEBOOK_CLOSED_PERIODS_BY_YEAR",
        {2024: [("2024-08-01", "2024-08-26")]},
    )


def generate_quarterly_clustering_analysis(df, year=None):
    """
    Portage fidele de la cellule "CLUSTERING TRIMESTRIEL 2024 + VACANCES"
    du notebook week_1_clean.ipynb, rendu parametrable par annee.
    """
    RANDOM_STATE = 42
    K_RANGE = range(2, 11)

    def quarter_start_end(quarter_str: str):
        p = pd.Period(quarter_str, freq="Q")
        return p.start_time.normalize(), p.end_time.normalize()

    def open_business_days_in_quarter(quarter_str: str, closed_periods=None) -> int:
        start, end = quarter_start_end(quarter_str)
        days = pd.bdate_range(start=start, end=end, freq="B")
        if closed_periods:
            mask = pd.Series(False, index=days)
            for cstart, cend in closed_periods:
                cstart = pd.Timestamp(cstart)
                cend = pd.Timestamp(cend)
                mask |= (days >= cstart) & (days <= cend)
            days = days[~mask.values]
        return int(len(days))

    def safe_div(a, b):
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        out = np.zeros_like(a, dtype=float)
        m = b != 0
        out[m] = a[m] / b[m]
        return out

    def align_labels_by_centroids(
        centroids_ref: np.ndarray,
        centroids_new: np.ndarray,
        labels_new: np.ndarray,
    ) -> np.ndarray:
        dists = np.linalg.norm(
            centroids_ref[:, None, :] - centroids_new[None, :, :], axis=2
        )
        row_ind, col_ind = linear_sum_assignment(dists)
        mapping = {new: ref for ref, new in zip(row_ind, col_ind)}
        aligned = np.vectorize(lambda x: mapping.get(x, x))(labels_new)
        return aligned

    def build_client_features_for_quarter(
        df_trim: pd.DataFrame, top_familles: list, open_days: int
    ) -> pd.DataFrame:
        df_trim = df_trim.dropna(subset=["Date Cde"]).copy()
        open_days = max(int(open_days), 1)

        df_client = df_trim.groupby("Cpt Client").agg(
            CA_Total=("Montant", "sum"),
            CA_Moyen=("Montant", "mean"),
            Qty_Total=("Quantité", "sum"),
            Delai_Moyen=("Delai_Prev_Days", "mean"),
            Nb_Commandes=("N° Bon", "nunique"),
        ).reset_index()

        df_client["CA_par_jour_ouvert"] = df_client["CA_Total"] / open_days
        df_client["Qty_par_jour_ouvert"] = df_client["Qty_Total"] / open_days
        df_client["Cmd_par_jour_ouvert"] = df_client["Nb_Commandes"] / open_days

        df_client["Panier_moyen"] = safe_div(
            df_client["CA_Total"], df_client["Nb_Commandes"]
        )
        df_client["Qty_par_commande"] = safe_div(
            df_client["Qty_Total"], df_client["Nb_Commandes"]
        )
        df_client["CA_par_qty"] = safe_div(
            df_client["CA_Total"], df_client["Qty_Total"]
        )

        for col in [
            "CA_par_jour_ouvert",
            "Qty_par_jour_ouvert",
            "Cmd_par_jour_ouvert",
            "CA_Moyen",
            "Panier_moyen",
            "Qty_par_commande",
            "CA_par_qty",
        ]:
            df_client[f"log_{col}"] = np.log1p(
                df_client[col].astype(float).clip(lower=0)
            )

        mat_punet = df_trim.pivot_table(
            index="Cpt Client", columns="Famille", values="PU Net", aggfunc="mean"
        )
        for fam in top_familles:
            if fam in mat_punet.columns:
                col = f"PU_Net_{fam}"
                df_client = df_client.merge(
                    mat_punet[[fam]].rename(columns={fam: col}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col] = df_client[col].fillna(0)

        df_trim["CA_Famille"] = df_trim["Montant"]
        mat_ca = df_trim.pivot_table(
            index="Cpt Client",
            columns="Famille",
            values="CA_Famille",
            aggfunc="sum",
        )
        for fam in top_familles:
            if fam in mat_ca.columns:
                col = f"CA_{fam}"
                df_client = df_client.merge(
                    mat_ca[[fam]].rename(columns={fam: col}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col] = df_client[col].fillna(0)
                df_client[f"Part_CA_{fam}"] = safe_div(
                    df_client[col], df_client["CA_Total"]
                )

        df_sorted = df_trim.sort_values(["Cpt Client", "Famille", "Date Cde"])
        df_sorted["Date_Suivante"] = df_sorted.groupby(
            ["Cpt Client", "Famille"]
        )["Date Cde"].shift(-1)
        df_sorted["Jours_Entre_Cmd"] = (
            df_sorted["Date_Suivante"] - df_sorted["Date Cde"]
        ).dt.days

        temp = (
            df_sorted.groupby(["Cpt Client", "Famille"])["Jours_Entre_Cmd"]
            .mean()
            .reset_index()
        )
        mat_temps = temp.pivot_table(
            index="Cpt Client",
            columns="Famille",
            values="Jours_Entre_Cmd",
            aggfunc="mean",
        )
        for fam in top_familles:
            if fam in mat_temps.columns:
                col = f"Temps_Entre_Cmd_{fam}"
                df_client = df_client.merge(
                    mat_temps[[fam]].rename(columns={fam: col}),
                    left_on="Cpt Client",
                    right_index=True,
                    how="left",
                )
                df_client[col] = df_client[col].fillna(0)

        country_map = df_trim.groupby("Cpt Client")["Country"].first().to_dict()
        df_client["Country"] = (
            df_client["Cpt Client"].map(country_map).fillna("UNKNOWN")
        )

        nb_fam = df_trim.groupby("Cpt Client")["Famille"].nunique().to_dict()
        df_client["Nb_Familles_Distinctes"] = (
            df_client["Cpt Client"].map(nb_fam).fillna(0)
        )

        return df_client

    def get_quarter_features_list(df_client: pd.DataFrame, top_familles: list) -> list:
        feats = [
            "log_CA_par_jour_ouvert",
            "log_Qty_par_jour_ouvert",
            "log_Cmd_par_jour_ouvert",
            "log_CA_Moyen",
            "log_Panier_moyen",
            "log_Qty_par_commande",
            "log_CA_par_qty",
            "Country_Encoded",
            "Nb_Familles_Distinctes",
            "Delai_Moyen",
        ]
        for fam in top_familles:
            feats.append(f"PU_Net_{fam}")
        for fam in top_familles:
            feats.append(f"Part_CA_{fam}")
        for fam in top_familles:
            feats.append(f"Temps_Entre_Cmd_{fam}")
        return [f for f in feats if f in df_client.columns]

    try:
        df_final = df.copy()
        available_years = get_quarterly_clustering_available_years(df_final)

        if "Date Cde" not in df_final.columns:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": "Le clustering trimestriel du notebook requiert la colonne 'Date Cde'.",
            }

        if not np.issubdtype(df_final["Date Cde"].dtype, np.datetime64):
            df_final["Date Cde"] = pd.to_datetime(df_final["Date Cde"], errors="coerce")

        if year is None:
            selected_year = available_years[-1] if available_years else None
        else:
            try:
                selected_year = int(year)
            except (TypeError, ValueError):
                return {
                    "results": {},
                    "graphs": {},
                    "kpis": {},
                    "error": "L'annee selectionnee est invalide pour le clustering trimestriel.",
                }

        if selected_year is None:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": "Aucune date exploitable n'est disponible pour le clustering trimestriel.",
            }

        # Le notebook source travaille avec un Quarter calendaire (to_period("Q")).
        df_final["Quarter"] = df_final["Date Cde"].dt.to_period("Q").astype(str)

        df_final = df_final.dropna(subset=["Date Cde"])
        df_year = df_final[
            df_final["Quarter"].astype(str).str.startswith(f"{selected_year}", na=False)
        ].copy()
        closed_periods = get_notebook_closed_periods_by_year().get(selected_year, [])

        if df_year.empty:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": (
                    f"Aucune donnee {selected_year} disponible pour executer le "
                    "clustering trimestriel du notebook."
                ),
            }

        trimestres = sorted(df_year["Quarter"].unique())
        top_familles = (
            df_year.groupby("Famille")["Montant"]
            .sum()
            .sort_values(ascending=False)
            .head(TOP_N_FAMILLES)
            .index.tolist()
        )
        all_clients = sorted(df_year["Cpt Client"].unique())
        country_global = df_year.groupby("Cpt Client")["Country"].first().to_dict()

        client_dfs = {}
        feature_lists = {}
        quarterly_summaries = []

        for trim in trimestres:
            df_trim = df_year[df_year["Quarter"] == trim].copy()
            open_days = open_business_days_in_quarter(trim, closed_periods)

            df_client_active = build_client_features_for_quarter(
                df_trim, top_familles, open_days
            )
            df_client_active["Trimestre"] = trim

            base = pd.DataFrame({"Cpt Client": all_clients, "Trimestre": trim})
            df_client = base.merge(
                df_client_active, on=["Cpt Client", "Trimestre"], how="left"
            )

            df_client["Nb_Commandes"] = df_client["Nb_Commandes"].fillna(0)
            df_client["is_active"] = (df_client["Nb_Commandes"] > 0).astype(int)

            num_cols = df_client.select_dtypes(include=[np.number]).columns
            df_client[num_cols] = df_client[num_cols].fillna(0)

            df_client["Country"] = (
                df_client["Country"]
                .fillna(df_client["Cpt Client"].map(country_global))
                .fillna("UNKNOWN")
            )

            client_dfs[trim] = df_client
            quarterly_summaries.append(
                {
                    "trimestre": trim,
                    "transactions": int(len(df_trim)),
                    "jours_ouverts": int(max(open_days, 1)),
                    "nb_clients_total": int(len(df_client)),
                    "nb_clients_actifs": int(df_client["is_active"].sum()),
                }
            )

        all_countries = pd.concat(
            [client_dfs[t]["Country"] for t in trimestres], axis=0
        ).astype(str).fillna("UNKNOWN")
        le_country = LabelEncoder().fit(all_countries)

        for trim in trimestres:
            client_dfs[trim]["Country_Encoded"] = le_country.transform(
                client_dfs[trim]["Country"].astype(str).fillna("UNKNOWN")
            )

        for trim in trimestres:
            feature_lists[trim] = get_quarter_features_list(
                client_dfs[trim], top_familles
            )

        all_feats = sorted({f for trim in trimestres for f in feature_lists[trim]})
        active_rows = []
        for trim in trimestres:
            df_c = client_dfs[trim].copy()
            df_a = df_c[df_c["is_active"] == 1].copy().fillna(0)

            for f in all_feats:
                if f not in df_a.columns:
                    df_a[f] = 0

            active_rows.append(df_a[all_feats])

        panel_active = pd.concat(active_rows, ignore_index=True).fillna(0)
        if panel_active.empty:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": "Aucun client actif trouve pour le clustering trimestriel.",
            }

        scaler_global = StandardScaler().fit(panel_active)

        k_scores = {}
        for k in K_RANGE:
            scores = []
            ok = True

            for trim in trimestres:
                df_c = client_dfs[trim].copy()
                df_c = df_c[df_c["is_active"] == 1].copy().fillna(0)

                for f in all_feats:
                    if f not in df_c.columns:
                        df_c[f] = 0

                X_scaled = scaler_global.transform(df_c[all_feats])

                if X_scaled.shape[0] <= k:
                    ok = False
                    break

                km_tmp = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
                labels_tmp = km_tmp.fit_predict(X_scaled)

                if len(np.unique(labels_tmp)) < 2:
                    ok = False
                    break

                sil = silhouette_score(X_scaled, labels_tmp)
                scores.append(sil)

            if ok and len(scores) > 0:
                k_scores[k] = float(np.mean(scores))

        if len(k_scores) == 0:
            return {
                "results": {},
                "graphs": {},
                "kpis": {},
                "error": (
                    "Impossible de calculer la silhouette "
                    "(trop peu de clients ou donnees problematiques)."
                ),
            }

        K_FIXED = max(k_scores, key=k_scores.get)

        clusters_par_trimestre = {}
        centroids_par_trimestre = {}
        distributions = []

        for idx, trim in enumerate(trimestres):
            df_c = client_dfs[trim].copy()

            active_mask = df_c["is_active"] == 1
            df_active = df_c[active_mask].copy().fillna(0)

            for f in all_feats:
                if f not in df_active.columns:
                    df_active[f] = 0

            X_scaled = scaler_global.transform(df_active[all_feats])

            km = KMeans(n_clusters=K_FIXED, random_state=RANDOM_STATE, n_init=10)
            labels = km.fit_predict(X_scaled)
            centroids = km.cluster_centers_

            if idx == 0:
                labels_aligned = labels
                centroids_ref = centroids
            else:
                labels_aligned = align_labels_by_centroids(
                    centroids_ref, centroids, labels
                )

                dists = np.linalg.norm(
                    centroids_ref[:, None, :] - centroids[None, :, :], axis=2
                )
                row_ind, col_ind = linear_sum_assignment(dists)
                centroids_aligned = np.zeros_like(centroids_ref)
                for k_ref, k_new in zip(row_ind, col_ind):
                    centroids_aligned[k_ref] = centroids[k_new]
                centroids = centroids_aligned

            df_c["Cluster"] = -1
            df_c.loc[active_mask, "Cluster"] = labels_aligned

            clusters_par_trimestre[trim] = df_c[
                ["Cpt Client", "Trimestre", "is_active", "Cluster"]
            ].copy()
            centroids_par_trimestre[trim] = centroids

            dist = df_c["Cluster"].value_counts().sort_index()
            rows = []
            for c, n in dist.items():
                rows.append(
                    {
                        "cluster": "INACTIF (-1)" if c == -1 else f"Cluster {c}",
                        "nb_clients": int(n),
                        "pct": round(n / len(df_c) * 100, 1),
                    }
                )
            dist_df = pd.DataFrame(rows)
            distributions.append(
                {
                    "trimestre": trim,
                    "table_html": dist_df.to_html(
                        index=False,
                        classes="table table-striped table-sm",
                        border=0,
                    ),
                }
            )

        KPIS = [
            "CA_par_jour_ouvert",
            "Cmd_par_jour_ouvert",
            "Panier_moyen",
            "Nb_Familles_Distinctes",
        ]
        comparisons = []

        for trim in trimestres:
            tmp = client_dfs[trim].merge(
                clusters_par_trimestre[trim][["Cpt Client", "Cluster"]],
                on="Cpt Client",
                how="left",
            )

            g = tmp.groupby("Cluster")[KPIS].mean()
            if -1 in g.index:
                g = g.drop(index=-1)

            if not set([0, 1]).issubset(set(g.index)):
                comparisons.append(
                    {
                        "trimestre": trim,
                        "table_html": None,
                        "message": (
                            f"Clusters 0/1 non disponibles "
                            f"(clusters presents: {list(g.index)})"
                        ),
                    }
                )
                continue

            c0 = g.loc[0]
            c1 = g.loc[1]
            rows = []
            for kpi in KPIS:
                v0, v1 = float(c0[kpi]), float(c1[kpi])
                rows.append(
                    {
                        "kpi": kpi,
                        "cluster_0": round(v0, 2),
                        "cluster_1": round(v1, 2),
                        "gagne": "Cluster 0" if v0 >= v1 else "Cluster 1",
                    }
                )
            comp_df = pd.DataFrame(rows)
            comparisons.append(
                {
                    "trimestre": trim,
                    "table_html": comp_df.to_html(
                        index=False,
                        classes="table table-striped table-sm",
                        border=0,
                    ),
                    "message": None,
                }
            )

        df_pivot = pd.DataFrame()
        for trim in trimestres:
            tmp = clusters_par_trimestre[trim][["Cpt Client", "Cluster"]].rename(
                columns={"Cluster": f"Q{trim}"}
            )
            df_pivot = tmp if df_pivot.empty else df_pivot.merge(
                tmp, on="Cpt Client", how="outer"
            )

        df_pivot = df_pivot.set_index("Cpt Client")

        matrices_transition = {}
        transition_tables = []
        for i in range(len(trimestres) - 1):
            t0, t1 = trimestres[i], trimestres[i + 1]
            col0, col1 = f"Q{t0}", f"Q{t1}"

            df_tr = df_pivot[[col0, col1]].dropna()
            n = len(df_tr)
            if n == 0:
                continue

            eff = pd.crosstab(df_tr[col0], df_tr[col1])
            pct = pd.crosstab(df_tr[col0], df_tr[col1], normalize="index") * 100
            stables = int((df_tr[col0] == df_tr[col1]).sum())
            migrants = int(n - stables)

            key = f"{t0}_{t1}"
            matrices_transition[key] = {
                "effectifs": eff,
                "pourcentages": pct,
                "nb_clients": int(n),
                "stables": stables,
                "migrants": migrants,
            }
            transition_tables.append(
                {
                    "label": f"{t0} -> {t1}",
                    "nb_clients": int(n),
                    "stables": stables,
                    "migrants": migrants,
                    "effectifs_html": eff.to_html(
                        classes="table table-striped table-sm", border=0
                    ),
                    "pourcentages_html": pct.round(1).to_html(
                        classes="table table-striped table-sm", border=0
                    ),
                }
            )

        transition_heatmap = None
        nb = len(matrices_transition)
        if nb > 0:
            fig, axes = plt.subplots(1, nb, figsize=(8 * nb, 6))
            if nb == 1:
                axes = [axes]

            for ax, (key, data) in zip(axes, matrices_transition.items()):
                sns.heatmap(
                    data["pourcentages"],
                    annot=True,
                    fmt=".1f",
                    vmin=0,
                    vmax=100,
                    ax=ax,
                )
                ax.set_title(f"Transition {key}\n({data['nb_clients']} clients)")
                ax.set_xlabel("Vers (trimestre suivant)")
                ax.set_ylabel("De (trimestre actuel)")

            plt.tight_layout()
            buffer = BytesIO()
            fig.savefig(buffer, format="png", bbox_inches="tight", dpi=150)
            buffer.seek(0)
            transition_heatmap = base64.b64encode(buffer.read()).decode("utf-8")
            plt.close(fig)

        k_scores_rows = [
            {"k": int(k), "silhouette_moyenne": round(v, 4)}
            for k, v in sorted(k_scores.items())
        ]
        k_scores_df = pd.DataFrame(k_scores_rows)

        results = {
            "selected_year": int(selected_year),
            "available_years": available_years,
            "trimestres": trimestres,
            "closed_periods": closed_periods,
            "top_familles": top_familles,
            "quarterly_summaries": quarterly_summaries,
            "k_scores_html": k_scores_df.to_html(
                index=False,
                classes="table table-striped table-sm",
                border=0,
            ),
            "quarter_distributions": distributions,
            "comparisons": comparisons,
            "transition_tables": transition_tables,
        }
        graphs = {"transition_heatmap": transition_heatmap}
        kpis = {
            "annee_analysee": int(selected_year),
            "k_fixed": int(K_FIXED),
            "silhouette_moyenne": round(float(k_scores[K_FIXED]), 4),
            "nb_trimestres": int(len(trimestres)),
            "nb_clients": int(len(all_clients)),
            "nb_top_familles": int(len(top_familles)),
        }

        return {"results": results, "graphs": graphs, "kpis": kpis}

    except Exception as e:
        return {"results": {}, "graphs": {}, "kpis": {}, "error": str(e)}


def generate_clustering_tab_analysis(df):
    """Alias pour compatibilité."""
    return generate_clustering_analysis(df)
