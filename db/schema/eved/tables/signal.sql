CREATE TABLE signal (
    signal_id           INTEGER PRIMARY KEY ASC,
    day_num             DOUBLE NOT NULL,
    vehicle_id          INTEGER NOT NULL,
    trip_id             INTEGER NOT NULL,
    time_stamp          INTEGER NOT NULL,
    latitude            DOUBLE NOT NULL,
    longitude           DOUBLE NOT NULL,
    speed               DOUBLE,
    maf                 DOUBLE,
    rpm                 DOUBLE,
    abs_load            DOUBLE,
    oat                 DOUBLE,
    fuel_rate           DOUBLE,
    ac_power_kw         DOUBLE,
    ac_power_w          DOUBLE,
    heater_power_w      DOUBLE,
    hv_bat_current      DOUBLE,
    hv_bat_soc          DOUBLE,
    hv_bat_volt         DOUBLE,

    st_ftb_1            DOUBLE,
    st_ftb_2            DOUBLE,
    lt_ftb_1            DOUBLE,
    lt_ftb_2            DOUBLE,

    elevation           DOUBLE,
    elevation_smooth    DOUBLE,
    gradient            DOUBLE,

    energy_consumption  DOUBLE,

    match_latitude      DOUBLE NOT NULL,
    match_longitude     DOUBLE NOT NULL,
    match_type          INTEGER NOT NULL,

    speed_limit_type    INTEGER,
    speed_limit         TEXT,
    speed_limit_direct  INTEGER,
    intersection        INTEGER,
    bus_stop            INTEGER,
    focus_points        TEXT,

    bearing             DOUBLE,
    quadkey             INTEGER
);