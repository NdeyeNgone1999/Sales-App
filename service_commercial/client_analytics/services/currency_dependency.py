"""Compat module: currency dependency analysis.

This project historically referenced `client_analytics.services.currency_dependency`.
The implementation lives in `analysis_currency_dependency.py`.

This shim keeps older imports (including tests/scripts) working.
"""

from .analysis_currency_dependency import (  # noqa: F401
    analyze_currency_dependency,
    normalize_currency,
    compute_kpi,
    clean_dataframe,
    create_month_column,
    fig_to_base64,
)

__all__ = [
    "analyze_currency_dependency",
    "normalize_currency",
    "compute_kpi",
    "clean_dataframe",
    "create_month_column",
    "fig_to_base64",
]
