"""
pwm_out.py
==========
Clase genérica PWMOut para MicroPython (Raspberry Pi Pico WH).
Controla salidas con modulación por ancho de pulsos (PWM) sobre cualquier pin GPIO.
Permite configurar frecuencia, ciclo de trabajo (duty cycle) de 16 bits, porcentaje y ancho de pulso en microsegundos.
"""

from machine import Pin, PWM


class PWMOut:
    def __init__(self, pin, freq=50, duty_u16=0):
        """
        pin: Número de pin GPIO o identificador (ej. 12, "GP12").
        freq: Frecuencia de la portadora en Hertz (por defecto 50 Hz para servos).
        duty_u16: Ciclo de trabajo inicial (0 a 65535).
        """
        if isinstance(pin, str):
            pin_number = int(pin.upper().replace("GP", ""))
        else:
            pin_number = int(pin)

        self.pin = Pin(pin_number, Pin.OUT)
        self.pwm = PWM(self.pin)
        self.freq = freq
        self.pwm.freq(freq)
        self.set_duty_u16(duty_u16)

    def set_freq(self, freq: int):
        """Ajusta la frecuencia del PWM en Hz."""
        self.freq = int(freq)
        self.pwm.freq(self.freq)

    def set_duty_u16(self, duty: int):
        """Ajusta el ciclo de trabajo de 16 bits (0 a 65535)."""
        clamped_duty = max(0, min(65535, int(duty)))
        self.pwm.duty_u16(clamped_duty)

    def set_duty_percent(self, percent: float):
        """Ajusta el ciclo de trabajo como porcentaje de 0.0% a 100.0%."""
        p = max(0.0, min(100.0, float(percent)))
        self.set_duty_u16(int((p / 100.0) * 65535))

    def set_pulse_us(self, pulse_us: float):
        """
        Ajusta el pulso en microsegundos (µs) en función de la frecuencia actual.
        Para 50 Hz, el periodo T = 1/50 = 20,000 µs.
        """
        period_us = 1_000_000.0 / self.freq
        duty = int((pulse_us / period_us) * 65535)
        self.set_duty_u16(duty)

    def deinit(self):
        """Libera el canal PWM."""
        try:
            self.pwm.deinit()
        except Exception:
            pass
