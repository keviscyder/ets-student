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


@st.cache_data(show_spinner=False, max_entries=64)
def _img_uri(name: str):
    """Darbo lapo paveikslėlis originalia kokybe (Streamlit jo nesumažina ir neperspaudžia)."""
    import base64
    p = _STATIC / name
    if not p.is_file():
        return None
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


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
                out += [f"b{i}.r{r}.c{c}" for c, cell in enumerate(row) if cell is None or re.search(r"\.{4,}", cell or "")]
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
    # Darbo lapo komponentų reikšmės: {"n": .., "v": {klausimo_id: {laukelis: reikšmė}}}
    sheet = {}
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("labsheet_"):
            v = st.session_state.get(k)
            if isinstance(v, dict) and isinstance(v.get("v"), dict):
                for t, d in v["v"].items():
                    if isinstance(d, dict):
                        sheet.setdefault(t, {}).update(d)
    for tq in questions or []:
        q = tq["question_bank"]
        if not is_lab(q):
            continue
        tid = tq["id"]
        vals = _vals(tid, st.session_state.get(f"ans_{tid}"))
        for fk, v in (sheet.get(tid) or {}).items():
            if v is None or str(v).strip() == "":
                vals.pop(fk, None)
            else:
                vals[fk] = str(v)
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

    with st.expander("Grafikas iš šios lentelės"):
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
        try:
            st.markdown(_svg_plot(data, names[x], ", ".join(names[c] for c in ys)), unsafe_allow_html=True)
        except Exception:
            st.caption("Grafiko nubraižyti nepavyko.")


def _ticks(lo, hi, n=5):
    import math
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    a = math.floor(lo / step)
    b = math.ceil(hi / step)
    return [round(i * step, 10) for i in range(a, b + 1)]


def _fmt(v):
    t = f"{v:.3g}" if abs(v) < 1000 else f"{v:.0f}"
    return t.replace(".", ",")


def _svg_plot(data, xname, yname):
    """Paprastas XY grafikas SVG (be papildomų bibliotekų – veikia ir senose planšetėse)."""
    W, H, L, R, T, B = 640, 360, 64, 16, 16, 52
    xs = [d["x"] for d in data]
    yv = [d["y"] for d in data]
    xt = _ticks(min(0, min(xs)), max(xs) * 1.05 or 1)
    yt = _ticks(min(0, min(yv)), max(yv) * 1.08 or 1)
    x0, x1, y0, y1 = xt[0], xt[-1], yt[0], yt[-1]
    px = lambda v: L + (W - L - R) * (v - x0) / ((x1 - x0) or 1)
    py = lambda v: H - B - (H - B - T) * (v - y0) / ((y1 - y0) or 1)
    g = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="background:#fff;border:1px solid #ccc;border-radius:4px" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="sans-serif" font-size="12">']
    for t in xt:
        g.append(f'<line x1="{px(t):.1f}" y1="{T}" x2="{px(t):.1f}" y2="{H - B}" stroke="#e5e5e5"/>'
                 f'<text x="{px(t):.1f}" y="{H - B + 16}" text-anchor="middle" fill="#333">{_fmt(t)}</text>')
    for t in yt:
        g.append(f'<line x1="{L}" y1="{py(t):.1f}" x2="{W - R}" y2="{py(t):.1f}" stroke="#e5e5e5"/>'
                 f'<text x="{L - 6}" y="{py(t) + 4:.1f}" text-anchor="end" fill="#333">{_fmt(t)}</text>')
    g.append(f'<path d="M{L} {T}V{H - B}H{W - R}" fill="none" stroke="#222" stroke-width="1.5"/>')
    g.append(f'<text x="{(L + W - R) / 2}" y="{H - 10}" text-anchor="middle" fill="#111" font-weight="600">{html.escape(xname)}</text>')
    g.append(f'<text transform="translate(14 {(T + H - B) / 2}) rotate(-90)" text-anchor="middle" fill="#111" font-weight="600">{html.escape(yname)}</text>')
    series = []
    for d in data:
        if d["Kreivė"] not in series:
            series.append(d["Kreivė"])
    cols = ["#1f2937", "#6b7280", "#9ca3af", "#374151"]
    dashes = ["", "6 4", "2 3", "8 3 2 3"]
    for k, name in enumerate(series):
        pts = sorted((d["x"], d["y"]) for d in data if d["Kreivė"] == name)
        c = cols[k % 4]
        if len(pts) > 1:
            path = " ".join(f"{'M' if i == 0 else 'L'}{px(a):.1f} {py(b):.1f}" for i, (a, b) in enumerate(pts))
            g.append(f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2" stroke-dasharray="{dashes[k % 4]}"/>')
        for a, b in pts:
            if k % 2:
                g.append(f'<rect x="{px(a) - 4:.1f}" y="{py(b) - 4:.1f}" width="8" height="8" fill="{c}"/>')
            else:
                g.append(f'<circle cx="{px(a):.1f}" cy="{py(b):.1f}" r="4.5" fill="{c}"/>')
        if len(series) > 1:
            g.append(f'<text x="{L + 10}" y="{T + 16 + 16 * k}" fill="{c}" font-weight="600">{"●■"[k % 2]} {html.escape(name)}</text>')
    g.append("</svg>")
    return "".join(g)


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
            uri = _img_uri(b["src"])
            if uri:
                st.markdown(f'<img src="{uri}" style="width:100%;height:auto;display:block;margin:.4rem 0;'
                            f'background:#fff;border:1px solid #e2e8f0;border-radius:4px" alt="">', unsafe_allow_html=True)
        elif t == "formula":
            st.markdown(f'<div class="lab-formula">{b["x"]}</div>', unsafe_allow_html=True)
        elif t == "text":
            st.text_area("Atsakymas", key=_ensure(tid, f"b{i}", vals), height=40 + 26 * int(b.get("rows") or 3),
                         placeholder="Rašyk čia…", label_visibility="collapsed")
        elif t == "pad":
            st.caption("Schemos ir grafiko lapas: elektros elementai, laidai, ašys ir taškai. Brėžinys išsaugomas automatiškai.")
            try:
                from utils.sketch import circuit_pad
                circuit_pad(key=f"draft_{tid}", initial_url=img_url, height=520)
            except Exception:
                if sketch_pad is not None:
                    sketch_pad(key=f"draft_{tid}", initial_url=img_url, height=520)


# ---------------------------------------------------------------- darbo lapas (komponentas)
import streamlit.components.v1 as _components

_sheet = _components.declare_component("ets_labsheet", path=str(Path(__file__).resolve().parent.parent / "labsheet"))


_FS_JS = r"""
(function(){
  // Šis kodas vykdomas programos lange (ne komponento rėmelyje)
  var P = window, D = P.document;
  if (D.getElementById('ets-fs-btn')) return;
  try { var old = P.top.document.getElementById('ets-fs-btn'); if (old && P.top !== P) old.remove(); } catch (e) {}
  // Programa gali būti įdėta į Streamlit Cloud rėmą – tada per visą ekraną rodom viršutinį langą
  var T = P; try { if (P.top && P.top.document) T = P.top; } catch (e) {}
  var TD = T.document, root = TD.documentElement;
  var req = root.requestFullscreen || root.webkitRequestFullscreen;
  if (!req) return;
  var isFs = function(){ return TD.fullscreenElement || TD.webkitFullscreenElement; };
  var b = D.createElement('button');
  b.id = 'ets-fs-btn'; b.type = 'button';
  b.style.cssText = 'position:fixed;top:44px;right:12px;z-index:99990;font:15px/1.2 "Times New Roman",Times,serif;' +
    'padding:6px 12px;border:1px solid #767676;border-radius:3px;background:#efefef;color:#000;cursor:pointer;opacity:.92';
  var label = function(){ b.textContent = isFs() ? 'Išeiti iš viso ekrano' : 'Visas ekranas'; };
  label();
  b.onclick = function(){
    try {
      if (isFs()) { (TD.exitFullscreen || TD.webkitExitFullscreen).call(TD); }
      else { var r = req.call(root); if (r && r.catch) r.catch(function(){}); }
    } catch (e) {}
  };
  TD.addEventListener('fullscreenchange', label); TD.addEventListener('webkitfullscreenchange', label);
  D.body.appendChild(b);
})();
"""


def _fullscreen_button():
    """Mygtukas „Visas ekranas“ viršuje dešinėje (jei naršyklė tai leidžia)."""
    import json
    import streamlit.components.v1 as components
    components.html(
        "<script>(function(){var P=window.parent;var el=P.document.createElement('script');el.textContent="
        + json.dumps(_FS_JS) + ";P.document.head.appendChild(el);})();</script>",
        height=0,
    )


def render_lab_sheet(labs, img_url_for):
    """Visas laboratorinis darbas vienu lapu, kaip spausdintas darbo lapas.
    Lapas dalijamas ties brėžimo vietomis – ten įterpiamas schemų lapas."""
    st.markdown(
        "<style>.block-container{max-width:min(1500px,100%) !important;"
        "padding:0.6rem max(14px,2.2vw) 4rem !important}"
        # nematomi pagalbiniai elementai (aukštis 0) neužima vietos virš lapo
        "[data-testid=stElementContainer]:has(> iframe[height='0']),"
        ".element-container:has(> iframe[height='0']){position:absolute !important}</style>",
        unsafe_allow_html=True,
    )
    _fullscreen_button()
    title = (lab_spec(labs[0]["question_bank"]).get("title") or "") if labs else ""
    title = re.sub(r"^[HS]\d\.\s*", "", title)
    toc = [{"tid": t["id"], "title": t["question_bank"]["prompt"]} for t in labs]
    chunks, cur = [], []
    for tq in labs:
        q = tq["question_bank"]
        blocks = lab_spec(q).get("blocks") or []
        part = {"tid": tq["id"], "title": q["prompt"], "points": q.get("points") or 0, "blocks": blocks}
        start = 0
        for bi, b in enumerate(blocks):
            if b.get("t") == "pad":
                cur.append(dict(part, **{"from": start, "to": bi + 1}))
                chunks.append(("sheet", cur))
                chunks.append(("pad", tq))
                cur, start = [], bi + 1
        if start < len(blocks) or start == 0:
            cur.append(dict(part, **{"from": start, "to": len(blocks)}))
    if cur:
        chunks.append(("sheet", cur))
    fig = 0
    for ci, (kind, x) in enumerate(chunks):
        if kind == "sheet":
            values = {p["tid"]: _vals(p["tid"], st.session_state.get(f"ans_{p['tid']}")) for p in x}
            _sheet(sheet={"master": ci == 0, "title": title, "toc": toc, "parts": x}, values=values, fig0=fig,
                   key=f"labsheet_{ci}", default=None)
            fig += sum(1 for p in x for b in p["blocks"][p["from"]:p["to"]] if b.get("t") == "img")
        else:
            try:
                from utils.sketch import circuit_pad
                circuit_pad(key=f"draft_{x['id']}", initial_url=img_url_for(x["id"]), height=640)
            except Exception:
                pass
