"""
pwm_out.py
==========
 Abstracción de salida PWM para Raspberry Pi Pico W (RP2040).
Usada tanto por el puente H L298N (pines ENA/ENB) como por los servomotores SG90 del brazo.
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
        self.pin_num = parse_gpio_pin(gpio)
        self.gpio = f"GP{self.pin_num}"
        self.freq = int(freq)
        self.pwm = PWM(Pin(self.pin_num))
        self.pwm.freq(self.freq)
        self.duty_u16 = 0
        self.set_duty_u16(duty_u16)

    def set_duty_u16(self, duty_u16: int) -> int:
        val = max(0, min(65535, int(duty_u16)))
        self.duty_u16 = val
        self.pwm.duty_u16(val)
        return val

    def set_pulse_us(self, pulse_us: float) -> int:
        period_us = 1_000_000.0 / float(self.freq)
        duty = int((float(pulse_us) / period_us) * 65535.0)
        return self.set_duty_u16(duty)
