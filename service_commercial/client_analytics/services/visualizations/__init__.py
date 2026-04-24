"""
Sous-module VISUALIZATIONS

Contient toutes les fonctions de création de graphiques, organisées par onglet/sous-onglet.
Chaque fichier viz_*.py correspond à un onglet et contient les fonctions de visualisation.

Fichiers:
- viz_overview.py : Graphiques pour l'onglet Overview
- viz_by_period.py : Graphiques pour le sous-onglet Analyse par périodes
- viz_time_series.py : Graphiques pour le sous-onglet Série temporelle
- viz_products.py : Graphiques pour le sous-onglet Produits
- viz_clients.py : Graphiques pour le sous-onglet Clients
- viz_geographic.py : Graphiques pour le sous-onglet Géographique
- viz_clustering.py : Graphiques pour l'onglet Clustering
- viz_currency.py : Graphiques pour le sous-onglet Dépendance aux devises
"""

# Imports pour faciliter l'utilisation
from .viz_overview import *
from .viz_by_period import *
from .viz_time_series import *
from .viz_products import *
from .viz_clients import *
from .viz_geographic import *
from .viz_clustering import *
from .viz_currency import *

__all__ = [
    # viz_overview
    
    # viz_by_period
    
    # viz_time_series
    'create_stl_decomposition_plot',
    
    # viz_products
    
    # viz_clients
    
    # viz_geographic
    
    # viz_clustering
    'create_clustering_pca_plot',
    
    # viz_currency
    'plot_revenue_by_currency',
    'plot_monthly_stacked_area',
    'plot_non_eur_pct_over_time',
    'plot_country_currency_heatmap',
    'plot_pareto_non_eur_clients',
    'plot_non_eur_by_family',
]
