"""
Dataset loading and summarization.

This module covers:
- Loading a dataset from a user-uploaded file
- Producing a shortsummary of the dataset

"""

from typing import Any, Dict
import pandas as pd


def load_dataset(file) -> pd.DataFrame:
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    elif file.name.endswith(".xlsx") or file.name.endswith(".xls"):
        return pd.read_excel(file)
    else:
        raise ValueError("Unsupported file format. Please upload a CSV or Excel file.")


def summarize_dataset(df: pd.DataFrame) -> Dict[str, Any]:

    summary = {
        "num_rows": df.shape[0],
        "num_columns": df.shape[1],
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "num_missing": int(df[col].isnull().sum()),
                "mean": float(df[col].mean()) if str(df[col].dtype) in ["int64", "float64"] else None,
                "min": float(df[col].min()) if str(df[col].dtype) in ["int64", "float64"] else None,
                "max": float(df[col].max()) if str(df[col].dtype) in ["int64", "float64"] else None,
            }
            for col in df.columns
        ],
    }

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    #datetime_cols = df.select_dtypes(include=["datetime"]).columns.tolist()
    summary["numeric_columns"] = numeric_cols
    summary["categorical_columns"] = cat_cols
    #summary["datetime_columns"] = datetime_cols

    
    pass
