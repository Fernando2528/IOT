"""
servo.py
========
Controlador para los servomotores SG90 montados en el chasis del robot
(brazo mecánico / mecanismo recolector visible en el montaje físico).
"""

from pwm_out import PWMOut


class Servo:
    def __init__(
        self,
        pubsub=None,
        gpio="GP12",
        min_us=500,
        max_us=2500,
        min_angle=0.0,
        max_angle=180.0,
        freq=50,
    ):
        self.pubsub = pubsub
        self.gpio = str(gpio)
        self.min_us = float(min_us)
        self.max_us = float(max_us)
        self.min_angle = float(min_angle)
        self.max_angle = float(max_angle)
        self.pwm = PWMOut(gpio=gpio, freq=freq)
        self.current_angle = 90.0
        self.set_angle(90.0)

        if self.pubsub is not None:
            self.pubsub.subscribe("servo/angle", self._on_servo_msg)
            self.pubsub.subscribe(f"Servo/{self.gpio}", self._on_servo_msg)

    def set_angle(self, angle: float):
        clamped = max(self.min_angle, min(self.max_angle, float(angle)))
        self.current_angle = clamped
        ratio = (clamped - self.min_angle) / (self.max_angle - self.min_angle)
        pulse_us = self.min_us + ratio * (self.max_us - self.min_us)
        duty = self.pwm.set_pulse_us(pulse_us)
        return pulse_us, duty

    def _on_servo_msg(self, topic, msg):
        try:
            if isinstance(msg, dict):
                val = msg.get("angle", msg.get("value", 90.0))
            else:
                val = float(msg)
            pulse_us, duty = self.set_angle(float(val))
            if self.pubsub:
                self.pubsub.publish(
                    "servo/status",
                    {
                        "gpio": self.gpio,
                        "angle": self.current_angle,
                        "pulse_us": round(pulse_us, 1),
                        "duty_u16": duty,
                    },
                )
        except Exception as e:
            print("[Servo] Error:", e)
