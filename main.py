"""
ETS - Mokinio testavimo langas.
Paleidimas: streamlit run student_app/main.py
"""

import time
import random
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components

from utils.db import get_client
from utils.storage import upload_image
from utils.sketch import sketch_pad
import base64
import io
# Streamlit Cloud po atnaujinimo gali laikyti seną modulio versiją (ImportError)
import importlib
import utils.grading as _grading
import utils.test_queries as _test_queries
importlib.reload(_grading)
importlib.reload(_test_queries)
from utils.grading import auto_grade, is_open_question
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
    get_existing_answer_ids,
    insert_answers,
    update_answer,
    get_saved_answers,
    update_submission_progress,
)
import json
import re


from pathlib import Path
from PIL import Image as _PILImage

st.set_page_config(
    page_title="E-testavimas",
    page_icon=_PILImage.open(Path(__file__).parent / "logo.png"),
    layout="centered",
)


# ============================================================
# ŠVARUS VAIZDAS MOKINIAMS
# Paslepiam Streamlit įrankių juostą ir meniu, o vietoj paslėpto
# Streamlit krovimo ženklo rodom savo krovimo juostą viršuje.
# ============================================================

st.markdown(
    """
    <style>
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer {
        display: none !important;
    }
    .block-container {
        padding-top: 2rem;
    }
    /* Krovimo juosta: rodoma, kol programa apdoroja veiksmą. */
    .stApp:has([data-stale="true"])::before,
    [data-testid="stApp"]:has([data-stale="true"])::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        z-index: 999999;
        background: linear-gradient(90deg, transparent, #ff4b4b, transparent);
        background-size: 40% 100%;
        background-repeat: no-repeat;
        animation: ets-loading 1s linear infinite;
    }
    @keyframes ets-loading {
        from { background-position: -40% 0; }
        to   { background-position: 140% 0; }
    }
    </style>
    """,
    unsafe_allow_html=True,
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


def _client_info():
    """Planšetės numeris ir programėlės versija iš naršyklės User-Agent
    (programėlė prideda "ETSApp/1.4 Tablet/12")."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:
        ua = ""
    app = re.search(r"ETSApp/([\w.]+)", ua)
    tab = re.search(r"Tablet/([\w-]+)", ua)
    return {
        "app": app.group(1) if app else None,
        "tablet": tab.group(1) if tab else None,
    }


def _order_questions(questions, seed):
    """Kiekvienam mokiniui klausimai kita tvarka (bet visada ta pati tam pačiam
    mokiniui). Sprendimo nuotraukų uždaviniai paliekami gale."""
    normal = [tq for tq in questions if tq["question_bank"]["type"] != "image_upload"]
    photos = [tq for tq in questions if tq["question_bank"]["type"] == "image_upload"]
    random.Random(f"order_{seed}").shuffle(normal)
    return normal + photos


def _prepare_test_state(submission, questions):
    """Pradedant (ar tęsiant) testą: sumaišo klausimus ir atkuria jau
    išsaugotus atsakymus (pvz., jei nutrūko ryšys ar mokinys prisijungė iš naujo)."""
    saved_rows = get_saved_answers(supabase, submission["id"])
    st.session_state._answer_ids = {k: v["id"] for k, v in saved_rows.items()}
    st.session_state._saved = {}
    st.session_state._restored_img = {}
    for tq in questions:
        q = tq["question_bank"]
        row = saved_rows.get(tq["id"])
        if not row:
            continue
        if q["type"] == "image_upload":
            if row.get("image_url"):
                st.session_state._saved[tq["id"]] = ("img", "restored")
                st.session_state._restored_img[tq["id"]] = row["image_url"]
            continue
        text = row.get("text_answer") or ""
        st.session_state._saved[tq["id"]] = text
        if text and (q["type"] != "mcq" or text in (q.get("options") or [])):
            st.session_state[f"ans_{tq['id']}"] = text
    st.session_state._leaves = list(submission.get("leave_events") or [])
    return _order_questions(questions, submission["id"])


def _merge_leave_log():
    """Prijungia naujus išėjimo iš testo įvykius (iš naršyklės) prie išsaugotų.
    Grąžina True, jei atsirado naujų."""
    raw = st.session_state.get("ets_leave_log") or ""
    try:
        events = json.loads(raw).get("leaves", []) if raw else []
    except Exception:
        events = []
    known = {e.get("out") for e in st.session_state.get("_leaves", [])}
    new = [e for e in events if isinstance(e, dict) and e.get("out") and e.get("out") not in known]
    if new:
        st.session_state._leaves = st.session_state.get("_leaves", []) + new
    return bool(new)


def _drawing_changed(tq_id):
    """Ar ranka rašytas lapas pasikeitė nuo paskutinio išsaugojimo."""
    key = f"draw_{tq_id}"
    if key not in st.session_state:
        return False
    drawing = st.session_state.get(key)
    prev = st.session_state.get("_saved", {}).get(tq_id)
    if drawing and drawing.get("n"):
        return prev != ("draw", drawing.get("n"))
    # lapas išvalytas - jei anksčiau buvo išsaugotas piešinys, ištrinam
    return isinstance(prev, tuple) and prev[0] == "draw"


def _autosave():
    """Išsaugo pasikeitusius atsakymus ir bandymo eigą (paskutinį aktyvumą,
    atsakytų klausimų skaičių, planšetę, išėjimus iš testo).
    Kviečiama prie kiekvieno mokinio veiksmo ir periodiškai."""
    if st.session_state.get("step") != "taking_test":
        return
    submission = st.session_state.submission
    questions = st.session_state.test_questions or []
    saved = st.session_state.setdefault("_saved", {})
    ids = st.session_state.setdefault("_answer_ids", {})
    to_insert = []

    for tq in questions:
        q = tq["question_bank"]
        key = f"ans_{tq['id']}"
        if key not in st.session_state and f"draw_{tq['id']}" not in st.session_state:
            continue
        ans = st.session_state.get(key)

        if q["type"] == "image_upload" and _drawing_changed(tq["id"]):
            drawing = st.session_state.get(f"draw_{tq['id']}")
            url = None
            if drawing and drawing.get("data"):
                raw = base64.b64decode(drawing["data"].split(",", 1)[1])
                url = upload_image(supabase, io.BytesIO(raw), folder="answers")
                st.session_state.setdefault("_img_urls", {})[tq["id"]] = url
            data = {"text_answer": None, "image_url": url, "score": None, "graded_by": "teacher"}
            saved[tq["id"]] = ("draw", drawing.get("n")) if drawing else ""
        elif q["type"] == "image_upload":
            if ans is None:
                continue
            fid = getattr(ans, "file_id", None) or f"{getattr(ans, 'name', '')}_{getattr(ans, 'size', '')}"
            if saved.get(tq["id"]) == ("img", fid):
                continue
            data = {
                "text_answer": None,
                "image_url": upload_image(supabase, ans, folder="answers"),
                "score": None,
                "graded_by": "teacher",
            }
            saved[tq["id"]] = ("img", fid)
            st.session_state.setdefault("_restored_img", {}).pop(tq["id"], None)
        else:
            text = ans or ""
            if saved.get(tq["id"]) == text or (text == "" and tq["id"] not in saved):
                continue
            score, graded_by = auto_grade(q, text)
            data = {"text_answer": text, "image_url": None, "score": score, "graded_by": graded_by}
            saved[tq["id"]] = text

        if tq["id"] in ids:
            update_answer(supabase, ids[tq["id"]], data)
        else:
            to_insert.append({**data, "submission_id": submission["id"], "test_question_id": tq["id"]})

    if to_insert:
        res = insert_answers(supabase, to_insert)
        for r in (res.data or []) if res is not None else []:
            ids[r["test_question_id"]] = r["id"]

    progress = {
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "answered_count": sum(1 for v in saved.values() if v not in ("", None)),
    }
    info = _client_info()
    if info["tablet"] and st.session_state.get("_tablet_saved") != submission["id"]:
        progress["tablet"] = info["tablet"]
        st.session_state._tablet_saved = submission["id"]
    if _merge_leave_log():
        progress["leave_events"] = st.session_state._leaves
    try:
        update_submission_progress(supabase, submission["id"], progress)
    except Exception:
        pass


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
    st.session_state.submit_requested = False
    st.session_state.step = "select_class"


def _request_submit():
    """Mygtuko callback'as: tik pažymi, kad reikia pateikti testą.
    Pats saugojimas vyksta puslapyje, kad mokinys matytų užrašą
    "Pateikiama...". Žymė išlieka sesijoje, todėl net jei veiksmas
    nutrūktų, kitas perkrovimas pateikimą užbaigs."""
    st.session_state.submit_requested = True


def _save_and_submit():
    """
    Išsaugo visus atsakymus ir pažymi testą pateiktu.

    Kviečiama kaip mygtuko on_click callback'as. Atsakymai imami iš
    st.session_state pagal valdiklių raktus. Duomenų bazei daromos tik
    kelios užklausos (ne po dvi kiekvienam klausimui), todėl veikia
    greitai net su daug klausimų ir daug mokinių vienu metu.
    """
    # Apsauga nuo pakartotinio paspaudimo.
    if st.session_state.get("step") == "submitted":
        return

    submission = st.session_state.submission
    questions = st.session_state.test_questions

    # Pirma išsaugom viską, kas pasikeitė (ir nuotraukas).
    _autosave()

    # Klausimams, į kuriuos mokinys neatsakė, įrašom tuščią atsakymą,
    # kad mokytojas matytų visus klausimus.
    ids = st.session_state.get("_answer_ids", {})
    existing = get_existing_answer_ids(supabase, submission["id"])
    to_insert = []
    for tq in questions:
        if tq["id"] in ids or tq["id"] in existing:
            continue
        q = tq["question_bank"]
        if q["type"] == "image_upload":
            data = {"text_answer": None, "image_url": None, "score": None, "graded_by": "teacher"}
        else:
            score, graded_by = auto_grade(q, "")
            data = {"text_answer": "", "image_url": None, "score": score, "graded_by": graded_by}
        to_insert.append({**data, "submission_id": submission["id"], "test_question_id": tq["id"]})

    insert_answers(supabase, to_insert)
    mark_submission_submitted(supabase, submission["id"])
    st.session_state.step = "submitted"

st.title("E-testavimas")

_info = _client_info()
if _info["app"] or _info["tablet"]:
    _label = " · ".join(
        x for x in [
            f"Planšetė {_info['tablet']}" if _info["tablet"] else None,
            f"v{_info['app']}" if _info["app"] else None,
        ] if x
    )
    st.markdown(
        f"""<div style="position:fixed;right:10px;bottom:6px;font-size:12px;
        color:#888;z-index:1000;">{_label}</div>""",
        unsafe_allow_html=True,
    )


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

            pin_ok = True
            if match.get("pin"):
                pin = st.text_input(
                    "Tavo asmeninis kodas",
                    type="password",
                    max_chars=8,
                    help="Kodą tau davė mokytojas.",
                )
                pin_ok = pin.strip() == str(match["pin"]).strip()
                if pin and not pin_ok:
                    st.error("Neteisingas asmeninis kodas.")

            if st.button("Toliau", type="primary", disabled=not pin_ok):

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

        with st.spinner("Kraunamas testas..."):

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

                    st.session_state.test_questions = _prepare_test_state(
                        submission,
                        get_test_questions_for_student(
                            supabase,
                            assignment["test_id"],
                        ),
                    )

                    st.session_state.submit_requested = False
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
    # PATEIKIMAS (paspaudus mygtuką)
    # --------------------------------------------------------

    if st.session_state.get("submit_requested"):
        with st.spinner("Pateikiama... Neuždaryk lango."):
            _save_and_submit()
        st.session_state.submit_requested = False
        st.rerun()

    # --------------------------------------------------------
    # AUTOMATINIS IŠSAUGOJIMAS
    # Kiekvienas mokinio veiksmas (atsakymo pakeitimas) iškart
    # išsaugomas, o kas 45 s atnaujinama eiga mokytojo stebėsenai.
    # Nutrūkus ryšiui atsakymai neprarandami.
    # --------------------------------------------------------

    _autosave()

    @st.fragment(run_every=45)
    def _heartbeat():
        _autosave()

    _heartbeat()

    # --------------------------------------------------------
    # IŠĖJIMO IŠ TESTO FIKSAVIMAS
    # Naršyklė praneša, kai testo langas paslepiamas (kita programa,
    # kitas skirtukas). Grįžus įvykis perduodamas į paslėptą lauką.
    # Fotografuojant sprendimą išėjimas neskaičiuojamas.
    # --------------------------------------------------------


    # --------------------------------------------------------
    # LAIKO PATIKRINIMAS
    # Serveris laiką tikrina prie kiekvieno mokinio veiksmo.
    # Periodinio viso lango perkrovimo nebėra: jis apkraudavo
    # serverį ir praryja "Pateikti" paspaudimus. Pasibaigus laikui
    # naršyklės laikmatis pats paspaudžia "Pateikti testą".
    # --------------------------------------------------------

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

                el.innerText = "⏱️ Laikas baigėsi. Pateikiama...";

                // Automatiškai paspaudžiam "Pateikti testą" (vieną kartą).
                if (!window.__autoSubmitted) {{
                    try {{
                        const btn = Array.from(
                            window.parent.document.querySelectorAll('button')
                        ).find(b => b.innerText.includes('Pateikti testą'));
                        if (btn) {{
                            window.__autoSubmitted = true;
                            btn.click();
                        }}
                    }} catch (e) {{}}
                }}

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

            if (totalSec <= 60) {{
                el.style.color = "#dc2626";
                el.innerText += "  – paskutinė minutė! Pateik testą.";
            }} else if (totalSec <= 300) {{
                el.style.color = "#d97706";
                el.innerText += "  – liko mažiau nei 5 min.";
            }}
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

            if is_open_question(q):
                # Atviras klausimas - mokinys rašo paaiškinimą, vertina mokytojas
                answers[tq["id"]] = st.text_area(
                    "Atsakymas",
                    key=f"ans_{tq['id']}",
                    height=130,
                    placeholder="Parašyk atsakymą ir paaiškinimą",
                )
            else:
                answers[tq["id"]] = st.text_input(
                    "Atsakymas",
                    key=f"ans_{tq['id']}",
                )


        # ====================================================
        # NUOTRAUKOS ĮKĖLIMAS
        # ====================================================

        elif q["type"] == "image_upload":

            st.caption("✍️ Spręsk čia: rašyk pirštu arba rašikliu. Lapas išsaugomas automatiškai.")
            sketch_pad(
                key=f"draw_{tq['id']}",
                initial_url=(
                    st.session_state.get("_img_urls", {}).get(tq["id"])
                    or st.session_state.get("_restored_img", {}).get(tq["id"])
                ),
            )

            with st.expander("Arba nufotografuok sprendimą iš sąsiuvinio"):
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
        on_click=_request_submit,
    )

    st.text_input("ets_leave_log", key="ets_leave_log", label_visibility="collapsed")
    st.markdown(
        """<style>div[data-testid="stTextInput"]:has(input[aria-label="ets_leave_log"])
        {display:none !important;}</style>""",
        unsafe_allow_html=True,
    )
    components.html(
        """
        <script>
        (function () {
          var P = window.parent;
          // Paslepiam techninį lauką ir senose naršyklėse (be CSS :has)
          try {
            var inp = P.document.querySelector('input[aria-label="ets_leave_log"]');
            var box = inp && inp.closest('[data-testid="stTextInput"]');
            if (box) box.style.display = 'none';
          } catch (e) {}
          if (P.__etsLeaveInstalled) return;
          P.__etsLeaveInstalled = true;
          var code = `
            (function () {
              var S = window.__etsLeave = { log: [], hiddenAt: null, photo: false };
              function now() { return new Date().toISOString(); }
              document.addEventListener('click', function (e) {
                if (e.target.closest && e.target.closest('[data-testid="stFileUploader"]')) {
                  window.__etsCamera = Date.now();
                }
              }, true);
              function hide() {
                if (S.hiddenAt) return;
                S.hiddenAt = now();
                S.photo = !!(window.__etsCamera && Date.now() - window.__etsCamera < 15000);
              }
              function show() {
                if (!S.hiddenAt) return;
                var out = S.hiddenAt; S.hiddenAt = null;
                if (S.photo) { S.photo = false; return; }
                S.log.push({ out: out, back: now() });
                push();
              }
              function push() {
                var inp = document.querySelector('input[aria-label="ets_leave_log"]');
                if (!inp) return;
                var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                setter.call(inp, JSON.stringify({ leaves: S.log }));
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
              }
              document.addEventListener('visibilitychange', function () { document.hidden ? hide() : show(); });
              window.addEventListener('ets-hidden', hide);
              window.addEventListener('ets-visible', show);
            })();`;
          var el = P.document.createElement('script');
          el.textContent = code;
          P.document.head.appendChild(el);
        })();
        </script>
        """,
        height=0,
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
