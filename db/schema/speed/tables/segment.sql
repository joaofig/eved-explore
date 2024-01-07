CREATE TABLE segment (
    speed_id    INTEGER PRIMARY KEY,
    h3_ini      INTEGER NOT NULL,
    h3_end      INTEGER NOT NULL,
    dt          FLOAT NOT NULL,
    day_num     FLOAT NOT NULL,
    traj_id     INTEGER NOT NULL
);