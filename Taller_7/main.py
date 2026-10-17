"""
main.py
=======
Punto de entrada principal para el Taller 7 / Taller 8.
Ejecuta la interfaz Flet con control de Servomotor (campo editable de grados, slider, presets)
y comandos de motores DC L298N.
"""

import os
import sys

# Agregar la carpeta flet al path para resolución de módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
flet_dir = os.path.join(current_dir, "flet")
if flet_dir not in sys.path:
    sys.path.insert(0, flet_dir)

import flet as ft
from main import main as flet_app_main

if __name__ == "__main__":
    ft.app(target=flet_app_main)