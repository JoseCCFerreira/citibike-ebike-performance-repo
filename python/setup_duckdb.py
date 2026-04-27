from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SQLITE_DB_PATH = PROCESSED_DIR / "citibike_oltp.db"
DUCKDB_DB_PATH = PROCESSED_DIR / "citibike_analytics.duckdb"


def load_table(sqlite_connection: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table_name}", sqlite_connection)


def main() -> None:
    if not SQLITE_DB_PATH.exists():
        raise FileNotFoundError("SQLite OLTP database missing. Run python/setup_sqlite.py first.")

    with sqlite3.connect(SQLITE_DB_PATH) as sqlite_connection:
        trips = load_table(sqlite_connection, "trips")
        stations = load_table(sqlite_connection, "stations")
        station_status = load_table(sqlite_connection, "station_status_snapshots")
        vehicle_types = load_table(sqlite_connection, "vehicle_types")

    connection = duckdb.connect(str(DUCKDB_DB_PATH))
    connection.register("trips_df", trips)
    connection.register("stations_df", stations)
    connection.register("station_status_df", station_status)
    connection.register("vehicle_types_df", vehicle_types)

    connection.execute("CREATE OR REPLACE TABLE trips AS SELECT * FROM trips_df")
    connection.execute("CREATE OR REPLACE TABLE stations AS SELECT * FROM stations_df")
    connection.execute("CREATE OR REPLACE TABLE station_status_snapshots AS SELECT * FROM station_status_df")
    connection.execute("CREATE OR REPLACE TABLE vehicle_types AS SELECT * FROM vehicle_types_df")

    connection.execute(
        """
        CREATE OR REPLACE TABLE fct_trips AS
        SELECT
            ride_id,
            rideable_type,
            CAST(started_at AS TIMESTAMP) AS started_at,
            CAST(ended_at AS TIMESTAMP) AS ended_at,
            DATE_DIFF('minute', CAST(started_at AS TIMESTAMP), CAST(ended_at AS TIMESTAMP)) AS trip_minutes,
            start_station_id,
            end_station_id,
            member_casual,
            EXTRACT('hour' FROM CAST(started_at AS TIMESTAMP)) AS start_hour,
            EXTRACT('dow' FROM CAST(started_at AS TIMESTAMP)) AS start_day_of_week
        FROM trips
        """
    )

    connection.execute(
        """
        CREATE OR REPLACE TABLE dim_stations AS
        SELECT
            station_id,
            name,
            short_name,
            lat,
            lon,
            capacity,
            region_id,
            electric_bike_surcharge_waiver
        FROM stations
        """
    )

    connection.execute(
        """
        CREATE OR REPLACE TABLE fct_station_status AS
        SELECT
            s.snapshot_ts,
            s.station_id,
            s.num_bikes_available,
            s.num_ebikes_available,
            s.num_docks_available,
            s.is_installed,
            s.is_renting,
            s.is_returning,
            s.last_reported,
            CASE
                WHEN st.capacity IS NULL OR st.capacity = 0 THEN NULL
                ELSE ROUND(s.num_bikes_available * 1.0 / st.capacity, 4)
            END AS utilization_ratio
        FROM station_status_snapshots s
        LEFT JOIN stations st
            ON st.station_id = s.station_id
        """
    )

    connection.close()
    print(f"DuckDB OLAP database created: {DUCKDB_DB_PATH}")


if __name__ == "__main__":
    main()
