from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb


ROOT_DIR = Path(__file__).resolve().parent.parent
DUCKDB_DB_PATH = ROOT_DIR / "data" / "processed" / "citibike_analytics.duckdb"
ML_OUTPUT_DIR = ROOT_DIR / "data" / "ml_outputs"


def run_command(command: list[str]) -> None:
    print(f">> Running: {' '.join(command)}")
    subprocess.run(command, cwd=str(ROOT_DIR), check=True)


def main() -> None:
    run_command([sys.executable, "python/run_pipeline.py", "--months", "1", "--sample-rows-per-file", "20000"])

    if not DUCKDB_DB_PATH.exists():
        raise FileNotFoundError(f"Missing {DUCKDB_DB_PATH}")

    conn = duckdb.connect(str(DUCKDB_DB_PATH), read_only=True)
    trip_count = conn.execute("SELECT COUNT(*) FROM fct_trips").fetchone()[0]
    conn.close()
    if trip_count <= 0:
        raise ValueError("fct_trips has no rows.")

    run_command([sys.executable, "python/ml_citibike.py"])
    run_command([sys.executable, "-m", "py_compile", "streamlit/app.py"])

    expected = {
        "citibike_ml_metrics.json",
        "trip_profile_clusters.csv",
        "ebike_feature_importance.csv",
    }
    missing = [name for name in expected if not (ML_OUTPUT_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing ML outputs: {missing}")

    print("SUCCESS: Citi Bike case validation completed.")


if __name__ == "__main__":
    main()
