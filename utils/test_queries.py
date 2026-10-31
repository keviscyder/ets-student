"""
Query helper'iai mokinio testavimo srautui (be auth, per session_code).
"""
import re
from datetime import datetime, timezone
from supabase import Client


def _normalize_name(name: str) -> str:
    name = name.replace("\xa0", " ").replace("\t", " ")
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def get_all_classes(supabase: Client):
    return supabase.table("classes").select("id, name").order("name").execute().data


_LT = str.maketrans("ąčęėįšųūž", "aceeisuuz")


def _name_tokens(name: str):
    """Vardo žodžiai be didžiųjų raidžių ir lietuviškų raidžių skirtumų."""
    return [t for t in _normalize_name(name).lower().translate(_LT).replace("-", " ").split(" ") if t]


def find_student_in_class(supabase: Client, class_id: str, full_name: str):
    """Ieško mokinio toje klasėje. Žodžių tvarka nesvarbi: tinka ir
    „Vardas Pavardė“, ir „Pavardė Vardas“ (sąraše dažnai pirma pavardė).
    Grąžintame įraše „display_name“ – vardas tokia tvarka, kokia įvesta."""
    typed = _name_tokens(full_name)
    if not typed:
        return None
    try:
        # accommodations – mokiniui pritaikyti nustatymai (šriftas, laikas, testo versija)
        rows = supabase.table("students").select("id, name, pin, accommodations").eq("class_id", class_id).execute().data or []
    except Exception:
        rows = supabase.table("students").select("id, name, pin").eq("class_id", class_id).execute().data or []
    for r in rows:
        stored = _name_tokens(r.get("name") or "")
        if sorted(stored) == sorted(typed):
            words = _normalize_name(r["name"]).split(" ")
            # sudėliojam žodžius ta tvarka, kuria įvedė mokinys
            order = {t: i for i, t in enumerate(typed)}
            if len(words) == len(stored):
                words = [w for _, w in sorted(zip(stored, words), key=lambda x: order.get(x[0], 99))]
            return {**r, "display_name": " ".join(words)}
    return None


_ASG_COLS = "id, test_id, class_id, opens_at, closes_at, duration_minutes, results_released, tests(title, description, show_formulas)"


def get_assignment_by_code(supabase: Client, session_code: str, class_id: str):
    def q(cols):
        return (
            supabase.table("assignments")
            .select(cols)
            .eq("session_code", session_code.strip().upper())
            .eq("class_id", class_id)
            .execute()
        )
    # student_ids – kam skirtas papildomas atsiskaitymas / perrašymas (tuščia = visai klasei)
    # pool_sizes – kiek klausimų iš kiekvienos grupės gauna mokinys
    # (jei duomenų bazėje stulpelių dar nėra – bandoma be jų)
    for cols in (_ASG_COLS.replace("show_formulas)", "show_formulas, pool_sizes)") + ", student_ids, kind, broadcast, broadcast_at",
                 _ASG_COLS.replace("show_formulas)", "show_formulas, pool_sizes)") + ", student_ids, kind",
                 _ASG_COLS.replace("show_formulas)", "show_formulas, pool_sizes)") + ", student_ids",
                 _ASG_COLS + ", student_ids", _ASG_COLS):
        try:
            res = q(cols)
            break
        except Exception:
            res = None
    if res is None:
        res = q(_ASG_COLS)
    return res.data[0] if res.data else None


def get_submission(supabase: Client, assignment_id: str, student_id: str):
    """Grąžina esamą mokinio bandymą (arba None), nieko nekuria."""
    res = (
        supabase.table("submissions")
        .select("*")
        .eq("assignment_id", assignment_id)
        .eq("student_id", student_id)
        .execute()
    )
    return res.data[0] if res.data else None


def get_submission_results(supabase: Client, submission_id: str):
    """
    Mokinio atsakymai su gautais balais ir mokytojo komentarais.
    Teisingi atsakymai (answer_key) sąmoningai neimami.
    """
    res = (
        supabase.table("answers")
        .select(
            "test_question_id, text_answer, image_url, score, teacher_comment, "
            "test_questions(order_idx, question_bank(prompt, prompt_image_url, points, type, options))"
        )
        .eq("submission_id", submission_id)
        .execute()
    )
    # Tas pats klausimas gali turėti kelias eilutes (nutrūkus ryšiui) – paliekam
    # vieną, pirmenybę teikiant užpildytai.
    best = {}
    for r in res.data or []:
        k = r.get("test_question_id") or id(r)
        o = best.get(k)
        if o is None or (not (o.get("text_answer") or o.get("image_url"))
                         and (r.get("text_answer") or r.get("image_url"))):
            best[k] = r
    rows = list(best.values())
    rows.sort(key=lambda r: r["test_questions"]["order_idx"])
    return rows


def get_or_create_submission(supabase: Client, assignment_id: str, student_id: str):
    existing = (
        supabase.table("submissions")
        .select("*")
        .eq("assignment_id", assignment_id)
        .eq("student_id", student_id)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    res = (
        supabase.table("submissions")
        .insert({
            "assignment_id": assignment_id,
            "student_id": student_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "in_progress",
        })
        .execute()
    )
    return res.data[0]


def get_test_questions_for_student(supabase: Client, test_id: str):
    def q(cols):
        return (
            supabase.table("test_questions")
            .select(cols)
            .eq("test_id", test_id)
            .order("order_idx")
            .execute()
        )
    try:
        res = q("id, order_idx, pool, question_bank(*)")   # pool – atsitiktinių variantų grupė
    except Exception:
        res = q("id, order_idx, question_bank(*)")
    return res.data


def save_answer(supabase: Client, submission_id: str, test_question_id: str, answer_data: dict):
    existing = (
        supabase.table("answers")
        .select("id")
        .eq("submission_id", submission_id)
        .eq("test_question_id", test_question_id)
        .execute()
    )
    if existing.data:
        return (
            supabase.table("answers")
            .update(answer_data)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    return (
        supabase.table("answers")
        .insert({**answer_data, "submission_id": submission_id, "test_question_id": test_question_id})
        .execute()
    )


def get_existing_answer_ids(supabase: Client, submission_id: str) -> dict:
    """{test_question_id: answer_id} jau išsaugotiems atsakymams (viena užklausa)."""
    res = (
        supabase.table("answers")
        .select("id, test_question_id")
        .eq("submission_id", submission_id)
        .execute()
    )
    return {r["test_question_id"]: r["id"] for r in (res.data or [])}


def insert_answers(supabase: Client, rows: list[dict]):
    """Įrašo kelis atsakymus viena užklausa."""
    if not rows:
        return None
    return supabase.table("answers").insert(rows).execute()


def update_answer(supabase: Client, answer_id: str, answer_data: dict):
    return (
        supabase.table("answers")
        .update(answer_data)
        .eq("id", answer_id)
        .execute()
    )


def mark_submission_submitted(supabase: Client, submission_id: str):
    return (
        supabase.table("submissions")
        .update({"status": "submitted", "submitted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", submission_id)
        .execute()
    )


def get_saved_answers(supabase: Client, submission_id: str) -> dict:
    """{test_question_id: {id, text_answer, image_url}} - jau išsaugoti atsakymai
    (naudojama atkurti atsakymus, jei ryšys nutrūko ar mokinys prisijungė iš naujo)."""
    res = (
        supabase.table("answers")
        .select("id, test_question_id, text_answer, image_url")
        .eq("submission_id", submission_id)
        .execute()
    )
    out = {}
    for r in (res.data or []):
        prev = out.get(r["test_question_id"])
        # Jei klausimui yra kelios eilutės (dubliai), imam užpildytą
        if prev is None or (_filled(r) and not _filled(prev)):
            out[r["test_question_id"]] = r
    return out


def _filled(r) -> bool:
    return bool((r.get("text_answer") or "").strip() or r.get("image_url"))


def update_submission_progress(supabase: Client, submission_id: str, data: dict):
    """Atnaujina bandymo eigos informaciją (last_seen, answered_count, tablet, leave_events)."""
    return (
        supabase.table("submissions")
        .update(data)
        .eq("id", submission_id)
        .execute()
    )



# ------------------------------------------------------------
# PRITAIKYMAI, TESTO VERSIJOS, PRANEŠIMAI (veikia tik jei DB jau yra stulpeliai)
# ------------------------------------------------------------

def find_variant_test(supabase: Client, test_id: str, kind: str):
    """Lengvesnė ar išversta testo versija (tests.variant_of = test_id). Grąžina (id, pool_sizes) arba None."""
    try:
        rows = (supabase.table("tests").select("id, pool_sizes").eq("variant_of", test_id).eq("variant_kind", kind)
                .execute().data or [])
        return (rows[0]["id"], rows[0].get("pool_sizes")) if rows else None
    except Exception:
        return None


def get_test_pool_sizes(supabase: Client, test_id: str):
    try:
        rows = supabase.table("tests").select("pool_sizes").eq("id", test_id).execute().data or []
        return rows[0].get("pool_sizes") if rows else None
    except Exception:
        return None


def set_submission_test(supabase: Client, submission_id: str, test_id: str) -> bool:
    try:
        supabase.table("submissions").update({"test_id": test_id}).eq("id", submission_id).execute()
        return True
    except Exception:
        return False


def get_broadcast(supabase: Client, assignment_id: str):
    try:
        rows = supabase.table("assignments").select("broadcast, broadcast_at").eq("id", assignment_id).execute().data or []
        return rows[0] if rows else None
    except Exception:
        return None
