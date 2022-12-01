import numpy as np
import utm

from db.api import EVedDb


def get_max_signal_id():
    db = EVedDb()
    return int(db.query_scalar("select max(signal_id) from signal"))


def get_signal_range(signal_ini, signal_end):
    db = EVedDb()
    sql = """
    select signal_id
    ,      match_latitude
    ,      match_longitude
    from   signal
    where  signal_id >= ? and signal_id < ?;
    """
    signals = db.query(sql, [signal_ini, signal_end])
    ids = np.array([s[0] for s in signals], dtype=int)
    lats = np.array([s[1] for s in signals])
    lons = np.array([s[2] for s in signals])
    return ids, lats, lons


def update_signals(utm_list):
    sql = """
    update signal
    set    easting = ?
    ,      northing = ?
    where  signal_id = ?
    """
    db = EVedDb()
    db.execute_sql(sql, utm_list, many=True)


def main():
    max_signal_id = get_max_signal_id()
    print(max_signal_id)

    window_size = 1_000_000
    signal_range = range(1, max_signal_id, window_size)
    for i in signal_range:
        ids, lats, lons = get_signal_range(i, i + window_size)
        print(i, ids.shape[0])

        easting, northing, zone_number, zone_letter = utm.from_latlon(lats, lons)
        utm_list = list(zip([float(x) for x in easting],
                            [float(x) for x in northing],
                            [int(i) for i in ids]))

        print("Updating UTM coordinates...")
        update_signals(utm_list)


if __name__ == '__main__':
    main()
