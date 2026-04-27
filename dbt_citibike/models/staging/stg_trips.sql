select
    ride_id,
    rideable_type,
    cast(started_at as timestamp) as started_at,
    cast(ended_at as timestamp) as ended_at,
    start_station_id,
    end_station_id,
    member_casual
from trips
