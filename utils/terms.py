"""Mokyklos ir aukštosios mokyklos žodynas.

Aukštosios mokyklos studentai jungiasi adresu .../?m=aukstoji: tada rodomos tik
dėstytojų (teachers.institution = 'aukstoji') grupės, o sąsajoje vietoj
„mokinys, mokytojas, klasė, pamoka“ – „studentas, dėstytojas, grupė, paskaita“.
"""
import re

import streamlit as st

_L = r"[^\W\d_]"
_MOKIN = {"ys": "as", "io": "o", "iui": "ui", "į": "ą", "iu": "u", "yje": "e", "iai": "ai", "ių": "ų",
          "iams": "ams", "ius": "us", "iais": "ais", "iuose": "uose"}


def _w(stem, ends):
    return re.compile(rf"(?<!{_L})({stem})({ends})(?!{_L})", re.IGNORECASE)


def _case(src, out):
    return out[0].upper() + out[1:] if src[:1].isupper() else out


_RULES = [
    (_w("mokin", "|".join(sorted(_MOKIN, key=len, reverse=True))),
     lambda m: _case(m.group(1), "student" + _MOKIN.get(m.group(2).lower(), m.group(2)))),
    (_w("mokytoj", "uose|ams|ais|as|ui|us|ai|o|ą|u|e|ų"), lambda m: _case(m.group(1), "dėstytoj" + m.group(2))),
    (_w("klas", "ėmis|ėje|ėms|ėse|ės|ei|ių|es|ė|ę|e"), lambda m: _case(m.group(1), "grup" + m.group(2))),
    (_w("pamok", "omis|oje|oms|ose|os|ai|as|a|ą|ų|o"), lambda m: _case(m.group(1), "paskait" + m.group(2))),
]


def is_uni() -> bool:
    if "_uni" not in st.session_state:
        try:
            st.session_state._uni = (st.query_params.get("m") or "").lower() in ("aukstoji", "universitetas", "uni")
        except Exception:
            st.session_state._uni = False
    return bool(st.session_state._uni)


def T(text: str) -> str:
    """Sąsajos tekstas pagal platformos tipą."""
    if not text or not is_uni():
        return text
    for rx, f in _RULES:
        text = rx.sub(f, text)
    return text


def filter_classes(supabase, classes):
    """Mokykloje – mokytojų klasės, aukštojoje – dėstytojų grupės.
    Jei duomenų bazėje dar nėra stulpelio institution – rodomos visos."""
    try:
        rows = supabase.table("teachers").select("id, institution").execute().data or []
    except Exception:
        return classes
    if not rows:   # mokytojų sąrašas neprieinamas (pvz. ribotas raktas) – rodom visas
        return classes
    uni_teachers = {r["id"] for r in rows if r.get("institution") == "aukstoji"}
    want = is_uni()
    return [c for c in classes if (c.get("teacher_id") in uni_teachers) == want]
