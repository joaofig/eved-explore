CREATE TABLE triple (
    triple_id INTEGER PRIMARY KEY,
    traj_id   NUMERIC NOT NULL,
    t0        INTEGER NOT NULL,
    t1        INTEGER NOT NULL,
    t2        INTEGER NOT NULL
);