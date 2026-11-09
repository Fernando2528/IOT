"""
watchdog_task.py
================
Tarea de supervisión Watchdog compatible al 100% con:
1. El panel Network Stats (Watchdog) del Gemelo Virtual (`PubSub_client_web.html`).
2. La pantalla OLED SSD1306 con scroll por potenciómetro (`oled_watchdog.py`).
3. El panel de telemetría de la interfaz Flet en PC.

Publica periódicamente en `watchdog/stats` el diccionario con:
    - `first_ts`       : Marca de tiempo para cálculo de RTT y Jitter RFC
    - `mem_free_bytes` : Memoria RAM libre en bytes
    - `mem_used_bytes` : Memoria RAM usada en bytes
    - `rssi`           : Potencia de señal Wi-Fi en dBm
    - `sended`         : Contador secuencial de paquetes para detección de pérdida
    - `temperature_c`  : Temperatura interna del RP2040 en °C
    - `<TaskName>`     : Diccionario `{min, max, avg, period, ...}` por cada tarea del Scheduler
"""

import gc
from machine import ADC
import util
from task import Task


class WatchdogTask(Task):
    def __init__(self, scheduler, pubsub, wifi=None, period_ms: int = 2000):
        super().__init__(scheduler, period_ms=period_ms, priority=5, name="WatchdogTask")
        self.pubsub = pubsub
        self.wifi = wifi
        self.sended = 0
        try:
            self.temp_adc = ADC(4)
        except Exception:
            self.temp_adc = None

    def _read_temperature_c(self) -> str:
        try:
            if self.temp_adc is not None:
                voltage = self.temp_adc.read_u16() * 3.3 / 65535.0
                temp = 27.0 - (voltage - 0.706) / 0.001721
                return f"{temp:.2f}"
        except Exception:
            pass
        return "28.50"

    def update(self):
        if self.wifi and not self.wifi.is_connected():
            self.wifi.connect()

        gc.collect()
        self.sended += 1

        rssi = self.wifi.get_rssi() if (self.wifi and hasattr(self.wifi, "get_rssi")) else -55
        data = {
            "first_ts": util.time_float(),
            "mem_free_bytes": gc.mem_free() if hasattr(gc, "mem_free") else 120000,
            "mem_used_bytes": gc.mem_alloc() if hasattr(gc, "mem_alloc") else 40000,
            "rssi": rssi,
            "sended": self.sended,
            "temperature_c": self._read_temperature_c(),
        } | self.scheduler.stats()

        self.pubsub.publish("watchdog/stats", data)
