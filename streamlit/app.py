from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "processed" / "citibike_analytics.duckdb"


@st.cache_data
def load_kpis() -> dict[str, float]:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_trips,
            ROUND(AVG(trip_minutes), 2) AS avg_trip_minutes,
            ROUND(AVG(CASE WHEN rideable_type = 'electric_bike' THEN 1 ELSE 0 END) * 100, 2) AS ebike_share_pct
        FROM fct_trips
        """
    ).fetchone()
    conn.close()
    return {"total_trips": row[0], "avg_trip_minutes": row[1], "ebike_share_pct": row[2]}


@st.cache_data
def load_ebike_share_by_hour() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df = conn.execute(
        """
        SELECT
            start_hour,
            COUNT(*) AS trips,
            ROUND(AVG(CASE WHEN rideable_type = 'electric_bike' THEN 1 ELSE 0 END) * 100, 2) AS ebike_share_pct
        FROM fct_trips
        GROUP BY 1
        ORDER BY 1
        """
    ).df()
    conn.close()
    return df


@st.cache_data
def load_top_stations() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df = conn.execute(
        """
        SELECT
            s.name AS station_name,
            COUNT(*) AS trip_count,
            ROUND(AVG(f.trip_minutes), 2) AS avg_trip_minutes
        FROM fct_trips f
        LEFT JOIN dim_stations s
            ON s.station_id = f.start_station_id
        GROUP BY 1
        ORDER BY trip_count DESC
        LIMIT 15
        """
    ).df()
    conn.close()
    return df


def main() -> None:
    st.set_page_config(page_title="Citi Bike E-Bike Performance", layout="wide")
    st.title("Citi Bike E-Bike Performance Dashboard")

    if not DB_PATH.exists():
        st.warning("DuckDB não encontrado. Executa: python python/run_pipeline.py --months 3")
        return

    kpis = load_kpis()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trips", f"{kpis['total_trips']:,}")
    col2.metric("Avg Trip Minutes", f"{kpis['avg_trip_minutes']}")
    col3.metric("E-Bike Share", f"{kpis['ebike_share_pct']}%")

    hourly = load_ebike_share_by_hour()
    fig_hour = px.line(hourly, x="start_hour", y="ebike_share_pct", markers=True, title="E-Bike Share by Start Hour")
    st.plotly_chart(fig_hour, use_container_width=True)

    top_stations = load_top_stations()
    fig_stations = px.bar(top_stations, x="station_name", y="trip_count", title="Top Start Stations by Trips")
    st.plotly_chart(fig_stations, use_container_width=True)
    st.dataframe(top_stations, use_container_width=True)


if __name__ == "__main__":
    main()
