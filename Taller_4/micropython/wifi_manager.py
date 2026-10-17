"""
wifi_manager.py
===============
Gestor de conexión Wi-Fi para Raspberry Pi Pico WH.
"""

import network
import time


class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

    def connect(self):
        if not self.wlan.isconnected():
            print(f"[*] Conectando a Wi-Fi: {self.ssid}...")
            self.wlan.connect(self.ssid, self.password)

            intentos = 0
            while not self.wlan.isconnected():
                time.sleep(0.5)
                intentos += 1
                if intentos > 30:
                    print("[!] Tiempo de espera agotado al conectar Wi-Fi.")
                    return False

        ip = self.wlan.ifconfig()[0]
        print(f"[+] Wi-Fi conectado exitosamente. IP: {ip} | Status: {self.wlan.status()}")
        return True

    def is_connected(self):
        return self.wlan.isconnected()
