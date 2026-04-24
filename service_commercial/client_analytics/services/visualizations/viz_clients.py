"""
Visualisations pour le sous-onglet CLIENTS
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import pandas as pd


def _make_responsive(fig):
    """Helper pour rendre un graphique Plotly responsive."""
    fig.update_layout(
        autosize=True,
        width=None,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    return fig


def _to_html_responsive(fig):
    """Convertit une figure Plotly en HTML avec config responsive."""
    fig = _make_responsive(fig)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})


def create_client_concentration_chart(client_stats_df):
    """
    Crée un graphique de concentration clients (Pareto)
    
    Args:
        client_stats_df: DataFrame avec stats clients incluant Part_CA_Cumul
        
    Returns:
        str: HTML du graphique Plotly
    """
    if client_stats_df is None or len(client_stats_df) == 0:
        return None
    
    try:
        # Prendre les 50 premiers clients pour lisibilité
        top_clients = client_stats_df.head(50).copy()
        top_clients['Rang'] = range(1, len(top_clients) + 1)
        
        # Créer le graphique avec double axe Y
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Barres : CA par client
        fig.add_trace(
            go.Bar(
                x=top_clients['Rang'],
                y=top_clients['CA_Total'],
                name='CA Total',
                marker_color='#3b82f6',
                hovertemplate='<b>Rang %{x}</b><br>CA: %{y:,.0f}€<extra></extra>'
            ),
            secondary_y=False
        )
        
        # Ligne : Cumul %
        fig.add_trace(
            go.Scatter(
                x=top_clients['Rang'],
                y=top_clients['Part_CA_Cumul'],
                name='Part Cumulée (%)',
                line=dict(color='#ef4444', width=3),
                mode='lines+markers',
                hovertemplate='<b>Rang %{x}</b><br>Cumul: %{y:.1f}%<extra></extra>'
            ),
            secondary_y=True
        )
        
        # Ligne horizontale à 80%
        fig.add_hline(y=80, line_dash="dash", line_color="orange", 
                     annotation_text="80% du CA", secondary_y=True)
        
        # Mise en forme
        fig.update_xaxes(title_text="Rang Client")
        fig.update_yaxes(title_text="Chiffre d'Affaires (€)", secondary_y=False)
        fig.update_yaxes(title_text="Part Cumulée (%)", secondary_y=True, range=[0, 105])
        
        fig.update_layout(
            title="Concentration Clients - Analyse de Pareto (Top 50)",
            hovermode='x unified',
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        return _to_html_responsive(fig)
        
    except Exception as e:
        print(f"Erreur lors de la création du graphique de concentration: {e}")
        return None


def create_rfm_distribution_chart(client_stats_df):
    """
    Crée un graphique de distribution des segments RFM
    
    Args:
        client_stats_df: DataFrame avec RFM_Segment
        
    Returns:
        str: HTML du graphique Plotly
    """
    if client_stats_df is None or 'RFM_Segment' not in client_stats_df.columns:
        return None
    
    try:
        # Compter les clients par segment
        segment_counts = client_stats_df['RFM_Segment'].value_counts()
        
        # Couleurs par segment
        colors = {
            'Champions': '#10b981',
            'Fidèles': '#3b82f6',
            'Potentiels': '#8b5cf6',
            'Nouveaux': '#f59e0b',
            'Risque': '#ef4444',
            'Perdus': '#6b7280'
        }
        
        segment_colors = [colors.get(seg, '#94a3b8') for seg in segment_counts.index]
        
        # Créer le graphique en barres
        fig = go.Figure(data=[
            go.Bar(
                x=segment_counts.index,
                y=segment_counts.values,
                marker_color=segment_colors,
                text=segment_counts.values,
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Clients: %{y}<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title="Distribution des Segments RFM",
            xaxis_title="Segment",
            yaxis_title="Nombre de Clients",
            height=400,
            showlegend=False
        )
        
        return _to_html_responsive(fig)
        
    except Exception as e:
        print(f"Erreur lors de la création du graphique RFM: {e}")
        return None


def create_client_ca_distribution_chart(client_stats_df):
    """
    Crée un histogramme de distribution du CA par client
    
    Args:
        client_stats_df: DataFrame avec CA_Total
        
    Returns:
        str: HTML du graphique Plotly
    """
    if client_stats_df is None or len(client_stats_df) == 0:
        return None


def create_client_mix_families_pie(families_table):
    """Camembert du mix familles (table sérialisable: [{'family','ca',...}])."""
    if not families_table:
        return None
    try:
        df = pd.DataFrame(families_table)
        if df.empty or 'family' not in df.columns or 'ca' not in df.columns:
            return None

        df = df.copy()
        df['ca'] = pd.to_numeric(df['ca'], errors='coerce')
        df = df.dropna(subset=['family', 'ca'])
        if df.empty:
            return None

        fig = px.pie(
            df,
            names='family',
            values='ca',
            title='Portefeuille familles (CA)',
            hole=0.35,
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=420, legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='left', x=0))
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_mix_families_pie: {e}")
        return None


def create_client_mix_families_stacked(monthly_family_df, period_label: str = 'Mois'):
    """Stacked (bar) du mix familles par période (records: month/period,family,ca)."""
    if not monthly_family_df:
        return None
    try:
        df = pd.DataFrame(monthly_family_df)
        x_col = 'period' if 'period' in df.columns else 'month'
        if df.empty or not {x_col, 'family', 'ca'}.issubset(df.columns):
            return None
        df = df.copy()
        df['ca'] = pd.to_numeric(df['ca'], errors='coerce')
        df = df.dropna(subset=[x_col, 'family', 'ca'])
        if df.empty:
            return None

        sort_cols = [x_col]
        if 'period_index' in df.columns and pd.to_numeric(df['period_index'], errors='coerce').notna().any():
            df['period_index'] = pd.to_numeric(df['period_index'], errors='coerce')
            sort_cols = ['period_index', x_col]

        # Normalisation en % par mois (100% empilé)
        totals = df.groupby(x_col, sort=False)['ca'].transform('sum')
        df['share_pct'] = (df['ca'] / totals.replace({0: pd.NA})) * 100.0

        fig = px.bar(
            df.sort_values(sort_cols),
            x=x_col,
            y='share_pct',
            color='family',
            title=f"Évolution du portefeuille familles (mix % par {period_label.lower()})",
        )

        # Ajouter le CA en info-bulle via customdata
        fig.update_traces(
            customdata=df[['ca']].to_numpy(),
            hovertemplate=f"{period_label} %{{x}}<br>Famille %{{legendgroup}}<br>Part: %{{y:.1f}}%<br>CA: %{{customdata[0]:,.0f}}<extra></extra>"
        )
        fig.update_layout(
            barmode='stack',
            height=450,
            xaxis_title=period_label,
            yaxis_title='Part du CA (%)',
            yaxis=dict(range=[0, 100]),
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_mix_families_stacked: {e}")
        return None


def create_client_orders_over_time(monthly_orders_df, period_label: str = 'Mois', period_adjective: str = 'mensuel'):
    """Série temporelle CA (ligne) + nb commandes (barres) par période."""
    if not monthly_orders_df:
        return None
    try:
        df = pd.DataFrame(monthly_orders_df)
        x_col = 'period' if 'period' in df.columns else 'month'
        if df.empty or not {x_col, 'ca', 'nb_orders'}.issubset(df.columns):
            return None

        df = df.copy()
        if 'period_index' in df.columns and pd.to_numeric(df['period_index'], errors='coerce').notna().any():
            df['period_index'] = pd.to_numeric(df['period_index'], errors='coerce')
            df = df.sort_values(['period_index', x_col])
        else:
            df = df.sort_values(x_col)

        # Normaliser l'axe X en datetime uniquement si TOUTES les valeurs sont parsables.
        # Sinon, on garde les libellés d'origine pour éviter des NaT qui peuvent casser l'affichage.
        x_as_dt = pd.to_datetime(df[x_col], errors='coerce')
        if x_as_dt.notna().all():
            df['_x'] = x_as_dt
            is_date_axis = True
        else:
            df['_x'] = df[x_col]
            is_date_axis = False
        df['ca'] = pd.to_numeric(df['ca'], errors='coerce')
        df['nb_orders'] = pd.to_numeric(df['nb_orders'], errors='coerce')

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=df[x_col],
                y=df['nb_orders'],
                name='Nb commandes',
                marker_color='#3b82f6',
                hovertemplate=f"{period_label} %{{x}}<br>Cmd: %{{y:.0f}}<extra></extra>"
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df['ca'],
                name='CA',
                mode='lines+markers',
                line=dict(color='#10b981', width=3),
                hovertemplate=f"{period_label} %{{x}}<br>CA: %{{y:,.0f}}<extra></extra>"
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title=f"Commandes et CA dans le temps ({period_adjective})",
            height=460,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        fig.update_yaxes(title_text='Nb commandes', secondary_y=False)
        fig.update_yaxes(title_text='CA', secondary_y=True)
        fig.update_xaxes(title_text=period_label)
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_orders_over_time: {e}")
        return None


def create_client_pu_box_by_family(df_client, top_families):
    """Box plot du PU Net par famille (df attendu: colonnes family, pu_net)."""
    if df_client is None or len(df_client) == 0:
        return None


def create_client_pu_over_time(
    monthly_summary,
    monthly_product_pu_records=None,
    top_n_products: int | None = 6,
    period_label: str = 'Mois',
    period_adjective: str = 'mensuel',
):
    """PU Net (pondéré) par mois.

    - monthly_summary: liste de dicts avec au moins {month, pu_net_weighted}
    - monthly_product_pu_records (optionnel): liste de dicts avec au moins
      {month, product, pu_net_weighted}. Optionnel: {ca} pour info-bulle.
    """
    if not monthly_summary:
        return None
    try:
        df = pd.DataFrame(monthly_summary)
        x_col = 'period' if 'period' in df.columns else 'month'
        if df.empty or x_col not in df.columns:
            return None
        col = 'pu_net_weighted'
        if col not in df.columns:
            return None

        df = df.copy()
        if 'period_index' in df.columns and pd.to_numeric(df['period_index'], errors='coerce').notna().any():
            df['period_index'] = pd.to_numeric(df['period_index'], errors='coerce')
            df = df.sort_values(['period_index', x_col])
        else:
            df = df.sort_values(x_col)
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=[col])
        if df.empty:
            return None

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df[col],
                name='Client (pondéré)',
                mode='lines+markers',
                line=dict(color='#8b5cf6', width=3),
                hovertemplate=f"{period_label} %{{x}}<br>PU Net: %{{y:.2f}}<extra></extra>"
            )
        )

        # Ajouter des séries sur le même graphique (top N) : produits OU clients
        if monthly_product_pu_records:
            try:
                dp = pd.DataFrame(monthly_product_pu_records)
                x2_col = 'period' if 'period' in dp.columns else 'month'
                if dp.empty or x2_col not in dp.columns or 'pu_net_weighted' not in dp.columns:
                    dp = pd.DataFrame()

                series_col = None
                if not dp.empty:
                    if 'family' in dp.columns:
                        series_col = 'family'
                    elif 'client' in dp.columns:
                        series_col = 'client'
                    elif 'product' in dp.columns:
                        series_col = 'product'

                if series_col:
                    dp = dp.copy()
                    dp['pu_net_weighted'] = pd.to_numeric(dp['pu_net_weighted'], errors='coerce')
                    dp = dp.dropna(subset=[x2_col, series_col, 'pu_net_weighted'])
                    if not dp.empty:
                        if 'ca' in dp.columns:
                            dp['ca'] = pd.to_numeric(dp['ca'], errors='coerce')

                        if top_n_products is not None and int(top_n_products) > 0 and dp[series_col].nunique() > int(top_n_products):
                            if 'ca' in dp.columns and dp['ca'].notna().any():
                                top_prod = (
                                    dp.groupby(series_col, dropna=False)['ca']
                                    .sum(min_count=1)
                                    .sort_values(ascending=False)
                                    .head(int(top_n_products))
                                    .index
                                )
                            else:
                                top_prod = dp[series_col].value_counts().head(int(top_n_products)).index
                            dp = dp[dp[series_col].isin(top_prod)]

                        if 'period_index' in dp.columns and pd.to_numeric(dp['period_index'], errors='coerce').notna().any():
                            dp['period_index'] = pd.to_numeric(dp['period_index'], errors='coerce')
                            dp = dp.sort_values(['period_index', x2_col, series_col])
                        else:
                            dp = dp.sort_values([x2_col, series_col])
                        if series_col == 'family':
                            label_prefix = 'Famille'
                        elif series_col == 'client':
                            label_prefix = 'Client'
                        else:
                            label_prefix = 'Produit'
                        for series_name, grp in dp.groupby(series_col, dropna=False):
                            if grp.empty:
                                continue
                            # couleur auto (pas de hard-code)
                            if 'ca' in grp.columns and grp['ca'].notna().any():
                                custom = grp[['ca']].to_numpy()
                                hover = f"Mois %{{x}}<br>{label_prefix} %{{legendgroup}}<br>PU Net: %{{y:.2f}}<br>CA: %{{customdata[0]:,.0f}}<extra></extra>"
                            else:
                                custom = None
                                hover = f"Mois %{{x}}<br>{label_prefix} %{{legendgroup}}<br>PU Net: %{{y:.2f}}<extra></extra>"

                            fig.add_trace(
                                go.Scatter(
                                    x=grp[x2_col],
                                    y=grp['pu_net_weighted'],
                                    name=str(series_name),
                                    mode='lines+markers',
                                    line=dict(width=2),
                                    opacity=0.9,
                                    customdata=custom,
                                    hovertemplate=hover,
                                )
                            )
            except Exception as e:
                print(f"Erreur create_client_pu_over_time (products): {e}")

        fig.update_layout(
            title=f"PU Net (pondéré) par {period_label.lower()} — par famille ({period_adjective})",
            xaxis_title=period_label,
            yaxis_title='PU Net',
            height=460,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_pu_over_time: {e}")
        return None
    try:
        df = pd.DataFrame(df_client)
        if df.empty or not {'family', 'pu_net'}.issubset(df.columns):
            return None
        df = df.copy()
        df['pu_net'] = pd.to_numeric(df['pu_net'], errors='coerce')
        df = df.dropna(subset=['family', 'pu_net'])
        if top_families:
            df = df[df['family'].astype(str).isin([str(x) for x in top_families])]
        if df.empty:
            return None

        fig = px.box(
            df,
            x='family',
            y='pu_net',
            title='Dispersion du PU Net (Top familles)',
            points='outliers',
        )
        fig.update_layout(height=450, xaxis_title='Famille', yaxis_title='PU Net')
        fig.update_xaxes(tickangle=25)
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_pu_box_by_family: {e}")
        return None


def create_client_pu_over_time_by_product(monthly_product_pu_records, top_n: int = 6):
    """PU Net (pondéré) par mois, ventilé par produit.

    monthly_product_pu_records: liste de dicts sérialisables avec au moins
    {month, product, pu_net_weighted}. Optionnel: {ca} pour l'info-bulle.
    """
    if not monthly_product_pu_records:
        return None
    try:
        df = pd.DataFrame(monthly_product_pu_records)
        if df.empty or not {'month', 'product', 'pu_net_weighted'}.issubset(df.columns):
            return None

        df = df.copy()
        df['pu_net_weighted'] = pd.to_numeric(df['pu_net_weighted'], errors='coerce')
        df = df.dropna(subset=['month', 'product', 'pu_net_weighted'])
        if df.empty:
            return None

        if 'ca' in df.columns:
            df['ca'] = pd.to_numeric(df['ca'], errors='coerce')

        # Limiter au top N produits (par CA si dispo, sinon fréquence)
        if top_n and df['product'].nunique() > int(top_n):
            if 'ca' in df.columns and df['ca'].notna().any():
                top_products = (
                    df.groupby('product', dropna=False)['ca']
                    .sum(min_count=1)
                    .sort_values(ascending=False)
                    .head(int(top_n))
                    .index
                )
            else:
                top_products = df['product'].value_counts().head(int(top_n)).index
            df = df[df['product'].isin(top_products)]

        df = df.sort_values(['month', 'product'])

        fig = px.line(
            df,
            x='month',
            y='pu_net_weighted',
            color='product',
            markers=True,
            title='PU Net (pondéré) par mois — Top produits',
        )

        if 'ca' in df.columns:
            fig.update_traces(
                customdata=df[['ca']].to_numpy(),
                hovertemplate='Mois %{x}<br>Produit %{legendgroup}<br>PU Net: %{y:.2f}<br>CA: %{customdata[0]:,.0f}<extra></extra>'
            )
        else:
            fig.update_traces(
                hovertemplate='Mois %{x}<br>Produit %{legendgroup}<br>PU Net: %{y:.2f}<extra></extra>'
            )

        fig.update_layout(
            xaxis_title='Mois',
            yaxis_title='PU Net',
            height=460,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_pu_over_time_by_product: {e}")
        return None


def create_client_lead_time_hist(df_client):
    """Histogramme des lead times (df attendu: colonne lead_time)."""
    if df_client is None or len(df_client) == 0:
        return None
    try:
        df = pd.DataFrame(df_client)
        if df.empty or 'lead_time' not in df.columns:
            return None
        s = pd.to_numeric(df['lead_time'], errors='coerce').dropna()
        if s.empty:
            return None

        fig = go.Figure(data=[
            go.Histogram(
                x=s,
                nbinsx=30,
                marker_color='#f59e0b',
                hovertemplate='Lead time: %{x}<br>Nb: %{y}<extra></extra>'
            )
        ])
        fig.update_layout(
            title='Distribution des lead times',
            xaxis_title='Lead time (jours)',
            yaxis_title='Nb lignes',
            height=420,
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_lead_time_hist: {e}")
        return None


def create_client_lead_time_over_time(monthly_lead_df, period_label: str = 'Mois'):
    """Lead time médian/p90 par période (records: month/period, lead_time_median, lead_time_p90)."""
    if not monthly_lead_df:
        return None
    try:
        df = pd.DataFrame(monthly_lead_df)
        x_col = 'period' if 'period' in df.columns else 'month'
        if df.empty or x_col not in df.columns:
            return None
        df = df.copy()
        if 'period_index' in df.columns and pd.to_numeric(df['period_index'], errors='coerce').notna().any():
            df['period_index'] = pd.to_numeric(df['period_index'], errors='coerce')
            df = df.sort_values(['period_index', x_col])
        else:
            df = df.sort_values(x_col)
        if 'lead_time_median' in df.columns:
            df['lead_time_median'] = pd.to_numeric(df['lead_time_median'], errors='coerce')
        if 'lead_time_p90' in df.columns:
            df['lead_time_p90'] = pd.to_numeric(df['lead_time_p90'], errors='coerce')

        has_any = False
        fig = go.Figure()

        if 'lead_time_median' in df.columns and df['lead_time_median'].notna().any():
            has_any = True
            fig.add_trace(
                go.Scatter(
                    x=df[x_col],
                    y=df['lead_time_median'],
                    name='Médiane',
                    mode='lines+markers',
                    line=dict(color='#3b82f6', width=3),
                )
            )
        if 'lead_time_p90' in df.columns and df['lead_time_p90'].notna().any():
            has_any = True
            fig.add_trace(
                go.Scatter(
                    x=df[x_col],
                    y=df['lead_time_p90'],
                    name='P90',
                    mode='lines+markers',
                    line=dict(color='#ef4444', width=3, dash='dot'),
                )
            )

        if not has_any:
            return None

        fig.update_layout(
            title='Lead time dans le temps',
            xaxis_title=period_label,
            yaxis_title='Lead time (jours)',
            height=430,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_lead_time_over_time: {e}")
        return None


def create_client_lead_time_impact_chart(monthly_summary, gap_records=None, high_lt_threshold=None, period_label: str = 'Mois'):
    """Visualise l'impact du lead time sur l'activité.

    - monthly_summary: liste de dicts avec {month, nb_orders, ca, lead_time_median/lead_time_p90}
      On trace LT_t vs (cmd_{t+1}, CA_{t+1}) pour suggérer un impact retardé.
    - gap_records (optionnel): liste de dicts {group, gap_next_days} pour un boxplot
      (ex: après LT élevé vs bas).
    """
    if not monthly_summary:
        return None
    try:
        df = pd.DataFrame(monthly_summary)
        x_col = 'period' if 'period' in df.columns else 'month'
        if df.empty or x_col not in df.columns:
            return None

        df = df.copy()
        if 'period_index' in df.columns and pd.to_numeric(df['period_index'], errors='coerce').notna().any():
            df['period_index'] = pd.to_numeric(df['period_index'], errors='coerce')
            df = df.sort_values(['period_index', x_col])
        else:
            df = df.sort_values(x_col)
        df['nb_orders'] = pd.to_numeric(df.get('nb_orders'), errors='coerce')
        df['ca'] = pd.to_numeric(df.get('ca'), errors='coerce')

        if 'lead_time_median' in df.columns and pd.to_numeric(df['lead_time_median'], errors='coerce').notna().any():
            df['lt'] = pd.to_numeric(df['lead_time_median'], errors='coerce')
        elif 'lead_time_p90' in df.columns and pd.to_numeric(df['lead_time_p90'], errors='coerce').notna().any():
            df['lt'] = pd.to_numeric(df['lead_time_p90'], errors='coerce')
        else:
            return None

        # Lag-1: activity next month
        df['orders_next'] = df['nb_orders'].shift(-1)
        df['ca_next'] = df['ca'].shift(-1)
        df['_x_next'] = df['_x'].shift(-1)

        # Guardrails: besoin de quelques points
        base = df[[x_col, 'lt', 'orders_next', 'ca_next']].dropna(subset=[x_col, 'lt'])
        if base.shape[0] < 3:
            return None

        has_gap = bool(gap_records)
        rows = 3 if has_gap else 2
        specs = [[{"secondary_y": True}], [{"secondary_y": True}]] + ([ [{}] ] if has_gap else [])
        row_heights = [0.42, 0.42, 0.16] if has_gap else [0.5, 0.5]
        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            specs=specs,
            row_heights=row_heights,
            subplot_titles=(
                'LT du mois t vs Commandes du mois t+1',
                'LT du mois t vs CA du mois t+1',
                'Temps avant prochaine commande (selon LT)' if has_gap else None,
            ) if has_gap else (
                'LT du mois t vs Commandes du mois t+1',
                'LT du mois t vs CA du mois t+1',
            ),
        )

        # Row 1: LT + orders_next
        fig.add_trace(
            go.Scatter(
                x=df['_x'],
                y=df['lt'],
                name='Lead time (t)',
                mode='lines+markers',
                line=dict(color='#3b82f6', width=3),
                hovertemplate=(
                    f"{period_label} %{{x}}<br>LT: %{{y:.1f}} j<extra></extra>"
                    if not is_date_axis else
                    f"{period_label} %{{x|%b %Y}}<br>LT: %{{y:.1f}} j<extra></extra>"
                ),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
        if df['orders_next'].notna().any():
            fig.add_trace(
                go.Bar(
                    x=df['_x'],
                    y=df['orders_next'],
                    name='Cmd (t+1)',
                    customdata=df['_x_next'],
                    marker_color='#10b981',
                    opacity=0.55,
                    hovertemplate=(
                        f"{period_label} (t) %{{x}}"
                        f"<br>{period_label} (t+1) %{{customdata}}"
                        f"<br>Cmd (t+1): %{{y:.0f}}"
                        "<extra></extra>"
                    ) if not is_date_axis else (
                        f"{period_label} (t) %{{x|%b %Y}}"
                        f"<br>{period_label} (t+1) %{{customdata|%b %Y}}"
                        f"<br>Cmd (t+1): %{{y:.0f}}"
                        "<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
                secondary_y=True,
            )

        # Row 2: LT + ca_next
        fig.add_trace(
            go.Scatter(
                x=df['_x'],
                y=df['lt'],
                name='Lead time (t)',
                mode='lines+markers',
                showlegend=False,
                line=dict(color='#3b82f6', width=3),
                hovertemplate=(
                    f"{period_label} %{{x}}<br>LT: %{{y:.1f}} j<extra></extra>"
                    if not is_date_axis else
                    f"{period_label} %{{x|%b %Y}}<br>LT: %{{y:.1f}} j<extra></extra>"
                ),
            ),
            row=2,
            col=1,
            secondary_y=False,
        )
        if df['ca_next'].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=df['_x'],
                    y=df['ca_next'],
                    name='CA (t+1)',
                    mode='lines+markers',
                    line=dict(color='#8b5cf6', width=2),
                    customdata=df['_x_next'],
                    hovertemplate=(
                        f"{period_label} (t) %{{x}}"
                        f"<br>{period_label} (t+1) %{{customdata}}"
                        f"<br>CA (t+1): %{{y:,.0f}}"
                        "<extra></extra>"
                    ) if not is_date_axis else (
                        f"{period_label} (t) %{{x|%b %Y}}"
                        f"<br>{period_label} (t+1) %{{customdata|%b %Y}}"
                        f"<br>CA (t+1): %{{y:,.0f}}"
                        "<extra></extra>"
                    ),
                ),
                row=2,
                col=1,
                secondary_y=True,
            )

        # Row 3: gap boxplot
        if has_gap:
            dg = pd.DataFrame(gap_records)
            if not dg.empty and {'group', 'gap_next_days'}.issubset(dg.columns):
                dg['gap_next_days'] = pd.to_numeric(dg['gap_next_days'], errors='coerce')
                dg = dg.dropna(subset=['group', 'gap_next_days'])
                for grp in ['LT < P75', 'LT ≥ P75']:
                    s = dg.loc[dg['group'] == grp, 'gap_next_days']
                    if s.empty:
                        continue
                    fig.add_trace(
                        go.Box(
                            y=s,
                            name=grp,
                            boxmean='sd',
                            hovertemplate=f"{grp}<br>Jours: %{{y:.0f}}<extra></extra>",
                        ),
                        row=3,
                        col=1,
                    )

        title = 'Impact du lead time sur l’activité'
        if high_lt_threshold is not None:
            try:
                title += f" (LT élevé ≈ P75: {float(high_lt_threshold):.1f} j)"
            except Exception:
                pass

        fig.update_layout(
            title=title,
            height=760 if has_gap else 620,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
            margin=dict(b=90),
        )

        fig.update_yaxes(title_text='Lead time (jours)', row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text='Cmd (t+1)', row=1, col=1, secondary_y=True)
        fig.update_yaxes(title_text='Lead time (jours)', row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text='CA (t+1)', row=2, col=1, secondary_y=True)

        # Avec shared_xaxes=True, Plotly n'affiche souvent les ticks que sur la dernière ligne.
        # Ici on force l'affichage sur les 2 sous-graphiques pour que l'utilisateur voie les mois.
        axis_kwargs = dict(showticklabels=True, tickangle=-45, automargin=True)
        if is_date_axis:
            # Éviter les options d'axe trop strictes: certaines versions/configs Plotly peuvent être sensibles.
            axis_kwargs.update(dict(tickformat='%b %Y'))
        fig.update_xaxes(title_text=period_label, row=rows, col=1, **axis_kwargs)
        fig.update_xaxes(row=1, col=1, **axis_kwargs)
        fig.update_xaxes(row=2, col=1, **axis_kwargs)
        if has_gap:
            fig.update_yaxes(title_text='Jours avant prochaine cmd', row=3, col=1)

        return _to_html_responsive(fig)
    except Exception as e:
        print(f"Erreur create_client_lead_time_impact_chart: {e}")
        return None
    
    try:
        fig = go.Figure(data=[
            go.Histogram(
                x=client_stats_df['CA_Total'],
                nbinsx=50,
                marker_color='#3b82f6',
                hovertemplate='CA: %{x:,.0f}€<br>Clients: %{y}<extra></extra>'
            )
        ])
        
        # Ajouter médiane
        median_ca = client_stats_df['CA_Total'].median()
        fig.add_vline(x=median_ca, line_dash="dash", line_color="red",
                     annotation_text=f"Médiane: {median_ca:,.0f}€")
        
        fig.update_layout(
            title="Distribution du CA par Client",
            xaxis_title="Chiffre d'Affaires (€)",
            yaxis_title="Nombre de Clients",
            height=400
        )
        
        return _to_html_responsive(fig)
        
    except Exception as e:
        print(f"Erreur lors de la création de l'histogramme CA: {e}")
        return None


def create_client_period_family_stacked(records: list, value_key: str = 'value', title: str = 'Analyse par période et famille', is_price: bool = False) -> str:
    """
    Crée un graphique en barres empilées pour visualiser les valeurs par période et famille.
    
    Args:
        records: Liste de dicts avec clés 'period', 'family', et value_key
                 Ex: [{"period": "2024-Q1", "family": "Bakery", "value": 12345}]
        value_key: Nom de la clé contenant la valeur (par défaut: 'value')
        title: Titre du graphique
        is_price: Si True, formate comme prix avec 2 décimales (par défaut: False)
    
    Returns:
        str: HTML du graphique Plotly
    """
    if not records:
        return None
    
    try:
        df = pd.DataFrame(records)
        if df.empty or 'period' not in df.columns or 'family' not in df.columns or value_key not in df.columns:
            return None
        
        # Nettoyer les données
        df = df.copy()
        df['period'] = df['period'].astype(str)
        df['family'] = df['family'].astype(str)
        df[value_key] = pd.to_numeric(df[value_key], errors='coerce')
        df = df.dropna(subset=['period', 'family', value_key])
        
        if df.empty:
            return None
        
        # Créer le graphique empilé
        fig = px.bar(
            df,
            x='period',
            y=value_key,
            color='family',
            title=title,
            barmode='stack',
            template='plotly_white',
        )
        
        # Déterminer le format d'affichage
        if is_price:
            hover_format = '<b>%{fullData.name}</b><br>Prix: %{y:,.2f}€<extra></extra>'
            yaxis_title = 'Prix Unitaire Net (€)'
        else:
            hover_format = '<b>%{fullData.name}</b><br>Valeur: %{y:,.0f}<extra></extra>'
            yaxis_title = 'Valeur'
        
        # Mise en forme
        fig.update_layout(
            height=520,
            xaxis_title='Période',
            yaxis_title=yaxis_title,
            legend=dict(
                orientation='v',
                yanchor='top',
                y=1,
                xanchor='left',
                x=1.02,
                title='Famille'
            ),
            hovermode='x unified',
            xaxis=dict(tickangle=-45),
        )
        
        fig.update_traces(
            hovertemplate=hover_format
        )
        
        return _to_html_responsive(fig)
        
    except Exception as e:
        print(f"Erreur create_client_period_family_stacked: {e}")
        return None
