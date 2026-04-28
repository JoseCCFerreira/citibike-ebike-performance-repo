from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "processed" / "citibike_analytics.duckdb"
ML_OUTPUT_DIR = ROOT_DIR / "data" / "ml_outputs"


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


@st.cache_data
def load_station_risk() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df = conn.execute(
        """
        WITH latest_snapshot AS (
            SELECT MAX(snapshot_ts) AS snapshot_ts
            FROM fct_station_status
        )
        SELECT
            s.name AS station_name,
            st.num_bikes_available,
            st.num_ebikes_available,
            st.num_docks_available,
            st.utilization_ratio
        FROM fct_station_status st
        LEFT JOIN dim_stations s
            ON s.station_id = st.station_id
        INNER JOIN latest_snapshot ls
            ON ls.snapshot_ts = st.snapshot_ts
        ORDER BY st.utilization_ratio DESC NULLS LAST
        LIMIT 20
        """
    ).df()
    conn.close()
    return df


def build_citibike_metric_frame(metrics: dict) -> pd.DataFrame:
    rows = []
    classification = metrics.get("classification_ebike_usage", {})
    if "accuracy" in classification:
        rows.append({"model": "Random Forest", "Accuracy": classification.get("accuracy")})
    else:
        for model_name, values in classification.items():
            rows.append(
                {
                    "model": model_name,
                    "Accuracy": values.get("Accuracy"),
                    "Precision": values.get("Precision"),
                    "Recall": values.get("Recall"),
                    "F1": values.get("F1"),
                    "ROC_AUC": values.get("ROC_AUC"),
                }
            )
    return pd.DataFrame(rows)


@st.cache_data
def load_ml_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    importance_path = ML_OUTPUT_DIR / "ebike_feature_importance.csv"
    clusters_path = ML_OUTPUT_DIR / "trip_profile_clusters.csv"
    metrics_path = ML_OUTPUT_DIR / "citibike_ml_metrics.json"
    importance_df = pd.read_csv(importance_path) if importance_path.exists() else pd.DataFrame()
    clusters_df = pd.read_csv(clusters_path) if clusters_path.exists() else pd.DataFrame()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    metrics_df = build_citibike_metric_frame(metrics)
    return importance_df, clusters_df, metrics_df


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

    station_risk = load_station_risk()
    fig_risk = px.bar(
        station_risk,
        x="station_name",
        y="utilization_ratio",
        color="num_ebikes_available",
        title="Station Utilization Risk in Latest GBFS Snapshot",
    )
    st.plotly_chart(fig_risk, use_container_width=True)

    importance, clusters, model_metrics = load_ml_outputs()
    if not importance.empty or not clusters.empty or not model_metrics.empty:
        st.subheader("Machine Learning: entender, aplicar e analisar")
    if not model_metrics.empty:
        metric_column = "F1" if "F1" in model_metrics.columns and model_metrics["F1"].notna().any() else "Accuracy"
        fig_models = px.bar(
            model_metrics.sort_values(metric_column, ascending=False),
            x="model",
            y=metric_column,
            title=f"Comparação de Modelos de E-Bike por {metric_column}",
        )
        st.plotly_chart(fig_models, use_container_width=True)
        st.dataframe(model_metrics, use_container_width=True)
    if not importance.empty:
        fig_importance = px.bar(
            importance,
            x="importance",
            y="feature",
            orientation="h",
            title="Feature Importance for E-Bike Usage",
        )
        st.plotly_chart(fig_importance, use_container_width=True)
    if not clusters.empty:
        fig_clusters = px.scatter(
            clusters,
            x="start_hour",
            y="trip_minutes",
            size="is_ebike",
            color=clusters["trip_profile_cluster"].astype(str),
            title="Trip Profile Clusters",
            labels={"color": "trip_profile_cluster"},
        )
        st.plotly_chart(fig_clusters, use_container_width=True)
        st.dataframe(clusters, use_container_width=True)


if __name__ == "__main__":
    main()
