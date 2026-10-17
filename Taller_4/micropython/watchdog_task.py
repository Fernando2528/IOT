"""
watchdog_task.py
================
Tarea periódica de Watchdog y Telemetría del Sistema.
Supervisa la salud del sistema, recolecta estadísticas de ejecución de las tareas,
memoria RAM, temperatura y calidad Wi-Fi, y las publica vía MQTT.
"""

import gc
import time
from machine import ADC
from task import Task


class WatchdogTask(Task):
    def __init__(self, scheduler, mqtt_client, wifi_manager, period_ms=1000, prefix="UDFJC/iot_ws/robot0/"):
        super().__init__(scheduler, period_ms, name="watchdog_telemetry", priority=2)
        self.mqtt = mqtt_client
        self.wifi = wifi_manager
        self.prefix = prefix
        self.heartbeat_counter = 0
        self.sensor_temp = ADC(4)

        # Opcional: Watchdog de hardware real con timeout de 8000 ms
        # from machine import WDT
        # self.wdt = WDT(timeout=8000)
        self.wdt = None

    def read_temperature(self):
        try:
            raw = self.sensor_temp.read_u16() * (3.3 / 65535)
            temp = 27 - (raw - 0.706) / 0.001721
            return round(temp, 1)
        except Exception:
            return 0.0

    def get_rssi(self):
        try:
            return self.wifi.wlan.status("rssi")
        except Exception:
            return 0

    def update(self):
        # 1. Alimentar Watchdog de hardware si está activo
        if self.wdt:
            self.wdt.feed()

        self.heartbeat_counter += 1

        # 2. Construir reporte de salud completo
        health_data = {
            "heartbeat": self.heartbeat_counter,
            "uptime_s": time.ticks_ms() // 1000,
            "mem_free_bytes": gc.mem_free(),
            "mem_alloc_bytes": gc.mem_alloc(),
            "temp_c": self.read_temperature(),
            "wifi_rssi": self.get_rssi(),
            "tasks_stats": self.scheduler.stats(),
        }

        # 3. Publicar por MQTT
        topic = self.prefix + "watchdog/stats"
        self.mqtt.publish(topic, health_data)
