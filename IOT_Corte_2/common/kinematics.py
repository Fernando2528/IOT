"""
kinematics.py
=============
Módulo matemático de cinemática diferencial, conversión de unidades para los tópicos
oficiales de Coreografía (`motion/state` y `motion/sequence` según `motionTopics.md`),
generadores de trayectorias (Línea Recta de 1m y 1/4 de Círculo R=1m) y secuencias
oficiales (`even.json` para robots pares como `robot12` y `odd.json` para impares).
"""

import math
from dataclasses import dataclass

# ==============================================================================
# SECUENCIAS OFICIALES DE COREOGRAFÍA (even.json y odd.json)
# ==============================================================================
EVEN_STATES = [
    {
        "v_dm/s": 0,
        "w_deg/s": 45,
        "alpha0_deg": 0,
        "duration_s": 2,
    },
    {
        "v_dm/s": 0,
        "w_deg/s": -45,
        "alpha0_deg": -90,
        "alpha1_deg": 0,
        "duration_s": 2,
    },
    {
        "v_dm/s": 1.5708,
        "w_deg/s": 36,
        "duration_s": 5,
    },
    {
        "v_dm/s": 0,
        "w_deg/s": 0,
        "alpha0_deg": 90,
        "alpha1_deg": 67.5,
        "alpha2_deg": -67.5,
        "duration_s": 2,
    },
    {
        "v_dm/s": -1.5708,
        "w_deg/s": 36,
        "duration_s": 5,
    },
]

ODD_STATES = [
    {
        "v_dm/s": 0,
        "w_deg/s": 45,
        "alpha0_deg": 0,
        "duration_s": 2,
    },
    {
        "v_dm/s": 0,
        "w_deg/s": -45,
        "alpha0_deg": 90,
        "alpha1_deg": 67.5,
        "alpha2_deg": -67.5,
        "duration_s": 2,
    },
    {
        "v_dm/s": -1.5708,
        "w_deg/s": 36,
        "duration_s": 5,
    },
    {
        "v_dm/s": 0,
        "w_deg/s": 0,
        "alpha0_deg": -90,
        "alpha1_deg": 0,
        "alpha2_deg": 0,
        "duration_s": 2,
    },
    {
        "v_dm/s": 1.5708,
        "w_deg/s": 36,
        "duration_s": 5,
    },
]


def get_choreography_payload(name: str = "even", action: str = "create", run_at: str | None = "now") -> dict:
    """
    Construye el payload oficial para `motion/sequence` correspondiente a `even.json` u `odd.json`.
    Para `robot12` (par), la secuencia por defecto es `"even"`.
    """
    seq_name = "odd" if str(name).lower().strip() == "odd" else "even"
    states = [dict(s) for s in (ODD_STATES if seq_name == "odd" else EVEN_STATES)]
    payload = {
        "action": action,
        "name": seq_name,
    }
    if run_at is not None:
        payload["run_at"] = run_at
    if action == "create":
        payload["states"] = states
    return payload


# ==============================================================================
# CONVERSIÓN DE UNIDADES Y NORMALIZACIÓN (`motion/state`)
# ==============================================================================
def normalize_motion_state(payload: dict, prev_angles: dict | None = None) -> dict:
    """
    Normaliza un diccionario recibido en `motion/state` o dentro de `motion/sequence`:
      - `v_dm/s`: decímetros por segundo -> convierte también a `v_m_s` (m/s = dm/s * 0.1)
      - `w_deg/s`: grados por segundo    -> convierte también a `w_rad_s` (rad/s = deg/s * pi / 180)
      - `alpha0_deg`, `alpha1_deg`, `alpha2_deg`: ángulos del brazo en grados (por defecto 0 o valor previo)
      - `duration_s`: duración del paso en segundos (por defecto 1.0 s)
    """
    if not isinstance(payload, dict):
        raise ValueError("El estado de movimiento debe ser un objeto JSON (dict).")

    prev = prev_angles or {}
    v_dm_s = float(payload.get("v_dm/s", payload.get("v", 0.0) * 10.0 if "v" in payload and "v_dm/s" not in payload else 0.0))
    w_deg_s = float(payload.get("w_deg/s", math.degrees(float(payload.get("w", 0.0))) if "w" in payload and "w_deg/s" not in payload else 0.0))

    alpha0_deg = float(payload.get("alpha0_deg", prev.get("alpha0_deg", 0.0)))
    alpha1_deg = float(payload.get("alpha1_deg", prev.get("alpha1_deg", 0.0)))
    alpha2_deg = float(payload.get("alpha2_deg", prev.get("alpha2_deg", 0.0)))
    duration_s = max(0.01, float(payload.get("duration_s", payload.get("t", payload.get("time", 1.0)))))

    v_m_s = v_dm_s * 0.1
    w_rad_s = math.radians(w_deg_s)

    return {
        "v_dm/s": round(v_dm_s, 4),
        "w_deg/s": round(w_deg_s, 4),
        "alpha0_deg": round(alpha0_deg, 2),
        "alpha1_deg": round(alpha1_deg, 2),
        "alpha2_deg": round(alpha2_deg, 2),
        "duration_s": round(duration_s, 3),
        "v_m_s": v_m_s,
        "w_rad_s": w_rad_s,
    }


def parse_iso8601_to_epoch(iso_str: str) -> float | None:
    """
    Convierte una fecha/hora ISO-8601 (ej. '2025-09-25T20:00:00Z' o '2026-11-03T15:30:00-05:00')
    a segundos Unix epoch (UTC). Compatible tanto con PC como con MicroPython sin librerías externas.
    """
    if not iso_str or not isinstance(iso_str, str):
        return None
    s = iso_str.strip()
    if s.lower() in ("now", "immediately"):
        return None

    try:
        tz_offset_s = 0
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1]
        elif "T" in s:
            t_pos = s.find("T")
            plus_pos = s.rfind("+")
            minus_pos = s.rfind("-")
            tz_pos = max(plus_pos, minus_pos)
            if tz_pos > t_pos:
                sign = 1 if s[tz_pos] == "+" else -1
                tz_part = s[tz_pos + 1 :]
                s = s[:tz_pos]
                if ":" in tz_part:
                    tz_h, tz_m = tz_part.split(":", 1)
                else:
                    tz_h, tz_m = tz_part[:2], tz_part[2:] or "0"
                tz_offset_s = sign * (int(tz_h) * 3600 + int(tz_m) * 60)

        date_part, time_part = s.split("T", 1)
        year, month, day = [int(x) for x in date_part.split("-")]
        time_fields = time_part.split(":")
        hour = int(time_fields[0])
        minute = int(time_fields[1]) if len(time_fields) > 1 else 0
        sec_float = float(time_fields[2]) if len(time_fields) > 2 else 0.0
        sec_int = int(sec_float)
        frac = sec_float - sec_int

        # Algoritmo civil_from_days (Howard Hinnant) a días desde 1970-01-01
        y = year - (1 if month <= 2 else 0)
        era = (y if y >= 0 else y - 399) // 400
        yoe = y - era * 400
        m_adj = month - 3 if month > 2 else month + 9
        doy = (153 * m_adj + 2) // 5 + day - 1
        doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
        days = era * 146097 + doe - 719468

        epoch_utc = days * 86400 + hour * 3600 + minute * 60 + sec_int + frac - tz_offset_s
        return float(epoch_utc)
    except Exception:
        return None


# ==============================================================================
# CINEMÁTICA DIFERENCIAL Y GENERADORES DE TRAYECTORIA
# ==============================================================================
@dataclass
class WheelCommand:
    """Resultado cinemático para un movimiento diferencial o paso de coreografía."""
    v: float             # Rapidez lineal del centro del robot (m/s)
    w: float             # Velocidad angular del robot (rad/s)
    t: float             # Duración del comando (s)
    v_l: float           # Velocidad lineal de la rueda izquierda (m/s)
    v_r: float           # Velocidad lineal de la rueda derecha (m/s)
    pwm_l: float         # Ciclo útil normalizado rueda izquierda [-1.0, 1.0]
    pwm_r: float         # Ciclo útil normalizado rueda derecha   [-1.0, 1.0]
    arc_length: float    # Distancia recorrida por el centro del robot s = |v| * t (m)
    angle_deg: float     # Ángulo total girado Δα en grados
    description: str     # Descripción legible de la maniobra


class BicycleModel:
    """Modelo cinemático de la bicicleta."""

    @staticmethod
    def steering_from_curvature(length_L: float, radius_R: float) -> float:
        if math.isinf(radius_R) or abs(radius_R) < 1e-9:
            return 0.0
        return math.atan(length_L / radius_R)

    @staticmethod
    def angular_velocity(v: float, length_L: float, beta_rad: float) -> float:
        if abs(length_L) < 1e-9:
            raise ValueError("La longitud L de la bicicleta debe ser mayor a cero.")
        return (v / length_L) * math.tan(beta_rad)


class DifferentialKinematics:
    """
    Cinemática directa e inversa para el Carrobot de tracción diferencial
    y generador de estados compatibles con `motion/state`.
    """

    def __init__(self, half_track_d: float = 0.0675, v_max: float = 0.25):
        if half_track_d <= 0:
            raise ValueError("La semitrocha 'd' debe ser positiva (en metros).")
        if v_max <= 0:
            raise ValueError("La velocidad máxima 'v_max' debe ser positiva (en m/s).")
        self.d = float(half_track_d)
        self.v_max = float(v_max)

    def inverse(self, v: float, w: float) -> tuple[float, float]:
        """v_l = v - w * d, v_r = v + w * d"""
        v_l = float(v) - float(w) * self.d
        v_r = float(v) + float(w) * self.d
        return v_l, v_r

    def forward(self, v_l: float, v_r: float) -> tuple[float, float]:
        """v = (v_r + v_l) / 2, w = (v_r - v_l) / (2 * d)"""
        v = (float(v_r) + float(v_l)) / 2.0
        w = (float(v_r) - float(v_l)) / (2.0 * self.d)
        return v, w

    def build_command(self, v: float, w: float, t: float, label: str = "Movimiento") -> WheelCommand:
        t_val = max(0.0, float(t))
        v_l, v_r = self.inverse(v, w)

        pwm_l = v_l / self.v_max
        pwm_r = v_r / self.v_max

        max_pwm = max(abs(pwm_l), abs(pwm_r))
        if max_pwm > 1.0:
            scale = 1.0 / max_pwm
            pwm_l *= scale
            pwm_r *= scale
            v_l *= scale
            v_r *= scale
            v, w = self.forward(v_l, v_r)

        arc_s = abs(v) * t_val
        delta_deg = math.degrees(w * t_val)

        return WheelCommand(
            v=round(v, 4),
            w=round(w, 4),
            t=round(t_val, 3),
            v_l=round(v_l, 4),
            v_r=round(v_r, 4),
            pwm_l=round(pwm_l, 4),
            pwm_r=round(pwm_r, 4),
            arc_length=round(arc_s, 4),
            angle_deg=round(delta_deg, 2),
            description=label,
        )

    def straight_line_state(
        self,
        distance_m: float = 1.0,
        speed_m_s: float = 0.20,
        alpha0_deg: float = 0.0,
        alpha1_deg: float = 0.0,
        alpha2_deg: float = 0.0,
    ) -> dict:
        """
        Genera el payload oficial `motion/state` para avanzar en línea recta `distance_m` metros.
        """
        v_abs = min(abs(float(speed_m_s)), self.v_max)
        if v_abs < 1e-4:
            v_abs = 0.20
        v_m_s = v_abs if distance_m >= 0 else -v_abs
        duration_s = abs(float(distance_m)) / v_abs
        return {
            "v_dm/s": round(v_m_s * 10.0, 4),
            "w_deg/s": 0.0,
            "alpha0_deg": round(float(alpha0_deg), 2),
            "alpha1_deg": round(float(alpha1_deg), 2),
            "alpha2_deg": round(float(alpha2_deg), 2),
            "duration_s": round(duration_s, 3),
        }

    def quarter_circle_state(
        self,
        radius_m: float = 1.0,
        direction: str = "right",
        speed_m_s: float = 0.20,
        alpha0_deg: float = 0.0,
        alpha1_deg: float = 0.0,
        alpha2_deg: float = 0.0,
    ) -> dict:
        """
        Genera el payload oficial `motion/state` para realizar 1/4 de círculo (90°)
        con radio `radius_m` (por defecto 1.0 m -> arco s = pi/2 * 1m = 1.5708 m = 15.708 dm).
        """
        r = max(0.05, abs(float(radius_m)))
        angle_rad = math.pi / 2.0  # 90 grados (1/4 de círculo)

        max_center_v = self.v_max / (1.0 + (self.d / r))
        v_m_s = min(abs(float(speed_m_s)), max_center_v)
        if v_m_s < 1e-4:
            v_m_s = max_center_v * 0.8

        w_mag_rad_s = v_m_s / r
        duration_s = angle_rad / w_mag_rad_s

        dir_norm = direction.strip().lower()
        if dir_norm in ("right", "derecha", "der", "cw", "horaria"):
            w_rad_s = -w_mag_rad_s
        else:
            w_rad_s = +w_mag_rad_s

        return {
            "v_dm/s": round(v_m_s * 10.0, 4),
            "w_deg/s": round(math.degrees(w_rad_s), 4),
            "alpha0_deg": round(float(alpha0_deg), 2),
            "alpha1_deg": round(float(alpha1_deg), 2),
            "alpha2_deg": round(float(alpha2_deg), 2),
            "duration_s": round(duration_s, 3),
        }
