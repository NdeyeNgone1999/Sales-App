"""
Service pour le sous-onglet ANALYSE SÉRIE TEMPORELLE
Analyse temporelle avancée avec saisonnalité, tendances, STL, ARIMA
AUTONOME - Ne dépend d'aucun autre fichier de services
"""
from __future__ import annotations

import logging

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from statsmodels.tsa.stattools import adfuller, kpss
import warnings
warnings.filterwarnings('ignore')

# Import visualizations
from .visualizations.viz_time_series import create_stl_decomposition_plot, create_anomaly_dashboard_plot

logger = logging.getLogger(__name__)


def _create_evolution_selector_plot(
    df_display: pd.DataFrame,
    clients_display: pd.Series | None,
    granularity: str,
) -> str | None:
    if df_display is None or df_display.empty:
        return None

    x_labels = df_display.index.astype(str).tolist()
    if len(x_labels) < 2:
        return None

    ca = pd.to_numeric(df_display.get('CA_Total'), errors='coerce') if 'CA_Total' in df_display.columns else None
    qty = pd.to_numeric(df_display.get('Qty_Total'), errors='coerce') if 'Qty_Total' in df_display.columns else None
    clients = None
    if clients_display is not None and len(clients_display) > 0:
        clients = pd.to_numeric(clients_display, errors='coerce')

    title_map = {'month': 'Mois', 'quarter': 'Trimestre', 'year': 'Année fiscale'}
    title_suffix = title_map.get(granularity, granularity)

    def _base100(series: pd.Series | None) -> list[float | None]:
        if series is None:
            return [None] * len(x_labels)
        s = pd.to_numeric(series, errors='coerce')
        s = s.reindex(pd.Index(x_labels, dtype=str), fill_value=np.nan) if not isinstance(s.index, pd.RangeIndex) else s
        first_valid = s.dropna().iloc[0] if len(s.dropna()) > 0 else np.nan
        if pd.isna(first_valid) or float(first_valid) == 0.0:
            return [None] * len(x_labels)
        out = (s.astype(float) / float(first_valid) * 100.0).tolist()
        return [float(v) if v == v else None for v in out]

    fig = go.Figure()

    # 0-2 : séries brutes (affichées une par une)
    fig.add_trace(go.Scatter(x=x_labels, y=(ca.tolist() if ca is not None else [None] * len(x_labels)), name='CA (€)', visible=True, mode='lines+markers'))
    fig.add_trace(go.Scatter(x=x_labels, y=(qty.tolist() if qty is not None else [None] * len(x_labels)), name='Quantité', visible=False, mode='lines+markers'))
    fig.add_trace(go.Scatter(x=x_labels, y=(clients.tolist() if clients is not None else [None] * len(x_labels)), name='Nb clients', visible=False, mode='lines+markers'))

    # 3-5 : séries normalisées base 100 (affichées ensemble)
    fig.add_trace(go.Scatter(x=x_labels, y=_base100(ca), name='CA (base 100)', visible=False, mode='lines+markers'))
    fig.add_trace(go.Scatter(x=x_labels, y=_base100(qty), name='Quantité (base 100)', visible=False, mode='lines+markers'))
    fig.add_trace(go.Scatter(x=x_labels, y=_base100(clients), name='Nb clients (base 100)', visible=False, mode='lines+markers'))

    buttons = [
        {
            'label': 'CA',
            'method': 'update',
            'args': [
                {'visible': [True, False, False, False, False, False]},
                {'yaxis': {'title': {'text': 'CA (€)'}}},
            ],
        },
        {
            'label': 'Quantité',
            'method': 'update',
            'args': [
                {'visible': [False, True, False, False, False, False]},
                {'yaxis': {'title': {'text': 'Quantité'}}},
            ],
        },
        {
            'label': 'Nb clients',
            'method': 'update',
            'args': [
                {'visible': [False, False, True, False, False, False]},
                {'yaxis': {'title': {'text': 'Nb clients'}}},
            ],
        },
        {
            'label': 'Tous (base 100)',
            'method': 'update',
            'args': [
                {'visible': [False, False, False, True, True, True]},
                {'yaxis': {'title': {'text': 'Index (base 100)'}}},
            ],
        },
    ]

    # Ticks X: éviter l'axe vide (labels coupés/masqués selon largeur)
    step = max(1, int(len(x_labels) / 18))
    tick_vals = x_labels[::step]
    tick_txt = tick_vals

    fig.update_layout(
        title=f"Évolution ({title_suffix})",
        height=420,
        margin=dict(l=40, r=20, t=60, b=120),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        updatemenus=[
            {
                'buttons': buttons,
                'direction': 'down',
                'x': 0,
                'y': 1.15,
                'xanchor': 'left',
                'yanchor': 'top',
                'showactive': True,
            }
        ],
        yaxis_title='CA (€)',
        xaxis_title='Période',
    )
    fig.update_xaxes(
        type='category',
        tickangle=-45,
        automargin=True,
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_txt,
        showticklabels=True,
        tickfont=dict(size=10),
    )

    return pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs=False,
        config={'displayModeBar': False, 'responsive': True},
    )


def _get_datetime_source(df: pd.DataFrame) -> pd.Series:
    """Retourne une série datetime utilisable comme base temporelle.

    Priorité: Date_Ref (si dispo) puis Date Fact. puis index datetime.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        index_dt = df.index
    else:
        index_dt = None

    if 'Date_Ref' in df.columns:
        dt = pd.to_datetime(df['Date_Ref'], errors='coerce')
    elif 'Date Fact.' in df.columns:
        dt = pd.to_datetime(df['Date Fact.'], errors='coerce')
    elif index_dt is not None:
        dt = pd.to_datetime(index_dt, errors='coerce')
        dt = pd.Series(dt, index=df.index)
    else:
        raise ValueError("Aucune colonne Date_Ref / Date Fact. et index non datetime")

    return dt


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège les ventes au jour.

    - Utilise Date_Ref si dispo sinon Date Fact.
    - Groupe par jour (floor('D'))
    - Calcule CA_Total, Qty_Total, Nb_Clients, Nb_Commandes
    - Reindex sur toutes les dates entre min et max (freq='D')
    - Remplit les manquants à 0 (PU_Net_Moyen reste NaN si Qty=0)
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes', 'PU_Net_Moyen'])

    df_local = df.copy()
    dt = _get_datetime_source(df_local)
    df_local['_date'] = dt
    df_local = df_local.dropna(subset=['_date'])
    if df_local.empty:
        return pd.DataFrame(columns=['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes', 'PU_Net_Moyen'])

    df_local['_day'] = df_local['_date'].dt.floor('D')

    agg_dict = {}
    if 'Montant' in df_local.columns:
        agg_dict['Montant'] = 'sum'
    if 'Quantité' in df_local.columns:
        agg_dict['Quantité'] = 'sum'
    if 'Cpt Client' in df_local.columns:
        agg_dict['Cpt Client'] = 'nunique'
    if 'N° Bon' in df_local.columns:
        agg_dict['N° Bon'] = 'nunique'

    if not agg_dict:
        raise ValueError("Colonnes insuffisantes pour l'agrégation journalière")

    df_daily = df_local.groupby('_day').agg(agg_dict)
    df_daily.rename(
        columns={
            'Montant': 'CA_Total',
            'Quantité': 'Qty_Total',
            'Cpt Client': 'Nb_Clients',
            'N° Bon': 'Nb_Commandes',
        },
        inplace=True,
    )

    for col in ['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes']:
        if col in df_daily.columns:
            df_daily[col] = pd.to_numeric(df_daily[col], errors='coerce')

    df_daily.sort_index(inplace=True)
    full_range = pd.date_range(df_daily.index.min(), df_daily.index.max(), freq='D')
    df_daily = df_daily.reindex(full_range)

    for col in ['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes']:
        if col not in df_daily.columns:
            df_daily[col] = 0.0
        df_daily[col] = df_daily[col].fillna(0.0)

    denom = pd.to_numeric(df_daily['Qty_Total'], errors='coerce').replace(0, np.nan)
    df_daily['PU_Net_Moyen'] = pd.to_numeric(df_daily['CA_Total'], errors='coerce') / denom
    df_daily['PU_Net_Moyen'] = df_daily['PU_Net_Moyen'].replace([np.inf, -np.inf], np.nan)

    df_daily.index.name = 'Date'
    return df_daily


def aggregate_from_daily(df_daily: pd.DataFrame, granularity: str) -> pd.DataFrame:
    """Agrége un DataFrame journalier vers une granularité d'affichage.

    - month: resample mensuel, index label "YYYY-MM"
    - quarter: resample fiscal "Q-MAR", index "YYYYQn"
    - year: groupby fiscal year label (FYxxxx)
    """
    if granularity not in ['month', 'quarter', 'year']:
        raise ValueError(f"Granularité '{granularity}' invalide")

    if df_daily is None or df_daily.empty:
        return pd.DataFrame(columns=['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes', 'PU_Net_Moyen'])

    df_local = df_daily.copy()
    if not isinstance(df_local.index, pd.DatetimeIndex):
        df_local.index = pd.to_datetime(df_local.index, errors='coerce')
    df_local = df_local.sort_index()

    value_cols = [c for c in ['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes'] if c in df_local.columns]
    if not value_cols:
        return pd.DataFrame(columns=['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes', 'PU_Net_Moyen'])

    if granularity == 'month':
        df_agg = df_local[value_cols].resample('M').sum()
        df_agg.index = df_agg.index.to_period('M').astype(str)  # "YYYY-MM"
    elif granularity == 'quarter':
        df_agg = df_local[value_cols].resample('Q-MAR').sum()
        df_agg.index = df_agg.index.to_period('Q-MAR').astype(str)  # "YYYYQn"
    else:  # year fiscal Avril->Mars
        fy = df_local.index.year + (df_local.index.month >= 4).astype(int)
        df_agg = df_local[value_cols].groupby(fy).sum()
        df_agg.index = 'FY' + df_agg.index.astype(str)

    for col in ['CA_Total', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes']:
        if col not in df_agg.columns:
            df_agg[col] = 0.0
        df_agg[col] = pd.to_numeric(df_agg[col], errors='coerce').fillna(0.0)

    denom = pd.to_numeric(df_agg['Qty_Total'], errors='coerce').replace(0, np.nan)
    df_agg['PU_Net_Moyen'] = pd.to_numeric(df_agg['CA_Total'], errors='coerce') / denom
    df_agg['PU_Net_Moyen'] = df_agg['PU_Net_Moyen'].replace([np.inf, -np.inf], np.nan)

    return df_agg


def analyze_temporal_data(df_final: pd.DataFrame) -> dict:
    """
    Analyse temporelle approfondie : Mois, Trimestre, Année Fiscale (Avril->Mars)

    Args:
        df_final: DataFrame nettoyé issu de process_raw_data

    Returns:
        dict contenant les statistiques par trimestre, mois et année fiscale
    """
    
    # Préparation des données temporelles
    df_temp = df_final.copy()
    
    # Extraction du numéro de trimestre depuis "2025Q1" -> 1
    if 'Quarter' in df_temp.columns:
        df_temp['Trimestre_Num'] = df_temp['Quarter'].astype(str).str.extract(r'Q(\d+)')[0].astype(int)
    
    # Extraction du nom du mois depuis "2025-01"
    if 'Month' in df_temp.columns:
        df_temp['Mois_Datetime'] = pd.to_datetime(df_temp['Month'] + '-01')
        df_temp['Mois_Nom'] = df_temp['Mois_Datetime'].dt.strftime('%B')
        df_temp['Mois_Num'] = df_temp['Mois_Datetime'].dt.month

    # ─────────────────────────────────────────────────────────────────────
    # 1. ANALYSE PAR TRIMESTRE FISCAL
    # ─────────────────────────────────────────────────────────────────────


    if 'Trimestre_Num' in df_temp.columns and 'Fiscal_Year_Label' in df_temp.columns:
        stats_trim = df_temp.groupby(['Fiscal_Year_Label', 'Trimestre_Num']).agg({
            'Montant': ['sum', 'mean', 'median', 'std', 'count'],
            'Quantité': ['sum', 'mean'],
            'PU Net': ['mean', 'median'],
            'Cpt Client': 'nunique',
            'N° Bon': 'nunique'
        }).round(2)

        stats_trim.columns = ['CA_Total', 'CA_Moyen', 'CA_Median', 'CA_StdDev', 'Nb_Ventes', 
                              'Qty_Total', 'Qty_Moyenne', 'PU_Moyen', 'PU_Median', 
                              'Nb_Clients', 'Nb_Commandes']

        # Calculs complémentaires
        stats_trim['Part_%'] = (stats_trim.groupby(level=0)['CA_Total']
                                .transform(lambda x: (x / x.sum() * 100))).round(1)
        stats_trim['CV_%'] = (stats_trim['CA_StdDev'] / stats_trim['CA_Moyen'] * 100).round(1)
        stats_trim['CA_par_Client'] = (stats_trim['CA_Total'] / stats_trim['Nb_Clients']).round(2)

        # Analyse de tendance pour la dernière année fiscale
        dernier_fy = df_temp['Fiscal_Year_Label'].max()
        stats_trim_fy = stats_trim.loc[dernier_fy]
        
        if len(stats_trim_fy) >= 2:
            croissance = ((stats_trim_fy.iloc[-1]['CA_Total'] / stats_trim_fy.iloc[0]['CA_Total']) - 1) * 100
            meilleur_q = stats_trim_fy['CA_Total'].idxmax()
            pire_q = stats_trim_fy['CA_Total'].idxmin()
    else:
        stats_trim = None

    # ─────────────────────────────────────────────────────────────────────
    # 2. ANALYSE PAR MOIS
    # ─────────────────────────────────────────────────────────────────────


    if 'Month' in df_temp.columns and 'Fiscal_Year_Label' in df_temp.columns:
        stats_mois = df_temp.groupby(['Fiscal_Year_Label', 'Month']).agg({
            'Montant': ['sum', 'mean', 'count'],
            'Quantité': 'sum',
            'Cpt Client': 'nunique',
            'N° Bon': 'nunique'
        }).round(2)

        stats_mois.columns = ['CA_Total', 'CA_Moyen', 'Nb_Ventes', 'Qty_Total', 'Nb_Clients', 'Nb_Commandes']
        stats_mois['Part_%'] = (stats_mois.groupby(level=0)['CA_Total']
                                .transform(lambda x: (x / x.sum() * 100))).round(1)

        # Ajouter les noms de mois
        mois_dict = {
            '01': 'Janvier', '02': 'Février', '03': 'Mars', '04': 'Avril',
            '05': 'Mai', '06': 'Juin', '07': 'Juillet', '08': 'Août',
            '09': 'Septembre', '10': 'Octobre', '11': 'Novembre', '12': 'Décembre'
        }
        stats_mois['Mois_Nom'] = stats_mois.index.get_level_values(1).str[-2:].map(mois_dict)

        # Top/Flop mois pour la dernière année fiscale
        stats_mois_fy = stats_mois.loc[dernier_fy] if dernier_fy in stats_mois.index else stats_mois

        top3_mois = stats_mois_fy.nlargest(3, 'CA_Total')
        bottom3_mois = stats_mois_fy.nsmallest(3, 'CA_Total')
    else:
        stats_mois = None

    # ─────────────────────────────────────────────────────────────────────
    # 3. ANALYSE PAR ANNÉE FISCALE
    # ─────────────────────────────────────────────────────────────────────


    if 'Fiscal_Year_Label' in df_temp.columns:
        stats_fy = df_temp.groupby('Fiscal_Year_Label').agg({
            'Montant': ['sum', 'mean', 'median', 'std', 'count'],
            'Quantité': ['sum', 'mean'],
            'PU Net': ['mean', 'median'],
            'Cpt Client': 'nunique',
            'N° Bon': 'nunique'
        }).round(2)

        stats_fy.columns = ['CA_Total', 'CA_Moyen', 'CA_Median', 'CA_StdDev', 'Nb_Ventes', 
                           'Qty_Total', 'Qty_Moyenne', 'PU_Moyen', 'PU_Median', 
                           'Nb_Clients', 'Nb_Commandes']

        stats_fy['Variation_%'] = stats_fy['CA_Total'].pct_change() * 100
        stats_fy['CA_par_Client'] = (stats_fy['CA_Total'] / stats_fy['Nb_Clients']).round(2)
        stats_fy['CA_par_Commande'] = (stats_fy['CA_Total'] / stats_fy['Nb_Commandes']).round(2)
    else:
        stats_fy = None

    return {
        'trimestre': stats_trim,
        'mois': stats_mois,
        'annee_fiscale': stats_fy
    }


def aggregate_by_time(df, granularity='month'):
    """Agrège les données selon une granularité temporelle"""
    if granularity not in ['month', 'quarter', 'year']:
        raise ValueError(f"Granularité '{granularity}' invalide")
    
    group_col = {'month': 'Month', 'quarter': 'Quarter', 'year': 'Year'}[granularity]
    
    if group_col not in df.columns:
        raise ValueError(f"Colonne '{group_col}' manquante")
    
    agg_dict = {}
    if 'Montant' in df.columns:
        agg_dict['Montant'] = 'sum'
    if 'Quantité' in df.columns:
        agg_dict['Quantité'] = 'sum'
    if 'Cpt Client' in df.columns:
        agg_dict['Cpt Client'] = 'nunique'
    if 'N° Bon' in df.columns:
        agg_dict['N° Bon'] = 'nunique'
    
    df_agg = df.groupby(group_col).agg(agg_dict)
    
    # Renommer colonnes
    df_agg.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col 
                      for col in df_agg.columns]
    
    rename_map = {
        'Montant': 'CA_Total', 'Montant_sum': 'CA_Total',
        'Quantité': 'Qty_Total', 'Quantité_sum': 'Qty_Total',
        'Cpt Client': 'Nb_Clients', 'Cpt Client_nunique': 'Nb_Clients',
        'N° Bon': 'Nb_Commandes', 'N° Bon_nunique': 'Nb_Commandes'
    }
    
    df_agg.rename(columns=rename_map, inplace=True)
    
    if 'CA_Total' in df_agg.columns and 'Qty_Total' in df_agg.columns:
        df_agg['PU_Net_Moyen'] = df_agg['CA_Total'] / df_agg['Qty_Total']
    
    return df_agg


def get_temporal_metrics(df, granularity='month'):
    """Extrait des métriques temporelles"""
    df_agg = aggregate_by_time(df, granularity)
    
    return {
        'granularity': granularity,
        'periods': df_agg.index.tolist(),
        'ca_total': df_agg['CA_Total'].tolist() if 'CA_Total' in df_agg.columns else [],
        'qty_total': df_agg['Qty_Total'].tolist() if 'Qty_Total' in df_agg.columns else [],
        'nb_clients': df_agg['Nb_Clients'].tolist() if 'Nb_Clients' in df_agg.columns else [],
        'nb_commandes': df_agg['Nb_Commandes'].tolist() if 'Nb_Commandes' in df_agg.columns else []
    }


def _series_insights(values: pd.Series, labels: list[str]) -> dict:
    y = pd.to_numeric(values, errors='coerce').fillna(0.0)
    n = int(len(y))
    out: dict = {'n_periods': n}

    if n == 0:
        return out

    out['last_period'] = labels[-1]
    out['last_value'] = float(y.iloc[-1])

    if n >= 2:
        prev = float(y.iloc[-2])
        last = float(y.iloc[-1])
        out['prev_period'] = labels[-2]
        out['prev_value'] = prev
        out['pct_change_last'] = float(((last / prev) - 1) * 100) if prev != 0 else None

        x = np.arange(n, dtype=float)
        slope, intercept = np.polyfit(x, y.values.astype(float), 1)
        y_pred = slope * x + intercept
        ss_res = float(np.sum((y.values - y_pred) ** 2))
        ss_tot = float(np.sum((y.values - float(np.mean(y.values))) ** 2))
        r2 = (1.0 - ss_res / ss_tot) if ss_tot > 0 else None

        out['trend_slope_per_period'] = float(slope)
        out['trend_r2'] = float(r2) if r2 is not None else None

    mean_v = float(np.mean(y.values))
    std_v = float(np.std(y.values))
    out['cv_pct'] = float((std_v / mean_v) * 100) if mean_v != 0 else None

    pairs = list(zip(labels, y.values.astype(float).tolist()))
    out['top_periods'] = [
        {'period': p, 'value': float(v)}
        for p, v in sorted(pairs, key=lambda t: t[1], reverse=True)[:3]
    ]
    out['bottom_periods'] = [
        {'period': p, 'value': float(v)}
        for p, v in sorted(pairs, key=lambda t: t[1])[:3]
    ]
    return out


def generate_temporal_analysis(
    df: pd.DataFrame,
    granularity: str = 'month',
    df_daily_cache: pd.DataFrame | None = None,
    anomaly_report_cache: dict | None = None,
):
    """
    Analyse temporelle complète avec STL, ARIMA, tests de stationnarité
    """
    results = {}
    graphs = {}
    
    # Base d'analyse = JOURNALIÈRE (pour suffisamment de points)
    df_daily = df_daily_cache if df_daily_cache is not None else aggregate_daily(df)
    df_display = aggregate_from_daily(df_daily, granularity)

    results['analysis_basis'] = 'daily'

    # Synthèses approfondies: CA / Quantité / Nb_Clients
    try:
        insights = {}

        # CA & Quantité: basés sur df_display (agrégé par granularité)
        if df_display is not None and not df_display.empty:
            labels = df_display.index.astype(str).tolist()

            if 'CA_Total' in df_display.columns:
                insights['ca'] = _series_insights(df_display['CA_Total'], labels)

            if 'Qty_Total' in df_display.columns:
                insights['qty'] = _series_insights(df_display['Qty_Total'], labels)

        # Nb_Clients: calcul correct = nunique par période sur le df brut
        period_col = None
        if granularity == 'month' and 'Month' in df.columns:
            period_col = 'Month'
        elif granularity == 'quarter' and 'Quarter' in df.columns:
            period_col = 'Quarter'
        elif granularity == 'year':
            if 'Fiscal_Year_Label' in df.columns:
                period_col = 'Fiscal_Year_Label'
            elif 'Year' in df.columns:
                period_col = 'Year'

        clients_per_period = None
        if period_col and 'Cpt Client' in df.columns:
            clients_per_period = (
                df.groupby(period_col)['Cpt Client']
                .nunique()
                .sort_index()
            )
            labels_c = clients_per_period.index.astype(str).tolist()
            insights['clients'] = _series_insights(clients_per_period, labels_c)

        if insights:
            results['insights'] = insights
    except Exception as e:
        results['insights_error'] = str(e)

    # Graph unique d'évolution avec sélecteur (CA / Quantité / Nb clients)
    try:
        clients_display = None
        if clients_per_period is not None and df_display is not None and not df_display.empty:
            display_labels = df_display.index.astype(str)
            clients_display = (
                clients_per_period.copy()
                .rename('Nb_Clients')
            )
            clients_display.index = clients_display.index.astype(str)
            clients_display = clients_display.reindex(display_labels)

        evolution_html = _create_evolution_selector_plot(df_display, clients_display, granularity)
        if evolution_html:
            graphs['evolution_selector'] = evolution_html
    except Exception as e:
        results['evolution_selector_error'] = str(e)

    # Graph: évolution (df_display) + STL (df_daily)
    try:
        stl_html, stl_metrics = create_stl_decomposition_plot(df_daily, df_display, display_granularity=granularity)
        if stl_html:
            graphs['stl_decomposition'] = stl_html
        if isinstance(stl_metrics, dict):
            if 'stl_period' in stl_metrics:
                results['stl_period'] = stl_metrics.get('stl_period')
            if 'stl_trend_strength' in stl_metrics:
                results['stl_trend_strength'] = stl_metrics.get('stl_trend_strength')
            if 'stl_seasonal_strength' in stl_metrics:
                results['stl_seasonal_strength'] = stl_metrics.get('stl_seasonal_strength')
    except Exception as e:
        results['stl_error'] = str(e)

    # Anomaly detection removed from this tab.

    # (Réduction volontaire) On ne génère plus de graphes STL supplémentaires (Quantité / Nb clients)
    # pour éviter un empilement de visuels; l'évolution est couverte par le graphique unique ci-dessus.

    # Stationnarité (ADF/KPSS) sur daily
    try:
        y = pd.to_numeric(df_daily['CA_Total'], errors='coerce').fillna(0)
        if len(y) >= 30 and y.nunique(dropna=True) > 1:
            adf_result = adfuller(y, autolag='AIC')
            kpss_result = kpss(y, regression='c', nlags='auto')

            results['stationnarite'] = {
                'adf_statistic': float(adf_result[0]),
                'adf_pvalue': float(adf_result[1]),
                'adf_stationnaire': adf_result[1] < 0.05,
                'kpss_statistic': float(kpss_result[0]),
                'kpss_pvalue': float(kpss_result[1]),
                'kpss_stationnaire': kpss_result[1] > 0.05
            }
    except Exception as e:
        results['stationnarite_error'] = str(e)
    
    return {'results': results, 'graphs': graphs}


def generate_time_series_analysis(df, granularity='month'):
    """
    Génère l'analyse de séries temporelles complète
    
    Args:
        df: DataFrame avec colonnes temporelles
        granularity: 'month', 'quarter' ou 'year'
    
    Returns:
        dict: {
            'results': dict avec les résultats d'analyse,
            'graphs': dict avec les graphiques HTML,
            'metrics': dict avec les métriques temporelles
        }
    """
    
    # Analyse complète
    analysis = generate_temporal_analysis(df, granularity)
    
    # Métriques avec granularité sélectable
    metrics = get_temporal_metrics(df, granularity=granularity)
    
    return {
        **analysis,
        'metrics': metrics,
        'granularity': granularity
    }


def aggregate_time_data(df, granularity='month'):
    """
    Agrège les données par période temporelle
    
    Args:
        df: DataFrame source
        granularity: 'month', 'quarter' ou 'year'
    
    Returns:
        DataFrame agrégé
    """
    return aggregate_by_time(df, granularity=granularity)
