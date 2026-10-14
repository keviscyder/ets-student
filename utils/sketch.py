"""Rašymo ranka lapas (piešimo laukas) sprendimams vietoj nuotraukos."""
from pathlib import Path

import streamlit.components.v1 as components

_sketch = components.declare_component(
    "ets_sketch",
    path=str(Path(__file__).resolve().parent.parent / "sketch"),
)


def sketch_pad(key: str, initial_url: str | None = None):
    """Grąžina None arba {"n": skaitiklis, "data": "data:image/jpeg;base64,..."}."""
    return _sketch(initial=initial_url, key=key, default=None)
