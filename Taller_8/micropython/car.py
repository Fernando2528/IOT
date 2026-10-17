"""
car.py
======
Implementación de la clase CAR para el Proyecto Final (Taller 8).

Conexiones Físicas por Defecto (Esquema Oficial Taller 8 - Driver Puente H MX1508 / L298N):
    - GP19 -> IN1 (Motor Izquierdo / Motor A - Pin 1)
    - GP18 -> IN2 (Motor Izquierdo / Motor A - Pin 2)
    - GP17 -> IN3 (Motor Derecho   / Motor B - Pin 1)
    - GP16 -> IN4 (Motor Derecho   / Motor B - Pin 2)
    - GND  -> (-) Masa común entre Raspberry Pi Pico W y Batería 18650
    - VSYS / Batería (+) -> (+) Alimentación de potencia del puente H

Cinemática Diferencial Implementada:
    Cinemática Inversa (de rapidez lineal `v` y velocidad angular `w` a ruedas):
        v_l = v - w * d
        v_r = v + w * d

    Cinemática Directa (de ruedas a centro del robot):
        v = (v_r + v_l) / 2
        w = (v_r - v_l) / (2 * d)

Suscripciones MQTT / PicoROS:
    - "CAR"       : {"v": float, "w": float, "t": float}
    - "CAR/cmd"   : {"v": float, "w": float, "t": float} o acciones ("straight", "arc", "stop")
    - "cmd"       : Compatible con formatos anteriores
    - "CAR/v"     : {"value": float} (ajusta rapidez lineal v)
    - "CAR/w"     : {"value": float} (ajusta velocidad angular w)
    - "CAR/t"     : {"value": float} (ajusta tiempo t y ejecuta el movimiento)
    - "CAR/stop"  : Detención inmediata de emergencia
    - "CAR/config": Calibración en tiempo real de d, v_max, deadzone, trim e inversión de giro
"""

import json
import math
import time
from machine import Pin
from pwm_out import PWMOut, parse_gpio_pin
from task import Task


class DualPWMBridgeMotor:
    """
    Controla un motor DC mediante un puente H de 2 pines PWM (IN1, IN2),
    como el módulo MX1508 del diagrama oficial (GP19/GP18 y GP17/GP16),
    o opcionalmente con un tercer pin Enable (ENA/ENB) para L298N de 6 hilos.
    """

    def __init__(self, in_a, in_b, en_pin=None, freq: int = 1000, invert: bool = False):
        self.invert = invert
        self.en_pwm = PWMOut(en_pin, freq=freq) if en_pin is not None else None

        if self.en_pwm is None:
            # Modo 4 pines PWM directo (MX1508 / L298N con jumpers puestos):
            # IN_A e IN_B operan como salidas PWM complementarias
            self.pwm_a = PWMOut(in_a, freq=freq)
            self.pwm_b = PWMOut(in_b, freq=freq)
            self.pin_a = None
            self.pin_b = None
        else:
            # Modo 6 pines con pin Enable dedicado (L298N sin jumpers)
            self.pin_a = Pin(parse_gpio_pin(in_a), Pin.OUT)
            self.pin_b = Pin(parse_gpio_pin(in_b), Pin.OUT)
            self.pwm_a = None
            self.pwm_b = None

        self.current_duty = 0
        self.stop()

    def set_speed(self, normalized: float, deadzone: float = 0.0) -> int:
        """
        Aplica una velocidad normalizada en el rango [-1.0, 1.0].
        Si normalized != 0 y deadzone > 0, compensa la fricción estática del motorreductor.
        Retorna el duty_u16 con signo aplicado.
        """
        u = max(-1.0, min(1.0, float(normalized)))
        if self.invert:
            u = -u

        if abs(u) < 1e-4:
            self.stop()
            return 0

        # Compensación suave de zona muerta (fricción estática de caja reductora TT)
        mag = abs(u)
        if deadzone > 0.0 and mag > 0.0:
            mag = deadzone + (1.0 - deadzone) * mag
            mag = min(1.0, mag)

        duty = int(mag * 65535)
        self.current_duty = duty if u > 0 else -duty

        if self.en_pwm is None:
            if u > 0:
                self.pwm_a.set_duty_u16(duty)
                self.pwm_b.set_duty_u16(0)
            else:
                self.pwm_a.set_duty_u16(0)
                self.pwm_b.set_duty_u16(duty)
        else:
            self.pin_a.value(1 if u > 0 else 0)
            self.pin_b.value(1 if u < 0 else 0)
            self.en_pwm.set_duty_u16(duty)

        return self.current_duty

    def stop(self):
        self.current_duty = 0
        if self.en_pwm is None:
            self.pwm_a.set_duty_u16(0)
            self.pwm_b.set_duty_u16(0)
        else:
            self.pin_a.value(0)
            self.pin_b.value(0)
            self.en_pwm.set_duty_u16(0)


class CAR(Task):
    """
    Clase CAR solicitada en el Taller 8 (Proyecto Final).
    Se suscribe a los tópicos correspondientes para avanzar con una rapidez lineal `v` (m/s)
    y una velocidad angular `w` (rad/s) durante un tiempo `t` (s), aplicando las ecuaciones
    de cinemática diferencial inversa y directa sobre las dos ruedas del carro.
    """

    def __init__(
        self,
        scheduler,
        pubsub,
        in1="GP19",
        in2="GP18",
        in3="GP17",
        in4="GP16",
        ena=None,
        enb=None,
        d: float = 0.0675,
        v_max: float = 0.25,
        deadzone: float = 0.28,
        pwm_freq: int = 1000,
        period_ms: int = 20,
    ):
        """
        Parámetros:
            scheduler : Instancia de Scheduler cooperativo.
            pubsub    : Instancia de Node / PubSubMQTT.
            in1, in2  : Pines GPIO del Motor Izquierdo (Por defecto GP19, GP18 según esquema).
            in3, in4  : Pines GPIO del Motor Derecho   (Por defecto GP17, GP16 según esquema).
            ena, enb  : Pines PWM opcionales si se usa L298N con jumpers retirados.
            d         : Distancia del centro del carro a cada rueda en metros (semitrocha).
                        Ej: Si la separación entre ruedas (2d) es 13.5 cm -> d = 0.0675 m.
            v_max     : Rapidez lineal máxima de las ruedas a PWM=100% (m/s).
            deadzone  : Fracción mínima de PWM para vencer la fricción estática (0.0 a 0.5).
            period_ms : Periodo de supervisión no bloqueante del temporizador de movimiento.
        """
        self.pubsub = pubsub
        self.d = float(d)
        self.v_max = float(v_max)
        self.deadzone = float(deadzone)

        # Factores de calibración fina por rueda (trim)
        self.trim_left = 1.0
        self.trim_right = 1.0

        # LED indicador de movimiento en la Pico W
        try:
            self.led = Pin("LED", Pin.OUT)
        except Exception:
            self.led = Pin(25, Pin.OUT)
        self.led.value(0)

        # Inicialización de los dos motores (Izquierdo y Derecho)
        self.motor_left = DualPWMBridgeMotor(in1, in2, en_pin=ena, freq=pwm_freq)
        self.motor_right = DualPWMBridgeMotor(in3, in4, en_pin=enb, freq=pwm_freq)

        # Variables de estado cinemático
        self.state = "IDLE"
        self.target_v = 0.0
        self.target_w = 0.0
        self.target_t = 0.0
        self.v_l = 0.0
        self.v_r = 0.0
        self.move_start_ms = 0
        self.move_end_ms = 0
        self.current_label = "En reposo"

        # Suscripciones a tópicos MQTT / PicoROS
        topics_cmd = ["CAR", "CAR/cmd", "car/cmd", "cmd"]
        for tp in topics_cmd:
            self.pubsub.subscribe(tp, self._on_command)

        self.pubsub.subscribe("CAR/v", self._on_set_v)
        self.pubsub.subscribe("CAR/w", self._on_set_w)
        self.pubsub.subscribe("CAR/t", self._on_set_t)
        self.pubsub.subscribe("CAR/stop", self._on_stop_topic)
        self.pubsub.subscribe("CAR/config", self._on_config_topic)

        super().__init__(scheduler, period_ms=period_ms, priority=1, name="CAR")
        print(
            f"[CAR] Inicializado en pines ({in1},{in2}) y ({in3},{in4}) | "
            f"d={self.d}m, v_max={self.v_max}m/s"
        )

    # ==================================================================
    # ECUACIONES DE CINEMÁTICA DIFERENCIAL
    # ==================================================================
    def inverse_kinematics(self, v: float, w: float) -> tuple[float, float]:
        """
        Cinemática Inversa:
            v_l = v - w * d
            v_r = v + w * d
        """
        v_l = float(v) - float(w) * self.d
        v_r = float(v) + float(w) * self.d
        return v_l, v_r

    def forward_kinematics(self, v_l: float, v_r: float) -> tuple[float, float]:
        """
        Cinemática Directa:
            v = (v_r + v_l) / 2
            w = (v_r - v_l) / (2 * d)
        """
        v = (float(v_r) + float(v_l)) / 2.0
        w = (float(v_r) - float(v_l)) / (2.0 * self.d)
        return v, w

    # ==================================================================
    # EJECUCIÓN DE MOVIMIENTO (v, w, t)
    # ==================================================================
    def move(self, v: float, w: float, t: float, label: str = "Comando (v,w,t)"):
        """
        Comanda al carro para avanzar con rapidez lineal `v` (m/s) y velocidad
        angular `w` (rad/s) durante un tiempo `t` (segundos) sin bloquear el CPU.
        """
        t_val = float(t)
        if t_val <= 0.0 or (abs(v) < 1e-5 and abs(w) < 1e-5):
            self.stop("Comando de parada / tiempo cero")
            return

        # 1. Cinemática Inversa: obtener velocidades lineales de cada rueda
        v_l, v_r = self.inverse_kinematics(v, w)

        # 2. Normalizar respecto a v_max
        u_l = (v_l / self.v_max) * self.trim_left
        u_r = (v_r / self.v_max) * self.trim_right

        # Si alguna rueda supera 1.0 (100% PWM), escalamos ambas ruedas por igual
        # para conservar intacto el radio de giro R = v / w y alargamos t en la misma proporción
        max_u = max(abs(u_l), abs(u_r))
        if max_u > 1.0:
            scale = 1.0 / max_u
            u_l *= scale
            u_r *= scale
            v_l *= scale
            v_r *= scale
            t_val /= scale

        # 3. Aplicar PWM a ambos puentes H
        duty_l = self.motor_left.set_speed(u_l, deadzone=self.deadzone)
        duty_r = self.motor_right.set_speed(u_r, deadzone=self.deadzone)
        self.led.value(1)

        # 4. Programar temporizador no bloqueante en ticks_ms
        now = time.ticks_ms()
        duration_ms = int(t_val * 1000)
        self.move_start_ms = now
        self.move_end_ms = time.ticks_add(now, duration_ms)

        self.target_v, self.target_w = self.forward_kinematics(v_l, v_r)
        self.target_t = t_val
        self.v_l = v_l
        self.v_r = v_r
        self.state = "MOVING"
        self.current_label = label

        self._publish_status(
            state="in_progress",
            message=(
                f"{label} | v={self.target_v:.3f} m/s, w={self.target_w:.3f} rad/s, "
                f"t={self.target_t:.2f} s -> v_l={v_l:.3f}, v_r={v_r:.3f} m/s"
            ),
            duty_l=duty_l,
            duty_r=duty_r,
        )

    def stop(self, reason: str = "Detenido"):
        """Detiene inmediatamente ambos motores y apaga el indicador LED."""
        self.motor_left.stop()
        self.motor_right.stop()
        self.led.value(0)
        self.state = "IDLE"
        self.v_l = 0.0
        self.v_r = 0.0
        self._publish_status(state="stopped", message=reason, duty_l=0, duty_r=0)

    def update(self):
        """
        Ejecutado periódicamente por el Scheduler (cada 20 ms).
        Verifica si el tiempo `t` de la maniobra ya concluyó sin usar sleep().
        """
        if self.state == "MOVING":
            now = time.ticks_ms()
            if time.ticks_diff(now, self.move_end_ms) >= 0:
                self.motor_left.stop()
                self.motor_right.stop()
                self.led.value(0)
                self.state = "IDLE"
                elapsed_s = time.ticks_diff(now, self.move_start_ms) / 1000.0
                self._publish_status(
                    state="completed",
                    message=f"Completado: {self.current_label} ({elapsed_s:.2f} s)",
                    duty_l=0,
                    duty_r=0,
                )

    # ==================================================================
    # MANEJADORES DE TÓPICOS MQTT
    # ==================================================================
    def _parse_payload(self, msg) -> dict:
        if isinstance(msg, dict):
            return msg
        if isinstance(msg, (bytes, bytearray)):
            msg = msg.decode("utf-8")
        if isinstance(msg, str):
            try:
                return json.loads(msg)
            except Exception:
                return {"value": msg}
        return {"value": msg}

    def _on_command(self, topic=None, msg=None):
        """
        Procesa mensajes enviados a 'CAR', 'CAR/cmd' o 'cmd'.
        Soporta:
        1. Formato directo (v, w, t):
           {"v": 0.20, "w": 0.0, "t": 5.0, "label": "Recta 1m"}
        2. Formato de acciones geométricas:
           - {"action": "straight", "distance": 1.0, "v": 0.20}
           - {"action": "arc", "radius": 1.0, "direction": "right"|"left", "angle_deg": 90, "v": 0.20}
           - {"action": "stop"}
        """
        try:
            data = self._parse_payload(msg)
            action = str(data.get("action", "")).lower()

            if action == "stop":
                self.stop("Parada de emergencia solicitada por el usuario")
                return

            if action == "straight":
                dist = float(data.get("distance", 1.0))
                v = float(data.get("v", self.v_max * 0.8))
                v_signed = abs(v) if dist >= 0 else -abs(v)
                t = abs(dist) / max(0.01, abs(v))
                self.move(v=v_signed, w=0.0, t=t, label=f"Línea recta {dist:.2f}m")
                return

            if action == "arc":
                radius = float(data.get("radius", 1.0))
                direction = str(data.get("direction", "right")).lower()
                angle_deg = float(data.get("angle_deg", 90.0))
                angle_rad = math.radians(abs(angle_deg))
                v = abs(float(data.get("v", self.v_max * 0.8)))
                w_mag = v / max(0.05, radius)
                t = angle_rad / w_mag
                w = -w_mag if direction in ("right", "derecha", "der") else +w_mag
                dir_txt = "Derecha" if w < 0 else "Izquierda"
                self.move(
                    v=v,
                    w=w,
                    t=t,
                    label=f"Arco {angle_deg:.0f}° R={radius:.2f}m ({dir_txt})",
                )
                return

            # Formato estándar de la clase CAR: {"v": v, "w": w, "t": t}
            if "v" in data or "w" in data or "t" in data:
                v = float(data.get("v", 0.0))
                w = float(data.get("w", 0.0))
                t = float(data.get("t", 0.0))
                label = str(data.get("label", f"CAR(v={v:.2f}, w={w:.2f}, t={t:.2f}s)"))
                self.move(v=v, w=w, t=t, label=label)

        except Exception as err:
            print("[CAR] Error procesando comando:", err)
            self._publish_status(state="error", message=str(err))

    def _on_set_v(self, topic=None, msg=None):
        data = self._parse_payload(msg)
        self.target_v = float(data.get("value", data.get("v", 0.0)))
        print(f"[CAR] Velocidad lineal preajustada: v = {self.target_v} m/s")

    def _on_set_w(self, topic=None, msg=None):
        data = self._parse_payload(msg)
        self.target_w = float(data.get("value", data.get("w", 0.0)))
        print(f"[CAR] Velocidad angular preajustada: w = {self.target_w} rad/s")

    def _on_set_t(self, topic=None, msg=None):
        data = self._parse_payload(msg)
        t = float(data.get("value", data.get("t", 0.0)))
        self.move(
            v=self.target_v,
            w=self.target_w,
            t=t,
            label=f"CAR individual (v={self.target_v:.2f}, w={self.target_w:.2f}, t={t:.2f}s)",
        )

    def _on_stop_topic(self, topic=None, msg=None):
        self.stop("Detenido vía tópico CAR/stop")

    def _on_config_topic(self, topic=None, msg=None):
        """Permite calibrar parámetros físicos en vivo desde Flet."""
        data = self._parse_payload(msg)
        if "d" in data and float(data["d"]) > 0:
            self.d = float(data["d"])
        if "v_max" in data and float(data["v_max"]) > 0:
            self.v_max = float(data["v_max"])
        if "deadzone" in data:
            self.deadzone = max(0.0, min(0.6, float(data["deadzone"])))
        if "trim_left" in data:
            self.trim_left = max(0.2, min(1.5, float(data["trim_left"])))
        if "trim_right" in data:
            self.trim_right = max(0.2, min(1.5, float(data["trim_right"])))
        if "invert_left" in data:
            self.motor_left.invert = bool(data["invert_left"])
        if "invert_right" in data:
            self.motor_right.invert = bool(data["invert_right"])

        self._publish_status(
            state="configured",
            message=(
                f"Calibrado: d={self.d:.4f}m, v_max={self.v_max:.2f}m/s, "
                f"deadzone={self.deadzone:.2f}, trim=({self.trim_left:.2f},{self.trim_right:.2f})"
            ),
        )

    def _publish_status(self, state: str, message: str, duty_l: int = 0, duty_r: int = 0):
        payload = {
            "state": state,
            "message": message,
            "v": round(self.target_v, 4),
            "w": round(self.target_w, 4),
            "t": round(self.target_t, 3),
            "v_l": round(self.v_l, 4),
            "v_r": round(self.v_r, 4),
            "d": round(self.d, 4),
            "v_max": round(self.v_max, 3),
            "duty_l": duty_l,
            "duty_r": duty_r,
            "timestamp": time.ticks_ms() if hasattr(time, "ticks_ms") else 0,
        }
        self.pubsub.publish("CAR/status", payload)
        self.pubsub.publish("status", payload)
        print(f"[CAR:{state.upper()}] {message}")


# Alias por compatibilidad de estilo PEP8
Car = CAR
