"""
Service de gestion des périodes temporelles.
Normalisation et création de colonnes temporelles pour l'analyse.
"""
import pandas as pd
from typing import Literal


def normalize_period(period: str) -> Literal['month', 'quarter', 'year']:
    """
    Normalise le paramètre de période.
    
    Args:
        period: Période fournie (month, quarter, year, etc.)
    
    Returns:
        Période normalisée ('month', 'quarter', 'year')
    """
    if not period:
        return 'month'
    
    period_lower = str(period).lower().strip()
    
    if period_lower in ['month', 'mois', 'm', 'mensuel', 'mensuelle']:
        return 'month'
    elif period_lower in ['quarter', 'trimestre', 'q', 't', 'trimestriel', 'trimestrielle']:
        return 'quarter'
    elif period_lower in ['year', 'annee', 'année', 'y', 'a', 'fiscal', 'fiscale', 'annuel', 'annuelle']:
        return 'year'
    else:
        return 'month'


def ensure_period_cols(df: pd.DataFrame, date_col_priority=("Date Fact.", "DATE_FACT.", "date_fact")) -> pd.DataFrame:
    """
    S'assure que le DataFrame contient les colonnes temporelles nécessaires.
    Utilise les colonnes existantes si présentes, sinon les crée.
    
    Args:
        df: DataFrame source
        date_col_priority: Tuple des noms possibles pour la colonne de date (ordre de priorité)
    
    Returns:
        DataFrame avec colonnes YEAR, MONTH, QUARTER ajoutées si nécessaire
    """
    df = df.copy()
    
    # Trouver la colonne de date
    date_col = None
    for col in date_col_priority:
        if col in df.columns:
            date_col = col
            break
    
    if not date_col:
        raise ValueError(f"Aucune colonne de date trouvée parmi {date_col_priority}")
    
    # Convertir en datetime si nécessaire
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    
    # Créer YEAR si absent
    if 'YEAR' not in df.columns:
        df['YEAR'] = df[date_col].dt.year
    
    # Créer MONTH si absent
    if 'MONTH' not in df.columns:
        df['MONTH'] = df[date_col].dt.month
    
    # Créer QUARTER si absent (trimestre fiscal : Oct-Déc = Q1)
    if 'QUARTER' not in df.columns:
        # Trimestre fiscal : Oct-Déc = Q1, Jan-Mar = Q2, Apr-Jun = Q3, Jul-Sep = Q4
        df['QUARTER'] = df[date_col].dt.month.map(
            {10: 1, 11: 1, 12: 1,  # Q1
             1: 2, 2: 2, 3: 2,      # Q2
             4: 3, 5: 3, 6: 3,      # Q3
             7: 4, 8: 4, 9: 4}      # Q4
        )
    
    return df


def make_period_label(df: pd.DataFrame, period: Literal['month', 'quarter', 'year']) -> pd.DataFrame:
    """
    Crée une colonne 'period_label' pour le tri et l'affichage.
    
    Args:
        df: DataFrame avec colonnes YEAR, MONTH, QUARTER
        period: Type de période ('month', 'quarter', 'year')
    
    Returns:
        DataFrame avec colonne 'period_label' ajoutée
    """
    df = df.copy()
    
    if period == 'month':
        # Format : "2024-01", "2024-02", etc.
        df['period_label'] = df['YEAR'].astype(str) + '-' + df['MONTH'].astype(str).str.zfill(2)
    elif period == 'quarter':
        # Format : "2024-Q1", "2024-Q2", etc.
        df['period_label'] = df['YEAR'].astype(str) + '-Q' + df['QUARTER'].astype(str)
    elif period == 'year':
        # Format : "2024", "2025", etc.
        df['period_label'] = df['YEAR'].astype(str)
    else:
        df['period_label'] = df['YEAR'].astype(str)
    
    return df


def get_period_group_cols(period: Literal['month', 'quarter', 'year']) -> list:
    """
    Retourne les colonnes à utiliser pour le groupby selon la période.
    
    Args:
        period: Type de période
    
    Returns:
        Liste des colonnes pour groupby
    """
    if period == 'month':
        return ['YEAR', 'MONTH']
    elif period == 'quarter':
        return ['YEAR', 'QUARTER']
    elif period == 'year':
        return ['YEAR']
    else:
        return ['YEAR', 'MONTH']
