from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "processed" / "citibike_analytics.duckdb"
OUTPUT_DIR = ROOT_DIR / "data" / "ml_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trip_features() -> pd.DataFrame:
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    df = conn.execute(
        """
        SELECT
            ride_id,
            rideable_type,
            trip_minutes,
            start_hour,
            start_day_of_week,
            member_casual,
            start_station_id,
            end_station_id
        FROM fct_trips
        WHERE trip_minutes IS NOT NULL
          AND trip_minutes > 0
        """
    ).df()
    conn.close()
    return df


def classify_ebike_usage(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    work_df = df.copy()
    start_station_encoder = LabelEncoder()
    end_station_encoder = LabelEncoder()
    work_df["start_station_encoded"] = start_station_encoder.fit_transform(work_df["start_station_id"].astype(str))
    work_df["end_station_encoded"] = end_station_encoder.fit_transform(work_df["end_station_id"].astype(str))
    work_df["member_encoded"] = (work_df["member_casual"] == "member").astype(int)
    work_df["target"] = (work_df["rideable_type"] == "electric_bike").astype(int)

    features = [
        "trip_minutes",
        "start_hour",
        "start_day_of_week",
        "member_encoded",
        "start_station_encoded",
        "end_station_encoded",
    ]

    X_train, X_test, y_train, y_test = train_test_split(
        work_df[features],
        work_df["target"],
        test_size=0.2,
        random_state=42,
        stratify=work_df["target"],
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=120, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=120, random_state=42),
    }

    results: dict[str, dict[str, float]] = {}
    fitted_random_forest: RandomForestClassifier | None = None
    for name, model in models.items():
        use_scaled = name == "Logistic Regression"
        Xtr = X_train_scaled if use_scaled else X_train
        Xte = X_test_scaled if use_scaled else X_test
        model.fit(Xtr, y_train)
        preds = model.predict(Xte)
        probabilities = model.predict_proba(Xte)[:, 1]

        results[name] = {
            "Accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "Precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
            "Recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
            "F1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
            "ROC_AUC": round(float(roc_auc_score(y_test, probabilities)), 4),
        }

        if name == "Random Forest":
            fitted_random_forest = model

    if fitted_random_forest is None:
        raise RuntimeError("Random Forest model did not train.")
    importance_df = pd.DataFrame(
        {"feature": features, "importance": fitted_random_forest.feature_importances_}
    ).sort_values("importance", ascending=False)
    importance_df.to_csv(OUTPUT_DIR / "ebike_feature_importance.csv", index=False)

    return results


def cluster_trip_profiles(df: pd.DataFrame) -> pd.DataFrame:
    work_df = df.copy()
    work_df["is_member"] = (work_df["member_casual"] == "member").astype(int)
    work_df["is_ebike"] = (work_df["rideable_type"] == "electric_bike").astype(int)

    feature_cols = ["trip_minutes", "start_hour", "start_day_of_week", "is_member", "is_ebike"]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(work_df[feature_cols])

    model = KMeans(n_clusters=4, random_state=42, n_init=10)
    work_df["trip_profile_cluster"] = model.fit_predict(scaled)
    cluster_summary = (
        work_df.groupby("trip_profile_cluster")[feature_cols]
        .mean()
        .reset_index()
        .sort_values("trip_profile_cluster")
    )
    cluster_summary.to_csv(OUTPUT_DIR / "trip_profile_clusters.csv", index=False)
    return cluster_summary


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError("DuckDB analytics database not found. Run python/run_pipeline.py first.")

    df = load_trip_features()
    classification_metrics = classify_ebike_usage(df)
    cluster_summary = cluster_trip_profiles(df)

    metrics = {
        "classification_ebike_usage": classification_metrics,
        "best_model_by_f1": max(classification_metrics, key=lambda name: classification_metrics[name]["F1"]),
        "cluster_count": int(cluster_summary.shape[0]),
    }
    output_path = OUTPUT_DIR / "citibike_ml_metrics.json"
    output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))
    print(f"Citi Bike ML outputs saved in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
