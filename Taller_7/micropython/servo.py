"""
servo.py
========
Clase Servo para el control angular de servomotores de 180° (SG90 / MG90S).
Utiliza la clase PWMOut para generar pulsos precisos a 50 Hz (periodo T = 20 ms).
"""

from pwm_out import PWMOut


class Servo:
    def __init__(
        self,
        pin,
        min_us=500,
        max_us=2500,
        min_angle=0.0,
        max_angle=180.0,
        freq=50,
    ):
        """
        pin: Pin GPIO conectado a la señal del servo (cable naranja/amarillo).
        min_us: Ancho de pulso en microsegundos correspondiente al ángulo mínimo (típicamente 500 µs).
        max_us: Ancho de pulso en microsegundos correspondiente al ángulo máximo (típicamente 2500 µs).
        min_angle: Ángulo mínimo admitido (ej. 0.0 o -90.0).
        max_angle: Ángulo máximo admitido (ej. 180.0 o +90.0).
        freq: Frecuencia de modulación (50 Hz para servomotores estándar).
        """
        self.min_us = min_us
        self.max_us = max_us
        self.min_angle = float(min_angle)
        self.max_angle = float(max_angle)
        self.current_angle = None

        self.pwm_out = PWMOut(pin=pin, freq=freq)

        # Iniciar en posición central / neutra
        center = (self.min_angle + self.max_angle) / 2.0
        self.set_angle(center)

    def set_angle(self, angle: float):
        """
        Posiciona el servomotor en cualquier ángulo especificado.
        Clampea el valor entre min_angle y max_angle.
        Retorna:
            (pulse_us, duty_u16)
        """
        clamped_angle = max(self.min_angle, min(self.max_angle, float(angle)))
        self.current_angle = clamped_angle

        # Mapeo lineal: ángulo -> ancho de pulso en microsegundos
        ratio = (clamped_angle - self.min_angle) / (self.max_angle - self.min_angle)
        pulse_us = self.min_us + ratio * (self.max_us - self.min_us)

        # Aplicar pulso en el hardware
        self.pwm_out.set_pulse_us(pulse_us)

        period_us = 1_000_000.0 / self.pwm_out.freq
        duty = int((pulse_us / period_us) * 65535)

        return pulse_us, duty

    def get_angle(self) -> float:
        return self.current_angle

    def deinit(self):
        self.pwm_out.deinit()
