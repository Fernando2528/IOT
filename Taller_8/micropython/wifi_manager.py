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

        status_names = {
            0: "0 (STAT_IDLE / Link Down)",
            1: "1 (STAT_CONNECTING / Link Join)",
            2: "2 (STAT_NO_IP / Link NoIp)",
            3: "3 (STAT_GOT_IP / Link Up - OK)",
            -1: "-1 (STAT_CONNECT_FAIL / Link Fail)",
            -2: "-2 (STAT_NO_AP_FOUND / Link NoNet - Red no encontrada)",
            -3: "-3 (STAT_WRONG_PASSWORD / Link BadAuth - Clave incorrecta)",
        }

        print(f"[WiFi] Conectando a '{self.ssid}'...")
        self.wlan.connect(self.ssid, self.password)
        t0 = time.time()
        last_status = None
        while not self.wlan.isconnected():
            st = self.wlan.status()
            if st != last_status:
                print(f"[WiFi] Estado actual: {status_names.get(st, str(st))}")
                last_status = st
            if time.time() - t0 > self.timeout_s:
                print(f"[WiFi] Tiempo de espera agotado ({self.timeout_s}s). Último estado: {status_names.get(st, str(st))}")
                return False
            time.sleep(0.5)

        ip = self.wlan.ifconfig()[0]
        print(f"[WiFi] Conectado exitosamente. Dirección IP: {ip}")
        return True

    def is_connected(self) -> bool:
        return self.wlan.isconnected()
