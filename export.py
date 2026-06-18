"""Export batch measurement rows to an Excel file. See PREPROCESSING.md section 8."""
from __future__ import annotations

import pandas as pd


def export_to_xlsx(rows: list[dict], out_path: str) -> None:
    df = pd.DataFrame(rows)
    df.to_excel(out_path, index=False, engine="openpyxl")
