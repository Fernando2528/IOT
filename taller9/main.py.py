import framebuf
import json
import time
from machine import Pin, I2C

# ==============================================================================
# CONTROLADOR SSD1306 INTEGRADO (No requiere archivos externos en la Pico)
# ==============================================================================
SET_CONTRAST = 0x81
SET_ENTIRE_ON = 0xA4
SET_NORM_INV = 0xA6
SET_DISP = 0xAE
SET_MEM_ADDR = 0x20
SET_COL_ADDR = 0x21
SET_PAGE_ADDR = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP = 0xA0
SET_MUX_RATIO = 0xA8
SET_COM_OUT_DIR = 0xC0
SET_DISP_OFFSET = 0xD3
SET_COM_PIN_CFG = 0xDA
SET_DISP_CLK_DIV = 0xD5
SET_PRECHARGE = 0xD9
SET_VCOM_DESEL = 0xDB
SET_CHARGE_PUMP = 0x8D

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB, self.width)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP,
            SET_MEM_ADDR, 0x00,
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.width > 2 * self.height else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b"\x40", None]
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)

# ==============================================================================
# CLASE OLED SOLICITADA EN EL TALLER
# ==============================================================================
class OLED:
    def __init__(self, sda_pin=4, scl_pin=5, i2c_id=0, width=128, height=64, addr=None):
        self.width = width
        self.height = height

        # I2C en GP4 y GP5 con pull-up internos
        self.i2c = I2C(
            i2c_id,
            sda=Pin(sda_pin, Pin.PULL_UP),
            scl=Pin(scl_pin, Pin.PULL_UP),
            freq=400000
        )

        # Autodetección de dirección
        devices = self.i2c.scan()
        if not devices:
            raise RuntimeError("Error: No se detectó la pantalla en las líneas I2C. Revisa las conexiones.")

        if addr is not None:
            self.addr = addr
        else:
            self.addr = 0x3C if 0x3C in devices else (0x3D if 0x3D in devices else devices[0])

        print(f"Pantalla OLED encontrada en: {hex(self.addr)}")
        self.display = SSD1306_I2C(self.width, self.height, self.i2c, addr=self.addr)
        self.clear()

    def clear(self):
        self.display.fill(0)
        self.display.show()

    def write_text(self, text, x=0, y=0, clear_first=False):
        if clear_first:
            self.display.fill(0)
        self.display.text(str(text), int(x), int(y), 1)
        self.display.show()

    def on_message(self, topic, message):
        """Manejador para suscripción al tópico 'oled/text'"""
        if isinstance(topic, bytes):
            topic = topic.decode('utf-8')
        if isinstance(message, bytes):
            message = message.decode('utf-8')

        if topic == "oled/text":
            try:
                # Intenta parsear si el mensaje es un JSON
                data = json.loads(message)
                text = data.get("text", "")
                x = data.get("x", 0)
                y = data.get("y", 0)
                clear_first = data.get("clear", False)
                self.write_text(text, x=x, y=y, clear_first=clear_first)
            except (ValueError, TypeError):
                # Texto plano directo
                self.write_text(message, x=0, y=0, clear_first=True)

# ==============================================================================
# DEMOSTRACIÓN DE EJECUCIÓN DIRECTA
# ==============================================================================
# Configuración física: GP4 = SDA (Pin 6), GP5 = SCL (Pin 7)
oled = OLED(sda_pin=4, scl_pin=5, i2c_id=0)

# 1. Enviar texto plano al tópico oled/text
oled.on_message("oled/text", "Taller 10 - I2C")
time.sleep(2)


# 2. Enviar parámetros estructurados (JSON) con posiciones
msg1 = json.dumps({"text": "Hola Mundo", "x": 0, "y": 0, "clear": True})
oled.on_message("oled/text", msg1)
time.sleep(5)


# 2. Enviar parámetros estructurados (JSON) con posiciones
#msg1 = json.dumps({"text": "Robot: ACTIVO", "x": 0, "y": 0, "clear": True})
#oled.on_message("oled/text", msg1)

#msg2 = json.dumps({"text": "WDT: OK", "x": 0, "y": 16, "clear": False})
#oled.on_message("oled/text", msg2)

#msg3 = json.dumps({"text": "Bat: 8.4V", "x": 0, "y": 32, "clear": False})
#oled.on_message("oled/text", msg3)

#msg4 = json.dumps({"text": "IP: 192.168.1.10", "x": 0, "y": 48, "clear": False})
#oled.on_message("oled/text", msg4)