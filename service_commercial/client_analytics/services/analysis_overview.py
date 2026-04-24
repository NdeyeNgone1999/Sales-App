"""
Service pour l'onglet OVERVIEW
Génère les informations de profiling de base du dataset
"""
import pandas as pd
import numpy as np


def get_dataset_info(df):
    """
    Informations de base sur le dataset
    
    Args:
        df: pandas.DataFrame
        
    Returns:
        dict avec les infos du dataset
    """
    info = {
        'shape': df.shape,
        'num_rows': df.shape[0],
        'num_cols': df.shape[1],
        'columns': list(df.columns),
        'dtypes': df.dtypes.astype(str).to_dict(),
        'memory_usage': df.memory_usage(deep=True).sum(),
    }
    return info


def get_missing_values(df):
    """
    Informations sur les valeurs manquantes
    
    Args:
        df: pandas.DataFrame
        
    Returns:
        list de dict avec les valeurs manquantes par colonne
    """
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    
    missing_info = []
    for col in df.columns:
        if missing[col] > 0:
            missing_info.append({
                'column': col,
                'count': int(missing[col]),
                'percentage': float(missing_pct[col])
            })
    
    return missing_info


def get_numeric_summary(df):
    """
    Statistiques descriptives pour les colonnes numériques
    
    Args:
        df: pandas.DataFrame
        
    Returns:
        pandas.DataFrame avec describe()
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) == 0:
        return None
    
    return df[numeric_cols].describe()


def get_categorical_summary(df, max_categories=20):
    """
    Résumé pour les colonnes catégorielles
    
    Args:
        df: pandas.DataFrame
        max_categories: nombre max de valeurs uniques
        
    Returns:
        list de dict avec les infos catégorielles
    """
    categorical_info = []
    
    for col in df.columns:
        if df[col].dtype == 'object' or df[col].nunique() < max_categories:
            unique_count = df[col].nunique()
            categorical_info.append({
                'column': col,
                'unique_count': int(unique_count),
                'most_common': df[col].value_counts().head(5).to_dict()
            })
    
    return categorical_info


def get_column_types(df):
    """
    Classifie les colonnes en numériques et catégorielles
    
    Args:
        df: pandas.DataFrame
        
    Returns:
        dict avec les types de colonnes
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    return {
        'numeric': numeric_cols,
        'categorical': categorical_cols,
        'datetime': datetime_cols
    }


def generate_overview_analysis(df):
    """
    Génère une analyse complète pour l'onglet Overview
    
    Args:
        df: pandas.DataFrame
        
    Returns:
        dict avec toutes les analyses pour l'onglet Overview
    """
    
    return {
        'info': get_dataset_info(df),
        'missing_info': get_missing_values(df),
        'numeric_summary': get_numeric_summary(df),
        'categorical_summary': get_categorical_summary(df),
        'column_types': get_column_types(df)
    }
