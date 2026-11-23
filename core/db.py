"""SQLite persistence: farmer profile, crop sowings and question history."""
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("KISAN_DB", Path(__file__).resolve().parent.parent / "data" / "kisanmitra.db"))
SCHEMA = """
CREATE TABLE IF NOT EXISTS farmers(
    name TEXT PRIMARY KEY, language TEXT, location_name TEXT, state TEXT, lat REAL, lon REAL,
    land_acres REAL, soil TEXT, created REAL);
CREATE TABLE IF NOT EXISTS sowings(
    id INTEGER PRIMARY KEY AUTOINCREMENT, farmer TEXT, crop TEXT, sow_date TEXT, area_acres REAL);
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT, farmer TEXT, ts REAL, kind TEXT, language TEXT, question TEXT, answer TEXT);
"""


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def get_farmer(name):
    with conn() as c:
        r = c.execute("SELECT * FROM farmers WHERE name=?", (name,)).fetchone()
    return dict(r) if r else None


def save_farmer(name, language, location_name=None, state=None, lat=None, lon=None, land_acres=None, soil=None):
    old = get_farmer(name) or {}
    row = {"language": language, "location_name": location_name or old.get("location_name"),
           "state": state or old.get("state"), "lat": lat if lat is not None else old.get("lat"),
           "lon": lon if lon is not None else old.get("lon"),
           "land_acres": land_acres if land_acres is not None else old.get("land_acres"),
           "soil": soil or old.get("soil")}
    with conn() as c:
        c.execute(
            "INSERT INTO farmers(name, language, location_name, state, lat, lon, land_acres, soil, created) "
            "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET language=excluded.language, "
            "location_name=excluded.location_name, state=excluded.state, lat=excluded.lat, lon=excluded.lon, "
            "land_acres=excluded.land_acres, soil=excluded.soil",
            (name, row["language"], row["location_name"], row["state"], row["lat"], row["lon"],
             row["land_acres"], row["soil"], time.time()))
    return get_farmer(name)


def add_sowing(farmer, crop, sow_date, area):
    with conn() as c:
        c.execute("INSERT INTO sowings(farmer, crop, sow_date, area_acres) VALUES(?,?,?,?)", (farmer, crop, sow_date, area))


def sowings(farmer):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM sowings WHERE farmer=? ORDER BY sow_date DESC", (farmer,))]


def delete_sowing(sid):
    with conn() as c:
        c.execute("DELETE FROM sowings WHERE id=?", (sid,))


def save_history(farmer, kind, language, question, answer):
    with conn() as c:
        c.execute("INSERT INTO history(farmer, ts, kind, language, question, answer) VALUES(?,?,?,?,?,?)",
                  (farmer, time.time(), kind, language, question, answer))


def history(farmer, kind=None, limit=5):
    q, p = "SELECT * FROM history WHERE farmer=?", [farmer]
    if kind:
        q += " AND kind=?"
        p.append(kind)
    q += " ORDER BY ts DESC LIMIT ?"
    p.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, p)]
