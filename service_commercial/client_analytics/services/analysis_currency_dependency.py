"""
Analyse de dépendance à la devise

Module dédié à l'analyse de l'exposition aux devises étrangères pour une entreprise
qui vend en France et à l'international. Produit des KPI de concentration et de mix
de devises sans conversion FX.

Auteur: Analytics Team
Date: 2026-01-21
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import warnings
import base64
from io import BytesIO

# Import des fonctions de visualizations
from .visualizations.viz_currency import (
    plot_revenue_by_currency,
    plot_monthly_stacked_area,
    plot_non_eur_pct_over_time,
    plot_country_currency_heatmap,
    plot_pareto_non_eur_clients,
    plot_non_eur_by_family
)

warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES DE CONVERSION & NORMALISATION
# ═══════════════════════════════════════════════════════════════════════════════

def fig_to_base64(fig) -> str:
    """
    Convertit une figure matplotlib en chaîne base64 pour intégration HTML.
    
    Args:
        fig: Figure matplotlib
        
    Returns:
        Chaîne base64 avec préfixe data:image/png;base64,
    """
    buffer = BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)
    return f"data:image/png;base64,{image_base64}"

def normalize_currency(df: pd.DataFrame, col: str = "Nom Devise") -> pd.DataFrame:
    """
    Normalise les codes devises pour harmoniser les variations.
    
    Transformations:
        - strip() et upper()
        - "€", "EURO", "EUROS" -> "EUR"
        - NaN -> "UNKNOWN"
    
    Args:
        df: DataFrame avec colonne devise
        col: Nom de la colonne devise (défaut: "Nom Devise")
    
    Returns:
        DataFrame avec colonne devise normalisée
    """
    if col not in df.columns:
        return df
    
    df = df.copy()
    
    # Strip et uppercase
    df[col] = df[col].astype(str).str.strip().str.upper()
    
    # Harmonisation
    mapping = {
        "€": "EUR",
        "EURO": "EUR",
        "EUROS": "EUR",
        "NAN": "UNKNOWN",
        "NONE": "UNKNOWN",
    }
    
    df[col] = df[col].replace(mapping)
    
    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie le DataFrame pour l'analyse devise.
    
    - Normalise les devises
    - Filtre Montant NaN
    - Convertit Montant en numérique
    - Filtre les montants négatifs ou nuls
    
    Args:
        df: DataFrame brut
    
    Returns:
        DataFrame nettoyé
    """
    df = df.copy()
    
    # Normaliser devises
    if "Nom Devise" in df.columns:
        df = normalize_currency(df)
    
    # Montant numérique
    if "Montant" in df.columns:
        df["Montant"] = pd.to_numeric(df["Montant"], errors="coerce")
        df = df.dropna(subset=["Montant"])
        df = df[df["Montant"] > 0]
    
    return df


def create_month_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Crée ou normalise une colonne Month pour agrégation temporelle.
    
    Si Month existe (format "YYYY-MM"), la garde.
    Sinon, essaie de créer à partir de "Date Fact."
    
    Args:
        df: DataFrame
    
    Returns:
        DataFrame avec colonne Month_Period (pd.Period)
    """
    df = df.copy()
    
    if "Month" in df.columns and df["Month"].notna().any():
        # Month existe déjà (format "YYYY-MM")
        df["Month_Period"] = pd.to_datetime(df["Month"] + "-01").dt.to_period("M")
    elif "Date Fact." in df.columns:
        df["Month_Period"] = pd.to_datetime(df["Date Fact."], errors="coerce").dt.to_period("M")
    else:
        df["Month_Period"] = None
    
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# CALCUL DES KPI
# ═══════════════════════════════════════════════════════════════════════════════

def compute_kpi(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcule tous les KPI de dépendance à la devise.
    
    KPI retournés:
        - total_revenue: CA total (somme Montant)
        - currencies_detected: Liste des devises uniques
        - non_eur_amount: Montant total en devises non-EUR
        - non_eur_pct: % du CA en devises non-EUR
        - top_currencies: Top 5 devises avec montants et parts
        - hhi_currency: Indice Herfindahl-Hirschman (concentration)
        - non_eur_top_clients: Top 5 clients sur non-EUR (concentration)
        - non_eur_top_countries: Top 5 pays sur non-EUR (concentration)
        - monthly_non_eur_volatility: Écart-type mensuel de la part non-EUR
    
    Args:
        df: DataFrame nettoyé (post clean_dataframe)
    
    Returns:
        Dictionnaire de KPI
    """
    kpi = {}
    
    # Vérifications colonnes nécessaires
    if "Montant" not in df.columns:
        return {"error": "Colonne 'Montant' absente"}
    
    # CA total
    kpi["total_revenue"] = df["Montant"].sum()
    
    # Devises détectées
    if "Nom Devise" in df.columns:
        kpi["currencies_detected"] = sorted(df["Nom Devise"].unique().tolist())
    else:
        kpi["currencies_detected"] = []
    
    # Part non-EUR
    if "Nom Devise" in df.columns:
        non_eur_df = df[df["Nom Devise"] != "EUR"]
        kpi["non_eur_amount"] = non_eur_df["Montant"].sum()
        kpi["non_eur_pct"] = (kpi["non_eur_amount"] / kpi["total_revenue"]) * 100 if kpi["total_revenue"] > 0 else 0
    else:
        kpi["non_eur_amount"] = 0
        kpi["non_eur_pct"] = 0
        non_eur_df = pd.DataFrame()
    
    # Top devises
    if "Nom Devise" in df.columns:
        currency_agg = df.groupby("Nom Devise")["Montant"].sum().sort_values(ascending=False)
        top_currencies = []
        
        for currency, amount in currency_agg.head(5).items():
            pct_total = (amount / kpi["total_revenue"]) * 100 if kpi["total_revenue"] > 0 else 0
            
            non_eur_total = kpi["non_eur_amount"]
            if currency != "EUR" and non_eur_total > 0:
                pct_non_eur = (amount / non_eur_total) * 100
            else:
                pct_non_eur = 0
            
            top_currencies.append({
                "currency": currency,
                "amount": amount,
                "pct_total": pct_total,
                "pct_non_eur": pct_non_eur
            })
        
        kpi["top_currencies"] = top_currencies
        
        # Indice HHI (concentration)
        shares = currency_agg / kpi["total_revenue"] if kpi["total_revenue"] > 0 else pd.Series()
        kpi["hhi_currency"] = (shares ** 2).sum() * 10000  # HHI en base 10000
    else:
        kpi["top_currencies"] = []
        kpi["hhi_currency"] = None
    
    # Concentration clients sur non-EUR
    if "Intitulé" in df.columns and len(non_eur_df) > 0:
        client_agg = non_eur_df.groupby("Intitulé")["Montant"].sum().sort_values(ascending=False)
        top_clients = []
        
        for client, amount in client_agg.head(5).items():
            pct = (amount / kpi["non_eur_amount"]) * 100 if kpi["non_eur_amount"] > 0 else 0
            top_clients.append({
                "client": client,
                "amount": amount,
                "pct_non_eur": pct
            })
        
        kpi["non_eur_top_clients"] = top_clients
        kpi["non_eur_top5_clients_pct"] = sum(c["pct_non_eur"] for c in top_clients)
    else:
        kpi["non_eur_top_clients"] = []
        kpi["non_eur_top5_clients_pct"] = None
    
    # Concentration pays sur non-EUR
    if "Country" in df.columns and len(non_eur_df) > 0:
        country_agg = non_eur_df.groupby("Country")["Montant"].sum().sort_values(ascending=False)
        top_countries = []
        
        for country, amount in country_agg.head(5).items():
            pct = (amount / kpi["non_eur_amount"]) * 100 if kpi["non_eur_amount"] > 0 else 0
            top_countries.append({
                "country": country,
                "amount": amount,
                "pct_non_eur": pct
            })
        
        kpi["non_eur_top_countries"] = top_countries
        kpi["non_eur_top5_countries_pct"] = sum(c["pct_non_eur"] for c in top_countries)
    else:
        kpi["non_eur_top_countries"] = []
        kpi["non_eur_top5_countries_pct"] = None
    
    # Volatilité temporelle
    df_temp = create_month_column(df)
    
    if "Month_Period" in df_temp.columns and df_temp["Month_Period"].notna().any() and "Nom Devise" in df_temp.columns:
        monthly_agg = df_temp.groupby("Month_Period")["Montant"].sum()
        
        non_eur_monthly = df_temp[df_temp["Nom Devise"] != "EUR"].groupby("Month_Period")["Montant"].sum()
        
        monthly_non_eur_pct = (non_eur_monthly / monthly_agg * 100).fillna(0)
        
        if len(monthly_non_eur_pct) > 1:
            kpi["monthly_non_eur_volatility"] = monthly_non_eur_pct.std()
        else:
            kpi["monthly_non_eur_volatility"] = None
    else:
        kpi["monthly_non_eur_volatility"] = None
    
    return kpi


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE D'ANALYSE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_currency_dependency(
    df_final: pd.DataFrame,
    output_dir: Optional[str] = None,
    granularity: str = 'month'
) -> Dict[str, Any]:
    """
    Analyse complète de dépendance à la devise.
    
    Produit:
        - KPI de mix et concentration de devises
        - 6 graphiques executive pour dashboard
    
    Args:
        df_final: DataFrame final (sortie de process_raw_data)
        output_dir: Répertoire de sauvegarde des graphiques (optionnel)
                   Si None, retourne les figures matplotlib
        granularity: 'month', 'quarter', 'year' - granularité d'agrégation temporelle
    
    Returns:
        Dictionnaire contenant:
            - 'kpi': dict des KPI calculés
            - 'charts': dict des figures matplotlib (si output_dir=None)
            - 'chart_paths': dict des chemins (si output_dir fourni)
    
    Raises:
        ValueError: Si DataFrame vide
    
    Example:
        >>> from client_analytics.services.data_processing import process_raw_data
        >>> from client_analytics.services.currency_dependency import analyze_currency_dependency
        >>> 
        >>> df_raw = pd.read_excel("data.xlsx")
        >>> df_final = process_raw_data(df_raw)
        >>> report = analyze_currency_dependency(df_final, output_dir="outputs/currency")
        >>> 
        >>> print(f"CA total: {report['kpi']['total_revenue']:,.0f} €")
        >>> print(f"Part non-EUR: {report['kpi']['non_eur_pct']:.1f}%")
    """
    
    # Validation
    if df_final.empty:
        raise ValueError("DataFrame vide : impossible d'analyser")
    
    
    # Nettoyage
    df_clean = clean_dataframe(df_final)
    
    # Calcul KPI
    kpi = compute_kpi(df_clean)
    
    if "error" in kpi:
        return {"kpi": kpi, "charts": {}, "chart_paths": {}}
    
    # Génération graphiques
    
    output_path_obj = Path(output_dir) if output_dir else None
    
    if output_path_obj:
        output_path_obj.mkdir(parents=True, exist_ok=True)
    
    charts = {}
    chart_paths = {}
    
    # Graph 1: CA par devise
    path = output_path_obj / "1_revenue_by_currency.png" if output_path_obj else None
    fig = plot_revenue_by_currency(df_clean, path)
    if fig:
        charts["revenue_by_currency"] = fig
    if path:
        chart_paths["revenue_by_currency"] = str(path)
    
    # Graph 2: Aire empilée (granularité choisie)
    path = output_path_obj / "2_monthly_stacked_area.png" if output_path_obj else None
    fig = plot_monthly_stacked_area(df_clean, path, granularity=granularity)
    if fig:
        charts["monthly_stacked_area"] = fig
    if path:
        chart_paths["monthly_stacked_area"] = str(path)

    # Graph 3: % non-EUR temporel (granularité choisie)
    path = output_path_obj / "3_non_eur_pct_over_time.png" if output_path_obj else None
    fig = plot_non_eur_pct_over_time(df_clean, path, granularity=granularity)
    if fig:
        charts["non_eur_pct_over_time"] = fig
    if path:
        chart_paths["non_eur_pct_over_time"] = str(path)
    
    # Graph 4: Heatmap Country × Devise
    path = output_path_obj / "4_country_currency_heatmap.png" if output_path_obj else None
    fig = plot_country_currency_heatmap(df_clean, path)
    if fig:
        charts["country_currency_heatmap"] = fig
    if path:
        chart_paths["country_currency_heatmap"] = str(path)
    
    # Graph 5: Pareto clients non-EUR
    path = output_path_obj / "5_pareto_non_eur_clients.png" if output_path_obj else None
    fig = plot_pareto_non_eur_clients(df_clean, path, top_n=10)
    if fig:
        charts["pareto_non_eur_clients"] = fig
    if path:
        chart_paths["pareto_non_eur_clients"] = str(path)
    
    # Graph 6: % non-EUR par Famille
    path = output_path_obj / "6_non_eur_by_family.png" if output_path_obj else None
    fig = plot_non_eur_by_family(df_clean, path)
    if fig:
        charts["non_eur_by_family"] = fig
    if path:
        chart_paths["non_eur_by_family"] = str(path)
    
    # Convertir les figures en base64 si output_dir=None (pour usage web)
    if not output_dir and charts:
        charts_base64 = {}
        for name, fig in charts.items():
            if fig:
                charts_base64[name] = fig_to_base64(fig)
        charts = charts_base64
    
    result = {
        "kpi": kpi,
        "charts": charts if not output_dir else {},
        "chart_paths": chart_paths if output_dir else {}
    }
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTION WRAPPER (EXEMPLE D'UTILISATION)
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_pipeline(df_raw: pd.DataFrame, output_dir: str = "outputs/currency") -> Dict[str, Any]:
    """
    Pipeline complet : process_raw_data + analyze_currency_dependency.
    
    Args:
        df_raw: DataFrame brut
        output_dir: Répertoire de sortie
    
    Returns:
        Rapport d'analyse complet
    
    Example:
        >>> import pandas as pd
        >>> from client_analytics.services.currency_dependency import run_full_pipeline
        >>> 
        >>> df_raw = pd.read_excel("Raw data High tech 2024.xlsx")
        >>> report = run_full_pipeline(df_raw, output_dir="outputs/currency_analysis")
        >>> 
        >>> # Afficher les KPI
        >>> for key, value in report['kpi'].items():
        >>>     print(f"{key}: {value}")
    """
    from .data_processing import process_raw_data
    
    # Étape 1: Processing
    df_final = process_raw_data(df_raw)
    
    # Étape 2: Analyse devise
    report = analyze_currency_dependency(df_final, output_dir=output_dir)
    
    return report


if __name__ == "__main__":
    pass
