select
    station_id,
    name,
    short_name,
    cast(lat as double) as lat,
    cast(lon as double) as lon,
    cast(capacity as bigint) as capacity,
    region_id
from stations
