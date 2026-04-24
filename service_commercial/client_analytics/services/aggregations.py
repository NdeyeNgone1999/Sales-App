"""
Service d'agrégations business pour analyses.
Calculs de KPIs, séries temporelles, Pareto, lead time.
"""
import pandas as pd
import numpy as np
from typing import Literal, Dict, Any, List
from . import periods as periods_service


def kpis_global(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcule les KPIs globaux sur tout le dataset.
    
    Args:
        df: DataFrame avec colonnes MONTANT, N° Bon, Intitulé, Pays, Famille 1
    
    Returns:
        Dictionnaire de KPIs
    """
    # Détecter les noms de colonnes (majuscules ou minuscules)
    montant_col = next((c for c in df.columns if c.upper() in ['MONTANT', 'MONTANT EUR']), 'MONTANT')
    bon_col = next((c for c in df.columns if 'BON' in c.upper() or 'N° BON' in c.upper()), 'N° Bon')
    client_col = next((c for c in df.columns if c.upper() in ['INTITULÉ', 'INTITULE', 'CPT CLIENT']), 'Intitulé')
    pays_col = next((c for c in df.columns if c.upper() in ['PAYS', 'COUNTRY']), 'Country')
    famille_col = next((c for c in df.columns if 'FAMILLE' in c.upper()), 'Famille')
    
    ca_total = df[montant_col].sum() if montant_col in df.columns else 0
    nb_transactions = df[bon_col].nunique() if bon_col in df.columns else len(df)
    nb_clients = df[client_col].nunique() if client_col in df.columns else 0
    nb_pays = df[pays_col].nunique() if pays_col in df.columns else 0
    nb_familles = df[famille_col].nunique() if famille_col in df.columns else 0
    
    panier_moyen = ca_total / nb_transactions if nb_transactions > 0 else 0
    
    return {
        'ca_total': ca_total,
        'nb_transactions': nb_transactions,
        'nb_clients': nb_clients,
        'nb_pays': nb_pays,
        'nb_familles': nb_familles,
        'panier_moyen': panier_moyen,
    }


def series_over_time(df: pd.DataFrame, period: Literal['month', 'quarter', 'year'], metric: str = 'MONTANT') -> List[Dict[str, Any]]:
    """
    Crée une série temporelle agrégée selon la période.
    
    Args:
        df: DataFrame avec colonnes temporelles
        period: Type de période
        metric: Colonne métrique à agréger
    
    Returns:
        Liste de dicts [{label, value}] triée chronologiquement
    """
    df = periods_service.ensure_period_cols(df)
    df = periods_service.make_period_label(df, period)
    
    group_cols = periods_service.get_period_group_cols(period)
    
    # Détecter le nom de la colonne métrique
    metric_col = next((c for c in df.columns if c.upper() == metric.upper()), metric)
    
    # Agréger
    series_df = df.groupby(group_cols + ['period_label'])[metric_col].sum().reset_index()
    series_df = series_df.sort_values(group_cols)
    
    return [
        {'label': row['period_label'], 'value': float(row[metric_col])}
        for _, row in series_df.iterrows()
    ]


def top_n(df: pd.DataFrame, group_col: str, metric: str = 'MONTANT', n: int = 10) -> List[Dict[str, Any]]:
    """
    Retourne le top N des entités par métrique.
    
    Args:
        df: DataFrame source
        group_col: Colonne de regroupement (ex: 'Intitulé', 'Pays', 'Nom Devise')
        metric: Métrique d'agrégation
        n: Nombre de résultats
    
    Returns:
        Liste [{label, value}] triée décroissante
    """
    # Détecter noms de colonnes
    group_col_real = next((c for c in df.columns if c.upper() == group_col.upper()), group_col)
    metric_col = next((c for c in df.columns if c.upper() == metric.upper()), metric)
    
    top_df = (df.groupby(group_col_real)[metric_col]
              .sum()
              .sort_values(ascending=False)
              .head(n)
              .reset_index())
    
    return [
        {'label': str(row[group_col_real]), 'value': float(row[metric_col])}
        for _, row in top_df.iterrows()
    ]


def pareto(df: pd.DataFrame, entity_col: str = 'INTITULÉ', metric: str = 'MONTANT') -> Dict[str, Any]:
    """
    Analyse de Pareto : courbe cumulée + part top 20% et top 10.
    
    Args:
        df: DataFrame source
        entity_col: Colonne entité (ex: client, produit)
        metric: Métrique
    
    Returns:
        Dict avec cumulative_curve (liste), top_20pct_share, top_10_share
    """
    # Détecter noms de colonnes
    entity_col_real = next((c for c in df.columns if c.upper() == entity_col.upper()), entity_col)
    metric_col = next((c for c in df.columns if c.upper() == metric.upper()), metric)
    
    # Agréger par entité
    entity_df = (df.groupby(entity_col_real)[metric_col]
                 .sum()
                 .sort_values(ascending=False)
                 .reset_index())
    
    entity_df['cumsum'] = entity_df[metric_col].cumsum()
    total = entity_df[metric_col].sum()
    entity_df['cumsum_pct'] = (entity_df['cumsum'] / total * 100) if total > 0 else 0
    
    # Courbe cumulée (pour graphe)
    cumulative_curve = [
        {'index': i + 1, 'cumsum_pct': float(row['cumsum_pct'])}
        for i, row in entity_df.iterrows()
    ]
    
    # Part des top 20%
    n_total = len(entity_df)
    n_20pct = max(1, int(n_total * 0.2))
    top_20pct_share = entity_df.head(n_20pct)[metric_col].sum() / total * 100 if total > 0 else 0
    
    # Part des top 10 entités
    top_10_share = entity_df.head(10)[metric_col].sum() / total * 100 if total > 0 else 0
    
    return {
        'cumulative_curve': cumulative_curve,
        'top_20pct_share': float(top_20pct_share),
        'top_10_share': float(top_10_share),
        'n_total': n_total,
        'n_20pct': n_20pct,
    }


def lead_time_pack(df: pd.DataFrame, period: Literal['month', 'quarter', 'year']) -> Dict[str, Any]:
    """
    Analyse complète des délais de livraison (lead time).
    
    Utilise Lead_Time_Days si disponible, sinon calcule depuis dates brutes.
    Calcul : Date Expédition - Date Commande
    Si Date Commande absente : Date Facturation - 60 jours (estimation)
    
    Args:
        df: DataFrame avec Lead_Time_Days ou colonnes de dates
        period: Période d'agrégation
    
    Returns:
        Dict avec médianes, anomalies, distribution, série temporelle
    """
    df_work = df.copy()
    
    # Initialiser date_fact_col pour utilisation ultérieure
    date_fact_col = None
    for col in df.columns:
        col_upper = col.upper()
        if 'FACT' in col_upper or 'INVOICE' in col_upper:
            date_fact_col = col
            break
    
    # Fallback sur Date_Ref si disponible
    if not date_fact_col and 'Date_Ref' in df_work.columns:
        date_fact_col = 'Date_Ref'
    
    # 🆕 PRIORITÉ 1 : Si Lead_Time_Days existe déjà, l'utiliser directement
    if 'Lead_Time_Days' in df_work.columns:
        df_work['lead_time_days'] = pd.to_numeric(df_work['Lead_Time_Days'], errors='coerce')
    else:
        # 🔄 PRIORITÉ 2 : Calculer depuis les dates brutes
        
        # Détecter colonnes de dates (avec recherche insensible à la casse et accents)
        all_cols = [c.upper() for c in df.columns]
        
        # Date expédition (plusieurs variantes possibles)
        date_exp_col = None
        for col in df.columns:
            col_upper = col.upper()
            if any(keyword in col_upper for keyword in ['EXPÉDITION', 'EXPEDITION', 'EXPEDIT', 'LIVRAISON', 'LIVR', 'SHIP', 'DELIVERY']):
                date_exp_col = col
                break
        
        # Date commande
        date_cmd_col = None
        for col in df.columns:
            col_upper = col.upper()
            if any(keyword in col_upper for keyword in ['COMMANDE', 'CMD', 'ORDER', 'COMMAND']):
                date_cmd_col = col
                break
        
        # Date facturation
        date_fact_col = None
        for col in df.columns:
            col_upper = col.upper()
            if 'Date Fact.' in col_upper or 'INVOICE' in col_upper:
                date_fact_col = col
                break
        
        # Vérifier si on peut calculer le lead time
        if not date_exp_col and not date_fact_col:
            return {
                'error': f'Colonnes de dates manquantes pour calculer le lead time. Colonnes trouvées : Expédition={date_exp_col}, Facturation={date_fact_col}',
                'median': 0,
                'mean': 0,
                'std': 0,
                'pct_anomalies': 0,
                'pct_extremes': 0,
                'distribution': [],
                'series_over_time': [],
            }
        
        # Convertir en datetime
        for col in [date_exp_col, date_cmd_col, date_fact_col]:
            if col and col in df_work.columns:
                df_work[col] = pd.to_datetime(df_work[col], errors='coerce')
        
        # Calculer lead time selon les colonnes disponibles
        if date_exp_col and date_cmd_col and date_exp_col in df_work.columns and date_cmd_col in df_work.columns:
            # Cas idéal : Date Expédition - Date Commande
            df_work['lead_time_days'] = (df_work[date_exp_col] - df_work[date_cmd_col]).dt.days
        elif date_exp_col and date_fact_col and date_exp_col in df_work.columns and date_fact_col in df_work.columns:
            # Cas avec estimation : Date Expédition - (Date Facturation - 60 jours)
            df_work['lead_time_days'] = (df_work[date_exp_col] - (df_work[date_fact_col] - pd.Timedelta(days=60))).dt.days
        elif date_cmd_col and date_fact_col and date_cmd_col in df_work.columns and date_fact_col in df_work.columns:
            # Alternative : Date Facturation - Date Commande
            df_work['lead_time_days'] = (df_work[date_fact_col] - df_work[date_cmd_col]).dt.days
        else:
            # Pas assez de données
            return {
                'error': f'Impossible de calculer le lead time. Colonnes nécessaires : (Date Expédition + Date Commande) OU (Date Expédition + Date Facturation) OU (Date Facturation + Date Commande). Disponibles : Exp={date_exp_col}, Cmd={date_cmd_col}, Fact={date_fact_col}',
                'median': 0,
                'mean': 0,
                'std': 0,
                'pct_anomalies': 0,
                'pct_extremes': 0,
                'distribution': [],
                'series_over_time': [],
            }
    
    # Filtrer les valeurs valides
    df_valid = df_work[df_work['lead_time_days'].notna()].copy()
    
    if len(df_valid) == 0:
        return {
            'error': 'Aucune donnée de lead time calculable',
            'median': 0,
            'mean': 0,
            'std': 0,
            'pct_anomalies': 0,
            'pct_extremes': 0,
            'distribution': [],
            'series_over_time': [],
        }
    
    # Détecter anomalies
    df_valid['is_anomaly'] = df_valid['lead_time_days'] < 0
    df_valid['is_extreme'] = df_valid['lead_time_days'] > 365
    
    pct_anomalies = (df_valid['is_anomaly'].sum() / len(df_valid) * 100)
    pct_extremes = (df_valid['is_extreme'].sum() / len(df_valid) * 100)
    
    # Statistiques sur valeurs valides (>= 0, <= 730)
    df_stats = df_valid[(df_valid['lead_time_days'] >= 0) & (df_valid['lead_time_days'] <= 730)]
    
    median_lt = df_stats['lead_time_days'].median() if len(df_stats) > 0 else 0
    mean_lt = df_stats['lead_time_days'].mean() if len(df_stats) > 0 else 0
    std_lt = df_stats['lead_time_days'].std() if len(df_stats) > 0 else 0
    
    # Distribution par buckets
    buckets = [
        (0, 3, '0-3 jours'),
        (4, 7, '4-7 jours'),
        (8, 14, '8-14 jours'),
        (15, 30, '15-30 jours'),
        (31, 60, '31-60 jours'),
        (61, 730, '>60 jours'),
    ]
    
    distribution = []
    for min_val, max_val, label in buckets:
        count = len(df_stats[(df_stats['lead_time_days'] >= min_val) & (df_stats['lead_time_days'] <= max_val)])
        distribution.append({'label': label, 'count': count})
    
    # Série temporelle : médiane par période
    df_stats = periods_service.ensure_period_cols(df_stats, date_col_priority=(date_fact_col,))
    df_stats = periods_service.make_period_label(df_stats, period)
    
    group_cols = periods_service.get_period_group_cols(period)
    series_df = df_stats.groupby(group_cols + ['period_label'])['lead_time_days'].median().reset_index()
    series_df = series_df.sort_values(group_cols)
    
    series_over_time = [
        {'label': row['period_label'], 'value': float(row['lead_time_days'])}
        for _, row in series_df.iterrows()
    ]
    
    return {
        'median': float(median_lt),
        'mean': float(mean_lt),
        'std': float(std_lt),
        'pct_anomalies': float(pct_anomalies),
        'pct_extremes': float(pct_extremes),
        'distribution': distribution,
        'series_over_time': series_over_time,
        'n_total': len(df_valid),
        'n_valid': len(df_stats),
    }
