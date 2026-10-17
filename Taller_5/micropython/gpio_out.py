"""
gpio_out.py
===========
Clase GPIOOut para control de salidas digitales y actuadores (LED, Sirena, Relé).
Mapea mensajes MQTT recibidos a cambios de estado físico en los pines GPIO.
"""

import json
from machine import Pin


class GPIOOut:
    def __init__(self, pubsub, gpio="LED", initial_value=0):
        """
        gpio: Identificador del pin. Ejemplo: "LED" (onboard Pico WH), "GP0", "GP1", "15".
        Tópico de control por defecto:
            GPIOOut/<gpio>  (y led/<gpio> para compatibilidad)
        Payload esperado:
            {"value": 1} o {"value": 0}
        """
        self.pubsub = pubsub
        self.gpio = str(gpio)

        # Soporte para "LED" onboard de Pico W / WH o pines numéricos
        if self.gpio.upper() == "LED":
            self.pin = Pin("LED", Pin.OUT)
        else:
            try:
                pin_number = int(self.gpio.upper().replace("GP", ""))
            except ValueError:
                pin_number = int(self.gpio)
            self.pin = Pin(pin_number, Pin.OUT)

        self.pin.value(initial_value)

        # Suscribir al tópico principal y de compatibilidad
        self.topic = "GPIOOut/" + self.gpio
        self.pubsub.subscribe(self.topic, self._callback)

        if self.gpio.upper() == "LED":
            self.pubsub.subscribe("led/LED", self._callback)

        print(f"[GPIOOut] Salida configurada en {self.gpio}. Escuchando en '{self.topic}'")

    def _callback(self, topic, msg):
        try:
            # Asegurar decodificación segura
            if isinstance(msg, (str, bytes)):
                try:
                    data = json.loads(msg)
                except Exception:
                    data = msg
            else:
                data = msg

            if isinstance(data, dict):
                value = data.get("value", 0)
            else:
                value = 1 if str(data).strip() in ("1", "true", "True", "on", "ON") else 0

            int_val = int(value)
            self.pin.value(int_val)
            estado_txt = "ENCENDIDO" if int_val == 1 else "APAGADO"
            print(f"[GPIOOut] Pin {self.gpio} físico -> {int_val} ({estado_txt})")

        except Exception as e:
            print(f"[GPIOOut] Error procesando comando en {self.gpio}: {e}")

    def set(self, val: int):
        self.pin.value(1 if val else 0)
