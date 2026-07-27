"""
Automatinio tikrinimo logika MCQ/trumpo atsakymo klausimams.
"""


def auto_grade(question: dict, submitted_answer: str):
    """
    Grąžina (score, graded_by) arba (None, 'teacher'), jei negalima
    automatiškai įvertinti (pvz. image_upload tipas).
    """
    q_type = question["type"]
    points = question.get("points", 1)
    answer_key = (question.get("answer_key") or "").strip().lower()
    submitted = (submitted_answer or "").strip().lower()

    if q_type == "mcq":
        return (points if submitted == answer_key else 0), "auto"

    if q_type == "short_answer":
        return (points if submitted == answer_key else 0), "auto"

    # image_upload - mokytojas vertins rankiniu būdu
    return None, "teacher"
