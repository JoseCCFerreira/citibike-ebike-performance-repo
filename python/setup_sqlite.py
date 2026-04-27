from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SQL_DIR = ROOT_DIR / "sql" / "sqlite"
DB_PATH = PROCESSED_DIR / "citibike_oltp.db"


def latest_gbfs_file(feed_name: str) -> Path:
    files = sorted((RAW_DIR / "gbfs").glob(f"*_{feed_name}.json"))
    if not files:
        raise FileNotFoundError(f"Missing GBFS file for {feed_name}. Run download_citibike_data.py first.")
    return files[-1]


def read_trip_csv(csv_file: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(csv_file, encoding=encoding, low_memory=False)
            return normalize_trip_columns(df)
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise RuntimeError(f"Could not read {csv_file}") from last_error


def trip_csv_chunks(csv_file: Path, chunksize: int = 100_000, sample_rows: int | None = None):
    ordered_columns = [
        "ride_id",
        "rideable_type",
        "started_at",
        "ended_at",
        "start_station_name",
        "start_station_id",
        "end_station_name",
        "end_station_id",
        "start_lat",
        "start_lng",
        "end_lat",
        "end_lng",
        "member_casual",
    ]
    last_error: Exception | None = None
    rows_emitted = 0
    for encoding in ("utf-8", "latin-1"):
        try:
            reader = pd.read_csv(csv_file, encoding=encoding, low_memory=False, chunksize=chunksize)
            for chunk in reader:
                normalized = normalize_trip_columns(chunk)
                if sample_rows is not None:
                    remaining = sample_rows - rows_emitted
                    if remaining <= 0:
                        return
                    normalized = normalized.head(remaining)
                for column in ordered_columns:
                    if column in {"ride_id", "rideable_type", "started_at", "ended_at", "start_station_name", "start_station_id", "end_station_name", "end_station_id", "member_casual"}:
                        normalized[column] = normalized[column].astype(str)
                rows_emitted += len(normalized)
                yield normalized
            return
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise RuntimeError(f"Could not stream {csv_file}") from last_error


def normalize_trip_columns(df: pd.DataFrame) -> pd.DataFrame:
    ordered_columns = [
        "ride_id",
        "rideable_type",
        "started_at",
        "ended_at",
        "start_station_name",
        "start_station_id",
        "end_station_name",
        "end_station_id",
        "start_lat",
        "start_lng",
        "end_lat",
        "end_lng",
        "member_casual",
    ]
    current_columns = set(ordered_columns)
    if current_columns.issubset(df.columns):
        return df[ordered_columns]

    legacy_map = {
        "tripduration": "tripduration",
        "starttime": "started_at",
        "stoptime": "ended_at",
        "start station name": "start_station_name",
        "start station id": "start_station_id",
        "end station name": "end_station_name",
        "end station id": "end_station_id",
        "start station latitude": "start_lat",
        "start station longitude": "start_lng",
        "end station latitude": "end_lat",
        "end station longitude": "end_lng",
        "usertype": "member_casual",
        "bikeid": "ride_id",
    }
    lower_map = {col.lower(): col for col in df.columns}
    if "starttime" in lower_map:
        renamed = {}
        for legacy_lower, new_name in legacy_map.items():
            if legacy_lower in lower_map:
                renamed[lower_map[legacy_lower]] = new_name
        df = df.rename(columns=renamed)
        if "rideable_type" not in df.columns:
            df["rideable_type"] = "classic_bike"
        if "member_casual" in df.columns:
            df["member_casual"] = df["member_casual"].replace(
                {"Subscriber": "member", "Customer": "casual"}
            )
        if "ride_id" not in df.columns:
            df["ride_id"] = df.index.astype(str)
        return df[
            [
                "ride_id",
                "rideable_type",
                "started_at",
                "ended_at",
                "start_station_name",
                "start_station_id",
                "end_station_name",
                "end_station_id",
                "start_lat",
                "start_lng",
                "end_lat",
                "end_lng",
                "member_casual",
            ]
        ]

    missing = current_columns.difference(df.columns)
    raise ValueError(f"Unexpected trip data schema. Missing columns: {sorted(missing)}")


def load_trips() -> pd.DataFrame:
    csv_files = sorted(
        path for path in (RAW_DIR / "tripdata_csv").glob("*.csv") if not path.name.startswith("._")
    )
    if not csv_files:
        raise FileNotFoundError("No trip CSV files found. Run download_citibike_data.py first.")
    frames = [read_trip_csv(csv_file) for csv_file in csv_files]
    dataframe = pd.concat(frames, ignore_index=True)
    dataframe = dataframe.drop_duplicates(subset=["ride_id"])
    return dataframe


def insert_trips(connection: sqlite3.Connection, sample_rows_per_file: int | None = None) -> int:
    csv_files = sorted(
        path for path in (RAW_DIR / "tripdata_csv").glob("*.csv") if not path.name.startswith("._")
    )
    if not csv_files:
        raise FileNotFoundError("No trip CSV files found. Run download_citibike_data.py first.")

    insert_sql = """
        INSERT OR REPLACE INTO trips (
            ride_id,
            rideable_type,
            started_at,
            ended_at,
            start_station_name,
            start_station_id,
            end_station_name,
            end_station_id,
            start_lat,
            start_lng,
            end_lat,
            end_lng,
            member_casual
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted_rows = 0
    for csv_file in csv_files:
        for chunk in trip_csv_chunks(csv_file, sample_rows=sample_rows_per_file):
            rows = [
                tuple(record)
                for record in chunk[
                    [
                        "ride_id",
                        "rideable_type",
                        "started_at",
                        "ended_at",
                        "start_station_name",
                        "start_station_id",
                        "end_station_name",
                        "end_station_id",
                        "start_lat",
                        "start_lng",
                        "end_lat",
                        "end_lng",
                        "member_casual",
                    ]
                ].itertuples(index=False, name=None)
            ]
            connection.executemany(insert_sql, rows)
            connection.commit()
            inserted_rows += len(rows)
    return inserted_rows


def load_station_information() -> pd.DataFrame:
    payload = json.loads(latest_gbfs_file("station_information").read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["data"]["stations"])
    if "electric_bike_surcharge_waiver" not in df.columns:
        df["electric_bike_surcharge_waiver"] = None
    return df[
        [
            "station_id",
            "name",
            "short_name",
            "lat",
            "lon",
            "capacity",
            "region_id",
            "electric_bike_surcharge_waiver",
        ]
    ]


def load_station_status() -> pd.DataFrame:
    gbfs_file = latest_gbfs_file("station_status")
    snapshot_ts = gbfs_file.name.split("_station_status.json")[0]
    payload = json.loads(gbfs_file.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["data"]["stations"])
    if "num_ebikes_available" not in df.columns:
        df["num_ebikes_available"] = None
    df["snapshot_ts"] = snapshot_ts
    return df[
        [
            "snapshot_ts",
            "station_id",
            "num_bikes_available",
            "num_ebikes_available",
            "num_docks_available",
            "is_installed",
            "is_renting",
            "is_returning",
            "last_reported",
        ]
    ]


def load_vehicle_types() -> pd.DataFrame:
    payload = json.loads(latest_gbfs_file("vehicle_types").read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["data"]["vehicle_types"])
    if "max_range_meters" not in df.columns:
        df["max_range_meters"] = None
    return df[["vehicle_type_id", "form_factor", "propulsion_type", "max_range_meters"]]


def load_system_information() -> pd.DataFrame:
    payload = json.loads(latest_gbfs_file("system_information").read_text(encoding="utf-8"))
    data = payload["data"]
    return pd.DataFrame(
        [
            {
                "system_id": data.get("system_id", "citi_bike"),
                "language": data.get("language"),
                "name": data.get("name"),
                "operator": data.get("operator"),
                "timezone": data.get("timezone"),
            }
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Citi Bike raw data into SQLite OLTP.")
    parser.add_argument(
        "--sample-rows-per-file",
        type=int,
        default=None,
        help="Optional limit of rows to ingest from each raw trip CSV file.",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = (SQL_DIR / "01_create_tables.sql").read_text(encoding="utf-8")

    stations = load_station_information()
    station_status = load_station_status()
    vehicle_types = load_vehicle_types()
    system_information = load_system_information()

    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript(schema_sql)
        inserted_rows = insert_trips(connection, sample_rows_per_file=args.sample_rows_per_file)
        stations.to_sql("stations", connection, if_exists="append", index=False)
        station_status.to_sql("station_status_snapshots", connection, if_exists="append", index=False)
        vehicle_types.to_sql("vehicle_types", connection, if_exists="append", index=False)
        system_information.to_sql("system_information", connection, if_exists="append", index=False)
        connection.commit()

    print(f"SQLite OLTP database created: {DB_PATH}")
    print(f"Inserted trip rows: {inserted_rows}")


if __name__ == "__main__":
    main()
