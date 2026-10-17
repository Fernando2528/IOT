"""
main.py
=======
Lanzador en la raíz de Taller_8 para iniciar el panel de control en Flet.
"""

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FLET_DIR = os.path.join(CURRENT_DIR, "flet")
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if FLET_DIR not in sys.path:
    sys.path.insert(0, FLET_DIR)

import flet as ft
from flet.main import main as flet_main

if __name__ == "__main__":
    ft.app(target=flet_main)
