"""
oled_watchdog.py
================
Muestra en la pantalla OLED SSD1306 (128x64 I2C) toda la información del Watchdog
y el estado de la coreografía del Carrobot (`robot12`), con scroll vertical
controlado en tiempo real por el potenciómetro conectado al ADC.

Características:
- Auto-detección de pines I2C en la Raspberry Pi Pico W (prueba primero los pines
  configurados y, si no detecta el OLED en 0x3C/0x3D, explora los pares I2C0/I2C1 libres).
- Lectura suavizada del potenciómetro (ADC en GP28/GP26/GP27) para desplazar
  verticalmente las líneas de información sin parpadeos.
- Barra de desplazamiento visual (scrollbar) en el borde derecho de la pantalla OLED.
- Publicación periódica del estado OLED + potenciómetro en `oled/status` para
  visualización simultánea en la interfaz Flet del PC.
"""

from machine import ADC, I2C, Pin
from pwm_out import parse_gpio_pin
from task import Task

try:
    from ssd1306 import SSD1306_I2C
except ImportError:
    SSD1306_I2C = None


class OledWatchdogTask(Task):
    def __init__(
        self,
        scheduler,
        pubsub,
        pot_gpio="GP28",
        sda_gpio="GP4",
        scl_gpio="GP5",
        i2c_id=0,
        oled_width=128,
        oled_height=64,
        period_ms=120,
        robot_label="robot12",
    ):
        self.pubsub = pubsub
        self.robot_label = robot_label
        self.oled_width = oled_width
        self.oled_height = oled_height
        self.visible_lines = 6  # 1 línea fija de encabezado + 6 líneas desplazables

        # Inicializar ADC del potenciómetro
        self.pot_gpio = str(pot_gpio)
        try:
            self.adc = ADC(parse_gpio_pin(pot_gpio))
        except Exception as err:
            print(f"[OLED] Aviso: No se pudo abrir ADC en {pot_gpio}:", err)
            self.adc = None

        self.filtered_adc = 0.0
        self.adc_initialized = False
        self.manual_scroll_override = None  # Permite prueba desde Flet si se desea

        # Inicializar pantalla OLED SSD1306 por I2C con auto-detección resiliente
        self.oled = None
        self.i2c_info = "No detectado"
        self._init_oled(i2c_id, sda_gpio, scl_gpio)

        # Estado almacenado de Watchdog y Movimiento
        self.watchdog_data = {
            "rssi": -55,
            "mem_free_bytes": 120000,
            "mem_used_bytes": 40000,
            "temperature_c": "28.0",
            "sended": 0,
        }
        self.task_lines = []
        self.motion_summary = {
            "mode": "IDLE",
            "seq": "even",
            "step": "0/5",
            "v_dm_s": 0.0,
            "w_deg_s": 0.0,
            "a1": 0.0,
            "a2": 0.0,
        }
        self.lines = []
        self.scroll_index = 0
        self.tick_count = 0

        # Suscripciones locales en el Node
        self.pubsub.subscribe("watchdog/stats", self._on_watchdog_stats)
        self.pubsub.subscribe("motion/status", self._on_motion_status)
        self.pubsub.subscribe("oled/scroll", self._on_remote_scroll)

        self._rebuild_lines()
        super().__init__(scheduler, period_ms=period_ms, priority=3, name="OledWatchdog")

    def _init_oled(self, preferred_bus: int, sda_gpio: str, scl_gpio: str):
        if SSD1306_I2C is None:
            print("[OLED] Driver ssd1306 no disponible.")
            return

        pref_sda = parse_gpio_pin(sda_gpio)
        pref_scl = parse_gpio_pin(scl_gpio)

        # Candidatos I2C (no entran en conflicto con GP6,7,12,13,16,17,18,19,28)
        candidates = [
            (preferred_bus, pref_sda, pref_scl),
            (0, 4, 5),
            (0, 0, 1),
            (0, 8, 9),
            (1, 2, 3),
            (1, 14, 15),
            (1, 10, 11),
        ]

        for bus_id, sda, scl in candidates:
            try:
                i2c = I2C(bus_id, sda=Pin(sda), scl=Pin(scl), freq=400_000)
                devices = i2c.scan()
                for addr in (0x3C, 0x3D):
                    if addr in devices:
                        self.oled = SSD1306_I2C(self.oled_width, self.oled_height, i2c, addr=addr)
                        self.i2c_info = f"I2C{bus_id} (SDA=GP{sda}, SCL=GP{scl}, 0x{addr:02X})"
                        print(f"[OLED] Pantalla SSD1306 detectada en {self.i2c_info}")
                        return
            except Exception:
                pass

        print("[OLED] No se detectó pantalla física SSD1306 en el bus I2C (modo espejo Flet activo).")

    def _on_watchdog_stats(self, topic=None, msg=None):
        if not isinstance(msg, dict):
            return
        for k in ("rssi", "mem_free_bytes", "mem_used_bytes", "temperature_c", "sended"):
            if k in msg:
                self.watchdog_data[k] = msg[k]

        t_lines = []
        for name, val in msg.items():
            if isinstance(val, dict) and "min" in val and "max" in val and "avg" in val:
                period = max(1, float(val.get("period", 100)))
                cpu_pct = (float(val["avg"]) / period) / 10.0
                short_name = str(name)[:6]
                t_lines.append(f"{short_name}:{cpu_pct:.1f}% {int(val['avg'])}us")
                t_lines.append(f"  mn:{int(val['min'])} mx:{int(val['max'])}")
        self.task_lines = t_lines
        self._rebuild_lines()

    def _on_motion_status(self, topic=None, msg=None):
        if not isinstance(msg, dict):
            return
        self.motion_summary["mode"] = str(msg.get("state", "IDLE")).upper()[:8]
        self.motion_summary["seq"] = str(msg.get("sequence", "even"))[:8]
        self.motion_summary["step"] = f"{msg.get('step', 0)}/{msg.get('total_steps', 0)}"
        self.motion_summary["v_dm_s"] = float(msg.get("v_dm/s", 0.0))
        self.motion_summary["w_deg_s"] = float(msg.get("w_deg/s", 0.0))
        self.motion_summary["a1"] = float(msg.get("alpha1_deg", 0.0))
        self.motion_summary["a2"] = float(msg.get("alpha2_deg", 0.0))
        self._rebuild_lines()

    def _on_remote_scroll(self, topic=None, msg=None):
        """Permite mover el scroll desde Flet o devolver el control al potenciómetro físico."""
        if not isinstance(msg, dict):
            return
        if msg.get("mode") == "auto":
            self.manual_scroll_override = None
        elif "pot_u16" in msg:
            self.manual_scroll_override = max(0, min(65535, int(msg["pot_u16"])))

    def _rebuild_lines(self):
        wd = self.watchdog_data
        ms = self.motion_summary
        free_kb = int(wd.get("mem_free_bytes", 0)) // 1024
        used_kb = int(wd.get("mem_used_bytes", 0)) // 1024

        base_lines = [
            f"ID:{self.robot_label} (PAR)",
            f"RSSI:{wd.get('rssi', '-')}dBm #{wd.get('sended', 0)}",
            f"RAM L:{free_kb}K U:{used_kb}K",
            f"Temp:{wd.get('temperature_c', '-')} C",
            f"Est:{ms['mode']} S:{ms['seq']}",
            f"Paso:{ms['step']}",
            f"v:{ms['v_dm_s']:.2f}dm w:{ms['w_deg_s']:.0f}d",
            f"Brazo:{ms['a1']:.1f}/{ms['a2']:.1f}",
            "-- TAREAS CPU --",
        ]
        if self.task_lines:
            base_lines.extend(self.task_lines)
        else:
            base_lines.append("Esperando stats")
        self.lines = base_lines

    def _read_pot_u16(self) -> int:
        if self.manual_scroll_override is not None:
            return self.manual_scroll_override
        if self.adc is None:
            return 0
        raw = self.adc.read_u16()
        if not self.adc_initialized:
            self.filtered_adc = float(raw)
            self.adc_initialized = True
        else:
            self.filtered_adc = 0.75 * self.filtered_adc + 0.25 * float(raw)
        return int(self.filtered_adc)

    def update(self):
        pot_u16 = self._read_pot_u16()
        total = len(self.lines)
        max_scroll = max(0, total - self.visible_lines)

        if max_scroll > 0:
            self.scroll_index = min(max_scroll, int((pot_u16 / 65535.0) * (max_scroll + 0.99)))
        else:
            self.scroll_index = 0

        visible_slice = self.lines[self.scroll_index : self.scroll_index + self.visible_lines]

        if self.oled is not None:
            try:
                self.oled.fill(0)
                # Encabezado superior fijo
                hdr = f"WDT {self.scroll_index + 1:02d}/{total:02d} P:{int(pot_u16 * 100 / 65535):02d}%"
                self.oled.text(hdr[:16], 0, 0, 1)
                self.oled.hline(0, 9, 128, 1)

                # Líneas desplazadas por el potenciómetro
                for i, line in enumerate(visible_slice):
                    y = 12 + i * 9
                    if y + 8 <= self.oled_height:
                        self.oled.text(line[:15], 0, y, 1)

                # Barra de scroll vertical en el borde derecho (x=125..127)
                track_top = 11
                track_h = self.oled_height - track_top - 1
                self.oled.vline(126, track_top, track_h, 1)
                if max_scroll > 0:
                    thumb_h = max(6, int(track_h * self.visible_lines / total))
                    thumb_y = track_top + int((track_h - thumb_h) * (self.scroll_index / max_scroll))
                else:
                    thumb_h = track_h
                    thumb_y = track_top
                self.oled.fill_rect(125, thumb_y, 3, thumb_h, 1)
                self.oled.show()
            except Exception as err:
                print("[OLED] Error refrescando pantalla:", err)
                self.oled = None

        # Publicar espejo de la pantalla OLED hacia Flet cada ~600 ms (cada 5 ciclos)
        self.tick_count += 1
        if self.tick_count >= 5:
            self.tick_count = 0
            self.pubsub.publish(
                "oled/status",
                {
                    "pot_u16": pot_u16,
                    "pot_pct": round(pot_u16 * 100.0 / 65535.0, 1),
                    "scroll_index": self.scroll_index,
                    "max_scroll": max_scroll,
                    "total_lines": total,
                    "visible_lines": visible_slice,
                    "all_lines": self.lines,
                    "i2c_info": self.i2c_info,
                },
            )
