"""
car.py
======
Controlador de tracción diferencial (Clase CAR) para las dos ruedas del Carrobot.
Usa el pinout físico verificado en el puente H L298N de la Raspberry Pi Pico W:
    - PIN_IN1 = "GP16" (Motor Izquierdo A - Dirección 1)
    - PIN_IN2 = "GP17" (Motor Izquierdo A - Dirección 2)
    - PIN_IN3 = "GP18" (Motor Derecho   B - Dirección 1)
    - PIN_IN4 = "GP19" (Motor Derecho   B - Dirección 2)
    - PIN_ENA = "GP6"  (PWM Velocidad Motor Izquierdo)
    - PIN_ENB = "GP7"  (PWM Velocidad Motor Derecho)
"""

import json
import math
import time
from machine import Pin
from pwm_out import PWMOut, parse_gpio_pin
from task import Task


class DualPWMBridgeMotor:
    """Controla un canal del puente H L298N (modo 6 hilos con ENA/ENB o 4 hilos PWM)."""

    def __init__(self, in_a, in_b, en_pin=None, freq: int = 1000, invert: bool = False):
        self.invert = invert
        self.en_pwm = PWMOut(en_pin, freq=freq) if en_pin is not None else None

        if self.en_pwm is None:
            self.pwm_a = PWMOut(in_a, freq=freq)
            self.pwm_b = PWMOut(in_b, freq=freq)
            self.pin_a = None
            self.pin_b = None
        else:
            self.pin_a = Pin(parse_gpio_pin(in_a), Pin.OUT)
            self.pin_b = Pin(parse_gpio_pin(in_b), Pin.OUT)
            self.pwm_a = None
            self.pwm_b = None

        self.current_duty = 0
        self.stop()

    def set_speed(self, normalized: float, deadzone: float = 0.0) -> int:
        u = max(-1.0, min(1.0, float(normalized)))
        if self.invert:
            u = -u

        if abs(u) < 1e-4:
            self.stop()
            return 0

        mag = abs(u)
        if deadzone > 0.0 and mag > 0.0:
            mag = min(1.0, deadzone + (1.0 - deadzone) * mag)

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
    Controlador cinemático diferencial de las ruedas del Carrobot.
    Trabaja en coordinación con `CarrobotMotionTask` para ejecutar tanto comandos
    individuales como las secuencias sincronizadas con el Gemelo Virtual.
    """

    def __init__(
        self,
        scheduler,
        pubsub,
        in1="GP16",
        in2="GP17",
        in3="GP18",
        in4="GP19",
        ena="GP6",
        enb="GP7",
        d: float = 0.0675,
        v_max: float = 0.25,
        deadzone: float = 0.55,
        pwm_freq: int = 1000,
        period_ms: int = 20,
    ):
        self.pubsub = pubsub
        self.d = float(d)
        self.v_max = float(v_max)
        self.deadzone = float(deadzone)
        self.trim_left = 1.0
        self.trim_right = 1.0

        try:
            self.led = Pin("LED", Pin.OUT)
        except Exception:
            self.led = Pin(25, Pin.OUT)
        self.led.value(0)

        self.motor_left = DualPWMBridgeMotor(in1, in2, en_pin=ena, freq=pwm_freq)
        self.motor_right = DualPWMBridgeMotor(in3, in4, en_pin=enb, freq=pwm_freq)

        self.state = "IDLE"
        self.target_v = 0.0
        self.target_w = 0.0
        self.target_t = 0.0
        self.v_l = 0.0
        self.v_r = 0.0
        self.move_start_ms = 0
        self.move_end_ms = 0
        self.current_label = "En reposo"

        for tp in ("CAR", "CAR/cmd", "car/cmd", "cmd"):
            self.pubsub.subscribe(tp, self._on_command)
        self.pubsub.subscribe("CAR/stop", self._on_stop_topic)
        self.pubsub.subscribe("CAR/config", self._on_config_topic)

        super().__init__(scheduler, period_ms=period_ms, priority=1, name="CAR")
        print(
            f"[CAR] Listo en IN=({in1},{in2},{in3},{in4}) EN=({ena},{enb}) | "
            f"d={self.d}m, v_max={self.v_max}m/s"
        )

    def inverse_kinematics(self, v: float, w: float) -> tuple[float, float]:
        """v_l = v - w * d, v_r = v + w * d"""
        v_l = float(v) - float(w) * self.d
        v_r = float(v) + float(w) * self.d
        return v_l, v_r

    def forward_kinematics(self, v_l: float, v_r: float) -> tuple[float, float]:
        """v = (v_r + v_l) / 2, w = (v_r - v_l) / (2 * d)"""
        v = (float(v_r) + float(v_l)) / 2.0
        w = (float(v_r) - float(v_l)) / (2.0 * self.d)
        return v, w

    def move(
        self,
        v: float,
        w: float,
        t: float,
        label: str = "Estado (v,w,t)",
        keep_duration: bool = True,
    ):
        """
        Aplica rapidez lineal `v` (m/s) y velocidad angular `w` (rad/s) durante `t` (s).
        Si `keep_duration=True` (por defecto para sincronía con el Gemelo Virtual),
        mantiene `t` exacto incluso si alguna rueda satura a PWM=100%.
        """
        t_val = max(0.0, float(t))
        if t_val <= 0.0 or (abs(v) < 1e-5 and abs(w) < 1e-5):
            self.motor_left.stop()
            self.motor_right.stop()
            self.led.value(0)
            self.target_v = 0.0
            self.target_w = 0.0
            self.target_t = t_val
            self.v_l = 0.0
            self.v_r = 0.0
            self.state = "IDLE"
            self.current_label = label
            return 0, 0

        v_l, v_r = self.inverse_kinematics(v, w)
        u_l = (v_l / self.v_max) * self.trim_left
        u_r = (v_r / self.v_max) * self.trim_right

        max_u = max(abs(u_l), abs(u_r))
        if max_u > 1.0:
            scale = 1.0 / max_u
            u_l *= scale
            u_r *= scale
            v_l *= scale
            v_r *= scale
            if not keep_duration:
                t_val /= scale

        duty_l = self.motor_left.set_speed(u_l, deadzone=self.deadzone)
        duty_r = self.motor_right.set_speed(u_r, deadzone=self.deadzone)
        self.led.value(1)

        now = time.ticks_ms()
        self.move_start_ms = now
        self.move_end_ms = time.ticks_add(now, int(t_val * 1000))

        self.target_v, self.target_w = self.forward_kinematics(v_l, v_r)
        self.target_t = t_val
        self.v_l = v_l
        self.v_r = v_r
        self.state = "MOVING"
        self.current_label = label

        self._publish_status(
            state="in_progress",
            message=f"{label} | v={self.target_v:.3f}m/s, w={self.target_w:.3f}rad/s, t={t_val:.2f}s",
            duty_l=duty_l,
            duty_r=duty_r,
        )
        return duty_l, duty_r

    def stop(self, reason: str = "Detenido"):
        self.motor_left.stop()
        self.motor_right.stop()
        self.led.value(0)
        self.state = "IDLE"
        self.target_v = 0.0
        self.target_w = 0.0
        self.v_l = 0.0
        self.v_r = 0.0
        self.current_label = reason
        self._publish_status(state="stopped", message=reason, duty_l=0, duty_r=0)

    def update(self):
        if self.state == "MOVING":
            now = time.ticks_ms()
            if time.ticks_diff(now, self.move_end_ms) >= 0:
                self.motor_left.stop()
                self.motor_right.stop()
                self.led.value(0)
                self.state = "IDLE"
                self.v_l = 0.0
                self.v_r = 0.0
                elapsed_s = time.ticks_diff(now, self.move_start_ms) / 1000.0
                self._publish_status(
                    state="completed",
                    message=f"Completado: {self.current_label} ({elapsed_s:.2f}s)",
                    duty_l=0,
                    duty_r=0,
                )

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
        try:
            data = self._parse_payload(msg)
            action = str(data.get("action", "")).lower()

            if action == "stop":
                self.stop("Parada de emergencia")
                return

            if action == "straight":
                dist = float(data.get("distance", 1.0))
                v = float(data.get("v", self.v_max * 0.8))
                v_signed = abs(v) if dist >= 0 else -abs(v)
                t = abs(dist) / max(0.01, abs(v))
                self.move(v=v_signed, w=0.0, t=t, label=f"Recta {dist:.2f}m", keep_duration=False)
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
                self.move(v=v, w=w, t=t, label=f"Arco {angle_deg:.0f}° R={radius:.2f}m", keep_duration=False)
                return

            if "v" in data or "w" in data or "t" in data:
                v = float(data.get("v", 0.0))
                w = float(data.get("w", 0.0))
                t = float(data.get("t", 1.0))
                label = str(data.get("label", f"CAR(v={v:.2f}, w={w:.2f}, t={t:.2f}s)"))
                self.move(v=v, w=w, t=t, label=label, keep_duration=True)
        except Exception as err:
            print("[CAR] Error en comando:", err)

    def _on_stop_topic(self, topic=None, msg=None):
        self.stop("Detenido por tópico CAR/stop")

    def _on_config_topic(self, topic=None, msg=None):
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
            message=f"Calibrado: d={self.d:.4f}m, v_max={self.v_max:.2f}m/s, dz={self.deadzone:.2f}",
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
