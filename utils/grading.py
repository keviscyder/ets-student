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


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _canon(text: str):
    """Tekstas su vienodai užrašytais skaičiais ir tų skaičių sąrašas.
    12,5 -> 12.5; 1 254 000 -> 1254000; 35.0 -> 35."""
    t = re.sub(r"(?<=\d),(?=\d)", ".", text)
    t = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))", "", t)
    nums = [float(x) for x in _NUM.findall(t)]
    t = _NUM.sub(lambda m: ("%.9f" % float(m.group())).rstrip("0").rstrip("."), t)
    return t, nums


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

        # Skaičiai turi sutapti tiksliai (12,5 = 12.5 = 12.50), rašybos klaidos
        # atleidžiamos tik žodžiams. Kitaip „Q = 386 kJ“ būtų įskaityta vietoj „Q = 336 kJ“.
        sub_c, sub_n = _canon(submitted)
        same, other = [], []
        for v in accepted_variants:
            v_c, v_n = _canon(v)
            if sub_c == v_c:
                return points, "auto"
            (same if v_n == sub_n else other).append(v_c)
        sim_same = _best_similarity(sub_c, same)
        sim_any = max(sim_same, _best_similarity(sub_c, other))

        if sim_same >= 0.9:
            # Tikėtina rašybos klaida žodyje, skaičiai tie patys - įskaitom automatiškai
            return points, "auto"
        elif sim_any >= 0.6:
            # Neaišku (arba kitas skaičius) - palieku mokytojui peržiūrėti, ne automatiškai 0
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
