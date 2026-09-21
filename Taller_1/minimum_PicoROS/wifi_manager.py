import network, time, json, gc
class WiFiManager:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.connect()

    def connect(self):
        print("""Connecting to WiFi...
            # Error meanings
            # 0  Link Down
            # 1  Link Join
            # 2  Link NoIp
            # 3  Link Up
            # -1 Link Fail
            # -2 Link NoNet
            # -3 Link BadAuth        
""")
        if not self.wlan.isconnected():
            self.wlan.connect(self.ssid, self.password)
            while not self.wlan.isconnected():
                time.sleep(1)
                print("wlan.status:", self.wlan.status())

        print("✅ WiFi status (3=OK):", self.wlan.status(),", IP:",self.wlan.ifconfig()[0])

