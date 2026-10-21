"""
Automatinio tikrinimo logika MCQ/trumpo atsakymo klausimams.
"""
import difflib
import re


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[.,!?;:]+$", "", text)   # nubraukia gale esančius skyrybos ženklus
    text = re.sub(r"\s+", " ", text)          # sutraukia kelis tarpus į vieną
    return text


def _best_similarity(submitted: str, accepted_variants: list[str]) -> float:
    return max(
        (difflib.SequenceMatcher(None, submitted, v).ratio() for v in accepted_variants),
        default=0.0,
    )


def accepted_answers(question: dict) -> list[str]:
    """Priimtini trumpo atsakymo variantai (be rubrikos eilučių, prasidedančių #)."""
    raw_key = question.get("answer_key") or ""
    return [
        _normalize(v) for v in raw_key.split("\n")
        if v.strip() and not v.strip().startswith("#")
    ]


def is_open_question(question: dict) -> bool:
    """Trumpo atsakymo klausimas be teisingų atsakymų = atviras (vertina mokytojas)."""
    return question.get("type") == "short_answer" and not accepted_answers(question)


def auto_grade(question: dict, submitted_answer: str):
    """
    Grąžina (score, graded_by).
    graded_by == 'teacher' reiškia, kad reikia žmogaus peržiūros
    (arba tikrai negalima automatiškai vertinti, arba atsakymas
    "beveik teisingas", bet ne pakankamai tikras, kad automatiškai įskaityti).
    """
    q_type = question["type"]
    if q_type == "game":
        return grade_game(question, submitted_answer or "")
    points = question.get("points", 1)
    submitted = _normalize(submitted_answer)

    if q_type == "mcq":
        answer_key = _normalize(question.get("answer_key"))
        return (points if submitted == answer_key else 0), "auto"

    if q_type == "short_answer":
        # answer_key gali turėti kelis priimtinus variantus, kiekvienas naujoje eilutėje
        # Eilutės, prasidedančios "#", yra vertinimo pastabos (rubrika), ne atsakymai.
        accepted_variants = accepted_answers(question)
        if not accepted_variants:
            # Atviras klausimas - vertina mokytojas (tuščias atsakymas = 0 iškart)
            if not submitted:
                return 0, "auto"
            return None, "teacher"

        if submitted in accepted_variants:
            return points, "auto"

        similarity = _best_similarity(submitted, accepted_variants)

        if similarity >= 0.9:
            # Tikėtina rašybos klaida ar mažas skirtumas - įskaitom automatiškai
            return points, "auto"
        elif similarity >= 0.6:
            # Neaišku - palieku mokytojui peržiūrėti, ne automatiškai 0
            return None, "teacher"
        else:
            return 0, "auto"

    # image_upload - mokytojas vertins rankiniu būdu
    return None, "teacher"



# ------------------------------------------------------------
# MINI ŽAIDIMAI (type = "game", options = [rūšis], answer_key = mokytojo tekstas)
#   match  – „kairė = dešinė“ po vieną eilutėje (sujunk poras)
#   order  – elementai teisinga tvarka, po vieną eilutėje (sudėliok)
#   groups – „Grupė: a; b; c“ po vieną eilutėje (surūšiuok)
# Mokinio atsakymas – JSON tekstas.
# ------------------------------------------------------------

GAME_KINDS = {
    "match": "Sujunk poras",
    "order": "Sudėliok eilės tvarka",
    "groups": "Surūšiuok į grupes",
}


def game_kind(question: dict) -> str:
    opts = question.get("options") or []
    if isinstance(opts, list) and opts and opts[0] in GAME_KINDS:
        return opts[0]
    return "match"


def _split_items(text: str):
    sep = ";" if ";" in text else ","
    return [x.strip() for x in text.split(sep) if x.strip()]


def parse_game(question: dict):
    """Grąžina žaidimo duomenis iš answer_key teksto."""
    kind = game_kind(question)
    lines = [l.strip() for l in (question.get("answer_key") or "").split("\n") if l.strip()]
    if kind == "match":
        pairs = []
        for l in lines:
            if "=" in l:
                a, b = l.split("=", 1)
                if a.strip() and b.strip():
                    pairs.append((a.strip(), b.strip()))
        return {"kind": kind, "pairs": pairs}
    if kind == "order":
        return {"kind": kind, "items": lines}
    groups = []
    for l in lines:
        if ":" in l:
            g, rest = l.split(":", 1)
            items = _split_items(rest)
            if g.strip() and items:
                groups.append((g.strip(), items))
    return {"kind": "groups", "groups": groups}


def game_size(question: dict) -> int:
    d = parse_game(question)
    if d["kind"] == "match":
        return len(d["pairs"])
    if d["kind"] == "order":
        return len(d["items"])
    return sum(len(items) for _, items in d["groups"])


def game_results(question: dict, submitted: str):
    """[(tekstas, teisingai?)] kiekvienam elementui – rodymui ir vertinimui."""
    import json
    d = parse_game(question)
    try:
        ans = json.loads(submitted) if submitted else {}
    except Exception:
        ans = {}
    out = []
    if d["kind"] == "match":
        got = ans.get("pairs") or {}
        for a, b in d["pairs"]:
            g = got.get(a)
            out.append((f"{a} → {g if g else '—'}", g == b))
    elif d["kind"] == "order":
        got = ans.get("order") or []
        for i, item in enumerate(d["items"]):
            g = got[i] if i < len(got) else None
            out.append((f"{i + 1}. {g if g else '—'}", g == item))
    else:
        got = ans.get("groups") or {}
        for g, items in d["groups"]:
            for it in items:
                sel = got.get(it)
                out.append((f"{it} → {sel if sel else '—'}", sel == g))
    return out


def grade_game(question: dict, submitted: str):
    points = float(question.get("points") or 1)
    res = game_results(question, submitted)
    if not res:
        return 0, "auto"
    right = sum(1 for _, ok in res if ok)
    if right == len(res):
        return points, "auto"
    score = round(points * right / len(res) * 2) / 2
    return score, "auto"
