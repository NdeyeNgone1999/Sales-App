# Services Package
"""
Services organisés par onglet/sous-onglet de l'application Analytics Portal

Structure:
- analysis_overview.py : Onglet Overview (profiling de base)
- analysis_clustering.py : Onglet Clustering (K-Means, RFM)
- analysis_by_period.py : Sous-onglet Analyse par périodes
- analysis_time_series.py : Sous-onglet Analyse Série temporelle
- analysis_products.py : Sous-onglet Analyse produits
- analysis_clients.py : Sous-onglet Analyse clients
- analysis_geographic.py : Sous-onglet Analyse géographique
- analysis_currency_dependency.py : Sous-onglet Dépendance aux devises

Modules utilitaires:
- data_processing.py : Traitement et nettoyage des données
- dataset_io.py : Chargement/sauvegarde datasets
- visualizations/ : Dossier contenant les sous-modules de visualisation
"""

# Import des modules principaux pour faciliter l'utilisation
from . import (
    analysis_overview,
    analysis_clustering,
    analysis_by_period,
    analysis_time_series,
    analysis_products,
    analysis_clients,
    analysis_anomalies,
    analysis_geographic,
    analysis_currency_dependency,
    data_processing,
    dataset_io,
)

__all__ = [
    'analysis_overview',
    'analysis_clustering',
    'analysis_by_period',
    'analysis_time_series',
    'analysis_products',
    'analysis_clients',
    'analysis_anomalies',
    'analysis_geographic',
    'analysis_currency_dependency',
    'data_processing',
    'dataset_io',
]

