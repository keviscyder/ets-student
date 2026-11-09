"""Rašymo ranka lapas (piešimo laukas) sprendimams vietoj nuotraukos."""
from pathlib import Path

import streamlit.components.v1 as components

_sketch = components.declare_component(
    "ets_sketch",
    path=str(Path(__file__).resolve().parent.parent / "sketch"),
)


def sketch_pad(key: str, initial_url: str | None = None, height: int = 650):
    """Grąžina None arba {"n": skaitiklis, "data": "data:image/jpeg;base64,..."}."""
    return _sketch(initial=initial_url, height=height, key=key, default=None)


_circuit = components.declare_component(
    "ets_circuit",
    path=str(Path(__file__).resolve().parent.parent / "circuit"),
)


def circuit_pad(key: str, initial_url: str | None = None, height: int = 520):
    """Schemų ir grafikų lapas (elektros elementai, laidai, ašys, taškai).
    Grąžina tą patį kaip sketch_pad: None arba {"n": skaitiklis, "data": "data:image/jpeg;base64,..."}."""
    return _circuit(initial=initial_url, height=height, key=key, default=None)
