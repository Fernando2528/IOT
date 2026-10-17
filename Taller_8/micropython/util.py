"""
util.py
=======
Funciones utilitarias de tiempo y serialización para PicoROS / MicroPython.
"""

import json
import time


def time_float() -> float:
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms() / 1000.0
    return time.time()


def to_json(obj) -> str:
    return json.dumps(obj)


def from_json(raw: str):
    return json.loads(raw)
