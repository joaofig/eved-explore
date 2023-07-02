CREATE TABLE traj_match (
    traj_id     INTEGER PRIMARY KEY
                        UNIQUE
                        NOT NULL,
    geometry    TEXT,
    match_error TEXT
);
