"""
common/kinematics.py
====================
Modelos matemáticos de locomoción para el Proyecto Final (Taller 8):
1. Modelo Cinemático de la Bicicleta (vehículos con dirección delantera).
2. Cinemática Diferencial Directa e Inversa (robot diferencial de dos ruedas).
3. Generador de comandos (v, w, t) para trayectorias de precisión:
   - Avance en línea recta (1 metro o distancia arbitraria).
   - Arco de 1/4 de círculo (R = 1 metro o radio arbitrario) a derecha e izquierda.
   - Arco de ángulo arbitrario.
"""

import math


class BicycleModel:
    """
    Modelo cinemático de la bicicleta para un vehículo con distancia entre ejes L
    y ángulo de dirección delantero alpha (en radianes).

    Ecuaciones geométricas:
        r_d = L / sin(alpha)   (Radio de giro de la rueda delantera)
        r_t = L / tan(alpha)   (Radio de giro de la rueda trasera)

    Si el vehículo barre un ángulo beta (rad):
        arco_trasero   = beta * r_t
        arco_delantero = beta * r_d

    Ecuaciones diferenciales de estado:
        dx/dt    = v * cos(beta)
        dy/dt    = v * sin(beta)
        dbeta/dt = (v / L) * tan(alpha)
    """

    def __init__(self, wheelbase_L: float = 0.15):
        if wheelbase_L <= 0:
            raise ValueError("La distancia entre ejes L debe ser mayor que 0.")
        self.L = float(wheelbase_L)

    def turning_radii(self, alpha_rad: float) -> tuple[float, float]:
        """
        Retorna (r_t, r_d): radios de giro de la rueda trasera y delantera.
        Si alpha == 0 (movimiento recto), retorna (inf, inf).
        """
        if abs(alpha_rad) < 1e-9:
            return float("inf"), float("inf")
        r_d = self.L / math.sin(alpha_rad)
        r_t = self.L / math.tan(alpha_rad)
        return r_t, r_d

    def wheel_arcs(self, alpha_rad: float, beta_rad: float) -> tuple[float, float]:
        """
        Si el vehículo avanza un ángulo beta (rad), retorna:
            (arco_rueda_trasera, arco_rueda_delantera) = (beta * r_t, beta * r_d)
        """
        r_t, r_d = self.turning_radii(alpha_rad)
        return beta_rad * r_t, beta_rad * r_d

    def derivatives(
        self, v: float, beta_rad: float, alpha_rad: float
    ) -> tuple[float, float, float]:
        """
        Calcula las derivadas temporales (x_dot, y_dot, beta_dot):
            x_dot    = v * cos(beta)
            y_dot    = v * sin(beta)
            beta_dot = (v / L) * tan(alpha)
        """
        x_dot = v * math.cos(beta_rad)
        y_dot = v * math.sin(beta_rad)
        beta_dot = (v / self.L) * math.tan(alpha_rad)
        return x_dot, y_dot, beta_dot

    def step(
        self,
        x: float,
        y: float,
        beta_rad: float,
        v: float,
        alpha_rad: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Integra un paso de tiempo dt mediante Euler explícito."""
        dx, dy, dbeta = self.derivatives(v, beta_rad, alpha_rad)
        return x + dx * dt, y + dy * dt, beta_rad + dbeta * dt


class DifferentialKinematics:
    """
    Modelo de Cinemática Diferencial para el robot CAR de dos ruedas motrices.

    Parámetros:
        d: Distancia desde el centro del robot a cada rueda (semitrocha, en metros).
           La distancia total entre las dos ruedas (trocha L_track) es 2 * d.

    Ecuaciones en un círculo de radio R con velocidad angular w = alpha_dot:
        v_l = w * (R - d)
        v_c = w * R
        v_r = w * (R + d)

    Cinemática Inversa (de (v, w) del centro a velocidades de rueda (v_l, v_r)):
        v_l = v - w * d
        v_r = v + w * d

    Cinemática Directa (de velocidades de rueda (v_l, v_r) a (v, w) del robot):
        v = (v_r + v_l) / 2
        w = (v_r - v_l) / (2 * d)
    """

    def __init__(self, half_track_d: float = 0.0675, v_max: float = 0.25):
        """
        half_track_d: Distancia d del centro del chasis a cada rueda (m).
                      Por ejemplo, si las ruedas están separadas 13.5 cm -> d = 0.0675 m.
        v_max: Rapidez lineal máxima estimada de cada rueda a PWM 100% (m/s).
        """
        if half_track_d <= 0:
            raise ValueError("La distancia d del centro a la rueda debe ser > 0.")
        if v_max <= 0:
            raise ValueError("La velocidad máxima v_max debe ser > 0.")
        self.d = float(half_track_d)
        self.v_max = float(v_max)

    def inverse(self, v: float, w: float) -> tuple[float, float]:
        """
        Cinemática Inversa:
            v_l = v - w * d
            v_r = v + w * d
        Donde:
            v: velocidad lineal del centro del carro (m/s)
            w: velocidad angular (rad/s).
               w > 0 -> giro a la izquierda (antihorario, v_r > v_l)
               w < 0 -> giro a la derecha (horario, v_l > v_r)
        """
        v_l = v - (w * self.d)
        v_r = v + (w * self.d)
        return v_l, v_r

    def forward(self, v_l: float, v_r: float) -> tuple[float, float]:
        """
        Cinemática Directa:
            v = (v_r + v_l) / 2
            w = (v_r - v_l) / (2 * d)
        """
        v = (v_r + v_l) / 2.0
        w = (v_r - v_l) / (2.0 * self.d)
        return v, w

    def wheel_speeds_from_radius(
        self, radius_R: float, w: float
    ) -> tuple[float, float, float]:
        """
        Calcula (v_l, v_c, v_r) usando las ecuaciones paramétricas del círculo:
            v_l = w * (R - d)
            v_c = w * R
            v_r = w * (R + d)
        """
        v_l = w * (radius_R - self.d)
        v_c = w * radius_R
        v_r = w * (radius_R + self.d)
        return v_l, v_c, v_r

    def create_command(
        self, v: float, w: float, t: float, label: str = "custom"
    ) -> dict:
        """
        Construye el diccionario de comando para la clase CAR junto con
        los cálculos detallados de cinemática inversa y arcos esperados.
        """
        t_clean = max(0.0, float(t))
        v_clean = float(v)
        w_clean = float(w)
        v_l, v_r = self.inverse(v_clean, w_clean)

        pwm_l = max(-1.0, min(1.0, v_l / self.v_max))
        pwm_r = max(-1.0, min(1.0, v_r / self.v_max))

        return {
            "v": round(v_clean, 4),
            "w": round(w_clean, 4),
            "t": round(t_clean, 4),
            "d": round(self.d, 4),
            "v_l": round(v_l, 4),
            "v_r": round(v_r, 4),
            "pwm_l": round(pwm_l, 4),
            "pwm_r": round(pwm_r, 4),
            "arc_center_m": round(abs(v_clean) * t_clean, 4),
            "angle_deg": round(math.degrees(w_clean * t_clean), 2),
            "label": label,
        }

    def command_straight(self, distance_m: float = 1.0, speed_v: float = 0.20) -> dict:
        """
        Genera el comando (v, w, t) para avanzar en línea recta `distance_m` metros.
            w = 0
            t = |distance_m / speed_v|
        """
        if abs(speed_v) < 1e-6:
            raise ValueError("La rapidez v no puede ser 0 para avanzar una distancia.")
        v_signed = abs(speed_v) if distance_m >= 0 else -abs(speed_v)
        t = abs(distance_m) / abs(speed_v)
        return self.create_command(
            v=v_signed,
            w=0.0,
            t=t,
            label=f"Recta {distance_m:.2f} m",
        )

    def command_arc(
        self,
        radius_m: float = 1.0,
        angle_rad: float = math.pi / 2.0,
        direction: str = "right",
        speed_v: float = 0.20,
    ) -> dict:
        """
        Genera el comando (v, w, t) para describir un arco de círculo de radio `radius_m`
        y ángulo `angle_rad` (por defecto pi/2 rad = 90° = 1/4 de círculo).

        Fórmulas:
            |w| = |v| / R
            t   = |angle_rad| / |w| = (|angle_rad| * R) / |v|
            - Si direction == "left"  (izquierda, antihorario): w > 0 -> v_r > v_l
            - Si direction == "right" (derecha, horario):       w < 0 -> v_l > v_r
        """
        if radius_m <= 0:
            raise ValueError("El radio R debe ser mayor que 0.")
        if abs(speed_v) < 1e-6:
            raise ValueError("La rapidez v no puede ser 0.")

        v_abs = abs(speed_v)
        w_mag = v_abs / float(radius_m)
        t = abs(angle_rad) / w_mag

        dir_norm = direction.strip().lower()
        if dir_norm in ("right", "derecha", "der", "cw"):
            w = -w_mag
            dir_label = "Derecha"
        elif dir_norm in ("left", "izquierda", "izq", "ccw"):
            w = +w_mag
            dir_label = "Izquierda"
        else:
            raise ValueError(f"Dirección no válida: {direction}. Use 'right' o 'left'.")

        deg = math.degrees(abs(angle_rad))
        return self.create_command(
            v=v_abs,
            w=w,
            t=t,
            label=f"Arco {deg:.0f}° (R={radius_m:.2f}m) a {dir_label}",
        )

    def command_quarter_circle(
        self,
        radius_m: float = 1.0,
        direction: str = "right",
        speed_v: float = 0.20,
    ) -> dict:
        """
        Atajo específico para el requerimiento del taller:
        1/4 de círculo (90° = pi/2 rad) de radio `radius_m` (1.0 m por defecto)
        a derecha o izquierda.
        """
        return self.command_arc(
            radius_m=radius_m,
            angle_rad=math.pi / 2.0,
            direction=direction,
            speed_v=speed_v,
        )

    def simulate_trajectory(
        self, v: float, w: float, t: float, steps: int = 60
    ) -> list[tuple[float, float, float]]:
        """
        Simula la trayectoria (x, y, theta) del centro del carro durante el tiempo t
        partiendo de (0, 0, pi/2 [apuntando hacia arriba en el plano 2D]).
        Retorna lista de tuplas (x_m, y_m, theta_rad).
        """
        if steps <= 0 or t <= 0:
            return [(0.0, 0.0, math.pi / 2.0)]

        dt = t / float(steps)
        x, y, theta = 0.0, 0.0, math.pi / 2.0
        points = [(x, y, theta)]

        for _ in range(steps):
            x += v * math.cos(theta) * dt
            y += v * math.sin(theta) * dt
            theta += w * dt
            points.append((x, y, theta))

        return points
