"""AI advisor: grounded Q&A, pest/disease diagnosis (text + photo) and stage-wise weekly plans."""
from datetime import date, timedelta

from . import alerts as al
from . import knowledge as kb
from . import llm
from .config import LANG_NAMES

SYSTEM = (
    "You are KisanMitra, a friendly agriculture advisor for small farmers in India. Rules: "
    "(1) Reply in the requested language using short, simple sentences a farmer understands. "
    "(2) Use the KNOWLEDGE provided for specifics; if it does not cover the question, give only well-known, safe, general "
    "advice and say you are not sure. (3) Prefer organic and low-cost steps first. (4) Never invent pesticide names or doses; "
    "for chemicals say to ask the agriculture officer or KVK and follow the label. (5) Give clear numbered steps. "
    "(6) For serious problems mention the Kisan Call Centre 1800-180-1551. (7) Keep the answer under 180 words."
)


def _from_kb(p):
    return {"likely_issue": p["name"], "confidence": "low (text match only)",
            "what_you_see": p["symptoms"], "cause": p["cause"],
            "organic_steps": [s.strip() for s in p["organic"].split(";") if s.strip()],
            "chemical_note": p["chemical_note"], "prevention": p["prevention"],
            "see_expert_if": "the problem spreads quickly, covers more than a small part of the field, or you are unsure."}


def diagnose(crop, symptoms, image, lang):
    """image: (bytes, mime) or None. Returns {result, candidates, mode}; mode in ai_photo | ai_text | kb."""
    query = f"{kb.crop_name(crop) if crop else ''} {llm.to_english(symptoms or '')}"
    cands = kb.pests_by_symptom(query, crop, 4)
    if not llm.ai_available():
        return {"result": _from_kb(cands[0]) if cands else None, "candidates": cands, "mode": "kb"}
    cand_text = "\n".join(f"- {p['name']}: signs {p['symptoms']}. Organic: {p['organic']}. Chemicals: {p['chemical_note']}. "
                          f"Prevention: {'; '.join(p['prevention'])}" for p in cands) or "none"
    prompt = (f"A farmer needs help. Crop: {kb.crop_name(crop) if crop else 'unknown'}. Farmer's description: {symptoms or 'none'}.\n"
              f"{'Look carefully at the attached photo.' if image else 'No photo was given.'}\n"
              f"CANDIDATE PROBLEMS FROM OUR DATABASE:\n{cand_text}\n\n"
              f"Decide the most likely problem. Prefer a database candidate if it fits; otherwise say 'Not sure' and explain. "
              f"Write all values in {LANG_NAMES[lang]} (keys stay in English). Return JSON: "
              '{"likely_issue": str, "confidence": "low|medium|high", "what_you_see": str, "cause": str, '
              '"organic_steps": [str, ...], "chemical_note": str, "prevention": [str, ...], "see_expert_if": str}. '
              "Never invent pesticide names or doses; for chemicals tell the farmer to ask the agriculture officer and follow the label.")
    fb = {"__fail__": True}
    res = llm.ask_json(prompt, system=SYSTEM, fallback=fb, temperature=0.2, image=image)
    if not res or res.get("__fail__"):
        return {"result": _from_kb(cands[0]) if cands else None, "candidates": cands, "mode": "kb"}
    return {"result": res, "candidates": cands, "mode": "ai_photo" if image else "ai_text"}


def weekly_plan(crop, sow_date, lang, forecast=None):
    """Stage-aware plan: current stage tasks (translated when needed) + weather alerts."""
    das = (date.today() - sow_date).days
    st = kb.stage_for(crop, das)
    c = kb.CROPS[crop]
    plan = {"crop": crop, "das": das, "status": st["status"], "harvest": sow_date + timedelta(days=c["duration_days"]),
            "stage_name": None, "tasks": [], "days_to_next": st.get("days_to_next"), "next_stage": None, "alerts": []}
    if st["status"] != "not_sown":
        s = st["stage"]
        plan["stage_name"] = llm.translate(s["name"], lang)
        plan["tasks"] = [llm.translate(t, lang) for t in s["tasks"]]
        plan["next_stage"] = llm.translate(st["next"]["name"], lang) if st.get("next") else None
    if forecast:
        plan["alerts"] = al.render(al.generate(forecast), lang)
    plan["tips"] = [llm.translate(t, lang) for t in c["tips"]]
    return plan


def plan_as_text(plan, lang):
    from . import i18n

    L = lambda k: i18n.t(k, lang)  # noqa: E731
    lines = [f"{kb.crop_name(plan['crop'], lang)}", f"{L('das')}: {plan['das']}", f"{L('harvest')}: {plan['harvest']}"]
    if plan["stage_name"]:
        lines += [f"{L('stage')}: {plan['stage_name']}", f"{L('this_week')}:"] + [f"  {i + 1}. {t}" for i, t in enumerate(plan["tasks"])]
    if plan["alerts"]:
        lines += [f"{L('alerts')}:"] + [f"  - {a['text']}" for a in plan["alerts"]]
    return "\n".join(lines)
