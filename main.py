"""
ETS - Mokinio testavimo langas.
Paleidimas: streamlit run student_app/main.py
"""

import time
import random
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
    get_submission,
    get_submission_results,
)


st.set_page_config(
    page_title="ETS — Testavimas",
    page_icon="",
    layout="centered",
)

supabase = get_client()


# ============================================================
# SESIJOS BŪSENOS INICIALIZAVIMAS
# ============================================================

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


# ============================================================
# PAGALBINĖ FUNKCIJA
# ============================================================

def _shuffled_options(options, seed_key):
    """
    Deterministiškai sumaišo atsakymų variantus.

    Tas pats mokinys tam pačiam klausimui viso bandymo metu
    matys tą pačią variantų tvarką, tačiau skirtingi mokiniai
    gaus skirtingą tvarką.
    """
    rnd = random.Random(seed_key)
    shuffled = options.copy()
    rnd.shuffle(shuffled)
    return shuffled


def _fmt_points(x):
    """1.0 -> '1', 1.5 -> '1.5'."""
    x = float(x or 0)
    return str(int(x)) if x.is_integer() else f"{x:g}"


def _reset_to_start():
    for key in [
        "class_id", "student_id", "student_name",
        "assignment", "submission", "test_questions",
    ]:
        st.session_state[key] = None
    st.session_state.step = "select_class"


def _save_and_submit():
    """
    Išsaugo visus atsakymus ir pažymi testą pateiktu.

    Kviečiama kaip mygtuko on_click callback'as: Streamlit jo
    nepertraukia, net jei tuo metu suveikia automatinis lango
    atnaujinimas (st_autorefresh). Atsakymai imami iš
    st.session_state pagal valdiklių raktus.
    """
    submission = st.session_state.submission
    questions = st.session_state.test_questions

    for tq in questions:
        q = tq["question_bank"]
        ans = st.session_state.get(f"ans_{tq['id']}")

        if q["type"] == "image_upload":
            image_url = (
                upload_image(supabase, ans, folder="answers")
                if ans
                else None
            )
            save_answer(
                supabase,
                submission["id"],
                tq["id"],
                {
                    "image_url": image_url,
                    "score": None,
                    "graded_by": "teacher",
                },
            )
        else:
            text_ans = ans if ans else ""
            score, graded_by = auto_grade(q, text_ans)
            save_answer(
                supabase,
                submission["id"],
                tq["id"],
                {
                    "text_answer": text_ans,
                    "score": score,
                    "graded_by": graded_by,
                },
            )

    mark_submission_submitted(supabase, submission["id"])
    st.session_state.step = "submitted"


st.title("E-testavimas")


# ============================================================
# ŽINGSNIS 1: KLASĖS PASIRINKIMAS
# ============================================================

if st.session_state.step == "select_class":

    classes = get_all_classes(supabase)

    if not classes:
        st.error("Kol kas nėra sukurtų klasių.")
        st.stop()

    class_id = st.selectbox(
        "Pasirink savo klasę",
        options=[c["id"] for c in classes],
        format_func=lambda x: next(
            c["name"] for c in classes if c["id"] == x
        ),
    )

    if st.button("Toliau", type="primary"):
        st.session_state.class_id = class_id
        st.session_state.step = "enter_name"
        st.rerun()


# ============================================================
# ŽINGSNIS 2: VARDAS + PAVARDĖ
# ============================================================

elif st.session_state.step == "enter_name":

    full_name = st.text_input("Vardas Pavardė")

    if full_name:

        match = find_student_in_class(
            supabase,
            st.session_state.class_id,
            full_name,
        )

        if match:

            st.success(
                f"✅ {match['name']} — rasta klasės sąraše"
            )

            if st.button("Toliau", type="primary"):

                st.session_state.student_id = match["id"]
                st.session_state.student_name = match["name"]
                st.session_state.step = "enter_code"

                st.rerun()

        else:

            st.warning(
                "❌ Toks vardas nerastas šioje klasėje. "
                "Patikrink rašybą arba kreipkis į mokytoją."
            )

    if st.button("← Atgal"):

        st.session_state.step = "select_class"
        st.rerun()


# ============================================================
# ŽINGSNIS 3: SESIJOS KODAS
# ============================================================

elif st.session_state.step == "enter_code":

    st.write(
        f"Labas, **{st.session_state.student_name.split()[0]}**!"
    )

    code = st.text_input(
        "Įvesk mokytojo pasakytą testavimo kodą"
    )

    if st.button("Pradėti testą", type="primary") and code:

        assignment = get_assignment_by_code(
            supabase,
            code,
            st.session_state.class_id,
        )

        if not assignment:

            st.error(
                "Kodas neteisingas arba neatitinka tavo klasės."
            )

        else:

            existing = get_submission(
                supabase,
                assignment["id"],
                st.session_state.student_id,
            )

            if existing and existing["status"] == "submitted":

                if assignment.get("results_released"):

                    st.session_state.assignment = assignment
                    st.session_state.submission = existing
                    st.session_state.step = "results"
                    st.rerun()

                st.info(
                    "Tu jau atlikai šį testą. Rezultatus pamatysi, "
                    "kai mokytojas juos paskelbs."
                )
                st.stop()

            now = datetime.now(timezone.utc)

            opens = datetime.fromisoformat(
                assignment["opens_at"]
            )

            closes = datetime.fromisoformat(
                assignment["closes_at"]
            )

            if now < opens:

                st.warning("Testas dar neprasidėjo.")

            elif now > closes:

                st.error("Testo laikas jau pasibaigęs.")

            else:

                submission = get_or_create_submission(
                    supabase,
                    assignment["id"],
                    st.session_state.student_id,
                )

                if submission["status"] == "submitted":

                    st.info(
                        "Tu jau atlikai šį testą. "
                        "Rezultatai perduoti mokytojui."
                    )

                    st.stop()

                st.session_state.assignment = assignment

                st.session_state.submission = submission

                st.session_state.test_questions = (
                    get_test_questions_for_student(
                        supabase,
                        assignment["test_id"],
                    )
                )

                st.session_state.step = "taking_test"

                st.rerun()


# ============================================================
# ŽINGSNIS 4: TESTO ATLIKIMAS
# ============================================================

elif st.session_state.step == "taking_test":

    assignment = st.session_state.assignment
    submission = st.session_state.submission
    questions = st.session_state.test_questions

    # --------------------------------------------------------
    # AUTOMATINIS SERVERIO LAIKO PATIKRINIMAS
    # Kas 10 sekundžių atnaujinamas Streamlit langas.
    # --------------------------------------------------------

    st_autorefresh(
        interval=10_000,
        key="exam_timer_refresh",
    )

    started_at = datetime.fromisoformat(
        submission["started_at"]
    )

    deadline_ts = (
        started_at.timestamp()
        + assignment["duration_minutes"] * 60
    )

    remaining = deadline_ts - time.time()

    # --------------------------------------------------------
    # TESTO LAIKAS PASIBAIGĖ
    # --------------------------------------------------------

    if remaining <= 0:

        # Laikas baigėsi: išsaugom tai, ką mokinys spėjo atsakyti.
        with st.spinner("Laikas baigėsi. Pateikiami atsakymai..."):
            _save_and_submit()
        st.rerun()


    # --------------------------------------------------------
    # VIZUALUS LAIKMATIS
    # Skaičiuojamas naršyklėje, todėl serveris nėra apkraunamas
    # kas sekundę.
    # --------------------------------------------------------

    components.html(
        f"""
        <div id="timer"
             style="
                 font-size:20px;
                 font-weight:600;
                 font-family:sans-serif;
                 color:#333;
             ">
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

            const totalSec =
                Math.floor(remainingMs / 1000);

            const m =
                Math.floor(totalSec / 60)
                .toString()
                .padStart(2, '0');

            const s =
                (totalSec % 60)
                .toString()
                .padStart(2, '0');

            el.innerText =
                "⏱️ Liko laiko: " + m + ":" + s;
        }}

        tick();

        setInterval(tick, 1000);

        </script>
        """,
        height=40,
    )


    # --------------------------------------------------------
    # TESTO PAVADINIMAS
    # --------------------------------------------------------

    st.subheader(
        assignment["tests"]["title"]
    )


    # --------------------------------------------------------
    # ATSAKYMAI
    # --------------------------------------------------------

    answers = {}


    for tq in questions:

        q = tq["question_bank"]

        st.divider()

        st.markdown(
            f"**{q['prompt']}**  ({q['points']} tšk.)"
        )


        # ----------------------------------------------------
        # KLAUSIMO PAVEIKSLĖLIS
        # ----------------------------------------------------

        if q.get("prompt_image_url"):

            st.image(
                q["prompt_image_url"],
                width=350,
            )


        # ====================================================
        # MCQ
        # ====================================================

        if q["type"] == "mcq":

            # Kiekvienas klausimas kiekvienam mokiniui
            # gauna savo deterministinę variantų tvarką.
            #
            # submission ID užtikrina, kad skirtingi mokiniai
            # gaus skirtingą tvarką.
            #
            # tq ID užtikrina, kad kiekvienas klausimas turės
            # savo variantų maišymą.

            seed_key = (
                f"{submission['id']}_{tq['id']}"
            )

            shuffled_options = _shuffled_options(
                q["options"],
                seed_key,
            )

            answers[tq["id"]] = st.radio(
                "Pasirink atsakymą",
                shuffled_options,
                key=f"ans_{tq['id']}",
                index=None,
            )


        # ====================================================
        # TRUMPAS ATSAKYMAS
        # ====================================================

        elif q["type"] == "short_answer":

            answers[tq["id"]] = st.text_input(
                "Atsakymas",
                key=f"ans_{tq['id']}",
            )


        # ====================================================
        # NUOTRAUKOS ĮKĖLIMAS
        # ====================================================

        elif q["type"] == "image_upload":

            answers[tq["id"]] = st.file_uploader(
                "Įkelk sprendimo nuotrauką",
                type=[
                    "png",
                    "jpg",
                    "jpeg",
                ],
                key=f"ans_{tq['id']}",
            )


    # ========================================================
    # TESTO PATEIKIMAS
    # ========================================================

    st.divider()

    st.button(
        "✅ Pateikti testą",
        type="primary",
        on_click=_save_and_submit,
    )


# ============================================================
# ŽINGSNIS 5: PATEIKTA
# ============================================================

elif st.session_state.step == "submitted":

    st.success(
        "Testas pateiktas! Rezultatai bus perduoti mokytojui."
    )

    if st.button("Baigti"):
        _reset_to_start()
        st.rerun()


# ============================================================
# ŽINGSNIS 6: REZULTATAI (kai mokytojas paskelbia)
# ============================================================

elif st.session_state.step == "results":

    assignment = st.session_state.assignment
    submission = st.session_state.submission

    st.subheader(assignment["tests"]["title"])

    rows = get_submission_results(supabase, submission["id"])

    total = sum(float(r["score"] or 0) for r in rows)
    max_total = sum(
        float(r["test_questions"]["question_bank"]["points"] or 0) for r in rows
    )
    pending = sum(1 for r in rows if r["score"] is None)
    percent = round(100 * total / max_total) if max_total else 0

    st.metric(
        "Tavo rezultatas",
        f"{_fmt_points(total)} / {_fmt_points(max_total)} tšk.",
        f"{percent} %",
        delta_color="off",
    )

    if pending:
        st.info(
            f"Dar neįvertinta klausimų: {pending}. "
            "Galutinis balas gali pasikeisti."
        )

    for i, r in enumerate(rows, start=1):

        q = r["test_questions"]["question_bank"]

        st.divider()
        st.markdown(f"**{i}. {q['prompt']}**")

        if q.get("prompt_image_url"):
            st.image(q["prompt_image_url"], width=350)

        if q["type"] == "image_upload":
            if r.get("image_url"):
                st.image(r["image_url"], width=350, caption="Tavo sprendimas")
            else:
                st.caption("Sprendimas neįkeltas.")
        else:
            st.text(f"Tavo atsakymas: {r.get('text_answer') or '—'}")

        points = float(q["points"] or 0)

        if r["score"] is None:
            st.caption(f"Laukia įvertinimo (galima gauti {_fmt_points(points)} tšk.)")
        else:
            score = float(r["score"])
            if score >= points:
                mark = "✅"
            elif score <= 0:
                mark = "❌"
            else:
                mark = "🟡"
            st.markdown(
                f"{mark} **{_fmt_points(score)} / {_fmt_points(points)} tšk.**"
            )

        if r.get("teacher_comment"):
            st.caption(f"Mokytojo komentaras: {r['teacher_comment']}")

    st.divider()

    if st.button("Baigti", type="primary"):
        _reset_to_start()
        st.rerun()
