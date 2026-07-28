"""
ETS - Mokinio testavimo langas.
Paleidimas: streamlit run student_app/main.py
"""
import time
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from utils.db import get_client
from utils.storage import upload_image
from utils.grading import auto_grade
from utils.test_queries import (
    get_all_classes,
    find_student_in_class,
    get_assignment_by_code,
    get_or_create_submission,
    get_test_questions_for_student,
    save_answer,
    mark_submission_submitted,
)

st.set_page_config(page_title="ETS — Testavimas", page_icon="✍️", layout="centered")

supabase = get_client()

# --- Sesijos būsenos inicializavimas ---
for key, default in [
    ("step", "select_class"),
    ("class_id", None),
    ("student_id", None),
    ("student_name", None),
    ("assignment", None),
    ("submission", None),
    ("test_questions", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("✍️ E-testavimas")

# === ŽINGSNIS 1: Klasės pasirinkimas ===
if st.session_state.step == "select_class":
    classes = get_all_classes(supabase)
    if not classes:
        st.error("Kol kas nėra sukurtų klasių.")
        st.stop()

    class_id = st.selectbox(
        "Pasirink savo klasę",
        options=[c["id"] for c in classes],
        format_func=lambda x: next(c["name"] for c in classes if c["id"] == x),
    )

    if st.button("Toliau", type="primary"):
        st.session_state.class_id = class_id
        st.session_state.step = "enter_name"
        st.rerun()

# === ŽINGSNIS 2: Vardas + pavardė su patvirtinimu ===
elif st.session_state.step == "enter_name":
    full_name = st.text_input("Vardas Pavardė")

    if full_name:
        match = find_student_in_class(supabase, st.session_state.class_id, full_name)
        if match:
            st.success(f"✅ {match['name']} — rasta klasės sąraše")
            if st.button("Toliau", type="primary"):
                st.session_state.student_id = match["id"]
                st.session_state.student_name = match["name"]
                st.session_state.step = "enter_code"
                st.rerun()
        else:
            st.warning("❌ Toks vardas nerastas šioje klasėje. Patikrink rašybą arba kreipkis į mokytoją.")

    if st.button("← Atgal"):
        st.session_state.step = "select_class"
        st.rerun()

# === ŽINGSNIS 3: Sesijos kodas ===
elif st.session_state.step == "enter_code":
    st.write(f"Sveikas, **{st.session_state.student_name}**!")
    code = st.text_input("Įvesk mokytojo pasakytą testavimo kodą")

    if st.button("Pradėti testą", type="primary") and code:
        assignment = get_assignment_by_code(supabase, code, st.session_state.class_id)
        if not assignment:
            st.error("Kodas neteisingas arba neatitinka tavo klasės.")
        else:
            now = datetime.now(timezone.utc)
            opens = datetime.fromisoformat(assignment["opens_at"])
            closes = datetime.fromisoformat(assignment["closes_at"])
            if now < opens:
                st.warning("Testas dar neprasidėjo.")
            elif now > closes:
                st.error("Testo laikas jau pasibaigęs.")
            else:
                submission = get_or_create_submission(
                    supabase, assignment["id"], st.session_state.student_id
                )
                if submission["status"] == "submitted":
                    st.info("Tu jau atlikai šį testą. Rezultatai perduoti mokytojui.")
                    st.stop()

                st.session_state.assignment = assignment
                st.session_state.submission = submission
                st.session_state.test_questions = get_test_questions_for_student(
                    supabase, assignment["test_id"]
                )
                st.session_state.step = "taking_test"
                st.rerun()

# === ŽINGSNIS 4: Testo atlikimas ===
elif st.session_state.step == "taking_test":
    assignment = st.session_state.assignment
    submission = st.session_state.submission
    questions = st.session_state.test_questions

    # Serveris tikrina laiką tik kas 10s (ne kas sekundę) - žymiai mažiau
    # apkrauna serverį, kai daug mokinių laiko testą tuo pačiu metu.
    st_autorefresh(interval=10_000, key="exam_timer_refresh")

    started_at = datetime.fromisoformat(submission["started_at"])
    deadline_ts = started_at.timestamp() + assignment["duration_minutes"] * 60
    remaining = deadline_ts - time.time()

    if remaining <= 0:
        st.session_state.step = "submitted"
        st.rerun()

    # Vizualus laikmatis skaičiuojamas naršyklėje (JavaScript) - neapkrauna
    # serverio kas sekundę, tik parodo tikslų atskaitymą tarp serverio patikrinimų.
    components.html(
        f"""
        <div id="timer" style="font-size:20px; font-weight:600; font-family:sans-serif; color:#333;">
          ⏱️ Liko laiko: --:--
        </div>
        <script>
          const deadline = {deadline_ts * 1000};
          function tick() {{
            const remainingMs = deadline - Date.now();
            const el = document.getElementById('timer');
            if (remainingMs <= 0) {{
              el.innerText = "⏱️ Laikas baigėsi";
              return;
            }}
            const totalSec = Math.floor(remainingMs / 1000);
            const m = Math.floor(totalSec / 60).toString().padStart(2, '0');
            const s = (totalSec % 60).toString().padStart(2, '0');
            el.innerText = "⏱️ Liko laiko: " + m + ":" + s;
          }}
          tick();
          setInterval(tick, 1000);
        </script>
        """,
        height=40,
    )

    st.subheader(assignment["tests"]["title"])

    answers = {}
    for tq in questions:
        q = tq["question_bank"]
        st.divider()
        st.markdown(f"**{q['prompt']}**  ({q['points']} tšk.)")
        if q.get("prompt_image_url"):
            st.image(q["prompt_image_url"], width=350)

        if q["type"] == "mcq":
            answers[tq["id"]] = st.radio(
                "Pasirink atsakymą", q["options"], key=f"ans_{tq['id']}", index=None
            )
        elif q["type"] == "short_answer":
            answers[tq["id"]] = st.text_input("Atsakymas", key=f"ans_{tq['id']}")
        elif q["type"] == "image_upload":
            answers[tq["id"]] = st.file_uploader(
                "Įkelk sprendimo nuotrauką", type=["png", "jpg", "jpeg"], key=f"ans_{tq['id']}"
            )

    st.divider()
    if st.button("✅ Pateikti testą", type="primary"):
        for tq in questions:
            q = tq["question_bank"]
            ans = answers.get(tq["id"])

            if q["type"] == "image_upload":
                image_url = upload_image(supabase, ans, folder="answers") if ans else None
                save_answer(supabase, submission["id"], tq["id"], {
                    "image_url": image_url,
                    "score": None,
                    "graded_by": "teacher",
                })
            else:
                text_ans = ans if ans else ""
                score, graded_by = auto_grade(q, text_ans)
                save_answer(supabase, submission["id"], tq["id"], {
                    "text_answer": text_ans,
                    "score": score,
                    "graded_by": graded_by,
                })

        mark_submission_submitted(supabase, submission["id"])
        st.session_state.step = "submitted"
        st.rerun()

# === ŽINGSNIS 5: Pateikta ===
elif st.session_state.step == "submitted":
    st.success("🎉 Testas pateiktas! Rezultatai bus perduoti mokytojui.")
