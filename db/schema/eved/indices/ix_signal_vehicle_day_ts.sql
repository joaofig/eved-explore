CREATE INDEX ix_signal_vehicle_day_ts ON signal (
    vehicle_id ASC,
    day_num ASC,
    time_stamp ASC
);