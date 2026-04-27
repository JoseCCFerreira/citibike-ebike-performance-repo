DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS stations;
DROP TABLE IF EXISTS station_status_snapshots;
DROP TABLE IF EXISTS vehicle_types;
DROP TABLE IF EXISTS system_information;

CREATE TABLE trips (
    ride_id TEXT PRIMARY KEY,
    rideable_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    start_station_name TEXT,
    start_station_id TEXT,
    end_station_name TEXT,
    end_station_id TEXT,
    start_lat REAL,
    start_lng REAL,
    end_lat REAL,
    end_lng REAL,
    member_casual TEXT NOT NULL
);

CREATE TABLE stations (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    capacity INTEGER,
    region_id TEXT,
    electric_bike_surcharge_waiver INTEGER
);

CREATE TABLE station_status_snapshots (
    snapshot_ts TEXT NOT NULL,
    station_id TEXT NOT NULL,
    num_bikes_available INTEGER,
    num_ebikes_available INTEGER,
    num_docks_available INTEGER,
    is_installed INTEGER,
    is_renting INTEGER,
    is_returning INTEGER,
    last_reported INTEGER,
    PRIMARY KEY (snapshot_ts, station_id)
);

CREATE TABLE vehicle_types (
    vehicle_type_id TEXT PRIMARY KEY,
    form_factor TEXT,
    propulsion_type TEXT,
    max_range_meters REAL
);

CREATE TABLE system_information (
    system_id TEXT PRIMARY KEY,
    language TEXT,
    name TEXT,
    operator TEXT,
    timezone TEXT
);
