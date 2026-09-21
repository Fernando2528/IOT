import json
from machine import Pin


class LED:

    def __init__(self, pubsub, gpio="LED"):
        """
        gpio: "LED" (onboard de Pico W) o "GP0", "GP1", etc.
        Tópico: led/
        """
        self.pubsub = pubsub
        self.gpio = gpio

        # Soporte para el LED integrado en Pico W o pines físicos GP
        if gpio.upper() == "LED":
            self.pin = Pin("LED", Pin.OUT)
        else:
            pin_number = int(gpio.replace("GP", ""))
            self.pin = Pin(pin_number, Pin.OUT)

        self.pin.value(0)

        # Suscripción: led/LED o led/GP0
        self.topic = "led/" + gpio
        print("LED subscribe:", self.topic)
        self.pubsub.subscribe(self.topic, self._callback)

    def _callback(self, topic, msg):
        print("LED callback:", topic, msg)
        try:
            # Asegurar decodificación si llega como texto o dict
            if isinstance(msg, (str, bytes)):
                data = json.loads(msg)
            elif isinstance(msg, dict):
                data = msg
            else:
                data = {"value": int(msg)}

            value = int(data.get("value", 0))
            self.pin.value(value)
            print(f"LED {self.gpio} físico -> {value}")

        except Exception as e:
            print("LED error:", e)