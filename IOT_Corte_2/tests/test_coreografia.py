"""
test_coreografia.py
===================
Pruebas unitarias para el Proyecto de Segundo Corte (Coreografía y Gemelo Virtual - Robot 12).
Verifica:
1. Conversión de unidades `v_dm/s` <-> `m/s` y `w_deg/s` <-> `rad/s`.
2. Generación de estados para Línea Recta (1 m) y 1/4 de Círculo (R = 1 m).
3. Estructura de las coreografías oficiales `even.json` (Robot 12) y `odd.json`.
4. Parseo de fechas ISO-8601 a época Unix para programación de secuencias (`run_at`).
"""

import json
import math
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.kinematics import (
    DifferentialKinematics,
    EVEN_STATES,
    ODD_STATES,
    get_choreography_payload,
    normalize_motion_state,
    parse_iso8601_to_epoch,
)


def test_normalize_motion_state_units():
    raw = {
        "v_dm/s": 1.5708,
        "w_deg/s": 36.0,
        "alpha0_deg": 90.0,
        "alpha1_deg": 67.5,
        "alpha2_deg": -67.5,
        "duration_s": 5.0,
    }
    norm = normalize_motion_state(raw)
    assert math.isclose(norm["v_m_s"], 0.15708, rel_tol=1e-5)
    assert math.isclose(norm["w_rad_s"], math.radians(36.0), rel_tol=1e-5)
    # En 5 segundos a 36°/s gira exactamente 180° (pi rad)
    assert math.isclose(norm["w_deg/s"] * norm["duration_s"], 180.0, rel_tol=1e-5)


def test_straight_1m_and_quarter_circle():
    kin = DifferentialKinematics(half_track_d=0.0675, v_max=0.25)

    # 1. Línea recta de 1 metro
    st_line = kin.straight_line_state(distance_m=1.0, speed_m_s=0.20)
    norm_line = normalize_motion_state(st_line)
    dist_m = norm_line["v_m_s"] * norm_line["duration_s"]
    assert math.isclose(dist_m, 1.0, rel_tol=1e-3)
    assert norm_line["w_deg/s"] == 0.0

    # 2. 1/4 de círculo (R = 1 m) a derecha e izquierda
    st_arc_r = kin.quarter_circle_state(radius_m=1.0, direction="right", speed_m_s=0.20)
    norm_arc_r = normalize_motion_state(st_arc_r)
    total_angle_deg = abs(norm_arc_r["w_deg/s"]) * norm_arc_r["duration_s"]
    arc_length_m = norm_arc_r["v_m_s"] * norm_arc_r["duration_s"]
    assert math.isclose(total_angle_deg, 90.0, rel_tol=1e-2)
    assert math.isclose(arc_length_m, math.pi / 2.0, rel_tol=1e-2)
    assert norm_arc_r["w_deg/s"] < 0


def test_even_and_odd_json_files():
    even_path = os.path.join(ROOT_DIR, "even.json")
    odd_path = os.path.join(ROOT_DIR, "odd.json")
    with open(even_path, "r", encoding="utf-8") as f:
        even_data = json.load(f)
    with open(odd_path, "r", encoding="utf-8") as f:
        odd_data = json.load(f)

    assert even_data["action"] == "create"
    assert even_data["name"] == "even"
    assert len(even_data["states"]) == 5
    assert odd_data["name"] == "odd"
    assert len(odd_data["states"]) == 5

    gen_even = get_choreography_payload("even", action="create", run_at="now")
    assert gen_even["states"] == EVEN_STATES
    assert len(ODD_STATES) == 5


def test_iso8601_parser():
    # 2025-09-25T20:00:00Z -> 1758830400.0
    ts = parse_iso8601_to_epoch("2025-09-25T20:00:00Z")
    assert ts is not None
    assert math.isclose(ts, 1758830400.0, abs_tol=1.0)
    assert parse_iso8601_to_epoch("now") is None
