from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def run(script_path: Path, extra_args: list[str] | None = None) -> None:
    command = [sys.executable, str(script_path)]
    if extra_args:
        command.extend(extra_args)
    print(f"Running {script_path.name}...")
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Citi Bike pipeline end-to-end.")
    parser.add_argument("--months", type=int, default=3, help="Number of latest official months to download.")
    parser.add_argument(
        "--sample-rows-per-file",
        type=int,
        default=None,
        help="Optional limit of rows to ingest from each raw trip CSV file for faster validation.",
    )
    args = parser.parse_args()

    run(ROOT_DIR / "python" / "download_citibike_data.py", ["--months", str(args.months)])
    sqlite_args: list[str] = []
    if args.sample_rows_per_file is not None:
        sqlite_args = ["--sample-rows-per-file", str(args.sample_rows_per_file)]
    run(ROOT_DIR / "python" / "setup_sqlite.py", sqlite_args)
    run(ROOT_DIR / "python" / "setup_duckdb.py")
    print("Citi Bike pipeline completed successfully.")


if __name__ == "__main__":
    main()
