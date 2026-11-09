"""
servo.py
========
Controlador para los servomotores SG90 de 180° del brazo mecánico del Carrobot
(`alpha1_deg` para el eslabón 1 / hombro y `alpha2_deg` para el eslabón 2 / codo).

Soporta mapeo centrado (`center_offset_deg = 90.0`), de modo que los ángulos con signo
de la coreografía oficial (`even.json` / `odd.json`, ej. `0°`, `+67.5°`, `-67.5°` en el
rango `[-90°, +90°]`) se traduzcan físicamente a `[0°, 180°]` alrededor de la posición
neutra de `90°` sin golpear los topes mecánicos del SG90.
"""

from pwm_out import PWMOut


class Servo:
    def __init__(
        self,
        pubsub=None,
        gpio="GP12",
        name="alpha1",
        min_us=500,
        max_us=2500,
        min_phys_deg=0.0,
        max_phys_deg=180.0,
        center_offset_deg=90.0,
        invert=False,
        freq=50,
    ):
        self.pubsub = pubsub
        self.gpio = str(gpio)
        self.name = str(name)
        self.min_us = float(min_us)
        self.max_us = float(max_us)
        self.min_phys_deg = float(min_phys_deg)
        self.max_phys_deg = float(max_phys_deg)
        self.center_offset_deg = float(center_offset_deg)
        self.invert = bool(invert)
        self.pwm = PWMOut(gpio=gpio, freq=freq)

        self.logical_angle_deg = 0.0
        self.physical_angle_deg = self.center_offset_deg
        self.set_logical_angle(0.0)

        if self.pubsub is not None:
            self.pubsub.subscribe(f"servo/{self.name}", self._on_servo_msg)
            self.pubsub.subscribe(f"Servo/{self.gpio}", self._on_servo_msg)

    def logical_to_physical(self, logical_deg: float) -> float:
        """
        Convierte el ángulo lógico del modelo (ej. -67.5° a +67.5°) al ángulo físico
        del servomotor SG90 (0° a 180°).
        """
        val = -float(logical_deg) if self.invert else float(logical_deg)
        phys = self.center_offset_deg + val
        return max(self.min_phys_deg, min(self.max_phys_deg, phys))

    def set_logical_angle(self, logical_deg: float):
        """Posiciona el servo según el ángulo lógico `alpha_deg` de `motion/state`."""
        self.logical_angle_deg = float(logical_deg)
        phys_deg = self.logical_to_physical(self.logical_angle_deg)
        return self.set_physical_angle(phys_deg)

    def set_physical_angle(self, phys_deg: float):
        """Posiciona directamente el servo en el rango físico [0°, 180°]."""
        clamped = max(self.min_phys_deg, min(self.max_phys_deg, float(phys_deg)))
        self.physical_angle_deg = clamped
        ratio = (clamped - self.min_phys_deg) / (self.max_phys_deg - self.min_phys_deg)
        pulse_us = self.min_us + ratio * (self.max_us - self.min_us)
        duty = self.pwm.set_pulse_us(pulse_us)
        return pulse_us, duty

    # Alias de compatibilidad con Taller 7 y Taller 8
    def set_angle(self, angle: float):
        return self.set_physical_angle(angle)

    def _on_servo_msg(self, topic=None, msg=None):
        try:
            if isinstance(msg, dict):
                if "logical_deg" in msg:
                    pulse_us, duty = self.set_logical_angle(float(msg["logical_deg"]))
                else:
                    val = float(msg.get("angle", msg.get("value", 90.0)))
                    pulse_us, duty = self.set_physical_angle(val)
            else:
                pulse_us, duty = self.set_physical_angle(float(msg))

            if self.pubsub:
                self.pubsub.publish(
                    "servo/status",
                    {
                        "name": self.name,
                        "gpio": self.gpio,
                        "logical_deg": round(self.logical_angle_deg, 2),
                        "physical_deg": round(self.physical_angle_deg, 2),
                        "pulse_us": round(pulse_us, 1),
                        "duty_u16": duty,
                    },
                )
        except Exception as err:
            print(f"[Servo:{self.name}] Error:", err)
