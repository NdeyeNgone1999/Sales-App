"""
Visualisations pour le sous-onglet DÉPENDANCE AUX DEVISES

Contient toutes les fonctions de création de graphiques pour l'analyse de devises.
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional
import warnings

warnings.filterwarnings('ignore')


# Configuration des styles
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

COLORS = {
    'EUR': '#2E86AB',      # Bleu foncé
    'non_EUR': '#A23B72',  # Violet/Rose
    'other': '#F18F01',    # Orange
}


def plot_revenue_by_currency(df: pd.DataFrame, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
    """
    Graph 1: Bar chart - CA par devise (global).
    
    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
    
    Returns:
        Figure matplotlib ou None si colonne absente
    """
    if "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None
    
    currency_agg = df.groupby("Nom Devise")["Montant"].sum().sort_values(ascending=False)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = [COLORS['EUR'] if c == 'EUR' else COLORS['non_EUR'] for c in currency_agg.index]
    
    bars = ax.bar(currency_agg.index, currency_agg.values, color=colors, edgecolor='black', linewidth=0.7)
    
    ax.set_xlabel("Devise", fontsize=12, fontweight='bold')
    ax.set_ylabel("Chiffre d'affaires (€)", fontsize=12, fontweight='bold')
    ax.set_title("Chiffre d'affaires par devise", fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    ax.ticklabel_format(style='plain', axis='y')
    
    # Annotations
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height/1e6:.1f}M',
                ha='center', va='bottom', fontsize=9)
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None
    
    return fig


def plot_monthly_stacked_area(df: pd.DataFrame, output_path: Optional[Path] = None, granularity: str = "month") -> Optional[plt.Figure]:
    """
    Graph 2: Aire empilée - CA par devise selon la granularité.

    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
        granularity: 'month', 'quarter' ou 'year'

    Returns:
        Figure matplotlib ou None
    """
    if "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None

    df_temp = df.copy()

    # Créer la colonne de période selon la granularité
    if "Date Fact." in df_temp.columns:
        dates = pd.to_datetime(df_temp["Date Fact."], errors="coerce")
    elif "Month" in df_temp.columns and df_temp["Month"].notna().any():
        dates = pd.to_datetime(df_temp["Month"] + "-01", errors="coerce")
    else:
        return None

    if granularity == "quarter":
        df_temp["_period"] = dates.dt.to_period("Q")
        xlabel = "Trimestre"
        title = "Évolution trimestrielle du CA par devise"
    elif granularity == "year":
        df_temp["_period"] = dates.dt.to_period("A")
        xlabel = "Année"
        title = "Évolution annuelle du CA par devise"
    else:
        df_temp["_period"] = dates.dt.to_period("M")
        xlabel = "Mois"
        title = "Évolution mensuelle du CA par devise"

    if df_temp["_period"].isna().all():
        return None

    pivot = df_temp.pivot_table(
        index="_period",
        columns="Nom Devise",
        values="Montant",
        aggfunc="sum",
        fill_value=0
    )

    if pivot.empty:
        return None

    # Trier colonnes: EUR en premier
    cols = pivot.columns.tolist()
    if "EUR" in cols:
        cols.remove("EUR")
        cols = ["EUR"] + sorted(cols)
        pivot = pivot[cols]

    fig, ax = plt.subplots(figsize=(14, 7))

    pivot.plot.area(ax=ax, alpha=0.7, linewidth=2)

    ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    ax.set_ylabel("Chiffre d'affaires (€)", fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.legend(title="Devise", bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True)
    ax.grid(axis='y', alpha=0.3)
    ax.ticklabel_format(style='plain', axis='y')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None

    return fig


def plot_non_eur_pct_over_time(df: pd.DataFrame, output_path: Optional[Path] = None, granularity: str = "month") -> Optional[plt.Figure]:
    """
    Graph 3: Courbe - Part non-EUR (%) dans le temps selon la granularité.

    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
        granularity: 'month', 'quarter' ou 'year'

    Returns:
        Figure matplotlib ou None
    """
    if "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None

    df_temp = df.copy()

    if "Date Fact." in df_temp.columns:
        dates = pd.to_datetime(df_temp["Date Fact."], errors="coerce")
    elif "Month" in df_temp.columns and df_temp["Month"].notna().any():
        dates = pd.to_datetime(df_temp["Month"] + "-01", errors="coerce")
    else:
        return None

    if granularity == "quarter":
        df_temp["_period"] = dates.dt.to_period("Q")
        xlabel = "Trimestre"
    elif granularity == "year":
        df_temp["_period"] = dates.dt.to_period("A")
        xlabel = "Année"
    else:
        df_temp["_period"] = dates.dt.to_period("M")
        xlabel = "Mois"

    if df_temp["_period"].isna().all():
        return None

    period_total = df_temp.groupby("_period")["Montant"].sum()
    period_non_eur = df_temp[df_temp["Nom Devise"] != "EUR"].groupby("_period")["Montant"].sum()

    non_eur_pct = (period_non_eur / period_total * 100).fillna(0)

    if non_eur_pct.empty:
        return None

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(non_eur_pct.index.astype(str), non_eur_pct.values,
            marker='o', linewidth=2.5, markersize=6, color=COLORS['non_EUR'])

    ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    ax.set_ylabel("Part non-EUR (%)", fontsize=12, fontweight='bold')
    ax.set_title("Évolution de la part du CA en devises étrangères", fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, max(non_eur_pct.values) * 1.1 if len(non_eur_pct) > 0 else 100)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None

    return fig


def plot_country_currency_heatmap(df: pd.DataFrame, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
    """
    Graph 4: Heatmap - Country × Devise : part du CA du pays.
    
    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
    
    Returns:
        Figure matplotlib ou None
    """
    if "Country" not in df.columns or "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None
    
    pivot = df.pivot_table(
        index="Country",
        columns="Nom Devise",
        values="Montant",
        aggfunc="sum",
        fill_value=0
    )
    
    if pivot.empty:
        return None
    
    # Normaliser par ligne (% du pays)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    
    # Trier par CA total décroissant
    country_totals = pivot.sum(axis=1).sort_values(ascending=False)
    pivot_pct = pivot_pct.loc[country_totals.index]
    
    # Limiter aux Top 15 pays
    if len(pivot_pct) > 15:
        pivot_pct = pivot_pct.head(15)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    sns.heatmap(pivot_pct, annot=True, fmt='.1f', cmap='YlOrRd', 
                linewidths=0.5, cbar_kws={'label': '% du CA du pays'}, ax=ax)
    
    ax.set_xlabel("Devise", fontsize=12, fontweight='bold')
    ax.set_ylabel("Pays", fontsize=12, fontweight='bold')
    ax.set_title("Répartition des devises par pays (Top 15)", fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None
    
    return fig


def plot_pareto_non_eur_clients(df: pd.DataFrame, output_path: Optional[Path] = None, top_n: int = 10) -> Optional[plt.Figure]:
    """
    Graph 5: Pareto - Top clients non-EUR (bar + courbe cumul).
    
    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
        top_n: Nombre de top clients à afficher
    
    Returns:
        Figure matplotlib ou None
    """
    if "Intitulé" not in df.columns or "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None
    
    non_eur_df = df[df["Nom Devise"] != "EUR"]
    
    if non_eur_df.empty:
        return None
    
    # Calculer l'agrégat complet pour Pareto (pour trouver n80)
    client_agg_full = non_eur_df.groupby("Intitulé")["Montant"].sum().sort_values(ascending=False)
    if client_agg_full.empty:
        return None

    # Calcul du nombre de clients pour atteindre 80% (n80)
    cumul_full_pct = (client_agg_full.cumsum() / client_agg_full.sum() * 100)
    try:
        n80_idx = int((cumul_full_pct >= 80).to_numpy().argmax())  # index (0-based)
        n80 = n80_idx + 1
        n80_pct = float(cumul_full_pct.iloc[n80_idx])
    except Exception:
        n80 = None
        n80_pct = None

    # Trancher pour l'affichage (top_n)
    client_agg = client_agg_full.head(top_n)

    # Cumul % (portion affichée)
    cumul_pct = (client_agg.cumsum() / client_agg_full.sum() * 100)

    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Barres
    ax1.bar(range(len(client_agg)), client_agg.values, color=COLORS['non_EUR'],
            edgecolor='black', linewidth=0.7, alpha=0.7)
    ax1.set_xlabel("Client", fontsize=12, fontweight='bold')
    ax1.set_ylabel("CA non-EUR (€)", fontsize=12, fontweight='bold', color=COLORS['non_EUR'])
    ax1.tick_params(axis='y', labelcolor=COLORS['non_EUR'])
    ax1.ticklabel_format(style='plain', axis='y')
    
    # Courbe cumul
    ax2 = ax1.twinx()
    ax2.plot(range(len(cumul_pct)), cumul_pct.values,
             marker='o', linewidth=2.5, markersize=8, color='red', label='Cumul %')
    ax2.set_ylabel("Cumul (%)", fontsize=12, fontweight='bold', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.set_ylim(0, 110)
    ax2.axhline(80, color='gray', linestyle='--', linewidth=1, alpha=0.7, label='80%')
    # Annotation n80 si calcul possible
    if n80 is not None:
        # Si n80 est dans la portion affichée, dessiner ligne verticale et annoter
        if n80 <= top_n:
            x_pos = n80 - 1
            ax1.axvline(x=x_pos, color='green', linestyle='--', linewidth=1)
            ax2.annotate(f"{n80} clients → {n80_pct:.1f}%",
                         xy=(x_pos, n80_pct), xycoords=('data', 'data'),
                         xytext=(10, 15), textcoords='offset points', color='green', fontsize=10,
                         arrowprops=dict(arrowstyle='->', color='green'))
        else:
            # Indiquer que n80 dépasse le Top affiché
            ax2.text(0.99, 0.95, f"n80 = {n80} (hors top {top_n})",
                     transform=ax2.transAxes, ha='right', va='top', color='green', fontsize=10,
                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    ax2.legend(loc='lower right')
    
    ax1.set_xticks(range(len(client_agg)))
    ax1.set_xticklabels(client_agg.index, rotation=45, ha='right')
    ax1.set_title(f"Top {top_n} clients sur CA non-EUR (Pareto)", fontsize=14, fontweight='bold', pad=20)
    ax1.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None
    
    return fig


def plot_non_eur_by_family(df: pd.DataFrame, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
    """
    Graph 6: Scatter/Bubble - CA total vs % non-EUR par Famille.
    
    Args:
        df: DataFrame nettoyé
        output_path: Chemin de sauvegarde (optionnel)
    
    Returns:
        Figure matplotlib ou None
    """
    if "Famille" not in df.columns or "Nom Devise" not in df.columns or "Montant" not in df.columns:
        return None
    
    family_total = df.groupby("Famille")["Montant"].sum()
    family_non_eur = df[df["Nom Devise"] != "EUR"].groupby("Famille")["Montant"].sum()
    
    family_pct_non_eur = (family_non_eur / family_total * 100).fillna(0)
    
    plot_df = pd.DataFrame({
        "CA_Total": family_total,
        "Pct_Non_EUR": family_pct_non_eur
    }).reset_index()
    
    if plot_df.empty:
        return None
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    scatter = ax.scatter(plot_df["CA_Total"], plot_df["Pct_Non_EUR"], 
                        s=plot_df["CA_Total"] / 1000,  # Taille proportionnelle au CA
                        alpha=0.6, c=plot_df["Pct_Non_EUR"], cmap='coolwarm', 
                        edgecolors='black', linewidth=1)
    
    # Annotations
    for idx, row in plot_df.iterrows():
        ax.annotate(row["Famille"], 
                   (row["CA_Total"], row["Pct_Non_EUR"]),
                   fontsize=9, ha='center', va='bottom')
    
    ax.set_xlabel("Chiffre d'affaires total (€)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Part non-EUR (%)", fontsize=12, fontweight='bold')
    ax.set_title("Exposition aux devises étrangères par famille produit", fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3)
    ax.ticklabel_format(style='plain', axis='x')
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('% non-EUR', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        return None
    
    return fig
