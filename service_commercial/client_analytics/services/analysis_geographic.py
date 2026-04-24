"""
Service for geographic analysis: countries, zones, scoring.
Autonomous – no dependency on other service files.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Zone definitions ────────────────────────────────────────────────────────

_ZONES: dict[str, list[str]] = {
    'Europe Ouest': ['FR', 'BE', 'DE', 'NL', 'LU'],
    'Europe Nord':  ['GB', 'DK', 'SE', 'NO', 'IE'],
    'Europe Sud':   ['ES', 'IT', 'PT', 'GR'],
    'Europe Est':   ['PL', 'CZ', 'AT', 'CH', 'HU', 'SK', 'RO', 'HR',
                     'BG', 'RS', 'MK', 'LT'],
    'Autres':       [],
}


def _get_zone(country_code: str) -> str:
    for zone, codes in _ZONES.items():
        if country_code in codes:
            return zone
    return 'Autres'


def _classify_score(score: float) -> str:
    if score >= 70:
        return 'Excellence'
    elif score >= 50:
        return 'Performant'
    elif score >= 30:
        return 'Moyen'
    return 'À Développer'


# ─── Main analysis function ───────────────────────────────────────────────────

def analyze_geographic_data(df_final: pd.DataFrame,
                             granularity: str = 'month') -> dict:
    """
    Full geographic analysis: country stats, zone stats, performance scoring.

    Args:
        df_final:    Cleaned DataFrame from data_processing.
        granularity: 'month' | 'quarter' | 'year' – used for temporal context.

    Returns:
        dict with keys: stats_pays, stats_zone, classif_summary,
                        top10_score, geo_graphs.
        All DataFrames are returned with their natural index as a regular
        column so they can be serialised directly with to_dict('records').
    """
    # ── 1. Country-level aggregation ──────────────────────────────────────
    stats_pays: pd.DataFrame = df_final.groupby('Country').agg(
        CA_Total=('Montant', 'sum'),
        CA_Moyen=('Montant', 'mean'),
        CA_Median=('Montant', 'median'),
        CA_StdDev=('Montant', 'std'),
        Nb_Ventes=('Montant', 'count'),
        Qty_Total=('Quantité', 'sum'),
        Qty_Moyenne=('Quantité', 'mean'),
        PU_Moyen=('PU Net', 'mean'),
        PU_Median=('PU Net', 'median'),
        Nb_Clients=('Cpt Client', 'nunique'),
        Nb_Commandes=('N° Bon', 'nunique'),
        Nb_Familles=('Famille', 'nunique'),
    ).round(2)

    stats_pays['Part_Pct'] = (
        stats_pays['CA_Total'] / stats_pays['CA_Total'].sum() * 100
    ).round(1)
    stats_pays = stats_pays.sort_values('CA_Total', ascending=False)
    stats_pays['Rang'] = range(1, len(stats_pays) + 1)
    stats_pays['CA_par_Client'] = (
        stats_pays['CA_Total'] / stats_pays['Nb_Clients']
    ).round(2)
    stats_pays['Panier_Moyen'] = (
        stats_pays['CA_Total'] / stats_pays['Nb_Commandes']
    ).round(2)
    stats_pays['Tx_Penetration_Pct'] = (
        stats_pays['Nb_Clients'] / stats_pays['Nb_Clients'].sum() * 100
    ).round(1)

    # Zone mapping (index is still the country code here)
    stats_pays['Zone'] = stats_pays.index.map(_get_zone)

    # ── 2. Zone-level aggregation ─────────────────────────────────────────
    df_geo = df_final.copy()
    df_geo['Zone'] = df_geo['Country'].apply(_get_zone)

    stats_zone: pd.DataFrame = df_geo.groupby('Zone').agg(
        CA_Total=('Montant', 'sum'),
        CA_Moyen=('Montant', 'mean'),
        Nb_Clients=('Cpt Client', 'nunique'),
        Nb_Commandes=('N° Bon', 'nunique'),
        Nb_Pays=('Country', 'nunique'),
    ).round(2)
    stats_zone['Part_Pct'] = (
        stats_zone['CA_Total'] / stats_zone['CA_Total'].sum() * 100
    ).round(1)
    stats_zone['Panier_Moyen'] = (
        stats_zone['CA_Total'] / stats_zone['Nb_Commandes']
    ).round(2)
    stats_zone = stats_zone.sort_values('CA_Total', ascending=False)

    # ── 3. Performance scoring ────────────────────────────────────────────
    ca_max = stats_pays['CA_Total'].max()
    basket_max = stats_pays['Panier_Moyen'].max()
    clients_max = stats_pays['Nb_Clients'].max()

    stats_pays['Score_CA'] = (
        stats_pays['CA_Total'] / ca_max * 100
    ).round(1)
    stats_pays['Score_Panier'] = (
        stats_pays['Panier_Moyen'] / basket_max * 100
    ).round(1)
    stats_pays['Score_Clients'] = (
        stats_pays['Nb_Clients'] / clients_max * 100
    ).round(1)
    stats_pays['Score_Global'] = (
        stats_pays['Score_CA'] * 0.5
        + stats_pays['Score_Panier'] * 0.3
        + stats_pays['Score_Clients'] * 0.2
    ).round(1)

    stats_pays = stats_pays.sort_values('Score_Global', ascending=False)
    stats_pays['Classification'] = stats_pays['Score_Global'].apply(_classify_score)

    # Top 10 (still with country-code index, for visualisations below)
    top10_score_raw: pd.DataFrame = stats_pays.head(10)

    # ── 4. Classification summary ─────────────────────────────────────────
    classif_summary: pd.DataFrame = stats_pays.groupby('Classification').agg(
        CA_Total=('CA_Total', 'sum'),
        Nb_Pays=('CA_Total', 'count'),
    )
    classif_summary = classif_summary.reindex(
        ['Excellence', 'Performant', 'Moyen', 'À Développer']
    ).fillna(0)
    classif_summary['Part_CA_Pct'] = (
        classif_summary['CA_Total'] / classif_summary['CA_Total'].sum() * 100
    ).round(1)
    score_moyens = stats_pays.groupby('Classification')['Score_Global'].mean().round(1)
    classif_summary['Score_Moyen'] = classif_summary.index.map(score_moyens).fillna(0)

    # ── 5. Visualisations (pass DataFrames with index = country code) ─────
    geo_graphs: dict = {}
    try:
        from .visualizations import viz_geographic

        chart = viz_geographic.create_world_map(stats_pays)
        if chart:
            geo_graphs['world_map'] = chart

        chart = viz_geographic.create_geographic_ca_chart(stats_pays)
        if chart:
            geo_graphs['ca_by_country'] = chart

        chart = viz_geographic.create_zone_performance_chart(stats_zone)
        if chart:
            geo_graphs['zone_performance'] = chart

        chart = viz_geographic.create_classification_chart(stats_pays)
        if chart:
            geo_graphs['classification'] = chart

        chart = viz_geographic.create_score_distribution_chart(stats_pays)
        if chart:
            geo_graphs['score_distribution'] = chart

    except Exception:
        logger.exception('[analysis_geographic] Error generating charts')

    # ── 6. Serialise for templates (reset index → 'Pays' column) ─────────
    def _to_records(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
        result = df.reset_index().rename(columns={df.index.name or 'index': index_col})
        return result

    stats_pays_out = _to_records(stats_pays, 'Pays')
    top10_out = _to_records(top10_score_raw, 'Pays')
    stats_zone_out = _to_records(stats_zone, 'Zone')
    classif_out = _to_records(classif_summary, 'Classification')

    return {
        'stats_pays':      stats_pays_out,
        'stats_zone':      stats_zone_out,
        'classif_summary': classif_out,
        'top10_score':     top10_out,
        'geo_graphs':      geo_graphs,
    }


def generate_geographic_analysis(df_final: pd.DataFrame) -> dict:
    """Wrapper kept for backward compatibility."""
    return analyze_geographic_data(df_final)
