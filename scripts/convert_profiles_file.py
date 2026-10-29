from pathlib import Path

import polars as pl

ROOT_FOLDER = Path(__file__).parent.parent
SOURCE_FILE = ROOT_FOLDER / "sandbox" / "20261017 timeseries_TL.xlsx"
TARGET_FILE = ROOT_FOLDER / "data" / "20261017 timeseries_TL.parquet"

# Write a compressed, row-grouped Parquet file
pl.read_excel(
    SOURCE_FILE,
    engine="calamine",  # fastest Excel engine
).sort(by="report_id").lazy().sink_parquet(
    TARGET_FILE,
    compression="zstd",
    row_group_size=100_000,  # smaller row groups → finer-grained row pruning
    statistics=True,  # keep min/max stats so filters can skip row groups
)
