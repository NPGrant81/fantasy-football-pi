"""
Utility functions and assertions for ETL pipeline testing and best practices.
"""
import pandas as pd

def assert_not_empty(df: pd.DataFrame, label: str = "DataFrame"):
    assert not df.empty, f"{label} is empty! Extraction or transformation failed."

def assert_columns_present(df: pd.DataFrame, columns, label: str = "DataFrame"):
    missing = [col for col in columns if col not in df.columns]
    assert not missing, f"{label} is missing columns: {missing}"

def assert_no_nulls(df: pd.DataFrame, columns, label: str = "DataFrame"):
    for col in columns:
        null_count = df[col].isnull().sum()
        assert null_count == 0, f"{label} column '{col}' has {null_count} nulls!"

def print_success(msg):
    print(f"\033[92m[SUCCESS]\033[0m {msg}")

def print_failure(msg):
    print(f"\033[91m[FAILURE]\033[0m {msg}")
