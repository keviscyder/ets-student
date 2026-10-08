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


def find_student_in_class(supabase: Client, class_id: str, full_name: str):
    """Ieško mokinio pagal vardą/pavardę (case-insensitive) toje klasėje."""
    res = (
        supabase.table("students")
        .select("id, name")
        .eq("class_id", class_id)
        .ilike("name", _normalize_name(full_name))
        .execute()
    )
    return res.data[0] if res.data else None


def get_assignment_by_code(supabase: Client, session_code: str, class_id: str):
    res = (
        supabase.table("assignments")
        .select("id, test_id, class_id, opens_at, closes_at, duration_minutes, results_released, tests(title, description)")
        .eq("session_code", session_code.strip().upper())
        .eq("class_id", class_id)
        .execute()
    )
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
            "text_answer, image_url, score, teacher_comment, "
            "test_questions(order_idx, question_bank(prompt, prompt_image_url, points, type))"
        )
        .eq("submission_id", submission_id)
        .execute()
    )
    rows = res.data or []
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
    res = (
        supabase.table("test_questions")
        .select("id, order_idx, question_bank(*)")
        .eq("test_id", test_id)
        .order("order_idx")
        .execute()
    )
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
