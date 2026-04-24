"""
Visualisations pour l'onglet ANALYSE PAR PÉRIODES
Graphiques pour les analyses statistiques par mois, trimestre ou année fiscale
"""
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from scipy import stats
from sklearn.ensemble import IsolationForest

def create_isolation_forest_time_anomaly_plot(df, time_col, value_col, contamination=0.05, title=None, return_anomalies=False):
    """
    Détecte les anomalies sur une série temporelle avec Isolation Forest et affiche un graphique interactif.
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle (ex: 'Month', 'Date')
        value_col: Colonne numérique à analyser (ex: 'Montant')
        contamination: Proportion attendue d'anomalies (float)
        title: Titre du graphique
        return_anomalies: Si True, retourne aussi un DataFrame des anomalies
    
    Returns:
        HTML du graphique Plotly (et DataFrame anomalies si return_anomalies=True)
    """
    try:
        data = df[[time_col, value_col]].dropna().copy()
        # Encodage temporel si nécessaire
        import numpy as np
        import pandas as pd
        import plotly.graph_objects as go
        if not np.issubdtype(data[time_col].dtype, np.number):
            data['_time_idx'] = pd.factorize(data[time_col])[0]
            X = np.c_[data['_time_idx'], data[value_col]]
        else:
            X = np.c_[data[time_col], data[value_col]]
        model = IsolationForest(contamination=contamination, random_state=42)
        preds = model.fit_predict(X)
        data['anomaly'] = preds
        data['color'] = np.where(data['anomaly'] == -1, 'Anomalie', 'Normal')
        if title is None:
            title = f"Détection d'anomalies sur {value_col} ({time_col})"
        fig = go.Figure()
        # Courbe normale
        normal = data[data['anomaly'] == 1]
        fig.add_trace(go.Scatter(
            x=normal[time_col],
            y=normal[value_col],
            mode='lines+markers',
            name='Normal',
            marker=dict(color='blue', size=7),
            line=dict(color='blue', width=2)
        ))
        # Points anomalies
        anomalies = data[data['anomaly'] == -1]
        fig.add_trace(go.Scatter(
            x=anomalies[time_col],
            y=anomalies[value_col],
            mode='markers',
            name='Anomalie',
            marker=dict(color='red', size=12, symbol='x')
        ))
        fig.update_layout(
            title=title,
            xaxis_title=time_col,
            yaxis_title=value_col,
            height=450,
            template='plotly_dark',
            paper_bgcolor='rgba(20, 30, 50, 1)',
            plot_bgcolor='rgba(30, 40, 60, 1)'
        )
        html = _to_html_responsive(fig)
        if return_anomalies:
            return html, anomalies[[time_col, value_col]]
        return html
    except Exception as e:
        print(f"   ⚠️ Erreur détection d'anomalies Isolation Forest: {e}")
        if return_anomalies:
            return None, None
        return None


def _make_responsive(fig):
    """
    Helper pour rendre un graphique Plotly responsive et éviter les overflows.
    Applique les paramètres standards pour tous les graphiques.
    """
    fig.update_layout(
        autosize=True,
        width=None,
        margin=dict(l=40, r=20, t=60, b=40)
    )
    return fig


def _to_html_responsive(fig):
    """
    Convertit une figure Plotly en HTML avec config responsive.
    """
    fig = _make_responsive(fig)
    return fig.to_html(full_html=False, include_plotlyjs=False, config={'responsive': True})


def create_correlation_matrix(df, variables):
    """Crée une matrice de corrélation interactive"""
    try:
        fig = go.Figure(data=go.Heatmap(
            z=df[variables].corr().values,
            x=variables,
            y=variables,
            colorscale='RdBu',
            zmid=0,
            text=df[variables].corr().round(2).values,
            texttemplate='%{text}',
            textfont={"size": 12}
        ))
        fig.update_layout(
            title='Matrice de corrélation',
            height=400,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur matrice corrélation: {e}")
        return None


def create_distribution_plot(df, variable, title=None):
    """Crée un histogramme de distribution"""
    try:
        if title is None:
            title = f'Distribution de {variable}'
        
        fig = px.histogram(
            df,
            x=variable,
            nbins=50,
            title=title,
            labels={variable: variable},
            template='plotly_white'
        )
        fig.update_layout(
            height=350,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur distribution {variable}: {e}")
        return None


def create_top_categories_plot(df, category_col, value_col, n_top=10, title=None):
    """Crée un graphique en barres horizontales des top catégories"""
    try:
        if title is None:
            title = f'Top {n_top} {category_col} par {value_col}'
        
        top_data = df.groupby(category_col)[value_col].sum().nlargest(n_top).sort_values()
        
        fig = px.bar(
            x=top_data.values,
            y=top_data.index,
            orientation='h',
            title=title,
            labels={'x': f'{value_col} (€)', 'y': category_col},
            template='plotly_white'
        )
        fig.update_layout(
            height=400,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur top {category_col}: {e}")
        return None


def create_temporal_aggregation_plot(df, time_col, value_col, granularity='month'):
    """
    Crée un graphique d'agrégation temporelle selon la granularité
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle ('Month', 'Quarter', 'Fiscal_Year_Label')
        value_col: Colonne à agréger (ex: 'Montant')
        granularity: 'month', 'quarter', 'year'
    """
    try:
        # Titres selon la granularité
        titles = {
            'month': 'CA par Mois',
            'quarter': 'CA par Trimestre Fiscal',
            'year': 'CA par Année Fiscale'
        }
        
        agg_data = df.groupby(time_col)[value_col].sum().sort_index()
        
        fig = px.bar(
            x=agg_data.index,
            y=agg_data.values,
            title=titles.get(granularity, 'CA par Période'),
            labels={'x': 'Période', 'y': 'CA (€)'},
            template='plotly_white'
        )
        fig.update_layout(
            height=400,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur agrégation temporelle: {e}")
        return None


def create_temporal_evolution_plot(df, time_col, value_col, granularity='month'):
    """
    Crée un graphique d'évolution temporelle (barres) selon la granularité
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger
        granularity: 'month', 'quarter', 'year'
    """
    try:
        titles = {
            'month': 'Évolution Mensuelle du CA',
            'quarter': 'Évolution Trimestrielle du CA',
            'year': 'Évolution Annuelle du CA'
        }
        
        agg_data = df.groupby(time_col)[value_col].sum().sort_index()
        
        # Créer un graphique en barres au lieu d'une ligne
        fig = go.Figure(data=[
            go.Bar(
                x=agg_data.index,
                y=agg_data.values,
                marker_color='rgb(99, 110, 250)',
                text=agg_data.values.round(0),
                texttemplate='%{text:,.0f}€',
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>CA: %{y:,.0f}€<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title=titles.get(granularity, 'Évolution du CA'),
            xaxis_title='Période',
            yaxis_title='CA (€)',
            height=400,
            showlegend=False,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                gridcolor='rgba(200,200,200,0.3)'
            )
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur évolution temporelle: {e}")
        return None


def create_variation_plot(df, time_col, value_col, granularity='month'):
    """
    Crée un graphique de variation (%) période à période
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger
        granularity: 'month', 'quarter', 'year'
    """
    try:
        titles = {
            'month': 'Variation Mensuelle du CA (%)',
            'quarter': 'Variation Trimestrielle du CA (%)',
            'year': 'Variation Annuelle du CA (%)'
        }
        
        agg_data = df.groupby(time_col)[value_col].sum().sort_index()
        variation_pct = agg_data.pct_change() * 100
        
        colors = ['red' if v < 0 else 'green' for v in variation_pct.values]
        
        fig = go.Figure(data=[
            go.Bar(
                x=variation_pct.index[1:],  # Exclure la première valeur (NaN)
                y=variation_pct.values[1:],
                marker_color=colors[1:],
                text=variation_pct.round(1).values[1:],
                texttemplate='%{text}%',
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title=titles.get(granularity, 'Variation du CA (%)'),
            xaxis_title='Période',
            yaxis_title='Variation (%)',
            height=400,
            template='plotly_white',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur variation: {e}")
        return None


def create_ca_repartition_pie(df, time_col, value_col, granularity='month'):
    """
    Crée un pie chart de répartition du CA par période
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger (Montant)
        granularity: 'month', 'quarter', 'year'
    """
    try:
        titles = {
            'month': 'Répartition du CA par Mois',
            'quarter': 'Répartition du CA par Trimestre',
            'year': 'Répartition du CA par Année Fiscale'
        }
        
        agg_data = df.groupby(time_col)[value_col].sum().sort_index()
        
        fig = go.Figure(data=[go.Pie(
            labels=agg_data.index,
            values=agg_data.values,
            hole=0.3,
            textinfo='label+percent',
            textposition='auto',
            marker=dict(
                colors=px.colors.sequential.Blues,
                line=dict(color='#000000', width=2)
            ),
            hovertemplate='<b>%{label}</b><br>CA: %{value:,.0f}€<br>Part: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title=titles.get(granularity, 'Répartition du CA'),
            height=450,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.05
            )
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur répartition CA: {e}")
        return None


def create_top_periods_bar(df, time_col, value_col, granularity='month', n_top=5, direction='top'):
    """
    Crée un graphique en barres des top/bottom N périodes par CA, triées chronologiquement
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger (Montant)
        granularity: 'month', 'quarter', 'year'
        n_top: Nombre de périodes à afficher
        direction: 'top' pour les plus hauts, 'bottom' pour les plus bas
    """
    try:
        granularity_labels = {
            'month': 'Mois',
            'quarter': 'Trimestres',
            'year': 'Années'
        }
        
        granularity_label = granularity_labels.get(granularity, 'Périodes')
        
        if direction == 'top':
            titles = {
                'month': f'Top {n_top} Mois par CA',
                'quarter': f'Top {n_top} Trimestres par CA',
                'year': f'Top {n_top} Années par CA'
            }
            color = 'rgb(40, 167, 69)'  # Vert
        else:
            titles = {
                'month': f'Bottom {n_top} Mois par CA',
                'quarter': f'Bottom {n_top} Trimestres par CA',
                'year': f'Bottom {n_top} Années par CA'
            }
            color = 'rgb(220, 53, 69)'  # Rouge
        
        # Agréger par période
        agg_data = df.groupby(time_col)[value_col].sum()
        
        # Sélectionner top ou bottom
        if direction == 'top':
            selected = agg_data.nlargest(n_top)
        else:
            selected = agg_data.nsmallest(n_top)
        
        # Trier par index (ordre chronologique) au lieu de par valeur
        selected = selected.sort_index()
        
        fig = go.Figure(data=[go.Bar(
            y=selected.index,
            x=selected.values,
            orientation='h',
            marker_color=color,
            text=selected.values.round(0),
            texttemplate='%{text:,.0f}€',
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>CA: %{x:,.0f}€<extra></extra>'
        )])
        
        fig.update_layout(
            title=titles.get(granularity, f'{direction.capitalize()} {n_top} Périodes par CA'),
            xaxis_title='CA (€)',
            yaxis_title='Période',
            height=350,
            template='plotly_white',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickfont=dict(size=10),
                gridcolor='rgba(200,200,200,0.3)'
            ),
            yaxis=dict(
                tickfont=dict(size=10)
            )
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur top périodes: {e}")
        return None


def create_ca_moyen_per_transaction(df, time_col, value_col, granularity='month'):
    """
    Crée un histogramme du CA moyen par transaction pour chaque période
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger (Montant)
        granularity: 'month', 'quarter', 'year'
    """
    try:
        titles = {
            'month': 'CA Moyen par Transaction (Mensuel)',
            'quarter': 'CA Moyen par Transaction (Trimestriel)',
            'year': 'CA Moyen par Transaction (Annuel)'
        }
        
        # Calculer le CA moyen par transaction = CA total / nombre de transactions
        agg_data = df.groupby(time_col).agg({
            value_col: ['sum', 'count']
        })
        agg_data.columns = ['ca_total', 'nb_transactions']
        agg_data['ca_moyen'] = agg_data['ca_total'] / agg_data['nb_transactions']
        agg_data = agg_data.sort_index()
        
        fig = go.Figure(data=[go.Bar(
            x=agg_data.index,
            y=agg_data['ca_moyen'],
            marker_color='rgb(76, 175, 80)',
            text=agg_data['ca_moyen'].round(2),
            texttemplate='%{text:.2f}€',
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>CA Moyen: %{y:.2f}€<br>Transactions: ' + 
                         agg_data['nb_transactions'].astype(str) + '<extra></extra>'
        )])
        
        fig.update_layout(
            title=titles.get(granularity, 'CA Moyen par Transaction'),
            xaxis_title='Période',
            yaxis_title='CA Moyen (€)',
            height=400,
            template='plotly_white',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                gridcolor='rgba(200,200,200,0.3)'
            )
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur CA moyen par transaction: {e}")
        return None


def create_stability_chart(df, time_col, value_col, granularity='month'):
    """
    Crée un histogramme de stabilité des ventes (écart-type du CA par période)
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle
        value_col: Colonne à agréger (Montant)
        granularity: 'month', 'quarter', 'year'
    """
    try:
        titles = {
            'month': 'Stabilité des Ventes par Mois (Écart-type)',
            'quarter': 'Stabilité des Ventes par Trimestre (Écart-type)',
            'year': 'Stabilité des Ventes par Année (Écart-type)'
        }
        
        # Calculer l'écart-type du CA par période
        stability_data = df.groupby(time_col)[value_col].std().sort_index()
        
        # Identifier les périodes stables (faible écart-type) vs volatiles (fort écart-type)
        median_std = stability_data.median()
        colors = ['green' if v < median_std else 'orange' for v in stability_data.values]
        
        fig = go.Figure(data=[go.Bar(
            x=stability_data.index,
            y=stability_data.values,
            marker_color=colors,
            text=stability_data.values.round(2),
            texttemplate='%{text:.2f}',
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Écart-type: %{y:.2f}€<extra></extra>'
        )])
        
        fig.update_layout(
            title=titles.get(granularity, 'Stabilité des Ventes'),
            xaxis_title='Période',
            yaxis_title='Écart-type (€)',
            height=400,
            template='plotly_white',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                gridcolor='rgba(200,200,200,0.3)'
            ),
            annotations=[
                dict(
                    x=0.5,
                    y=1.05,
                    xref='paper',
                    yref='paper',
                    text='🟢 Vert = Stable (faible variation) | 🟠 Orange = Volatile (forte variation)',
                    showarrow=False,
                    font=dict(size=10),
                    xanchor='center'
                )
            ]
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur stabilité des ventes: {e}")
        return None


def create_qq_plot(df, variable):
    """
    Crée un graphique QQ-plot (Quantile-Quantile) pour tester la normalité
    
    Args:
        df: DataFrame
        variable: Nom de la variable à analyser
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        # Supprimer les NaN
        data = df[variable].dropna()
        
        # Calculer les quantiles théoriques et empiriques
        theoretical_quantiles = stats.probplot(data, dist="norm")[0][0]
        sample_quantiles = stats.probplot(data, dist="norm")[0][1]
        
        # Créer le graphique
        fig = go.Figure()
        
        # Points QQ
        fig.add_trace(go.Scatter(
            x=theoretical_quantiles,
            y=sample_quantiles,
            mode='markers',
            name='Données',
            marker=dict(color='blue', size=5, opacity=0.6)
        ))
        
        # Ligne théorique (y=x)
        min_val = min(theoretical_quantiles.min(), sample_quantiles.min())
        max_val = max(theoretical_quantiles.max(), sample_quantiles.max())
        fig.add_trace(go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode='lines',
            name='Distribution normale théorique',
            line=dict(color='red', dash='dash')
        ))
        
        fig.update_layout(
            title=f'QQ-Plot - {variable}',
            xaxis_title='Quantiles théoriques (distribution normale)',
            yaxis_title='Quantiles empiriques (données)',
            height=400,
            template='plotly_white',
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur QQ-plot pour {variable}: {e}")
        return None


def create_normality_test_plot(df, variable):
    """
    Crée un histogramme avec courbe normale théorique superposée
    
    Args:
        df: DataFrame
        variable: Nom de la variable à analyser
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        # Supprimer les NaN
        data = df[variable].dropna()
        
        # Calculer la moyenne et l'écart-type
        mean = data.mean()
        std = data.std()
        
        # Créer l'histogramme
        fig = go.Figure()
        
        # Histogramme des données
        fig.add_trace(go.Histogram(
            x=data,
            name='Données réelles',
            nbinsx=50,
            histnorm='probability density',
            marker_color='lightblue',
            opacity=0.7
        ))
        
        # Courbe normale théorique
        x_range = np.linspace(data.min(), data.max(), 100)
        y_normal = stats.norm.pdf(x_range, mean, std)
        
        fig.add_trace(go.Scatter(
            x=x_range,
            y=y_normal,
            mode='lines',
            name='Distribution normale théorique',
            line=dict(color='red', width=2)
        ))
        
        fig.update_layout(
            title=f'Test de Normalité - {variable}',
            xaxis_title=variable,
            yaxis_title='Densité de probabilité',
            height=400,
            template='plotly_white',
            showlegend=True,
            bargap=0.1,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur test normalité pour {variable}: {e}")
        return None


def create_outliers_boxplot(df, variables):
    """
    Crée des boxplots pour visualiser les valeurs aberrantes
    
    Args:
        df: DataFrame
        variables: Liste des variables à analyser
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        fig = go.Figure()
        
        for variable in variables:
            if variable in df.columns:
                data = df[variable].dropna()
                fig.add_trace(go.Box(
                    y=data,
                    name=variable,
                    boxmean='sd',  # Affiche moyenne et écart-type
                    marker_color='lightblue',
                    boxpoints='outliers'  # Affiche uniquement les outliers
                ))
        
        fig.update_layout(
            title='Analyse des Valeurs Aberrantes (Boxplot)',
            yaxis_title='Valeur',
            height=500,
            template='plotly_white',
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur boxplot outliers: {e}")
        return None


def create_correlation_heatmap_enhanced(df, variables):
    """
    Crée une matrice de corrélation enrichie avec annotations détaillées
    
    Args:
        df: DataFrame
        variables: Liste des variables numériques
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        corr_matrix = df[variables].corr()
        
        # Masquer le triangle supérieur pour plus de clarté
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        corr_masked = corr_matrix.copy()
        corr_masked[mask] = np.nan
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_masked.values,
            x=variables,
            y=variables,
            colorscale='RdBu',
            zmid=0,
            zmin=-1,
            zmax=1,
            text=corr_masked.round(3).values,
            texttemplate='%{text}',
            textfont={"size": 14, "color": "black"},
            colorbar=dict(title="Corrélation")
        ))
        
        fig.update_layout(
            title='Matrice de Corrélation (Triangle inférieur)',
            height=450,
            template='plotly_white',
            xaxis=dict(side='bottom'),
            yaxis=dict(autorange='reversed'),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur matrice corrélation enrichie: {e}")
        return None


def create_monthly_evolution_plot(df, time_col, value_col, stat_type='mean', title=None):
    """
    Crée un graphique d'évolution mensuelle avec mois sur l'axe X
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle (ex: 'Month')
        value_col: Variable à analyser (ex: 'Montant', 'PU Net')
        stat_type: Type de statistique - 'mean', 'median', 'sum'
        title: Titre personnalisé du graphique
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        # Déterminer la fonction d'agrégation
        agg_funcs = {
            'mean': 'mean',
            'median': 'median',
            'sum': 'sum'
        }
        agg_func = agg_funcs.get(stat_type, 'mean')
        
        # Agréger par période
        if stat_type == 'median':
            agg_data = df.groupby(time_col)[value_col].median().sort_index()
        elif stat_type == 'sum':
            agg_data = df.groupby(time_col)[value_col].sum().sort_index()
        else:
            agg_data = df.groupby(time_col)[value_col].mean().sort_index()
        
        # Titre par défaut
        if title is None:
            stat_labels = {
                'mean': 'Moyenne',
                'median': 'Médiane',
                'sum': 'Total'
            }
            title = f"{stat_labels.get(stat_type, 'Évolution')} de {value_col} par Période"
        
        # Créer le graphique
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=agg_data.index,
            y=agg_data.values,
            mode='lines+markers',
            name=value_col,
            line=dict(color='rgb(99, 110, 250)', width=3),
            marker=dict(size=8, color='rgb(99, 110, 250)')
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title='Période (Mois)',
            yaxis_title=f'{value_col} (€)' if 'Montant' in value_col or 'PU' in value_col else value_col,
            height=450,
            template='plotly_white',
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickmode='auto',
                tickfont=dict(size=11),
                showgrid=True,
                gridcolor='rgba(200,200,200,0.3)'
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                showgrid=True,
                gridcolor='rgba(200,200,200,0.3)'
            ),
            hovermode='x unified',
            font=dict()
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur évolution mensuelle {value_col}: {e}")
        return None


def create_distribution_by_month(df, time_col, value_col, title=None, granularity='month'):
    """
    Crée des violin plots élégants pour montrer la distribution par période
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle (ex: 'Month', 'Quarter', 'Fiscal_Year')
        value_col: Variable à analyser (ex: 'Montant', 'PU Net')
        title: Titre personnalisé du graphique
        granularity: 'month', 'quarter', ou 'year' pour adapter les labels
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        # Déterminer les labels selon la granularité
        granularity_labels = {
            'month': 'Mois',
            'quarter': 'Trimestre',
            'year': 'Année Fiscale'
        }
        period_label = granularity_labels.get(granularity, 'Mois')
        
        if title is None:
            title = f"Distribution de {value_col} par {period_label}"
        
        # Trier les données par période
        df_sorted = df.sort_values(time_col)
        
        # Créer un violin plot élégant
        fig = go.Figure()
        
        # Grouper par période et créer un violin plot pour chaque
        periods = sorted(df[time_col].unique())
        colors = px.colors.sequential.Blues_r  # Palette de bleus
        
        for i, period in enumerate(periods):
            period_data = df[df[time_col] == period][value_col].dropna()
            if len(period_data) > 0:
                color_idx = int((i / len(periods)) * (len(colors) - 1))
                fig.add_trace(go.Violin(
                    y=period_data,
                    x=[str(period)] * len(period_data),
                    name=str(period),
                    box_visible=True,
                    meanline_visible=True,
                    fillcolor=colors[color_idx],
                    opacity=0.7,
                    line_color='rgba(0, 217, 255, 0.8)',
                    showlegend=False
                ))
        
        fig.update_layout(
            title=title,
            xaxis_title=f'Période ({period_label})',
            yaxis_title=f'{value_col} (€)' if 'Montant' in value_col or 'PU' in value_col else value_col,
            height=500,
            template='plotly_white',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10),
                showgrid=False
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                showgrid=True,
                gridcolor='rgba(200,200,200,0.3)'
            ),
            font=dict(),
            violinmode='group'
        )
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur distribution par période {value_col}: {e}")
        return None


def create_boxplot_by_month(df, time_col, value_col, title=None):
    """
    Crée des boxplots par mois pour voir l'évolution de la distribution
    
    Args:
        df: DataFrame
        time_col: Colonne temporelle (ex: 'Month')
        value_col: Variable à analyser (ex: 'Montant', 'PU Net')
        title: Titre personnalisé du graphique
    
    Returns:
        HTML du graphique Plotly
    """
    try:
        if title is None:
            title = f"Distribution de {value_col} par Mois (Boxplot)"
        
        # Trier les périodes
        df_sorted = df.sort_values(time_col)
        
        fig = px.box(
            df_sorted,
            x=time_col,
            y=value_col,
            title=title,
            template='plotly_white',
            points='outliers'  # Afficher uniquement les outliers
        )
        
        fig.update_layout(
            height=450,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=11),
                title='Période (Mois)',
                title_font=dict()
            ),
            yaxis=dict(
                tickfont=dict(size=11),
                title=f'{value_col} (€)' if 'Montant' in value_col or 'PU' in value_col else value_col,
                title_font=dict()
            ),
            font=dict()
        )
        
        fig.update_traces(marker_color='rgb(99, 110, 250)')
        
        return _to_html_responsive(fig)
    except Exception as e:
        print(f"   ⚠️ Erreur boxplot par mois {value_col}: {e}")
        return None

