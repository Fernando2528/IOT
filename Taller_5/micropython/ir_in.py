"""
ir_in.py
========
Clase IRIn para recepción y decodificación de control remoto Infrarrojo (Protocolo NEC).
Demodulación: Los controles remotos modulan la señal a 38 kHz para evitar interferencias
con la luz solar y lámparas. El receptor (ej. VS1838B) filtra los 38 kHz y entrega pulsos digitales.
Publica cada tecla recibida a MQTT:
    alarm/key  ->  {"key": "1"}
"""

import time
from machine import Pin

# Mapa de códigos hexadecimales estándar del protocolo NEC para teclado numérico
IR_KEYMAP = {
    "0xc": "1",
    "0x18": "2",
    "0x5e": "3",
    "0x8": "4",
    "0x1c": "5",
    "0x5a": "6",
    "0x42": "7",
    "0x52": "8",
    "0x4a": "9",
    "0x16": "0",
    "0x45": "*",
    "0x4d": "#",
    "0x19": "OK",
}


class IRIn:
    def __init__(self, pubsub, gpio=2, cooldown_ms=250):
        """
        gpio: Pin del receptor IR (ej. GP2).
        cooldown_ms: Tiempo mínimo entre pulsaciones para evitar rebotes de señal.
        """
        self.pubsub = pubsub
        self.gpio = gpio
        self.pin = Pin(gpio, Pin.IN, Pin.PULL_UP)
        self.cooldown_ms = cooldown_ms
        self.last_press = 0

        print(f"[IRIn] Receptor IR activo en GP{gpio}. Listo para capturar control...")

    def _decode_nec(self):
        """Decodifica una trama del protocolo NEC midiendo el ancho de pulsos en microsegundos."""
        # 1. Esperar inicio de pulso bajo líder (~9 ms)
        t0 = time.ticks_us()
        while self.pin.value() == 0:
            if time.ticks_diff(time.ticks_us(), t0) > 15000:
                return None

        # 2. Medir espacio alto líder (~4.5 ms)
        t1 = time.ticks_us()
        while self.pin.value() == 1:
            if time.ticks_diff(time.ticks_us(), t1) > 10000:
                return None
        t_high = time.ticks_diff(time.ticks_us(), t1)

        # Validación del encabezado NEC (3 a 6 ms)
        if not (3000 < t_high < 6000):
            return None

        # 3. Leer los 32 bits (16 de dirección + 8 de comando + 8 de comando invertido)
        bits = []
        for _ in range(32):
            t_bit = time.ticks_us()
            while self.pin.value() == 0:
                if time.ticks_diff(time.ticks_us(), t_bit) > 2500:
                    return None

            t_space = time.ticks_us()
            while self.pin.value() == 1:
                if time.ticks_diff(time.ticks_us(), t_space) > 3000:
                    return None
            dur = time.ticks_diff(time.ticks_us(), t_space)
            bits.append(1 if dur > 1000 else 0)

        # 4. Extraer el byte del comando (Bits 16 al 23)
        cmd = 0
        for j in range(8):
            cmd |= bits[16 + j] << j

        return hex(cmd)

    def update(self):
        """Llamar periódicamente desde el bucle principal o Scheduler."""
        # El receptor IR en reposo está en 1 (HIGH). Si está en 0, empezó una ráfaga.
        if self.pin.value() == 1:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press) < self.cooldown_ms:
            return

        cmd_hex = self._decode_nec()
        if not cmd_hex:
            return

        self.last_press = now
        digit = IR_KEYMAP.get(cmd_hex, cmd_hex)

        print(f"[IRIn] Comando detectado: '{digit}' ({cmd_hex})")
        # Publicar tecla a la red MQTT
        self.pubsub.publish("alarm/key", {"key": str(digit)})
        self.pubsub.publish("ir_reader/value", {"code": cmd_hex, "key": str(digit)})
