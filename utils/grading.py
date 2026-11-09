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
    12,5 -> 12.5; 1 254 000 -> 1254000; 35.0 -> 35; −5 -> -5;
    „Q = 336 kJ“ -> „336kj“ (dydžio pavadinimas prieš = ir tarpai nesvarbūs)."""
    t = (text or "").replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    t = t.replace("°", "").replace("\u00a0", " ").replace("\u202f", " ")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", t)
    # „Q =“, „t1=“, „m =“ ... atsakymo pradžioje
    t = re.sub(r"^\s*[a-ząčęėįšųūžα-ω]{1,4}[0-9]{0,2}\s*=\s*", "", t)
    nums = [float(x) for x in _NUM.findall(t)]
    t = _NUM.sub(lambda m: ("%.9f" % float(m.group())).rstrip("0").rstrip("."), t)
    t = re.sub(r"\s+", "", t)
    return t, nums


def _best_similarity(submitted: str, accepted_variants: list[str]) -> float:
    return max(
        (difflib.SequenceMatcher(None, submitted, v).ratio() for v in accepted_variants),
        default=0.0,
    )


def accepted_answers(question: dict) -> list[str]:
    """Priimtini trumpo atsakymo variantai (be rubrikos eilučių, prasidedančių #)."""
    raw_key = question.get("answer_key") or ""
    out = []
    for line in raw_key.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        # Keli variantai vienoje eilutėje: „336 kJ; 336000 J“ arba „a | b“
        out += [_normalize(v) for v in re.split(r"[;|]", line) if v.strip()]
    return out


def is_open_question(question: dict) -> bool:
    """Trumpo atsakymo klausimas be teisingų atsakymų = atviras (vertina mokytojas)."""
    return question.get("type") == "short_answer" and not accepted_answers(question) and not is_calc(question)


def auto_grade(question: dict, submitted_answer: str):
    """
    Grąžina (score, graded_by).
    graded_by == 'teacher' reiškia, kad reikia žmogaus peržiūros
    (arba tikrai negalima automatiškai vertinti, arba atsakymas
    "beveik teisingas", bet ne pakankamai tikras, kad automatiškai įskaityti).
    """
    q_type = question["type"]
    if q_type == "lab":
        # Laboratorinio darbo dalį vertina mokytojas; informacinė dalis (0 tšk.) – iškart 0.
        return (0, "auto") if not float(question.get("points") or 0) else (None, "teacher")
    if q_type == "game":
        return grade_game(question, submitted_answer or "")
    points = question.get("points", 1)
    submitted = _normalize(submitted_answer)

    if q_type == "mcq":
        answer_key = _normalize(question.get("answer_key"))
        return (points if submitted == answer_key else 0), "auto"

    if q_type == "short_answer" and is_calc(question):
        return grade_calc(question, submitted_answer, question.get("_seed"))

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
            # Teisingas atsakymas – tik skaičius, mokinys pridėjo vienetus („336“ → „336 kJ“)
            if v_n and v_n == sub_n and not re.search(r"[^\d.\-]", v_c) and len(sub_n) == 1:
                return points, "auto"
            (same if v_n == sub_n else other).append(v_c)
        sim_same = _best_similarity(sub_c, same)
        sim_any = max(sim_same, _best_similarity(sub_c, other))

        if sim_same >= 0.9:
            # Tikėtina rašybos klaida žodyje, skaičiai tie patys - įskaitom automatiškai
            return points, "auto"
        elif sim_any >= 0.6 or (same and sub_n):
            # (skaičiai sutampa, bet kiti vienetai ar žodžiai – sprendžia mokytojas)
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


# ------------------------------------------------------------
# UŽDAVINIAI SU ATSITIKTINIAIS SKAIČIAIS
# type = "short_answer", options = {"calc": {"vars": {"m": [2, 5, 0.5], ...},
#   "formula": "4.2*m*(t2-t1)", "decimals": 1, "tol": 1, "unit": "kJ"}}
# Klausimo tekste kintamieji rašomi {m}. Kiekvienas mokinys gauna savo
# skaičius (pagal bandymo ir klausimo id), atsakymą sistema apskaičiuoja pati.
# ------------------------------------------------------------

import ast as _ast
import math as _math
import random as _random

_CALC_FUNCS = {"sqrt": _math.sqrt, "sin": lambda x: _math.sin(_math.radians(x)),
               "cos": lambda x: _math.cos(_math.radians(x)), "tan": lambda x: _math.tan(_math.radians(x)),
               "abs": abs, "log": _math.log10, "ln": _math.log, "exp": _math.exp, "round": round}
_CALC_CONST = {"pi": _math.pi, "g": 9.8}


def calc_spec(q):
    o = q.get("options")
    return o.get("calc") if isinstance(o, dict) and isinstance(o.get("calc"), dict) else None


def is_calc(q) -> bool:
    return q.get("type") == "short_answer" and calc_spec(q) is not None


def safe_eval(expr: str, values: dict) -> float:
    """Apskaičiuoja formulę: tik skaičiai, kintamieji, + - * / ** ( ) ir kelios funkcijos."""
    tree = _ast.parse((expr or "").replace("^", "**").replace("·", "*").replace(",", "."), mode="eval")

    def ev(n):
        if isinstance(n, _ast.Expression):
            return ev(n.body)
        if isinstance(n, _ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, _ast.Name):
            if n.id in values:
                return float(values[n.id])
            if n.id in _CALC_CONST:
                return _CALC_CONST[n.id]
            raise ValueError(f"Nežinomas kintamasis: {n.id}")
        if isinstance(n, _ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            ops = {_ast.Add: lambda: a + b, _ast.Sub: lambda: a - b, _ast.Mult: lambda: a * b,
                   _ast.Div: lambda: a / b, _ast.Pow: lambda: a ** b}
            for t, f in ops.items():
                if isinstance(n.op, t):
                    return f()
        if isinstance(n, _ast.UnaryOp) and isinstance(n.op, (_ast.USub, _ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, _ast.USub) else v
        if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name) and n.func.id in _CALC_FUNCS and not n.keywords:
            return float(_CALC_FUNCS[n.func.id](*[ev(a) for a in n.args]))
        raise ValueError("Neleistina formulės dalis")
    return ev(tree)


def calc_values(q, seed: str) -> dict:
    """Mokinio skaičiai: kiekvienam kintamajam [nuo, iki, žingsnis]."""
    spec = calc_spec(q) or {}
    rnd = _random.Random(f"calc_{seed}")
    out = {}
    for name, rng in (spec.get("vars") or {}).items():
        try:
            lo, hi = float(rng[0]), float(rng[1])
            step = float(rng[2]) if len(rng) > 2 and float(rng[2]) > 0 else 1.0
        except Exception:
            continue
        n = int(round((hi - lo) / step)) if hi > lo else 0
        v = lo + step * rnd.randint(0, max(n, 0))
        out[name] = round(v, 6)
    return out


def _num_lt(x, decimals=None):
    if decimals is not None:
        x = round(x, int(decimals))
    s = ("%.6f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def calc_answer(q, seed: str):
    """(teisingas_atsakymas, mokinio_skaičiai) arba (None, skaičiai), jei formulė klaidinga."""
    spec = calc_spec(q) or {}
    vals = calc_values(q, seed)
    try:
        return safe_eval(spec.get("formula", ""), vals), vals
    except Exception:
        return None, vals


def calc_prompt(q, seed: str) -> str:
    """Klausimo tekstas su mokinio skaičiais vietoje {m}."""
    vals = calc_values(q, seed)
    text = q.get("prompt") or ""
    for k, v in vals.items():
        text = text.replace("{" + k + "}", _num_lt(v))
    return text


def calc_expected_text(q, seed: str) -> str:
    spec = calc_spec(q) or {}
    ans, vals = calc_answer(q, seed)
    if ans is None:
        return "formulės klaida"
    unit = spec.get("unit") or ""
    return f"{_num_lt(ans, spec.get('decimals', 2))} {unit}".strip()


def grade_calc(q, submitted: str, seed: str):
    points = q.get("points", 1)
    if not seed:
        return None, "teacher"
    spec = calc_spec(q) or {}
    ans, _ = calc_answer(q, seed)
    if ans is None:
        return None, "teacher"
    _c, nums = _canon(_normalize(submitted))
    if not nums:
        return (0, "auto") if not (submitted or "").strip() else (None, "teacher")
    got = nums[-1] if len(nums) > 1 and re.search(r"=", submitted or "") else nums[0]
    tol = abs(float(spec.get("tol", 1))) / 100.0
    ok = lambda v: abs(v - ans) <= max(abs(ans) * tol, 10 ** -(int(spec.get("decimals", 2)) + 1))
    if ok(got):
        return points, "auto"
    if any(ok(got * f) for f in (1000, 0.001, 100, 0.01)):
        return None, "teacher"   # gal kiti vienetai (J ↔ kJ) – sprendžia mokytojas
    return 0, "auto"


# ------------------------------------------------------------
# ATSITIKTINIAI VARIANTAI: iš klausimų grupės kiekvienam mokiniui
# parenkama po N klausimų (tests.pool_sizes = {"A": 10}, test_questions.pool = "A").
# ------------------------------------------------------------

def select_questions(tqs: list, pool_sizes, seed: str) -> list:
    """Kurie testo klausimai tenka šiam mokiniui (tvarka išlaikoma).
    Klausimai be grupės rodomi visiems."""
    sizes = pool_sizes if isinstance(pool_sizes, dict) else {}
    chosen = set()
    groups = {}
    for tq in tqs:
        p = (tq.get("pool") or "").strip()
        if p and int(sizes.get(p) or 0) > 0:
            groups.setdefault(p, []).append(tq["id"])
        else:
            chosen.add(tq["id"])
    for p, ids in groups.items():
        n = min(int(sizes[p]), len(ids))
        chosen.update(_random.Random(f"pool_{seed}_{p}").sample(sorted(ids), n))
    return [tq for tq in tqs if tq["id"] in chosen]


def with_seed(q: dict, submission_id, test_question_id) -> dict:
    """Uždaviniui su atsitiktiniais skaičiais pridedama mokinio „sėkla“."""
    return {**q, "_seed": f"{submission_id}_{test_question_id}"} if is_calc(q) else q
