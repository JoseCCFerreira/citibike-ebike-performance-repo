-- E-bike share by start hour
SELECT
    start_hour,
    COUNT(*) AS trips,
    ROUND(AVG(CASE WHEN rideable_type = 'electric_bike' THEN 1 ELSE 0 END) * 100, 2) AS ebike_share_pct
FROM fct_trips
GROUP BY 1
ORDER BY 1;

-- Top start stations by demand
SELECT
    s.name AS station_name,
    COUNT(*) AS trip_count,
    ROUND(AVG(f.trip_minutes), 2) AS avg_trip_minutes
FROM fct_trips f
LEFT JOIN dim_stations s
    ON s.station_id = f.start_station_id
GROUP BY 1
ORDER BY trip_count DESC
LIMIT 20;

-- Stations at risk of emptiness or saturation in latest snapshot
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
LIMIT 20;
