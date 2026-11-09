"""Laboratorinio darbo klausimas (type = "lab").

Laboratorinis darbas sukuriamas mokytojo programėlėje iš šablono: kiekviena darbo
dalis yra atskiras "lab" tipo klausimas, o jos turinys (tekstas, paveikslėliai,
lentelės, laukeliai) laikomas question_bank.options["lab"]["blocks"].

Mokinio įrašai laikomi viename JSON atsakyme (answers.text_answer):
{"b3.r0.c2": "12,5", "b5.0": "40", "b9": "Atsakymas..."}.
Schemos brėžinys saugomas kaip įprasto juodraščio paveikslėlis (answers.image_url).
"""
import html
import json
import re
from pathlib import Path

import streamlit as st

_STATIC = Path(__file__).resolve().parent.parent / "static" / "lab"


def is_lab(q: dict) -> bool:
    return (q or {}).get("type") == "lab"


def lab_spec(q: dict) -> dict:
    o = q.get("options") or {}
    if isinstance(o, str):
        try:
            o = json.loads(o)
        except Exception:
            o = {}
    return (o.get("lab") if isinstance(o, dict) else None) or {}


def lab_fields(q: dict) -> list:
    """Visų laukelių raktai (tvarka kaip darbo lape)."""
    out = []
    for i, b in enumerate(lab_spec(q).get("blocks") or []):
        t = b.get("t")
        if t == "p":
            out += [f"b{i}.{k}" for k in range(len(b.get("segs") or []) - 1)]
        elif t == "ol":
            for j, it in enumerate(b.get("items") or []):
                out += [f"b{i}.l{j}.{k}" for k in range(len(it) - 1)]
        elif t == "table":
            for r, row in enumerate(b.get("rows") or []):
                out += [f"b{i}.r{r}.c{c}" for c, cell in enumerate(row) if cell is None]
        elif t == "text":
            out.append(f"b{i}")
    return out


def _wkey(tid, fk):
    return f"lab_{tid}__{fk}"


def _vals(tid, saved_text=None) -> dict:
    store = st.session_state.setdefault("_lab_vals", {})
    if tid not in store:
        d = {}
        if saved_text:
            try:
                d = json.loads(saved_text) or {}
            except Exception:
                d = {}
        store[tid] = {k: str(v) for k, v in d.items() if isinstance(k, str)}
    return store[tid]


def lab_sync(questions) -> None:
    """Perkelia ekrane pakeistas reikšmes į bendrą žodyną ir atnaujina atsakymą
    (ans_<id>), kurį išsaugo įprastas automatinis išsaugojimas."""
    for tq in questions or []:
        q = tq["question_bank"]
        if not is_lab(q):
            continue
        tid = tq["id"]
        vals = _vals(tid, st.session_state.get(f"ans_{tid}"))
        pre = f"lab_{tid}__"
        for k in list(st.session_state.keys()):
            if isinstance(k, str) and k.startswith(pre):
                v = st.session_state.get(k)
                fk = k[len(pre):]
                if v is None or str(v).strip() == "":
                    vals.pop(fk, None)
                else:
                    vals[fk] = str(v)
        if vals:
            st.session_state[f"ans_{tid}"] = json.dumps(vals, ensure_ascii=False, sort_keys=True)


def filled(q: dict, text: str | None):
    """(užpildyta, iš viso) laukelių skaičius."""
    keys = lab_fields(q)
    try:
        d = json.loads(text) if text else {}
    except Exception:
        d = {}
    return sum(1 for k in keys if str(d.get(k, "")).strip()), len(keys)


# ---------------------------------------------------------------- vaizdavimas
_CSS = """<style>
.lab-p{margin:.35rem 0;line-height:1.55}
.lab-h{font-weight:600;font-size:1.05rem;margin:1rem 0 .2rem}
.lab-blank{display:inline-block;min-width:3.2em;border-bottom:1.5px solid #888;text-align:center;font-size:.8em;color:#666}
.lab-th{font-weight:600;font-size:.82rem;line-height:1.25;padding:.2rem 0;border-bottom:2px solid #999}
.lab-td{font-size:.85rem;padding-top:.45rem}
.lab-formula{font-family:monospace;background:rgba(127,127,127,.12);padding:.3rem .6rem;display:inline-block}
</style>"""


def _md(htmltext):
    st.markdown(f'<div class="lab-p">{htmltext}</div>', unsafe_allow_html=True)


def _plain(htmltext):
    return html.unescape(re.sub(r"<[^>]+>", "", htmltext or ""))


def _ensure(tid, fk, vals):
    k = _wkey(tid, fk)
    if k not in st.session_state:
        st.session_state[k] = vals.get(fk, "")
    return k


def _blanks(tid, base, segs, vals):
    """Tekstas su tuščiais laukeliais: tekste (1), (2)..., o laukeliai – po juo."""
    n = len(segs) - 1
    if n <= 0:
        _md(segs[0])
        return
    parts = []
    for k, s in enumerate(segs):
        parts.append(s)
        if k < n:
            parts.append(f'<span class="lab-blank">({k + 1})</span>' if n > 1 else '<span class="lab-blank">&nbsp;</span>')
    _md("".join(parts))
    cols = st.columns(min(n, 4))
    for k in range(n):
        before = _plain(segs[k]).strip().split()
        label = " ".join(before[-4:]) if before else "Atsakymas"
        with cols[k % len(cols)]:
            st.text_input(f"({k + 1}) {label}" if n > 1 else label, key=_ensure(tid, f"{base}.{k}", vals))


def _num(s):
    if s is None:
        return None
    t = re.sub(r"\s", "", str(s)).replace(",", ".")
    t = re.sub(r"[^0-9.\-eE]", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def _graph(tid, bi, b, vals):
    head = [_plain(h) for h in b["head"]]
    rows = b["rows"]
    cols_in = sorted({c for row in rows for c, cell in enumerate(row) if cell is None})
    if len(cols_in) < 2 or len(rows) < 2 or head[0].startswith("Rodiklis"):
        return

    def col(c):
        return [(_num(vals.get(f"b{bi}.r{r}.c{c}")) if row[c] is None else _num(_plain(row[c]))) for r, row in enumerate(rows)]

    with st.expander("📈 Grafikas iš šios lentelės"):
        names = {c: head[c] or f"Stulpelis {c + 1}" for c in range(len(head))}
        numeric = [c for c in range(len(head)) if sum(v is not None for v in col(c)) >= 1 or c in cols_in]
        tcol = next((c for c in numeric if re.match(r"^(t\s*,|t$|laikas)", names[c], re.I)), None)
        x0 = tcol if tcol is not None else cols_in[0]
        x = st.selectbox("X ašis", numeric, index=numeric.index(x0) if x0 in numeric else 0,
                         format_func=lambda c: names[c], key=f"labgx_{tid}_{bi}")
        ys = st.multiselect("Y ašis", [c for c in numeric if c != x], default=[c for c in cols_in if c != x][:1],
                            format_func=lambda c: names[c], key=f"labgy_{tid}_{bi}")
        xs = col(x)
        data = []
        for c in ys:
            for xv, yv in zip(xs, col(c)):
                if xv is not None and yv is not None:
                    data.append({"x": xv, "y": yv, "Kreivė": names[c]})
        if not data:
            st.caption("Įrašyk bent vieną tašką (X ir Y reikšmes) – jis atsiras grafike.")
            return
        import altair as alt
        import pandas as pd
        df = pd.DataFrame(data)
        base = alt.Chart(df).encode(
            x=alt.X("x:Q", title=names[x]), y=alt.Y("y:Q", title=", ".join(names[c] for c in ys)),
            color=alt.Color("Kreivė:N", scale=alt.Scale(range=["#1f2937", "#6b7280", "#9ca3af", "#374151"]), legend=alt.Legend(orient="bottom")),
            shape="Kreivė:N")
        st.altair_chart(base.mark_line(strokeWidth=1.5).encode(order="x:Q") + base.mark_point(size=60, filled=True),
                        use_container_width=True)


def _table(tid, bi, b, vals):
    head, rows = b["head"], b["rows"]
    widths = [1.4 if c == 0 else 1 for c in range(len(head))]
    hc = st.columns(widths)
    for c, h in enumerate(head):
        hc[c].markdown(f'<div class="lab-th">{h}</div>', unsafe_allow_html=True)
    for r, row in enumerate(rows):
        rc = st.columns(widths)
        for c, cell in enumerate(row):
            with rc[c]:
                if cell is None:
                    st.text_input(f"{_plain(head[c])}, {r + 1} eil.", key=_ensure(tid, f"b{bi}.r{r}.c{c}", vals),
                                  label_visibility="collapsed")
                else:
                    st.markdown(f'<div class="lab-td">{cell}</div>', unsafe_allow_html=True)
    _graph(tid, bi, b, vals)


def render_lab(tq, sketch_pad=None, img_url=None):
    """Nupiešia vieną darbo dalį su laukeliais."""
    q = tq["question_bank"]
    tid = tq["id"]
    vals = _vals(tid, st.session_state.get(f"ans_{tid}"))
    st.markdown(_CSS, unsafe_allow_html=True)
    for i, b in enumerate(lab_spec(q).get("blocks") or []):
        t = b.get("t")
        if t == "h":
            st.markdown(f'<div class="lab-h">{b["x"]}</div>', unsafe_allow_html=True)
        elif t == "p":
            _blanks(tid, f"b{i}", b["segs"], vals)
        elif t == "ol":
            for j, it in enumerate(b["items"]):
                if len(it) == 1:
                    _md(f"<b>{j + 1}.</b> {it[0]}")
                else:
                    _blanks(tid, f"b{i}.l{j}", [f"<b>{j + 1}.</b> {it[0]}"] + it[1:], vals)
        elif t == "table":
            _table(tid, i, b, vals)
        elif t == "img":
            p = _STATIC / b["src"]
            if p.is_file():
                st.image(str(p), use_container_width=True)
        elif t == "formula":
            st.markdown(f'<div class="lab-formula">{b["x"]}</div>', unsafe_allow_html=True)
        elif t == "text":
            st.text_area("Atsakymas", key=_ensure(tid, f"b{i}", vals), height=40 + 26 * int(b.get("rows") or 3),
                         placeholder="Rašyk čia…", label_visibility="collapsed")
        elif t == "pad" and sketch_pad is not None:
            st.caption("✍️ Nubraižyk schemą pirštu arba rašikliu. Brėžinys išsaugomas automatiškai.")
            sketch_pad(key=f"draft_{tid}", initial_url=img_url, height=520)
