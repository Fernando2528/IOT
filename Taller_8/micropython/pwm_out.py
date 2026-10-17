"""
pwm_out.py
==========
Abstracción de hardware para salidas PWM en Raspberry Pi Pico W.
Permite controlar tanto motores DC (frecuencia 1000 Hz, duty normalizado 0.0-1.0)
como servomotores (frecuencia 50 Hz, ancho de pulso en microsegundos).
"""

from machine import Pin, PWM


def parse_gpio_pin(gpio) -> int:
    if isinstance(gpio, int):
        return gpio
    s = str(gpio).strip().upper()
    if s.startswith("GP"):
        return int(s[2:])
    return int(s)


class PWMOut:
    def __init__(self, gpio, freq: int = 1000, duty_u16: int = 0):
        self.gpio = str(gpio)
        self.pin_number = parse_gpio_pin(gpio)
        self.freq = int(freq)
        self.pwm = PWM(Pin(self.pin_number, Pin.OUT))
        self.pwm.freq(self.freq)
        self.set_duty_u16(duty_u16)

    def set_duty_u16(self, duty_u16: int):
        val = max(0, min(65535, int(duty_u16)))
        self.pwm.duty_u16(val)
        return val

    def set_duty_ratio(self, ratio: float) -> int:
        r = max(0.0, min(1.0, float(ratio)))
        return self.set_duty_u16(int(r * 65535))

    def set_pulse_us(self, pulse_us: float) -> int:
        period_us = 1_000_000.0 / self.freq
        duty = int((float(pulse_us) / period_us) * 65535)
        return self.set_duty_u16(duty)

    def deinit(self):
        self.pwm.duty_u16(0)
        self.pwm.deinit()
