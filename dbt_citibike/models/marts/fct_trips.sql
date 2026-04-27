select
    ride_id,
    rideable_type,
    started_at,
    ended_at,
    date_diff('minute', started_at, ended_at) as trip_minutes,
    start_station_id,
    end_station_id,
    member_casual
from {{ ref('stg_trips') }}
