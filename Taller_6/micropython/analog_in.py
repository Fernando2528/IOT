"""
analog_in.py
============
Clase AnalogIn para lectura de entradas analógicas (ADC) y monitoreo de voltaje.
Publica en el tópico:
    AnalogIn_u16/<gpio>
Payload:
    {"value": 12345}
"""

from machine import ADC
from task import Task


class AnalogIn(Task):
    def __init__(self, scheduler, pubsub, gpio="GP28", period_ms=1000):
        """
        gpio: Identificador del pin ADC. Ejemplo: "GP26", "GP27", "GP28".
        period_ms: Intervalo entre lecturas y publicaciones.
        """
        self.pubsub = pubsub
        self.gpio = gpio

        # Extraer número de pin (ej. GP28 -> 28)
        pin_number = int(gpio.replace("GP", ""))
        self.adc = ADC(pin_number)

        self.topic = "AnalogIn_u16/" + gpio
        print(f"[AnalogIn] Inicializado en {self.gpio}. Tópico: '{self.topic}'")

        super().__init__(scheduler, period_ms=period_ms, name=f"adc_{gpio}")

    def update(self):
        # Lectura de 16 bits sin signo (0 a 65535)
        value = self.adc.read_u16()

        msg = {
            "value": value
        }

        print(f"[AnalogIn_u16] {self.gpio} -> Valor RAW: {value}")
        self.pubsub.publish(self.topic, msg)
