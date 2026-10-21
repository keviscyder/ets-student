"""Mini žaidimų komponentas (žr. game/index.html)."""
import random
from pathlib import Path

import streamlit.components.v1 as components

from utils.grading import parse_game

_component = components.declare_component(
    "ets_game", path=str(Path(__file__).resolve().parent.parent / "game")
)


def game_spec(question: dict, seed: str) -> dict:
    """Ką rodyti mokiniui (be teisingų atsakymų), sumaišyta pagal seed."""
    d = parse_game(question)
    rnd = random.Random(seed)
    if d["kind"] == "match":
        left = [a for a, _ in d["pairs"]]
        right = [b for _, b in d["pairs"]]
        rnd.shuffle(left)
        rnd.shuffle(right)
        return {"kind": "match", "left": left, "right": right}
    if d["kind"] == "order":
        items = list(d["items"])
        for _ in range(5):
            rnd.shuffle(items)
            if items != d["items"] or len(items) < 2:
                break
        return {"kind": "order", "items": items}
    items = [it for _, its in d["groups"] for it in its]
    rnd.shuffle(items)
    return {"kind": "groups", "groups": [g for g, _ in d["groups"]], "items": items}


def game_widget(question: dict, seed: str, key: str, initial: str = None):
    return _component(spec=game_spec(question, seed), initial=initial or "", key=key, default=None)
