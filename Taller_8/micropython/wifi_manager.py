"""
wifi_manager.py
===============
Administrador de conexión Wi-Fi para Raspberry Pi Pico W con reconexión automática.
"""

import network
import time


class WiFiManager:
    def __init__(self, ssid: str, password: str, timeout_s: int = 20):
        self.ssid = ssid
        self.password = password
        self.timeout_s = timeout_s
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.connect()

    def connect(self) -> bool:
        if self.wlan.isconnected():
            return True

        print(f"[WiFi] Conectando a '{self.ssid}'...")
        self.wlan.connect(self.ssid, self.password)
        t0 = time.time()
        while not self.wlan.isconnected():
            if time.time() - t0 > self.timeout_s:
                print("[WiFi] Tiempo de espera agotado al conectar.")
                return False
            time.sleep(0.5)

        ip = self.wlan.ifconfig()[0]
        print(f"[WiFi] Conectado exitosamente. Dirección IP: {ip}")
        return True

    def is_connected(self) -> bool:
        return self.wlan.isconnected()
