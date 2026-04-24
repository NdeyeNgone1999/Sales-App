"""Dataset I/O helpers for uploaded Excel files."""

import os
from pathlib import Path

import pandas as pd


def _get_excel_engines(file_path):
    """Return the engines to try for a given Excel file path."""
    suffix = Path(file_path).suffix.lower()

    if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
        return ["openpyxl"]

    if suffix == ".xls":
        # Try legacy BIFF first, then openpyxl to support old datasets
        # that were saved back as modern Excel content with a .xls suffix.
        return ["xlrd", "openpyxl"]

    return ["openpyxl", "xlrd"]


def read_excel_file(file_path):
    """Read an Excel file with the most suitable engine for its format."""
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    errors = []
    for engine in _get_excel_engines(file_path):
        try:
            return pd.read_excel(file_path, engine=engine)
        except Exception as exc:
            errors.append(f"{engine}: {exc}")

    raise ValueError(
        f"Unable to read Excel file '{os.path.basename(file_path)}'. "
        f"Tried engines: {' | '.join(errors)}"
    )


def get_processed_output_name(file_name):
    """Persist processed datasets as .xlsx files."""
    return f"{Path(file_name).stem}.xlsx"


def load_dataset_df(dataset):
    """
    Load a pandas DataFrame from a Dataset model instance.

    Args:
        dataset: Dataset model instance

    Returns:
        pandas.DataFrame or None if error
    """
    file_path = dataset.get_file_path()

    if not file_path or not os.path.exists(file_path):
        return None

    try:
        return read_excel_file(file_path)
    except Exception:
        return None
