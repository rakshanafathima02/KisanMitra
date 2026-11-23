"""Built-in agriculture knowledge base + TF-IDF pest symptom matching."""
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


CROPS = {c["id"]: c for c in _load("crops.json")}
PESTS = _load("pests.json")
PRACTICES = _load("practices.json")
CITIES = _load("cities.json")


def _tok(s):
    # Custom tokenizer: Python's \w splits Tamil/Hindi words at vowel signs, so split on spaces/punctuation instead.
    return re.findall(r"[^\s,.;:!?()\[\]\"'/\\\-]+", s.lower())


def crop_name(cid, lang="en"):
    names = CROPS[cid]["names"]
    return names.get(lang) or names["en"]


@lru_cache(maxsize=1)
def _pest_index():
    vec = TfidfVectorizer(tokenizer=_tok, token_pattern=None, lowercase=False, ngram_range=(1, 2), sublinear_tf=True)
    docs = [f"{p['name']} {p['symptoms']} {p['symptoms']} {p['cause']}".lower() for p in PESTS]
    return vec, vec.fit_transform(docs)


def pests_by_symptom(text, crop=None, k=3):
    """Rank pests/diseases by similarity of their symptoms to the farmer's description."""
    vec, mat = _pest_index()
    sims = cosine_similarity(vec.transform([text.lower()]), mat)[0].copy()
    for i, p in enumerate(PESTS):
        if crop:
            sims[i] = sims[i] * 1.6 if (crop in p["crops"] or "all" in p["crops"]) else sims[i] * 0.3
    order = sorted(range(len(PESTS)), key=lambda i: -sims[i])
    return [{**PESTS[i], "score": float(sims[i])} for i in order[:k] if sims[i] > 0]


def stage_for(crop_id, das):
    """Current growth stage for `das` days after sowing. Returns a dict describing the situation."""
    c = CROPS[crop_id]
    stages = c["stages"]
    if das < 0:
        return {"status": "not_sown", "stage": None}
    if das > c["duration_days"]:
        return {"status": "past", "stage": stages[-1], "index": len(stages) - 1, "next": None, "days_to_next": None}
    for i, s in enumerate(stages):
        if s["start"] <= das < s["end"] or (i == len(stages) - 1 and das <= s["end"]):
            nxt = stages[i + 1] if i + 1 < len(stages) else None
            return {"status": "ok", "stage": s, "index": i, "next": nxt, "days_to_next": s["end"] - das if nxt else None}
    return {"status": "ok", "stage": stages[-1], "index": len(stages) - 1, "next": None, "days_to_next": None}


def sowable_in_month(month):
    return [cid for cid, c in CROPS.items() if month in c["sowing_months"]]


def search_cities(name, limit=5):
    n = name.strip().lower()
    return [c for c in CITIES if n and (n in c["name"].lower() or c["name"].lower() in n)][:limit]
