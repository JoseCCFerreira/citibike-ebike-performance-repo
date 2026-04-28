from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"


def run(script_path: Path, extra_args: list[str] | None = None) -> None:
    command = [sys.executable, str(script_path)]
    if extra_args:
        command.extend(extra_args)
    print(f"Running {script_path.name}...")
    subprocess.run(command, check=True)


def cleanup_raw_files() -> None:
    for child in ("tripdata_zip", "tripdata_csv", "gbfs"):
        path = RAW_DIR / child
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
    print("Cleaned raw Citi Bike files after database load.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Citi Bike pipeline end-to-end.")
    parser.add_argument("--months", type=int, default=3, help="Number of latest official months to download.")
    parser.add_argument("--years", type=int, default=None, help="Number of latest years to download. Example: --years 2.")
    parser.add_argument(
        "--sample-rows-per-file",
        type=int,
        default=None,
        help="Optional limit of rows to ingest from each raw trip CSV file for faster validation.",
    )
    parser.add_argument(
        "--cleanup-raw-files",
        action="store_true",
        help="Delete raw ZIP, CSV, and GBFS files after SQLite and DuckDB are created.",
    )
    args = parser.parse_args()

    download_args = ["--years", str(args.years)] if args.years is not None else ["--months", str(args.months)]
    if args.sample_rows_per_file is not None:
        download_args.extend(["--sample-rows-per-file", str(args.sample_rows_per_file)])
    run(ROOT_DIR / "python" / "download_citibike_data.py", download_args)
    sqlite_args: list[str] = []
    if args.sample_rows_per_file is not None:
        sqlite_args = ["--sample-rows-per-file", str(args.sample_rows_per_file)]
    run(ROOT_DIR / "python" / "setup_sqlite.py", sqlite_args)
    run(ROOT_DIR / "python" / "setup_duckdb.py")
    if args.cleanup_raw_files:
        cleanup_raw_files()
    print("Citi Bike pipeline completed successfully.")


if __name__ == "__main__":
    main()
