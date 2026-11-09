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


@st.cache_data(ttl=600, show_spinner=False)
def _class_inst(class_id: str):
    """Klasės/grupės savininko įstaigos tipas ('mokykla' | 'aukstoji') arba None."""
    try:
        from utils.db import get_client
        r = get_client().rpc("class_institution", {"p_class": class_id}).execute()
        return r.data if isinstance(r.data, str) else None
    except Exception:
        return None


def is_uni() -> bool:
    """Ar rodyti aukštosios mokyklos žodyną. Kai jau žinoma klasė/grupė (įvedus kodą),
    sprendžia jos mokytojo/dėstytojo paskyros tipas; kitaip – adreso ?m=aukstoji."""
    cid = st.session_state.get("class_id")
    if cid:
        inst = _class_inst(str(cid))
        if inst:
            return inst == "aukstoji"
    if "_uni" not in st.session_state:
        try:
            st.session_state._uni = (st.query_params.get("m") or "").lower() in ("aukstoji", "universitetas", "uni")
        except Exception:
            st.session_state._uni = False
    return bool(st.session_state._uni)


_STUD = {v: k for k, v in _MOKIN.items()}
_TO_SCHOOL = [
    (_w("student", "uose|ams|ais|as|o|ui|ą|u|e|ai|ų|us"),
     lambda m: _case(m.group(1), "mokin" + _STUD.get(m.group(2).lower(), m.group(2)))),
    (_w("dėstytoj", "uose|ams|ais|as|o|ui|ą|u|e|ai|ų|us"), lambda m: _case(m.group(1), "mokytoj" + m.group(2))),
]


def people(text: str) -> str:
    """Darbo turinio žmonių žodžiai griežtai pagal įstaigą (abiem kryptimis):
    mokykloje – mokytojas/mokinys, aukštojoje – dėstytojas/studentas."""
    if not text or not isinstance(text, str):
        return text
    for rx, f in (_RULES[:2] if is_uni() else _TO_SCHOOL):
        text = rx.sub(f, text)
    return text


def people_deep(x):
    """people() visoms eilutėms struktūroje (paveikslėlių failų vardai nekeičiami)."""
    if isinstance(x, str):
        return people(x)
    if isinstance(x, list):
        return [people_deep(v) for v in x]
    if isinstance(x, dict):
        return {k: (v if k in ("src", "t") else people_deep(v)) for k, v in x.items()}
    return x


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
