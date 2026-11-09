"""
main.py (Lanzador Raíz - Proyecto Segundo Corte: Coreografía Carrobot)
======================================================================
Ejecuta la interfaz gráfica de PC en Flet (`flet/main.py`).
Uso:
    python main.py
"""

import os
import sys
import flet as ft

FLET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flet")
if FLET_DIR not in sys.path:
    sys.path.insert(0, FLET_DIR)

from flet.main import main

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
