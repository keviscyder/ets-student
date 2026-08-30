"""
Supabase kliento inicializavimas mokinio app'ui.
Mokiniai neturi Supabase Auth - viskas veikia per anon/publishable
raktą ir siauras RLS policy (žr. db/migration_002_student_flow.sql).
"""
import os
import streamlit as st
from supabase import create_client, Client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (FileNotFoundError, KeyError, st.errors.StreamlitSecretNotFoundError):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("Trūksta SUPABASE_URL arba SUPABASE_KEY.")

    return create_client(url, key)


def set_access_token(supabase: Client, token) -> None:
    """
    Prideda arba pašalina 'x-access-token' antraštę tolimesnėms šio
    kliento REST užklausoms (submissions/answers RLS – žr.
    db/migration_003_rls_hardening_DRAFT.sql).

    SVARBU: Streamlit kiekvieną rerun'ą iš naujo kviečia get_client(),
    tad tai sukuria NAUJĄ postgrest sesiją be prieš tai nustatytų
    antraščių. Šią funkciją reikia iškviesti iš naujo po KIEKVIENO
    get_client() – žr. main.py, kur tai daroma iš st.session_state
    kiekvieno rerun'o pradžioje, o ne tik submission sukūrimo metu.

    Jei `token` yra None/tuščias (pvz., migracija dar netaikyta ir
    stulpelio access_token dar nėra), antraštė tiesiog nededama –
    veikia lygiai taip pat, kaip ir prieš šį pakeitimą.
    """
    if token:
        supabase.postgrest.session.headers["x-access-token"] = str(token)
    else:
        supabase.postgrest.session.headers.pop("x-access-token", None)
