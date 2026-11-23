"""Rule-based farm alert engine: turns a 7-day forecast into actionable alerts in 3 languages."""
from datetime import date as _date

from . import config as C
from . import i18n


def _fmt(d):
    return _date.fromisoformat(d).strftime("%a %d %b")


def generate(fc):
    """Return a list of alert dicts: {key, severity, params}. Severity: high | medium | info."""
    days, cur, out = fc["daily"], fc["current"], []
    # 1. Heavy rain in the next 4 days
    for d in days[:4]:
        if d["rain_mm"] >= C.HEAVY_RAIN_MM or (d["rain_prob"] >= C.HEAVY_RAIN_PROB and d["rain_mm"] >= 10):
            out.append({"key": "heavy_rain", "severity": "high", "params": {"date": _fmt(d["date"]), "mm": round(d["rain_mm"])}})
            break
    # 2. Heat / cold / wind (first offending day in 5 days)
    for d in days[:5]:
        if d["tmax"] is not None and d["tmax"] >= C.HEAT_C:
            out.append({"key": "heat", "severity": "high", "params": {"date": _fmt(d["date"]), "temp": round(d["tmax"])}})
            break
    for d in days[:5]:
        if d["tmin"] is not None and d["tmin"] <= C.COLD_C:
            out.append({"key": "cold", "severity": "medium", "params": {"date": _fmt(d["date"]), "temp": round(d["tmin"])}})
            break
    for d in days[:5]:
        if d["wind"] >= C.WIND_KMH:
            out.append({"key": "wind", "severity": "medium", "params": {"date": _fmt(d["date"]), "wind": round(d["wind"])}})
            break
    # 3. Dry spell: little rain in 5 days and high evapotranspiration
    five = days[:5]
    if sum(d["rain_mm"] for d in five) < C.DRY_SPELL_MM and sum(d["et0"] for d in five) / len(five) >= C.DRY_SPELL_ET0:
        out.append({"key": "dry_spell", "severity": "medium", "params": {}})
    # 4. Fungal disease risk: humid now and rain on 2+ of the next 3 days
    rainy = sum(1 for d in days[:3] if d["rain_mm"] >= 2)
    if (cur.get("humidity") or 0) >= C.HUMID_PCT and rainy >= 2:
        out.append({"key": "fungal", "severity": "medium", "params": {}})
    # 5. Best spraying day in the next 5 days
    for d in days[:5]:
        if d["rain_prob"] <= C.SPRAY_MAX_PROB and d["wind"] <= C.SPRAY_MAX_WIND:
            out.append({"key": "spray_window", "severity": "info", "params": {"date": _fmt(d["date"])}})
            break
    return out


def render(alerts, lang="en"):
    return [{"severity": a["severity"], "text": i18n.alert_text(a["key"], lang, **a["params"])} for a in alerts]
