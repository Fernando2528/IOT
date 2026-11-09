"""
wifi_manager.py
===============
Gestor de conexión Wi-Fi para Raspberry Pi Pico W con sincronización NTP
automática para permitir la ejecución de coreografías en fecha/hora ISO-8601.
"""

import time

try:
    import network
except ImportError:
    network = None

try:
    import ntptime
except ImportError:
    ntptime = None


class WiFiManager:
    def __init__(self, ssid: str, password: str, max_wait_s: int = 20):
        self.ssid = ssid
        self.password = password
        self.max_wait_s = max_wait_s
        self.ntp_synced = False
        self.wlan = network.WLAN(network.STA_IF) if network else None
        if self.wlan:
            self.wlan.active(True)
            self.connect()

    def connect(self) -> bool:
        if not self.wlan:
            return False
        if self.wlan.isconnected():
            return True

        print(f"[WiFi] Conectando a '{self.ssid}'...")
        self.wlan.connect(self.ssid, self.password)
        elapsed = 0
        while not self.wlan.isconnected() and elapsed < self.max_wait_s:
            time.sleep(1)
            elapsed += 1
            print(f"[WiFi] Esperando conexión... estado={self.wlan.status()}")

        if self.wlan.isconnected():
            ip = self.wlan.ifconfig()[0]
            print(f"[WiFi] Conectado exitosamente. IP: {ip}")
            self.sync_ntp()
            return True

        print("[WiFi] No fue posible conectar dentro del tiempo límite.")
        return False

    def sync_ntp(self):
        """Sincroniza el reloj RTC en UTC mediante NTP para `run_at` con fecha ISO-8601."""
        if ntptime is None:
            return
        try:
            ntptime.settime()
            self.ntp_synced = True
            print("[WiFi] Reloj UTC sincronizado por NTP correctamente.")
        except Exception as err:
            print("[WiFi] Aviso: No se pudo sincronizar NTP (se usará tiempo relativo):", err)

    def is_connected(self) -> bool:
        return bool(self.wlan and self.wlan.isconnected())

    def get_rssi(self) -> int:
        try:
            if self.wlan and self.wlan.isconnected():
                return int(self.wlan.status("rssi"))
        except Exception:
            pass
        return -60
