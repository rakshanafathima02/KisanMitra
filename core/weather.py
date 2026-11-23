"""Weather via the free Open-Meteo API (no key). Falls back to a local city table and sample data when offline."""
from datetime import date, timedelta

import requests

from . import knowledge

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FC_URL = "https://api.open-meteo.com/v1/forecast"
DAILY = ("temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
         "wind_speed_10m_max,et0_fao_evapotranspiration")


def geocode(name, count=5):
    """Return [{name, state, lat, lon, source}] for a place name (Open-Meteo, then built-in city table)."""
    try:
        r = requests.get(GEO_URL, params={"name": name, "count": count, "language": "en", "format": "json"}, timeout=8)
        r.raise_for_status()
        res = r.json().get("results") or []
        out = [{"name": x["name"], "state": x.get("admin1", ""), "lat": x["latitude"], "lon": x["longitude"],
                "country": x.get("country", ""), "source": "open-meteo"} for x in res]
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    return [{**c, "country": "India", "source": "built-in"} for c in knowledge.search_cities(name, count)]


def sample_forecast(lat=0.0, lon=0.0):
    """Deterministic demo forecast used when the live API is unreachable."""
    today = date.today()
    rain = [0, 0, 3, 28, 12, 0, 0]
    prob = [10, 15, 60, 90, 70, 20, 10]
    tmax = [34, 35, 31, 29, 30, 33, 39]
    tmin = [24, 24, 23, 22, 23, 24, 25]
    wind = [10, 12, 18, 32, 20, 12, 10]
    et0 = [5.2, 5.4, 4.0, 2.5, 3.0, 4.8, 5.6]
    return {
        "source": "sample",
        "current": {"temperature": 31.0, "humidity": 78.0},
        "daily": [{"date": (today + timedelta(days=i)).isoformat(), "tmax": tmax[i], "tmin": tmin[i], "rain_mm": rain[i],
                   "rain_prob": prob[i], "wind": wind[i], "et0": et0[i]} for i in range(7)],
    }


def forecast(lat, lon):
    """Live 7-day forecast. Returns the same dict shape as sample_forecast()."""
    try:
        r = requests.get(FC_URL, params={"latitude": lat, "longitude": lon, "daily": DAILY,
                                         "current": "temperature_2m,relative_humidity_2m", "timezone": "auto",
                                         "forecast_days": 7}, timeout=10)
        r.raise_for_status()
        j = r.json()
        d = j["daily"]
        days = []
        for i, day in enumerate(d["time"]):
            days.append({"date": day, "tmax": d["temperature_2m_max"][i], "tmin": d["temperature_2m_min"][i],
                         "rain_mm": d["precipitation_sum"][i] or 0, "rain_prob": d["precipitation_probability_max"][i] or 0,
                         "wind": d["wind_speed_10m_max"][i] or 0, "et0": d["et0_fao_evapotranspiration"][i] or 0})
        cur = j.get("current", {})
        return {"source": "open-meteo", "current": {"temperature": cur.get("temperature_2m"), "humidity": cur.get("relative_humidity_2m")},
                "daily": days}
    except Exception:  # noqa: BLE001
        return sample_forecast(lat, lon)


def summary_text(fc):
    """Short English summary of the forecast for the AI prompt."""
    cur = fc["current"]
    lines = [f"Now: {cur.get('temperature')}°C, humidity {cur.get('humidity')}%."]
    for d in fc["daily"][:5]:
        lines.append(f"{d['date']}: {d['tmin']}-{d['tmax']}°C, rain {d['rain_mm']} mm ({d['rain_prob']}%), wind {d['wind']} km/h")
    return " ".join(lines)
