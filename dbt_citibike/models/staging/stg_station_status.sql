select
    snapshot_ts,
    station_id,
    cast(num_bikes_available as bigint) as num_bikes_available,
    cast(num_ebikes_available as bigint) as num_ebikes_available,
    cast(num_docks_available as bigint) as num_docks_available,
    cast(is_installed as bigint) as is_installed,
    cast(is_renting as bigint) as is_renting,
    cast(is_returning as bigint) as is_returning
from station_status_snapshots
