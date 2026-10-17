"""
tests/test_kinematics.py
========================
Suite de pruebas unitarias automáticas (pytest) para verificar las ecuaciones
del Modelo de la Bicicleta y la Cinemática Diferencial de la clase CAR.
"""

import math
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common.kinematics import BicycleModel, DifferentialKinematics


def test_bicycle_model_radii_and_arcs():
    """
    Verifica:
        r_d = L / sin(alpha)
        r_t = L / tan(alpha)
        arco_t = beta * r_t
        arco_d = beta * r_d
    """
    L = 0.20
    alpha = math.radians(30.0)  # sin(30°) = 0.5, tan(30°) = 1/sqrt(3)
    beta = math.pi / 2.0        # 90 grados

    bike = BicycleModel(wheelbase_L=L)
    r_t, r_d = bike.turning_radii(alpha)

    assert math.isclose(r_d, L / 0.5, rel_tol=1e-6)
    assert math.isclose(r_t, L / math.tan(alpha), rel_tol=1e-6)

    arc_t, arc_d = bike.wheel_arcs(alpha, beta)
    assert math.isclose(arc_t, beta * r_t, rel_tol=1e-6)
    assert math.isclose(arc_d, beta * r_d, rel_tol=1e-6)


def test_bicycle_model_differential_equations():
    """
    Verifica:
        x_dot    = v * cos(beta)
        y_dot    = v * sin(beta)
        beta_dot = (v / L) * tan(alpha)
    """
    L = 0.15
    v = 0.30
    beta = math.radians(60.0)
    alpha = math.radians(45.0)  # tan(45°) = 1.0

    bike = BicycleModel(wheelbase_L=L)
    x_dot, y_dot, beta_dot = bike.derivatives(v=v, beta_rad=beta, alpha_rad=alpha)

    assert math.isclose(x_dot, v * math.cos(beta), rel_tol=1e-6)
    assert math.isclose(y_dot, v * math.sin(beta), rel_tol=1e-6)
    assert math.isclose(beta_dot, (v / L) * 1.0, rel_tol=1e-6)


def test_differential_inverse_and_forward_kinematics():
    """
    Verifica la reciprocidad exacta entre Cinemática Inversa y Cinemática Directa:
        v_l = v - w * d
        v_r = v + w * d
        v   = (v_r + v_l) / 2
        w   = (v_r - v_l) / (2 * d)
    """
    d = 0.0675
    kin = DifferentialKinematics(half_track_d=d, v_max=0.25)

    v_orig = 0.18
    w_orig = 0.45

    v_l, v_r = kin.inverse(v_orig, w_orig)
    assert math.isclose(v_l, v_orig - w_orig * d, rel_tol=1e-9)
    assert math.isclose(v_r, v_orig + w_orig * d, rel_tol=1e-9)

    v_rec, w_rec = kin.forward(v_l, v_r)
    assert math.isclose(v_rec, v_orig, rel_tol=1e-9)
    assert math.isclose(w_rec, w_orig, rel_tol=1e-9)


def test_command_straight_1_meter():
    """
    Verifica el comando para avanzar 1 metro en línea recta:
        w = 0
        v_l == v_r == v
        v * t == 1.0 m
    """
    kin = DifferentialKinematics(half_track_d=0.0675, v_max=0.25)
    cmd = kin.command_straight(distance_m=1.0, speed_v=0.20)

    assert cmd["w"] == 0.0
    assert math.isclose(cmd["v_l"], cmd["v_r"], rel_tol=1e-6)
    assert math.isclose(cmd["v"] * cmd["t"], 1.0, rel_tol=1e-4)


def test_command_quarter_circle_1m_right_and_left():
    """
    Verifica los comandos para generar 1/4 de círculo (90° = pi/2 rad) de radio R = 1.0 m:
        - Arco central: v * t = (pi / 2) * 1.0 m ≈ 1.5708 m
        - Ángulo barrido: |w| * t = pi / 2 rad (90°)
        - A izquierda (w > 0): v_r > v_l
        - A derecha   (w < 0): v_l > v_r
    """
    d = 0.0675
    kin = DifferentialKinematics(half_track_d=d, v_max=0.25)

    cmd_left = kin.command_quarter_circle(radius_m=1.0, direction="left", speed_v=0.20)
    cmd_right = kin.command_quarter_circle(radius_m=1.0, direction="right", speed_v=0.20)

    expected_arc = math.pi / 2.0  # R = 1.0 m * pi/2 rad
    assert math.isclose(cmd_left["arc_center_m"], expected_arc, rel_tol=1e-3)
    assert math.isclose(cmd_right["arc_center_m"], expected_arc, rel_tol=1e-3)

    assert math.isclose(cmd_left["angle_deg"], 90.0, rel_tol=1e-2)
    assert math.isclose(cmd_right["angle_deg"], -90.0, rel_tol=1e-2)

    # A la izquierda la rueda derecha es la exterior (mayor velocidad)
    assert cmd_left["v_r"] > cmd_left["v_l"]
    # A la derecha la rueda izquierda es la exterior (mayor velocidad)
    assert cmd_right["v_l"] > cmd_right["v_r"]
