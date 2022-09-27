CREATE INDEX ix_signal_quadkey_wd_ts ON signal (
    quadkey ASC,
    week_day ASC,
    day_slot ASC
);
