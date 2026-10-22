"""
ETS - Mokinio testavimo langas.
Paleidimas: streamlit run student_app/main.py
"""

import time
import random
from datetime import datetime, timezone

import streamlit as st


def _install_polyfill():
    """Įterpia trūkstamas JS funkcijas į Streamlit pradinį puslapį (index.html),
    kad jos veiktų dar prieš paleidžiant programą. Reikia senoms planšetėms,
    kurių Android System WebView neturi String.replaceAll, Object.hasOwn ir pan."""
    from pathlib import Path as _P
    try:
        index = _P(st.__file__).parent / "static" / "index.html"
        html = index.read_text(encoding="utf-8")
        if "ets-polyfill" not in html:
            js = (_P(__file__).parent / "assets" / "polyfill.js").read_text(encoding="utf-8")
            html = html.replace("<head>", '<head><script id="ets-polyfill">' + js + "</script>", 1)
            index.write_text(html, encoding="utf-8")
    except Exception:
        pass
    # Jei failo pakeisti negalima (serverio failai tik skaitymui) – įterpiam
    # polyfill tiesiai siunčiant pradinį puslapį.
    try:
        from streamlit.web.server import routes as _routes
        H = _routes.StaticFileHandler
        if getattr(H, "_ets_patch_v4", False):
            return
        js = (_P(__file__).parent / "assets" / "polyfill.js").read_text(encoding="utf-8")
        tag = ('<script id="ets-polyfill">' + js + "</script>").encode("utf-8")
        import re as _re0
        orig_get_content = H.get_content.__func__
        orig_size = H.get_content_size

        def _patched(abspath):
            data = open(abspath, "rb").read()
            if b"ets-polyfill" not in data:
                data = data.replace(b"<head>", b"<head>" + tag, 1)
            # Naujas adresas, kad planšetės nenaudotų seno, talpykloje išsaugoto failo
            data = _re0.sub(rb'(static/js/main\.[0-9a-f]+\.js)"', rb'\1?v=ets3"', data)
            return data

        def get_content(cls, abspath, start=None, end=None):
            if str(abspath).endswith("index.html"):
                return _patched(abspath)[start:end]
            return orig_get_content(cls, abspath, start, end)

        def get_content_size(self):
            if str(self.absolute_path).endswith("index.html"):
                return len(_patched(self.absolute_path))
            return orig_size(self)

        H.get_content = classmethod(get_content)
        H.get_content_size = get_content_size

        # Labai senoms planšetėms (Android System WebView < 85) Streamlit JS
        # failai nesuprantami (?. ?? ir pan. – baltas ekranas). Joms siunčiam
        # tų pačių failų versijas, perrašytas senesniu JavaScript (compat_js/).
        import re as _re
        compat_dir = _P(__file__).parent / "compat_js"
        orig_validate = H.validate_absolute_path
        orig_headers = H.set_extra_headers

        def _old_browser(handler):
            ua = handler.request.headers.get("User-Agent", "")
            m = _re.search(r"Chrome/(\d+)", ua)
            return bool(m) and int(m.group(1)) < 85

        def validate_absolute_path(self, root, absolute_path):
            path = orig_validate(self, root, absolute_path)
            self._ets_compat = False
            try:
                if path and str(path).endswith(".js") and _old_browser(self):
                    alt = compat_dir / _P(str(path)).name
                    if alt.is_file():
                        self._ets_compat = True
                        import os as _os
                        self._stat_result = _os.stat(str(alt))
                        return str(alt)
            except Exception:
                pass
            return path

        def set_extra_headers(self, path):
            orig_headers(self, path)
            if str(path).endswith(".js"):
                self.set_header("Vary", "User-Agent")
                if getattr(self, "_ets_compat", False):
                    self.set_header("Cache-Control", "private, max-age=86400")

        H.validate_absolute_path = validate_absolute_path
        H.set_extra_headers = set_extra_headers
        H._ets_patch_v4 = True
    except Exception:
        pass


_install_polyfill()
import streamlit.components.v1 as components

from utils.db import get_client
import importlib as _il
import utils.storage as _storage
_il.reload(_storage)
from utils.storage import upload_image, upload_draft, find_draft
from utils.sketch import sketch_pad
import utils.game as _game_mod
_il.reload(_game_mod)
from utils.game import game_widget
import base64
import uuid
import io
# Streamlit Cloud po atnaujinimo gali laikyti seną modulio versiją (ImportError)
import importlib
import utils.grading as _grading
import utils.test_queries as _test_queries
importlib.reload(_grading)
importlib.reload(_test_queries)
from utils.grading import auto_grade, is_open_question, GAME_KINDS, game_kind, game_results
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
# Ar ankstesnis pilnas paleidimas nupiešė testo klausimus (žr. TESTO PATEIKIMAS)
_PREV_TEST_RENDERED = st.session_state.pop("_test_rendered", False)


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


# ------------------------------------------------------------
# VIENAS ĮRENGINYS VIENAM MOKINIUI
# Kiekvienas įrenginys turi savo pastovų kodą (planšetės numeris arba
# naršyklėje išsaugotas atsitiktinis kodas). Tą patį mokinį kitame
# įrenginyje įleidžiam tik tada, kai pirmasis ilgiau nei 2 min. neaktyvus
# (pvz., sugedo planšetė). Tada senasis įrenginys sustabdomas.
# ------------------------------------------------------------

DEVICE_IDLE_SECONDS = 120


def _device_id():
    tab = _client_info()["tablet"]
    if tab:
        return f"tab-{tab}"
    if st.session_state.get("_device"):
        return st.session_state._device
    if not st.session_state.get("_session_dev"):
        st.session_state._session_dev = "ses-" + uuid.uuid4().hex[:12]
    return st.session_state._session_dev


def _on_device():
    v = (st.session_state.get("ets_dev") or "").strip()
    if v:
        st.session_state._device = "dev-" + v[:40]


def _seconds_ago(ts):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return None


def _busy_elsewhere(submission):
    """True, jei šis bandymas dabar atidarytas kitame (aktyviame) įrenginyje."""
    other = submission.get("device_id")
    if not other or other == _device_id() or submission.get("status") != "in_progress":
        return False
    ago = _seconds_ago(submission.get("last_seen"))
    return ago is not None and ago < DEVICE_IDLE_SECONDS


def _claim_device(submission):
    try:
        update_submission_progress(supabase, submission["id"], {
            "device_id": _device_id(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        })
        submission["device_id"] = _device_id()
    except Exception:
        pass   # jei duomenų bazėje dar nėra stulpelio – veikiam be šio apribojimo


def _still_my_device():
    """Testo metu: ar kitas įrenginys neperėmė šio bandymo."""
    sub = st.session_state.get("submission")
    if not sub:
        return True
    try:
        row = get_submission(supabase, sub["assignment_id"], sub["student_id"])
    except Exception:
        return True
    other = (row or {}).get("device_id")
    return not other or other == _device_id()


def _order_questions(questions, seed):
    """Kiekvienam mokiniui klausimai kita tvarka (bet visada ta pati tam pačiam
    mokiniui). Sprendimo nuotraukų uždaviniai paliekami gale."""
    normal = [tq for tq in questions if tq["question_bank"]["type"] != "image_upload"]
    photos = [tq for tq in questions if tq["question_bank"]["type"] == "image_upload"]
    random.Random(f"order_{seed}").shuffle(normal)
    return normal + photos


def _prepare_test_state(submission, questions):
    """Pradedant (ar tęsiant) testą: sumaišo klausimus ir atkuria jau
    išsaugotus atsakymus, juodraščius ir sprendimų lapus
    (pvz., jei nutrūko ryšys ar mokinys prisijungė iš naujo)."""
    saved_rows = get_saved_answers(supabase, submission["id"])
    st.session_state._answer_ids = {k: v["id"] for k, v in saved_rows.items()}
    st.session_state._saved = {}        # pagrindinis atsakymas
    st.session_state._saved_draft = {}  # juodraščio lapas
    st.session_state._saved_final = {}  # galutinis atsakymas prie sprendimo lapo
    st.session_state._restored_img = {}
    st.session_state._img_urls = {}
    for tq in questions:
        q = tq["question_bank"]
        row = saved_rows.get(tq["id"])
        if not row:
            continue
        text = row.get("text_answer") or ""
        if q["type"] == "image_upload":
            if row.get("image_url"):
                st.session_state._saved[tq["id"]] = ("img", "restored")
                st.session_state._restored_img[tq["id"]] = row["image_url"]
            st.session_state._saved_final[tq["id"]] = text
            if text:
                st.session_state[f"final_{tq['id']}"] = text
            continue
        st.session_state._saved[tq["id"]] = text
        if q["type"] == "game":
            st.session_state.setdefault("_game_saved", {})[tq["id"]] = text
            continue
        if text and (q["type"] != "mcq" or text in (q.get("options") or [])):
            st.session_state[f"ans_{tq['id']}"] = text
        if row.get("image_url"):
            st.session_state._saved_draft[tq["id"]] = ("draw", "restored")
            st.session_state._restored_img[tq["id"]] = row["image_url"]
    st.session_state._leaves = list(submission.get("leave_events") or [])
    st.session_state._draft_url = find_draft(supabase, submission["id"])
    st.session_state._draft_pending = None
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


def _pad_change(key, prev):
    """Ar piešimo lapas (sprendimo ar juodraščio) pasikeitė.
    Grąžina (pasikeitė, naujas_vaizdas_arba_None, nauja_žymė)."""
    if key not in st.session_state:
        return False, None, prev
    pad = st.session_state.get(key)
    if pad and pad.get("n"):
        mark = ("draw", pad.get("n"))
        return prev != mark, pad.get("data"), mark
    # lapas išvalytas - jei anksčiau buvo išsaugotas piešinys, jį pašalinam
    was_drawing = isinstance(prev, tuple) and prev[0] == "draw"
    return was_drawing, None, ("" if was_drawing else prev)


def _upload_pad(data_url):
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return upload_image(supabase, io.BytesIO(raw), folder="answers")


def _save_draft(data_url):
    """Įkelia bendrą juodraštį į serverį. Grąžina True, jei pavyko."""
    sub = st.session_state.get("submission")
    if not sub or not data_url or not data_url.startswith("data:image"):
        return True
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
        url = upload_draft(supabase, sub["id"], raw)
        st.session_state._draft_url = f"{url}?v={int(time.time())}"
        return True
    except Exception:
        return False


def _on_draft():
    """Juodraštis atsiunčiamas tik jį uždarius. Laukelį iškart išvalom, kad
    didelis paveikslėlis nebūtų siunčiamas su kiekvienu veiksmu."""
    data = st.session_state.get("ets_draft") or ""
    st.session_state.ets_draft = ""
    if data and not _save_draft(data):
        st.session_state._draft_pending = data   # bandysim dar kartą vėliau


def _on_battery():
    """Planšetės baterijos lygis (siunčiamas, kai pasikeičia bent 5 %)."""
    try:
        st.session_state._battery = max(0, min(100, int(st.session_state.get("ets_batt") or "")))
    except ValueError:
        pass


def _only_one_draft(open_id):
    """Senoms planšetėms: vienu metu atidarytas tik vienas juodraštis
    (kiti užsidaro, bet jų turinys lieka išsaugotas)."""
    if not st.session_state.get(f"draft_on_{open_id}"):
        return
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("draft_on_") and k != f"draft_on_{open_id}":
            st.session_state[k] = False


def _current_answer(tq):
    """Dabartinė mokinio atsakymo reikšmė iš valdiklių (arba None, jei neparodyta)."""
    q = tq["question_bank"]
    tid = tq["id"]
    if q["type"] == "image_upload":
        key = f"final_{tid}"
        return (st.session_state.get(key) or "") if key in st.session_state else None
    key = f"ans_{tid}"
    return (st.session_state.get(key) or "") if key in st.session_state else None


def _autosave(force_progress=False):
    """Išsaugo pasikeitusius atsakymus, juodraščius ir bandymo eigą.

    Svarbu: atmintyje pažymime „išsaugota“ TIK po sėkmingo įrašymo į duomenų
    bazę. Lėtose planšetėse Streamlit gali nutraukti vykdymą pusiaukelėje
    (mokinys jau spaudžia kitą veiksmą) – tada pakeitimas liks neišsaugotas
    atmintyje ir bus įrašytas kito veiksmo metu.
    """
    if st.session_state.get("step") != "taking_test":
        return
    if st.session_state.get("_draft_pending") and _save_draft(st.session_state._draft_pending):
        st.session_state._draft_pending = None
    submission = st.session_state.submission
    questions = st.session_state.test_questions or []
    saved = st.session_state.setdefault("_saved", {})
    saved_draft = st.session_state.setdefault("_saved_draft", {})
    saved_final = st.session_state.setdefault("_saved_final", {})
    img_urls = st.session_state.setdefault("_img_urls", {})
    ids = st.session_state.setdefault("_answer_ids", {})

    pending_insert = []   # (eilutė, [žymių atnaujinimai])
    for tq in questions:
        q = tq["question_bank"]
        tid = tq["id"]
        upd, marks = {}, []
        try:
            if q["type"] == "image_upload":
                changed, data_url, mark = _pad_change(f"draw_{tid}", saved.get(tid))
                if changed:
                    url = _upload_pad(data_url) if data_url else None
                    upd.update({"image_url": url, "score": None, "graded_by": "teacher"})
                    marks.append((saved, tid, mark)); marks.append((img_urls, tid, url))
                photo = st.session_state.get(f"ans_{tid}")
                if photo is not None:
                    fid = getattr(photo, "file_id", None) or f"{getattr(photo, 'name', '')}_{getattr(photo, 'size', '')}"
                    if saved.get(tid) != ("img", fid):
                        upd.update({"image_url": upload_image(supabase, photo, folder="answers"),
                                    "score": None, "graded_by": "teacher"})
                        marks.append((saved, tid, ("img", fid)))
                fkey = f"final_{tid}"
                if fkey in st.session_state:
                    final = st.session_state.get(fkey) or ""
                    if final != saved_final.get(tid, "") and final != "":
                        upd.update({"text_answer": final, "score": None, "graded_by": "teacher"})
                        marks.append((saved_final, tid, final))
                defaults = {"text_answer": None, "image_url": None, "score": None, "graded_by": "teacher"}
            else:
                key = f"ans_{tid}"
                if key in st.session_state:
                    text = st.session_state.get(key) or ""
                    # Tuščias laukelis niekada neperrašo jau išsaugoto atsakymo
                    # (pvz., jei po persikrovimo atsakymas dar neatsikūrė ekrane).
                    if not (saved.get(tid) == text or text == ""):
                        score, graded_by = auto_grade(q, text)
                        upd.update({"text_answer": text, "score": score, "graded_by": graded_by})
                        marks.append((saved, tid, text))
                changed, data_url, mark = _pad_change(f"draft_{tid}", saved_draft.get(tid))
                if changed:
                    url = _upload_pad(data_url) if data_url else None
                    upd["image_url"] = url
                    marks.append((saved_draft, tid, mark)); marks.append((img_urls, tid, url))
                score0, graded0 = auto_grade(q, "")
                defaults = {"text_answer": "", "image_url": None, "score": score0, "graded_by": graded0}

            if not upd:
                continue
            if tid in ids:
                update_answer(supabase, ids[tid], upd)
                for d, k, v in marks:
                    d[k] = v
            else:
                pending_insert.append(({**defaults, **upd, "submission_id": submission["id"],
                                        "test_question_id": tid}, marks, upd))
        except Exception:
            # nepavyko (pvz., ryšys) - bandysim kito veiksmo metu
            continue

    if pending_insert:
        # Ankstesnis (nutrauktas) veiksmas galėjo eilutę jau įrašyti – tada ją
        # atnaujinam, o ne kuriam antrą (dubliai painiodavo atsakymų atkūrimą).
        try:
            existing = get_saved_answers(supabase, submission["id"])
        except Exception:
            existing = {}
        still = []
        for row, marks, only in pending_insert:
            ex = existing.get(row["test_question_id"])
            if ex:
                try:
                    ids[row["test_question_id"]] = ex["id"]
                    update_answer(supabase, ex["id"], only)
                    for d, k, v in marks:
                        d[k] = v
                except Exception:
                    pass
            else:
                still.append((row, marks, only))
        pending_insert = still
    if pending_insert:
        try:
            res = insert_answers(supabase, [row for row, _, _ in pending_insert])
            for r in (res.data or []) if res is not None else []:
                ids[r["test_question_id"]] = r["id"]
            for _, marks, _ in pending_insert:
                for d, k, v in marks:
                    d[k] = v
        except Exception:
            pass

    # Eigos informacija: ne dažniau kaip kas 20 s (nebent kas pasikeitė)
    answered = sum(1 for v in saved.values() if v not in ("", None))
    now_ts = time.time()
    progress = {}
    info = _client_info()
    if info["tablet"] and st.session_state.get("_tablet_saved") != submission["id"]:
        progress["tablet"] = info["tablet"]
    if _merge_leave_log():
        progress["leave_events"] = st.session_state._leaves
    batt = st.session_state.get("_battery")
    if batt is not None and batt != st.session_state.get("_battery_saved"):
        progress["battery"] = batt
    if (force_progress or progress or answered != st.session_state.get("_last_answered")
            or now_ts - st.session_state.get("_last_progress", 0) > 20):
        progress.update({"last_seen": datetime.now(timezone.utc).isoformat(), "answered_count": answered})
        try:
            update_submission_progress(supabase, submission["id"], progress)
            st.session_state._last_progress = now_ts
            st.session_state._last_answered = answered
            if "tablet" in progress:
                st.session_state._tablet_saved = submission["id"]
            if "battery" in progress:
                st.session_state._battery_saved = progress["battery"]
        except Exception:
            pass


def _show_mcq_summary(submission_id):
    """Iškart po pateikimo: tik bendras testinės dalies rezultatas
    (be klausimų ir teisingų atsakymų)."""
    try:
        rows = get_submission_results(supabase, submission_id)
    except Exception:
        return
    mcq = [r for r in rows if (r.get("test_questions") or {}).get("question_bank", {}).get("type") == "mcq"]
    if not mcq:
        return
    got = sum(float(r.get("score") or 0) for r in mcq)
    total = sum(float(r["test_questions"]["question_bank"].get("points") or 1) for r in mcq)
    right = sum(1 for r in mcq if float(r.get("score") or 0) > 0)
    st.subheader(f"Testiniai klausimai: {_fmt_points(got)} iš {_fmt_points(total)} tšk.")
    st.caption(f"Teisingai atsakyta {right} iš {len(mcq)}. Atvirus klausimus ir uždavinius įvertins mokytojas.")


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

    # Pirma išsaugom viską, kas pasikeitė (ir nuotraukas, juodraščius).
    _autosave(force_progress=True)

    # Galutinis patikrinimas su duomenų baze: jei kurio nors atsakymo
    # duomenų bazėje nėra arba jis kitoks nei ekrane – įrašom iš naujo.
    db_rows = get_saved_answers(supabase, submission["id"])
    to_insert = []
    for tq in questions:
        q = tq["question_bank"]
        cur = _current_answer(tq)
        row = db_rows.get(tq["id"])
        if row:
            if cur is not None and (row.get("text_answer") or "") != cur and (cur or not (row.get("text_answer") or "").strip()):
                if q["type"] == "image_upload":
                    update_answer(supabase, row["id"], {"text_answer": cur, "score": None, "graded_by": "teacher"})
                else:
                    score, graded_by = auto_grade(q, cur)
                    update_answer(supabase, row["id"], {"text_answer": cur, "score": score, "graded_by": graded_by})
            continue
        if q["type"] == "image_upload":
            data = {"text_answer": cur, "image_url": None, "score": None, "graded_by": "teacher"}
        else:
            score, graded_by = auto_grade(q, cur or "")
            data = {"text_answer": cur or "", "image_url": None, "score": score, "graded_by": graded_by}
        to_insert.append({**data, "submission_id": submission["id"], "test_question_id": tq["id"]})

    insert_answers(supabase, to_insert)
    mark_submission_submitted(supabase, submission["id"])
    st.session_state.step = "submitted"

st.title("E-testavimas")

_CALC_JS = (Path(__file__).parent / "assets" / "calculator.js").read_text(encoding="utf-8")
_DRAFT_JS = (Path(__file__).parent / "assets" / "draft.js").read_text(encoding="utf-8")
_GUARD_JS = (Path(__file__).parent / "assets" / "typing_guard.js").read_text(encoding="utf-8")
_FORM_JS = (Path(__file__).parent / "assets" / "formulas.js").read_text(encoding="utf-8")
_BATT_JS = (Path(__file__).parent / "assets" / "battery.js").read_text(encoding="utf-8")
if st.session_state.get("step") != "taking_test":
    # Ne testo metu skaičiuotuvo nerodom
    components.html(
        "<script>try{['ets-calc-btn','ets-calc','ets-draft-btn','ets-draft','ets-form-btn','ets-form'].forEach(function(i){"
        "var e=window.parent.document.getElementById(i);if(e)e.remove();});}catch(e){}</script>",
        height=0,
    )

if st.session_state.get("step") in (None, "select_class", "enter_name", "enter_code"):
    # Pastovus šio įrenginio kodas iš naršyklės atminties (žr. _device_id)
    st.text_input("ets_dev", key="ets_dev", label_visibility="collapsed", on_change=_on_device)
    st.markdown(
        """<style>div[data-testid="stTextInput"]:has(input[aria-label="ets_dev"]){display:none !important;}</style>""",
        unsafe_allow_html=True,
    )
    if not st.session_state.get("_device"):
        components.html(
            """<script>(function(){var P=window.parent,D=P.document,n=0;
            function go(){var inp=D.querySelector('input[aria-label="ets_dev"]');
              if(!inp){if(++n<40)setTimeout(go,250);return;}
              var b=inp.closest('[data-testid="stTextInput"]');if(b)b.style.display='none';
              var id=null;try{id=P.localStorage.getItem('ets-dev-id');}catch(e){}
              if(!id){id=Math.random().toString(36).slice(2)+Date.now().toString(36);try{P.localStorage.setItem('ets-dev-id',id);}catch(e){}}
              if(inp.value===id)return;
              var set=Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype,'value').set;set.call(inp,id);
              inp.dispatchEvent(new P.Event('input',{bubbles:true}));
              ['keydown','keypress','keyup'].forEach(function(t){inp.dispatchEvent(new P.KeyboardEvent(t,{key:'Enter',code:'Enter',keyCode:13,which:13,charCode:13,bubbles:true}));});}
            go();})();</script>""",
            height=0,
        )

components.html(
    "<script>(function(){var P=window.parent;var el=P.document.createElement('script');el.textContent="
    + json.dumps(_BATT_JS)
    + ";P.document.head.appendChild(el);})();</script>",
    height=0,
)

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
                f"✅ {match.get('display_name') or match['name']} — rasta klasės sąraše"
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
                st.session_state.student_name = match.get("display_name") or match["name"]
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

                    if _busy_elsewhere(submission):
                        st.error(
                            "🔒 Šis mokinys jau sprendžia testą kitame įrenginyje. "
                            "Testą galima spręsti tik viename įrenginyje. "
                            "Jei tai tu ir planšetė sugedo – palauk 2 minutes ir bandyk dar kartą "
                            "arba kreipkis į mokytoją."
                        )
                        st.stop()

                    _claim_device(submission)

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
        if not _still_my_device():
            st.session_state.step = "other_device"
            st.rerun(scope="app")
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
    # SKAIČIUOTUVAS (plaukiojantis mygtukas 🧮 kairėje apačioje)
    # Veikia tik naršyklėje, serverio neapkrauna.
    # --------------------------------------------------------

    components.html(
        "<script>(function(){var P=window.parent;"
        "if(P.document.getElementById('ets-calc-btn'))return;"
        "var el=P.document.createElement('script');el.textContent="
        + json.dumps(_CALC_JS)
        + ";P.document.head.appendChild(el);})();</script>",
        height=0,
    )

    # --------------------------------------------------------
    # BENDRAS JUODRAŠTIS (mygtukas „✏️ Juodraštis“ apačioje)
    # Piešiama tik planšetėje, į serverį siunčiama tik uždarius.
    # --------------------------------------------------------

    # Formulynas (VBE fizikos priedas) – tik testuose, kuriems mokytojas jį įjungė
    if (assignment.get("tests") or {}).get("show_formulas"):
        components.html(
            "<script>(function(){var P=window.parent;"
            "if(P.document.getElementById('ets-form-btn'))return;"
            "var el=P.document.createElement('script');el.textContent="
            + json.dumps(_FORM_JS)
            + ";P.document.head.appendChild(el);})();</script>",
            height=0,
        )
    else:
        components.html(
            "<script>try{['ets-form-btn','ets-form'].forEach(function(i){"
            "var e=window.parent.document.getElementById(i);if(e)e.remove();});}catch(e){}</script>",
            height=0,
        )

    # Rašomų atsakymų apsauga: saugo planšetėje ir pats nusiunčia sustojus rašyti
    components.html(
        "<script>(function(){var P=window.parent;P.__etsGuardCfg="
        + json.dumps({"key": submission["id"]})
        + ";var el=P.document.createElement('script');el.textContent="
        + json.dumps(_GUARD_JS)
        + ";P.document.head.appendChild(el);})();</script>",
        height=0,
    )

    _draft_cfg = {"key": submission["id"], "url": st.session_state.get("_draft_url")}
    components.html(
        "<script>(function(){var P=window.parent;P.__etsDraftCfg="
        + json.dumps(_draft_cfg)
        + ";var el=P.document.createElement('script');el.textContent="
        + json.dumps(_DRAFT_JS)
        + ";P.document.head.appendChild(el);})();</script>",
        height=0,
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

    # Jei po ryšio trikdžio ar persikrovimo laukeliai ekrane tapo tušti, nors
    # atsakymas jau išsaugotas – grąžinam išsaugotą reikšmę į ekraną.
    # Jei ankstesnis paleidimas klausimų nenupiešė (klaida, nutrūkimas), ekrane
    # laukeliai sukuriami iš naujo tušti – tada reikšmes nusiunčiam priverstinai.
    _force_restore = not _PREV_TEST_RENDERED
    _saved_now = st.session_state.get("_saved", {})
    _saved_fin = st.session_state.get("_saved_final", {})
    for _tq in questions:
        _q, _tid = _tq["question_bank"], _tq["id"]
        if _q["type"] == "game":
            continue
        if _q["type"] == "image_upload":
            _k, _v = f"final_{_tid}", _saved_fin.get(_tid)
        else:
            _k, _v = f"ans_{_tid}", _saved_now.get(_tid)
        if not isinstance(_v, str) or not _v.strip():
            continue
        if _q["type"] == "mcq" and _v not in (_q.get("options") or []):
            continue
        if _force_restore or st.session_state.get(_k) in (None, ""):
            st.session_state[_k] = _v


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
        # MINI ŽAIDIMAS
        # ====================================================

        elif q["type"] == "game":

            st.caption("🎮 " + GAME_KINDS.get(game_kind(q), "Mini žaidimas"))
            game_widget(
                q,
                seed=f"{submission['id']}_{tq['id']}",
                key=f"ans_{tq['id']}",
                initial=(st.session_state.get(f"ans_{tq['id']}")
                         or st.session_state.get("_game_saved", {}).get(tq["id"])),
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

            st.text_input(
                "Galutinis atsakymas",
                key=f"final_{tq['id']}",
                placeholder="Užrašyk galutinį atsakymą, pvz. t = 35 °C",
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


        # ====================================================
        # JUODRAŠTIS (lapas skaičiavimams prie kiekvieno klausimo)
        # Atidaromas tik paspaudus, kad senos planšetės neapsunktų.
        # ====================================================

        # (Juodraštis dabar vienas bendras – mygtukas „✏️ Juodraštis“ apačioje.)


    st.session_state["_test_rendered"] = True

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
    st.text_input("ets_draft", key="ets_draft", label_visibility="collapsed", on_change=_on_draft)
    st.text_input("ets_batt", key="ets_batt", label_visibility="collapsed", on_change=_on_battery)
    st.markdown(
        """<style>div[data-testid="stTextInput"]:has(input[aria-label="ets_leave_log"]),
        div[data-testid="stTextInput"]:has(input[aria-label="ets_draft"]),
        div[data-testid="stTextInput"]:has(input[aria-label="ets_batt"])
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
            ['ets_leave_log', 'ets_draft', 'ets_batt'].forEach(function (n) {
              var inp = P.document.querySelector('input[aria-label="' + n + '"]');
              var box = inp && inp.closest('[data-testid="stTextInput"]');
              if (box) box.style.display = 'none';
            });
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
                // Streamlit laukelį įrašo paspaudus Enter (keypress)
                ['keydown', 'keypress', 'keyup'].forEach(function (t) {
                  inp.dispatchEvent(new KeyboardEvent(t, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, charCode: 13, bubbles: true }));
                });
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
# TESTAS ATIDARYTAS KITAME ĮRENGINYJE
# ============================================================

elif st.session_state.step == "other_device":

    st.error(
        "🔒 Šis testas dabar atidarytas kitame įrenginyje, todėl čia jis sustabdytas. "
        "Tavo atsakymai išsaugoti."
    )
    if st.button("Grįžti į pradžią"):
        _reset_to_start()
        st.rerun()


# ============================================================
# ŽINGSNIS 5: PATEIKTA
# ============================================================

elif st.session_state.step == "submitted":

    st.success(
        "Testas pateiktas! Rezultatai bus perduoti mokytojui."
    )

    if st.session_state.get("submission"):
        _show_mcq_summary(st.session_state.submission["id"])

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
        elif q["type"] == "game":
            st.text("🎮 Mini žaidimas " + ("atliktas" if (r.get("text_answer") or "").strip() else "neatliktas"))
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
