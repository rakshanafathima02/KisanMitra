"""KisanMitra - multilingual farmer helper (Streamlit UI)."""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import advisor, alerts, config, db, i18n, knowledge as kb, llm, speech, weather

st.set_page_config(page_title="KisanMitra | Farmer Companion", page_icon="🌾", layout="wide", initial_sidebar_state="expanded")
db.init()
st.markdown("""<style>
/* KisanMitra farmer-first visual system */
:root{--km-green:#28633b;--km-deep:#194b2b;--km-leaf:#e8f3e8;--km-cream:#fbfaf4;--km-ink:#25352a;--km-muted:#68766b;--km-border:#dce7d9}
.stApp{background:var(--km-cream);color:var(--km-ink)}
.block-container{padding-top:1.35rem;padding-bottom:3rem;max-width:1180px}
[data-testid="stHeader"]{background:rgba(251,250,244,.92)}
[data-testid="stSidebar"]{background:#f0f6ec;border-right:1px solid var(--km-border)}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2{color:var(--km-deep);font-size:1.55rem}
[data-testid="stSidebar"] .stRadio label{padding:9px 12px;border-radius:12px;font-weight:600}
[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"]{display:none}
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3{color:var(--km-deep);letter-spacing:-.02em}
h1{font-size:2.15rem!important} h2{font-size:1.55rem!important} h3{font-size:1.2rem!important}
p,li,label,.stCaption{font-size:1rem}
.stButton>button,.stDownloadButton>button{background:var(--km-green);color:white;border:0;border-radius:12px;min-height:44px;padding:.55rem 1.15rem;font-weight:700;box-shadow:0 2px 5px rgba(25,75,43,.12)}
.stButton>button:hover,.stDownloadButton>button:hover{background:var(--km-deep);color:white;border:0}
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div,.stDateInput input{border-radius:10px;border-color:#cbdcc8;background:#fff}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--km-border);padding:16px;border-radius:15px;box-shadow:0 2px 8px rgba(32,70,42,.04)}
[data-testid="stMetricLabel"]{color:var(--km-muted);font-weight:600}
[data-testid="stMetricValue"]{color:var(--km-deep)}
[data-testid="stFileUploader"]{background:#fff;border:1.5px dashed #a9c6a8;border-radius:15px;padding:10px}
[data-testid="stAlert"]{border-radius:13px}
[data-testid="stExpander"]{background:#fff;border:1px solid var(--km-border);border-radius:12px}
.stTabs [data-baseweb="tab-list"]{gap:8px}
.stTabs [data-baseweb="tab"]{background:#edf4e9;border-radius:10px 10px 0 0;padding:10px 16px}
.km-hero{background:linear-gradient(115deg,#e7f3e5,#f5f8e9);border:1px solid #d4e5d0;border-radius:22px;padding:23px 25px;margin:3px 0 22px}
.km-hero h2{margin:0;color:#194b2b;font-size:1.65rem}
.km-hero p{margin:7px 0 0;color:#536b56;font-size:1.02rem}
.km-card{background:#fff;border:1px solid var(--km-border);border-radius:16px;padding:16px 18px;margin:10px 0;color:var(--km-ink);box-shadow:0 2px 8px rgba(32,70,42,.04)}
.km-high{border-left:6px solid #d94b43}.km-medium{border-left:6px solid #e59a28}.km-info{border-left:6px solid #43a047}
.km-section{background:#fff;border:1px solid var(--km-border);border-radius:16px;padding:16px 18px;margin:12px 0}
@media(max-width:700px){.block-container{padding-left:1rem;padding-right:1rem}h1{font-size:1.75rem!important}.km-hero{padding:18px}}
</style>""", unsafe_allow_html=True)

PAGE_KEYS = ["nav_home", "nav_weather", "nav_pest", "nav_plan"]
ICONS = {"nav_home": "🏡", "nav_weather": "⛅", "nav_pest": "🐛", "nav_plan": "📅"}

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("## 🌾 KisanMitra")
    st.caption("Your simple farming companion")
    st.divider()
    lang_label = st.selectbox("Choose your language", list(config.LANGS.keys()), key="lang_label")
    lang = config.LANGS[lang_label]
    T = lambda k: i18n.t(k, lang)  # noqa: E731
    st.markdown("**What do you need today?**")
    page_key = st.radio("nav", PAGE_KEYS, format_func=lambda k: f"{ICONS[k]}  {i18n.t(k, lang)}", label_visibility="collapsed")
    st.divider()
    if st.session_state.get("farmer"):
        st.markdown("**👩‍🌾 Your farm**")
        st.write(st.session_state.farmer['name'])
    with st.expander("⚙️ AI settings", expanded=False):
        key_in = st.text_input("Gemini API key", type="password", help="Optional. You can also set GEMINI_API_KEY in your .env file.")
        if key_in:
            llm.set_api_key(key_in)
        st.success("AI service connected") if llm.ai_available() else st.warning(T("ai_offline"))
        if llm.status["last_error"]:
            st.caption(f"Technical detail: {llm.status['last_error'][:100]}")



def farmer():
    return st.session_state.get("farmer")


def need_farmer():
    f = farmer()
    if not f:
        st.info(T("set_profile_first"))
        st.stop()
    return db.get_farmer(f["name"])  # always fresh


def get_forecast(f):
    if f.get("lat") is None:
        return None
    return weather.forecast(f["lat"], f["lon"])


def show_alerts(fc):
    items = alerts.render(alerts.generate(fc), lang)
    if not items:
        st.success(T("no_alerts"))
    for a in items:
        icon = {"high": "🔴", "medium": "🟠", "info": "🟢"}[a["severity"]]
        st.markdown(f"<div class='km-card km-{a['severity']}'>{icon} {a['text']}</div>", unsafe_allow_html=True)


def crop_options():
    return list(kb.CROPS.keys())


# ------------------------------------------------------------------ pages
def page_home():
    st.markdown(f"<div class='km-hero'><h2>🌾 Welcome to KisanMitra</h2><p>{T('tagline')}<br>Manage your farm, check the weather and get crop care guidance in one place.</p></div>", unsafe_allow_html=True)
    name = st.text_input(T("name"), value=(farmer() or {}).get("name", ""))
    if st.button(T("load_profile"), type="primary") and name.strip():
        f = db.get_farmer(name.strip()) or db.save_farmer(name.strip(), lang)
        st.session_state.farmer = f
        st.rerun()
    f = farmer()
    if not f:
        return
    f = db.get_farmer(f["name"])
    st.divider()
    st.subheader(f"🏡 {f['name']}")
    # --- location
    c1, c2 = st.columns([3, 1])
    q = c1.text_input(T("village_city"), key="loc_q")
    if c2.button(T("find_location")) and q.strip():
        st.session_state.geo = weather.geocode(q.strip())
        if not st.session_state.geo:
            st.warning(T("no_location_found"))
    if st.session_state.get("geo"):
        opts = st.session_state.geo
        i = st.selectbox(T("choose_location"), range(len(opts)),
                         format_func=lambda i: f"{opts[i]['name']}, {opts[i]['state']} ({opts[i]['lat']:.2f}, {opts[i]['lon']:.2f})")
        if st.button(f"📍 {T('save')}", key="saveloc"):
            o = opts[i]
            db.save_farmer(f["name"], lang, o["name"], o["state"], o["lat"], o["lon"])
            st.session_state.geo = None
            st.success(T("saved"))
            st.rerun()
    if f.get("location_name"):
        st.write(f"📍 **{T('location')}:** {f['location_name']}, {f.get('state') or ''}")
    # --- land & soil
    c1, c2, c3 = st.columns([1, 1, 1])
    acres = c1.number_input(T("land_acres"), 0.0, 1000.0, float(f.get("land_acres") or 1.0), 0.5)
    soil_keys = list(i18n.SOILS.keys())
    cur = f.get("soil") if f.get("soil") in soil_keys else "unknown"
    soil = c2.selectbox(T("soil"), soil_keys, index=soil_keys.index(cur), format_func=lambda k: i18n.soil_label(k, lang))
    c3.write("")
    if c3.button(T("save"), key="saveprof"):
        db.save_farmer(f["name"], lang, land_acres=acres, soil=soil)
        st.success(T("saved"))
    # --- crops
    st.markdown(f"### 🌱 {T('my_crops')}")
    a, b, c, d = st.columns([2, 2, 1, 1])
    crop = a.selectbox(T("crop"), crop_options(), format_func=lambda k: kb.crop_name(k, lang))
    sd = b.date_input(T("sowing_date"), date.today() - timedelta(days=20))
    area = c.number_input(T("area_acres"), 0.1, 1000.0, 1.0, 0.5)
    d.write("")
    if d.button(T("add_crop")):
        db.add_sowing(f["name"], crop, sd.isoformat(), area)
        st.rerun()
    rows = db.sowings(f["name"])
    if not rows:
        st.caption(T("none_yet"))
    for r in rows:
        das = (date.today() - date.fromisoformat(r["sow_date"])).days
        x, y = st.columns([5, 1])
        x.markdown(f"**{kb.crop_name(r['crop'], lang)}** · {r['sow_date']} · {r['area_acres']} ac · {T('das')}: {das}")
        if y.button(T("remove"), key=f"rm{r['id']}"):
            db.delete_sowing(r["id"])
            st.rerun()


def page_weather():
    st.header(f"⛅ {T('nav_weather')}")
    st.caption("Check local conditions and plan farm work around the weather.")
    f = need_farmer()
    if f.get("lat") is None:
        st.info(T("set_location_first"))
        st.stop()
    fc = weather.forecast(f["lat"], f["lon"])
    st.caption(f"📍 {f['location_name']}, {f.get('state') or ''}")
    if fc["source"] == "sample":
        st.warning(T("demo_weather"))
    c1, c2 = st.columns(2)
    c1.metric(f"{T('now')}: {T('temp')}", f"{fc['current'].get('temperature')} °C")
    c2.metric(T("humidity"), f"{fc['current'].get('humidity')} %")
    st.subheader(f"🚨 {T('alerts')}")
    show_alerts(fc)
    st.subheader(f"📈 {T('forecast')}")
    df = pd.DataFrame(fc["daily"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=df["date"], y=df["rain_mm"], name=T("rain_mm"), marker_color="#42A5F5", secondary_y=True)
    fig.add_scatter(x=df["date"], y=df["tmax"], name=T("temp_max"), mode="lines+markers", line_color="#EF5350", secondary_y=False)
    fig.add_scatter(x=df["date"], y=df["tmin"], name=T("temp_min"), mode="lines+markers", line_color="#FFA726", secondary_y=False)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, width="stretch")
    show = df.rename(columns={"date": T("date"), "tmax": T("temp_max"), "tmin": T("temp_min"), "rain_mm": T("rain_mm"),
                              "rain_prob": T("rain_prob"), "wind": T("wind")}).drop(columns=["et0"])
    st.dataframe(show, hide_index=True, width="stretch")


def page_pest():
    st.header(f"🐛 {T('nav_pest')}")
    st.markdown("<div class='km-hero'><h2>🌿 Let’s check your crop</h2><p>Take a clear photo of the affected leaf, or describe what you see. You can add both for better guidance.</p></div>", unsafe_allow_html=True)
    crop = st.selectbox(T("crop"), [None] + crop_options(), format_func=lambda k: T("any_crop") if k is None else kb.crop_name(k, lang))
    photo = st.file_uploader(T("upload_photo"), type=["jpg", "jpeg", "png"])
    cam = st.camera_input(T("take_photo")) if st.toggle(T("take_photo")) else None
    symptoms = st.text_area(T("symptoms"), height=80)
    audio = st.audio_input(T("record"), key="pest_audio") if hasattr(st, "audio_input") else None
    if st.button(T("diagnose"), type="primary"):
        if audio is not None:
            tr = speech.transcribe(audio.getvalue(), lang)
            symptoms = f"{symptoms} {tr}".strip() if tr else symptoms
        img = photo or cam
        image = (img.getvalue(), img.type or "image/jpeg") if img else None
        if not image and not (symptoms or "").strip():
            st.warning(T("give_input"))
        else:
            if image:
                st.image(img, width=260)
            with st.spinner("..."):
                out = advisor.diagnose(crop, symptoms, image, lang)
            st.session_state.pest_out = out
            if image and out["mode"] == "kb":
                st.info(T("photo_needs_ai"))
            f = farmer()
            if f and out["result"]:
                db.save_history(f["name"], "pest", lang, symptoms or "(photo)", out["result"]["likely_issue"])
    out = st.session_state.get("pest_out")
    if out and out["result"]:
        r = out["result"]
        st.markdown(f"<div class='km-card km-medium'><h3>🩺 {T('likely_issue')}: {r.get('likely_issue')}</h3>"
                    f"<b>{T('confidence')}:</b> {r.get('confidence')}</div>", unsafe_allow_html=True)
        for key, label in (("what_you_see", "what_you_see"), ("cause", "cause")):
            if r.get(key):
                st.markdown(f"**{T(label)}:** {r[key]}")
        st.markdown(f"**{T('what_to_do')}**")
        for s in r.get("organic_steps", []):
            st.markdown(f"- {s}")
        if r.get("chemical_note"):
            st.markdown(f"**{T('chemical')}:** {r['chemical_note']}")
        if r.get("prevention"):
            st.markdown(f"**{T('prevention')}**")
            for s in r["prevention"]:
                st.markdown(f"- {s}")
        if r.get("see_expert_if"):
            st.markdown(f"**{T('see_expert')}:** {r['see_expert_if']}")
        st.warning(T("expert_note"))
        if len(out["candidates"]) > 1:
            with st.expander("Other possibilities"):
                for p in out["candidates"][:4]:
                    st.markdown(f"- **{p['name']}**: {p['symptoms'][:140]}...")
        if st.button(T("listen"), key="pest_listen"):
            txt = f"{r.get('likely_issue')}. " + " ".join(r.get("organic_steps", [])) + " " + T("expert_note")
            mp3 = speech.tts(txt, lang)
            if mp3:
                st.audio(mp3, format="audio/mp3")


def page_plan():
    st.header(f"📅 {T('nav_plan')}")
    st.caption("See your crop stage and the important tasks for this week.")
    f = need_farmer()
    rows = db.sowings(f["name"])
    choice = None
    if rows:
        labels = {r["id"]: f"{kb.crop_name(r['crop'], lang)} · {r['sow_date']}" for r in rows}
        pick = st.selectbox(T("select_sowing"), [None] + [r["id"] for r in rows], format_func=lambda i: "-" if i is None else labels[i])
        if pick:
            r = next(x for x in rows if x["id"] == pick)
            choice = (r["crop"], date.fromisoformat(r["sow_date"]))
    if choice is None:
        st.caption(T("or_manual"))
        a, b = st.columns(2)
        crop = a.selectbox(T("crop"), crop_options(), format_func=lambda k: kb.crop_name(k, lang), key="pc")
        sd = b.date_input(T("sowing_date"), date.today() - timedelta(days=30), key="pd")
        choice = (crop, sd)
    crop, sd = choice
    fc = get_forecast(f)
    plan = advisor.weekly_plan(crop, sd, lang, fc)
    c = kb.CROPS[crop]
    m1, m2, m3 = st.columns(3)
    m1.metric(T("das"), plan["das"])
    m2.metric(T("stage"), plan["stage_name"] or "-")
    m3.metric(T("harvest"), plan["harvest"].strftime("%d %b %Y"))
    if plan["status"] == "not_sown":
        st.info(T("not_sown"))
    if plan["status"] == "past":
        st.warning(T("past_maturity"))
    if plan["days_to_next"] is not None and plan["next_stage"]:
        st.caption(f"{T('next_stage')} {plan['days_to_next']} {T('days')}: {plan['next_stage']}")
    if plan["tasks"]:
        st.subheader(f"✅ {T('this_week')}")
        for i, t in enumerate(plan["tasks"], 1):
            st.markdown(f"{i}. {t}")
    if plan["alerts"]:
        st.subheader(f"🚨 {T('alerts')}")
        for a in plan["alerts"]:
            st.markdown(f"- {a['text']}")
    # timeline
    rows_t = [{"Stage": s["name"], "Start": sd + timedelta(days=s["start"]), "End": sd + timedelta(days=s["end"])} for s in c["stages"]]
    fig = px.timeline(pd.DataFrame(rows_t), x_start="Start", x_end="End", y="Stage", color="Stage")
    fig.update_yaxes(autorange="reversed")
    fig.add_shape(type="line", x0=date.today(), x1=date.today(), y0=0, y1=1, yref="paper", line=dict(color="white", dash="dash"))
    fig.update_layout(height=280, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
    st.subheader(f"🗓️ {T('timeline')}")
    st.plotly_chart(fig, width="stretch")
    st.markdown(f"**{T('water_need')}:** {c['water']} · **{T('tips')}:**")
    for t in plan["tips"]:
        st.markdown(f"- {t}")
    st.download_button(T("download_plan"), advisor.plan_as_text(plan, lang), file_name=f"plan_{crop}.txt")
    st.divider()
    st.subheader(f"🌾 {T('sow_now')}")
    ids = kb.sowable_in_month(date.today().month)
    st.write(", ".join(kb.crop_name(i, lang) for i in ids) or "-")
    st.caption(T("sow_note"))


PAGES = {"nav_home": page_home, "nav_weather": page_weather, "nav_pest": page_pest, "nav_plan": page_plan}
PAGES[page_key]()
