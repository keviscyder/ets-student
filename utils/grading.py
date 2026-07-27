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


def auto_grade(question: dict, submitted_answer: str):
    """
    Grąžina (score, graded_by).
    graded_by == 'teacher' reiškia, kad reikia žmogaus peržiūros
    (arba tikrai negalima automatiškai vertinti, arba atsakymas
    "beveik teisingas", bet ne pakankamai tikras, kad automatiškai įskaityti).
    """
    q_type = question["type"]
    points = question.get("points", 1)
    submitted = _normalize(submitted_answer)

    if q_type == "mcq":
        answer_key = _normalize(question.get("answer_key"))
        return (points if submitted == answer_key else 0), "auto"

    if q_type == "short_answer":
        # answer_key gali turėti kelis priimtinus variantus, kiekvienas naujoje eilutėje
        raw_key = question.get("answer_key") or ""
        accepted_variants = [_normalize(v) for v in raw_key.split("\n") if v.strip()]
        if not accepted_variants:
            return 0, "auto"

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

