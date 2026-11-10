"""Anglų ir vokiečių kalbos mokinių programėlėje (mokytojams iš užsienio).

Python kode tekstai lieka lietuviški. Kai mokytojo/dėstytojo paskyros kalba – anglų
(arba adrese ?lang=en), į puslapį įterpiamas vertėjas: jis pakeičia matomus tekstus pagal
žodyną assets/i18n_en.json (tikslios eilutės ir šablonai su {}), taip pat to paties
adreso komponentų rėmeliuose (laikmatis, darbo lapas, schemų lapas). Mokinių įvesti
atsakymai ir testų turinys neverčiami.
"""
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils.terms import is_uni, ui_lang

_ASSETS = Path(__file__).resolve().parent.parent / "assets"

_JS = r"""
(function(){
  var W = window;   // vykdoma programos lange (įterpta kaip <script>), ne komponento rėmelyje
  var CFG = __CFG__;
  try { W.__etsI18n && W.__etsI18n.stop(); } catch (e) {}
  // kalba pakeista po vertimo: jau išversti tekstai atgal nepasikeis – perkraunama su nauja kalba
  var prev = W.__etsLang; W.__etsLang = CFG.lang;
  if (prev && prev !== 'lt' && prev !== CFG.lang) {
    try { var u = new URL(W.location.href); u.searchParams.set('lang', CFG.lang); W.location.replace(u.toString()); } catch (e) {}
    return;
  }
  if (!CFG.on) return;
  var D = CFG.dict, exact = {}, tpls = [];
  var norm = function (s) { return s.replace(/\s+/g, ' ').trim(); };
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
  Object.keys(D.exact).forEach(function (k) { exact[norm(k)] = D.exact[k]; });
  Object.keys(D.tpl).forEach(function (k) {
    tpls.push([new RegExp('^' + norm(k).split('{}').map(esc).join('([\\s\\S]*?)') + '$'), norm(D.tpl[k])]);
  });
  tpls.sort(function (a, b) { return b[0].source.length - a[0].source.length; });
  var UNI = CFG.lang === 'de' ? [[/Lernende/g,'Studierende'],[/Lehrkraft/g,'Lehrperson'],[/Klassen(?!buch)/g,'Gruppen'],[/Klasse/g,'Gruppe'],[/klassen(?!buch)/g,'gruppen'],[/klasse/g,'gruppe']] : [[/\bTeachers\b/g,'Lecturers'],[/\bteachers\b/g,'lecturers'],[/\bTeacher\b/g,'Lecturer'],[/\bteacher\b/g,'lecturer'],
             [/\bClasses\b/g,'Groups'],[/\bclasses\b/g,'groups'],[/\bClass\b/g,'Group'],[/\bclass\b/g,'group'],
             [/\bLessons?\b/g,'Lecture'],[/\blessons?\b/g,'lecture']];
  function tr(t) {
    var core = norm(t); if (!core || !/[A-Za-zĀ-ž]/.test(core)) return t;
    var out = exact[core];
    if (out === undefined) for (var i = 0; i < tpls.length; i++) {
      var m = core.match(tpls[i][0]);
      if (m) { var k = 0; out = tpls[i][1].replace(/\{\}/g, function () { var g = m[++k] || ''; var e = exact[norm(g)]; return e !== undefined ? e : g; }); break; }
    }
    if (out === undefined) return t;
    if (CFG.uni) UNI.forEach(function (r) { out = out.replace(r[0], r[1]); });
    return t.match(/^\s*/)[0] + out + t.match(/\s*$/)[0];
  }
  var SKIP = 'textarea, input, script, style, code, .katex, [data-testid="stMarkdownContainer"] .ets-q, .lab-content, section > h2 + *';
  var ATTRS = ['placeholder', 'title', 'aria-label'];
  function fixEl(e) { ATTRS.forEach(function (a) { var v = e.getAttribute && e.getAttribute(a); if (v) { var n = tr(v); if (n !== v) e.setAttribute(a, n); } }); }
  function fix(n) {
    if (!n) return;
    if (n.nodeType === 3) {
      var p = n.parentElement; if (!p || p.closest('textarea, script, style, code, .katex, [data-ets-raw]')) return;
      var v = n.nodeValue, nv = tr(v); if (nv !== v) n.nodeValue = nv; return;
    }
    if (n.nodeType !== 1) return;
    if (n.closest && n.closest('[data-ets-raw]')) return;
    fixEl(n);
    if (n.tagName === 'IFRAME') { hookFrame(n); return; }
    var tw = n.ownerDocument.createTreeWalker(n, 5);
    for (var c = tw.nextNode(); c; c = tw.nextNode()) {
      if (c.nodeType === 1) { fixEl(c); if (c.tagName === 'IFRAME') hookFrame(c); } else fix(c);
    }
  }
  var observers = [];
  function watch(doc) {
    if (!doc || !doc.body || doc.__etsI18n) return;
    doc.__etsI18n = true;
    fix(doc.body);
    var o = new (doc.defaultView || W).MutationObserver(function (ms) {
      ms.forEach(function (m) {
        if (m.type === 'characterData' || m.type === 'attributes') fix(m.target);
        else m.addedNodes.forEach(fix);
      });
    });
    o.observe(doc.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    observers.push([o, doc]);
  }
  function hookFrame(f) {
    var go = function () { try { watch(f.contentDocument); } catch (e) {} };
    go(); f.addEventListener('load', go);
  }
  watch(W.document);
  W.document.documentElement.lang = CFG.lang;
  W.__etsI18n = { stop: function () { observers.forEach(function (x) { x[0].disconnect(); try { delete x[1].__etsI18n; } catch (e) {} }); observers = []; } };
})();
"""


@st.cache_data(show_spinner=False)
def _dict(lang: str = "en"):
    try:
        return json.loads((_ASSETS / f"i18n_{lang}.json").read_text(encoding="utf-8"))
    except Exception:
        return {"exact": {}, "tpl": {}}


def inject_translator():
    """Įjungia arba išjungia vertimą puslapyje pagal dabartinę kalbą."""
    lang = ui_lang()
    on = lang != "lt"
    if not on and not st.session_state.get("_i18n_was_on"):
        return
    st.session_state._i18n_was_on = on
    cfg = {"on": on, "lang": lang, "uni": bool(on and is_uni()), "dict": _dict(lang) if on else {"exact": {}, "tpl": {}}}
    code = _JS.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
    components.html(
        "<script>(function(){var P=window.parent;var el=P.document.createElement('script');el.textContent="
        + json.dumps(code) + ";P.document.head.appendChild(el);})();</script>",
        height=0,
    )
