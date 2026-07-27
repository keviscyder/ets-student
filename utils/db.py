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
