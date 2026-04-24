# 📊 MODULE VISUALIZATIONS

## Structure

Ce dossier contient toutes les fonctions de création de graphiques, organisées par onglet/sous-onglet de l'application.

```
visualizations/
├── __init__.py                 # Exports centralisés
├── viz_overview.py            # Graphiques pour Overview
├── viz_by_period.py           # Graphiques pour Analyse par périodes
├── viz_time_series.py         # Graphiques pour Série temporelle
├── viz_products.py            # Graphiques pour Produits
├── viz_clients.py             # Graphiques pour Clients
├── viz_geographic.py          # Graphiques pour Géographique
├── viz_clustering.py          # Graphiques pour Clustering
└── viz_currency.py            # Graphiques pour Dépendance aux devises
```

---

## 📋 Fichiers et Fonctions

### `viz_overview.py`
Visualisations pour l'onglet **Overview**
- Pas de graphiques complexes pour l'instant
- Préparé pour futures visualisations

### `viz_by_period.py`
Visualisations pour **Analyse par périodes**
- Affichage principalement sous forme de tableaux
- Pas de graphiques complexes pour l'instant

### `viz_time_series.py`
Visualisations pour **Analyse de séries temporelles**
- `create_stl_decomposition_plot(df_agg)` - Décomposition STL (Tendance, Saisonnalité, Résidus)

### `viz_products.py`
Visualisations pour **Analyse produits**
- Préparé pour migration future depuis visualizations.py

### `viz_clients.py`
Visualisations pour **Analyse clients**
- Pas de graphiques pour l'instant
- Analyse retourne principalement des DataFrames

### `viz_geographic.py`
Visualisations pour **Analyse géographique**
- Préparé pour migration future depuis visualizations.py

### `viz_clustering.py`
Visualisations pour **Clustering**
- `create_clustering_pca_plot(df_client, X, title)` - Scatter plot 2D avec réduction PCA
- `create_cluster_stats_table(cluster_stats)` - Tableau HTML des statistiques par cluster

### `viz_currency.py`
Visualisations pour **Dépendance aux devises**
- `plot_revenue_by_currency(df, output_path)` - Bar chart CA par devise
- `plot_monthly_stacked_area(df, output_path)` - Aire empilée mensuelle
- `plot_non_eur_pct_over_time(df, output_path)` - Évolution % non-EUR
- `plot_country_currency_heatmap(df, output_path)` - Heatmap pays × devises
- `plot_pareto_non_eur_clients(df, output_path, top_n)` - Pareto top clients non-EUR
- `plot_non_eur_by_family(df, output_path)` - Scatter/Bubble famille produit

---

## 🔧 Utilisation

### Import depuis un fichier analysis_*

```python
# Dans analysis_time_series.py
from .visualizations.viz_time_series import create_stl_decomposition_plot

# Utilisation
stl_plot = create_stl_decomposition_plot(df_agg)
if stl_plot:
    graphs['stl_decomposition'] = stl_plot
```

### Import depuis currency_dependency.py

```python
from .visualizations.viz_currency import (
    plot_revenue_by_currency,
    plot_monthly_stacked_area,
    plot_non_eur_pct_over_time,
    plot_country_currency_heatmap,
    plot_pareto_non_eur_clients,
    plot_non_eur_by_family
)

# Utilisation
fig = plot_revenue_by_currency(df_clean, output_path=None)
if fig:
    charts["revenue_by_currency"] = fig_to_base64(fig)
```

---

## 📦 Types de Retour

### Plotly (HTML)
Fonctions retournant du HTML Plotly pour intégration directe dans templates Django :
- `create_stl_decomposition_plot()` → `str` (HTML)
- `create_clustering_pca_plot()` → `str` (HTML)

### Matplotlib (Figure ou None)
Fonctions retournant des figures matplotlib (ou None si erreur) :
- Toutes les fonctions `plot_*` de `viz_currency.py`
- Si `output_path` fourni : sauvegarde le fichier et retourne `None`
- Si `output_path=None` : retourne la `Figure` matplotlib

---

## ✨ Avantages de cette Structure

### 1. **Séparation des Responsabilités**
- **Fichiers `analysis_*.py`** : Logique métier et calculs
- **Fichiers `viz_*.py`** : Visualisation pure

### 2. **Réutilisabilité**
- Les fonctions de visualisation peuvent être utilisées dans plusieurs analyses
- Pas de duplication de code

### 3. **Maintenance Facilitée**
- Modifications graphiques centralisées
- Un fichier = un type de graphiques
- Facile à tester individuellement

### 4. **Clarté**
- Structure mirror des onglets de l'application
- Facile de trouver où est défini un graphique

---

## 🎨 Standards de Code

### Conventions de Nommage
- **Plotly** : `create_*_plot()` - retourne HTML
- **Matplotlib** : `plot_*()` - retourne Figure ou None

### Paramètres Standard
```python
def plot_example(df: pd.DataFrame, output_path: Optional[Path] = None) -> Optional[plt.Figure]:
    """
    Description du graphique
    
    Args:
        df: DataFrame avec les données
        output_path: Chemin de sauvegarde (optionnel)
        
    Returns:
        Figure matplotlib ou None
    """
```

### Style Matplotlib
- Utiliser `plt.style.use('seaborn-v0_8-darkgrid')`
- Palette de couleurs cohérente (définie dans COLORS)
- Annotations claires et lisibles
- Grilles alpha=0.3 pour meilleure lisibilité

### Style Plotly
- Templates cohérents
- Légendes positionnées de manière uniforme
- Hover data pertinents
- Couleurs harmonieuses

---

## 🔄 Migrations Futures

Certains fichiers sont marqués "Préparé pour migration future" :
- `viz_products.py` : Migrer depuis `visualizations.generate_family_visualizations()`
- `viz_geographic.py` : Migrer depuis `visualizations.generate_geographic_visualizations()`

Ces migrations nécessitent de copier les fonctions complexes depuis l'ancien fichier `visualizations.py` (racine services).

---

**Date de création :** Janvier 2026  
**Statut :** ✅ Structure opérationnelle
