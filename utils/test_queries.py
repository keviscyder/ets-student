"""
Query helper'iai mokinio testavimo srautui (be auth, per session_code).
"""
from datetime import datetime, timezone
from supabase import Client


def get_all_classes(supabase: Client):
    return supabase.table("classes").select("id, name").order("name").execute().data


def find_student_in_class(supabase: Client, class_id: str, full_name: str):
    """Ieško mokinio pagal vardą/pavardę (case-insensitive) toje klasėje."""
    res = (
        supabase.table("students")
        .select("id, name")
        .eq("class_id", class_id)
        .ilike("name", full_name.strip())
        .execute()
    )
    return res.data[0] if res.data else None


def get_assignment_by_code(supabase: Client, session_code: str, class_id: str):
    res = (
        supabase.table("assignments")
        .select("id, test_id, class_id, opens_at, closes_at, duration_minutes, tests(title, description)")
        .eq("session_code", session_code.strip().upper())
        .eq("class_id", class_id)
        .execute()
    )
    return res.data[0] if res.data else None


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


def mark_submission_submitted(supabase: Client, submission_id: str):
    return (
        supabase.table("submissions")
        .update({"status": "submitted", "submitted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", submission_id)
        .execute()
    )
