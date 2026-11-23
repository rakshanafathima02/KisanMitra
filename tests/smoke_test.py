"""Headless end-to-end smoke test (offline mode, no API key / internet needed): python tests/smoke_test.py"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["KISAN_MOCK"] = "1"
os.environ["KISAN_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

from core import advisor, alerts, db, knowledge as kb, weather  # noqa: E402


def btn(at, label):
    return [b for b in at.button if b.label == label][0]


def go(at, key):
    at.sidebar.radio[0].set_value(key).run(timeout=60)
    assert not at.exception, (key, at.exception)


def unit_tests():
    assert kb.stage_for("rice", 30)["stage"]["name"] == "Tillering"
    assert kb.stage_for("rice", -3)["status"] == "not_sown" and kb.stage_for("rice", 999)["status"] == "past"
    keys = {a["key"] for a in alerts.generate(weather.sample_forecast())}
    assert {"heavy_rain", "wind", "spray_window"} <= keys, keys
    hot = weather.sample_forecast()
    hot["daily"][0]["tmax"] = 41
    assert any(a["key"] == "heat" for a in alerts.generate(hot))
    assert all(alerts.render(alerts.generate(weather.sample_forecast()), l) for l in ("en", "ta", "hi"))
    d = advisor.diagnose("tomato", "leaves curling upward and many tiny white insects under leaves", None, "en")
    assert d["mode"] == "kb" and d["result"], d
    print("Unit tests passed")


def main():
    unit_tests()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception, at.exception
    [t for t in at.text_input if t.label == "Your name"][0].set_value("Murugan")
    btn(at, "Open / create my farm").click().run()
    assert at.session_state.farmer["name"] == "Murugan"
    [t for t in at.text_input if t.label == "Village / town / city"][0].set_value("Coimbatore")
    btn(at, "Find location").click().run()
    assert at.session_state.geo, "geocode returned nothing"
    btn(at, "📍 Save").click().run()
    assert db.get_farmer("Murugan")["lat"] is not None
    btn(at, "Add crop").click().run()
    assert len(db.sowings("Murugan")) == 1
    print("Profile, location and crop saved")

    go(at, "nav_weather")
    go(at, "nav_pest")
    [t for t in at.text_area if t.label == "Describe what you see (optional)"][0].set_value("white powder on leaves").run()
    btn(at, "Diagnose").click().run()
    assert at.session_state.pest_out["result"], "no diagnosis"
    go(at, "nav_plan")

    at.sidebar.selectbox[0].set_value("தமிழ்").run(timeout=60)  # switch to Tamil
    assert not at.exception, at.exception
    for key in ("nav_home", "nav_weather", "nav_pest", "nav_plan"):
        go(at, key)
    at.sidebar.selectbox[0].set_value("हिन्दी").run(timeout=60)
    assert not at.exception, at.exception
    print("All pages render in English, Tamil and Hindi")
    print("ALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
