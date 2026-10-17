"""
gpio_in.py
==========
Clase GPIOIn para lectura de entradas digitales (Botones, Sensores de Puerta / Reed Switch).
Detecta cambios de estado con anti-rebote (debounce) y publica automáticamente a MQTT:
    GPIOIn/<gpio>
    gpio/<gpio>
Payload emitido:
    {"value": 1}  o  {"value": 0}
"""

import time
from machine import Pin


class GPIOIn:
    def __init__(self, pubsub, gpio="GP1", pull=Pin.PULL_UP, debounce_ms=50, invert=True):
        """
        gpio: Identificador del pin. Ejemplo: "GP1", "GP0", 1.
        pull: Pin.PULL_UP o Pin.PULL_DOWN.
        debounce_ms: Ventana de tiempo en milisegundos para filtrar rebotes mecánicos.
        invert: Si invert=True (habitual con PULL_UP), pin en 0 físico publica value=1 (activo).
        """
        self.pubsub = pubsub
        self.gpio = str(gpio)
        self.debounce_ms = debounce_ms
        self.invert = invert

        try:
            pin_number = int(self.gpio.upper().replace("GP", ""))
        except ValueError:
            pin_number = int(self.gpio)

        self.pin = Pin(pin_number, Pin.IN, pull)
        self.last_state = self._read_logical()
        self.last_change_time = time.ticks_ms()

        self.topic = "GPIOIn/" + self.gpio
        print(f"[GPIOIn] Entrada configurada en {self.gpio}. Publicará en '{self.topic}'")

    def _read_logical(self):
        raw = self.pin.value()
        # Si invert es True (pull-up a masa al cerrar contacto): 0 físico = 1 lógico
        return 1 if (raw == 0 if self.invert else raw == 1) else 0

    def update(self):
        """Llamar periódicamente desde el bucle principal o Scheduler."""
        current = self._read_logical()
        now = time.ticks_ms()

        if current != self.last_state:
            if time.ticks_diff(now, self.last_change_time) >= self.debounce_ms:
                self.last_state = current
                self.last_change_time = now

                payload = {"value": current}
                self.pubsub.publish(self.topic, payload)
                # Tópico alternativo corto para compatibilidad
                self.pubsub.publish(f"gpio/{self.gpio}", payload)
                print(f"[GPIOIn] Cambio detectado en {self.gpio} -> {current} (Publicado en {self.topic})")

    def value(self):
        return self.last_state
