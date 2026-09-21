from datetime import datetime
import json
import sys
import paho.mqtt.client as mqtt
from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"
TOPIC_SUB = PREFIX + "#"


class MqttBridge(QObject):
    sig_key = pyqtSignal(str, str, int)
    sig_status = pyqtSignal(str, int, str)
    sig_door = pyqtSignal(int, str)
    sig_log = pyqtSignal(str, str)  # nivel, mensaje
    sig_conn = pyqtSignal(bool)


class SecurityDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Consola Central de Seguridad IoT - Pico W")
        self.resize(920, 560)
        self.setStyleSheet("background-color: #0E1117; color: #E6EDF3;")

        self.current_state = "DISARMED"
        self.door_open = 0

        self.bridge = MqttBridge()
        self.bridge.sig_key.connect(self.on_key)
        self.bridge.sig_status.connect(self.on_status)
        self.bridge.sig_door.connect(self.on_door)
        self.bridge.sig_log.connect(self.add_log)
        self.bridge.sig_conn.connect(self.on_connection_change)

        self._build_ui()
        self._init_mqtt()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # ----------------------------------------------------
        # 1. Cabecera: Título y Estado del Enlace MQTT
        # ----------------------------------------------------
        header = QHBoxLayout()
        title = QLabel("SISTEMA DE SEGURIDAD PERIMETRAL")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; letter-spacing: 1px;")

        self.lbl_broker = QLabel("● Desconectado")
        self.lbl_broker.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_broker.setStyleSheet("color: #FF5252;")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.lbl_broker)
        layout.addLayout(header)

        # ----------------------------------------------------
        # 2. Gran Banner de Estado de Seguridad (Dominante)
        # ----------------------------------------------------
        self.banner_state = QLabel("🛡️ SISTEMA DESARMADO")
        self.banner_state.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.banner_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_state.setFixedHeight(65)
        self.banner_state.setStyleSheet("""
            background-color: #122818;
            border: 2px solid #2EA043;
            border-radius: 10px;
            color: #3FB950;
        """)
        layout.addWidget(self.banner_state)

        # ----------------------------------------------------
        # 3. Paneles de Telemetría (Grid de 3 Columnas)
        # ----------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(15)

        # Panel A: Teclado IR y Búfer
        box_keypad = QFrame()
        box_keypad.setStyleSheet(
            "background-color: #161B22; border-radius: 8px; padding: 10px;"
        )
        lay_keypad = QVBoxLayout(box_keypad)
        lay_keypad.addWidget(
            self._section_title("TECLADO INFRARROJO (GP2)")
        )

        row_digits = QHBoxLayout()
        row_digits.setSpacing(8)
        self.digits = []
        for _ in range(4):
            d = QLabel("•")
            d.setFont(QFont("Consolas", 28, QFont.Weight.Bold))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setFixedSize(50, 60)
            d.setStyleSheet("""
                background-color: #0D1117;
                border: 2px solid #30363D;
                border-radius: 6px;
                color: #8B949E;
            """)
            row_digits.addWidget(d)
            self.digits.append(d)

        lay_keypad.addLayout(row_digits)
        self.lbl_key_hint = QLabel("Apunta el control para ingresar 4 dígitos")
        self.lbl_key_hint.setFont(QFont("Segoe UI", 10))
        self.lbl_key_hint.setStyleSheet("color: #8B949E;")
        lay_keypad.addWidget(self.lbl_key_hint)
        lay_keypad.addStretch()

        # Panel B: Sensores y Actuadores (Puerta y Sirena)
        box_sensors = QFrame()
        box_sensors.setStyleSheet(
            "background-color: #161B22; border-radius: 8px; padding: 10px;"
        )
        lay_sensors = QVBoxLayout(box_sensors)
        lay_sensors.addWidget(
            self._section_title("SENSORES Y SIRENA")
        )

        self.card_door = QLabel("PUERTA: CERRADA")
        self.card_door.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_door.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_door.setFixedHeight(45)
        self.card_door.setStyleSheet("""
            background-color: #0D1117;
            border: 1.5px solid #238636;
            border-radius: 6px;
            color: #2EA043;
        """)
        lay_sensors.addWidget(self.card_door)

        self.card_siren = QLabel("SIRENA / LED: APAGADA")
        self.card_siren.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_siren.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_siren.setFixedHeight(45)
        self.card_siren.setStyleSheet("""
            background-color: #0D1117;
            border: 1.5px solid #30363D;
            border-radius: 6px;
            color: #8B949E;
        """)
        lay_sensors.addWidget(self.card_siren)
        lay_sensors.addStretch()

        # Panel C: Reglas de Operación
        box_rules = QFrame()
        box_rules.setStyleSheet(
            "background-color: #161B22; border-radius: 8px; padding: 10px;"
        )
        lay_rules = QVBoxLayout(box_rules)
        lay_rules.addWidget(self._section_title("LÓGICA DEL SISTEMA"))

        rules_text = QLabel(
            "• Clave '1111': Alterna entre Armado / Desarmado.\n"
            "• Desarmado + Puerta abierta: No dispara sirena.\n"
            "• Armado + Puerta abierta: ¡DISPARA SIRENA!\n"
            "• Clave errónea: ¡DISPARA SIRENA!\n"
            "• Clave '1111' en alarma: Silencia y Desarma."
        )
        rules_text.setFont(QFont("Segoe UI", 9))
        rules_text.setStyleSheet("color: #8B949E; line-height: 1.4;")
        lay_rules.addWidget(rules_text)
        lay_rules.addStretch()

        grid.addWidget(box_keypad, 0, 0)
        grid.addWidget(box_sensors, 0, 1)
        grid.addWidget(box_rules, 0, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 4)
        layout.addLayout(grid)

        # ----------------------------------------------------
        # 4. Terminal de Auditoría y Eventos
        # ----------------------------------------------------
        layout.addWidget(self._section_title("REGISTRO DE EVENTOS (EN VIVO)"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFixedHeight(120)
        self.txt_log.setFont(QFont("Consolas", 9))
        self.txt_log.setStyleSheet("""
            background-color: #0D1117;
            border: 1px solid #30363D;
            border-radius: 6px;
            color: #C9D1D9;
        """)
        layout.addWidget(self.txt_log)

    def _section_title(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #58A6FF; text-transform: uppercase;")
        return lbl

    # ====================================================
    # MANEJADORES DE INTERFAZ
    # ====================================================
    def on_connection_change(self, ok):
        if ok:
            self.lbl_broker.setText("● HiveMQ Online")
            self.lbl_broker.setStyleSheet("color: #3FB950;")
        else:
            self.lbl_broker.setText("● Sin conexión")
            self.lbl_broker.setStyleSheet("color: #FF5252;")

    def on_key(self, key, buf, digits):
        for i in range(4):
            if i < len(buf):
                self.digits[i].setText(buf[i])
                self.digits[i].setStyleSheet("""
                    background-color: #0D1117;
                    border: 2px solid #58A6FF;
                    border-radius: 6px;
                    color: #58A6FF;
                """)
            else:
                self.digits[i].setText("•")
                self.digits[i].setStyleSheet("""
                    background-color: #0D1117;
                    border: 2px solid #30363D;
                    border-radius: 6px;
                    color: #8B949E;
                """)

        self.lbl_key_hint.setText(f"Dígito ingresado: '{key}' ({digits}/4)")

    def on_status(self, state, siren, reason):
        self.current_state = state

        # Flash visual en casillas según éxito o fallo
        is_safe = state in ("DISARMED", "ARMED") and siren == 0
        color_flash = "#2EA043" if is_safe else "#DA3633"

        for d in self.digits:
            d.setStyleSheet(f"""
                background-color: #0D1117;
                border: 2px solid {color_flash};
                border-radius: 6px;
                color: {color_flash};
            """)

        # Limpiar casillas tras 600 ms
        QTimer.singleShot(600, self._reset_digits)

        # Transición del Banner Superior
        if state == "DISARMED":
            self.banner_state.setText("🛡️ SISTEMA DESARMADO")
            self.banner_state.setStyleSheet("""
                background-color: #122818;
                border: 2px solid #2EA043;
                border-radius: 10px;
                color: #3FB950;
            """)
        elif state == "ARMED":
            self.banner_state.setText("🔒 SISTEMA ARMADO (VIGILANDO)")
            self.banner_state.setStyleSheet("""
                background-color: #152238;
                border: 2px solid #1F6FEB;
                border-radius: 10px;
                color: #58A6FF;
            """)
        elif state == "TRIGGERED":
            self.banner_state.setText("🚨 ¡ALARMA DISPARADA!")
            self.banner_state.setStyleSheet("""
                background-color: #381214;
                border: 2px solid #DA3633;
                border-radius: 10px;
                color: #F85149;
            """)

        # Actualizar Tarjeta de Sirena / LED
        if siren == 1:
            self.card_siren.setText("SIRENA / LED: ¡ENCENDIDA!")
            self.card_siren.setStyleSheet("""
                background-color: #381214;
                border: 2px solid #DA3633;
                border-radius: 6px;
                color: #F85149;
            """)
        else:
            self.card_siren.setText("SIRENA / LED: APAGADA")
            self.card_siren.setStyleSheet("""
                background-color: #0D1117;
                border: 1.5px solid #30363D;
                border-radius: 6px;
                color: #8B949E;
            """)

        # Actualizar el aspecto de la puerta según el nuevo estado
        self._refresh_door_card()
        self.add_log("ESTADO", f"[{state}] {reason}")

    def on_door(self, open_val, status_text):
        self.door_open = open_val
        self._refresh_door_card()
        self.add_log("SENSOR", f"Puerta GP1: {status_text}")

    def _refresh_door_card(self):
        if self.door_open == 1:
            # Si está armada y la puerta se abre -> ALERTA ROJA
            if self.current_state in ("ARMED", "TRIGGERED"):
                self.card_door.setText("PUERTA: ¡ABIERTA (INTRUSIÓN)!")
                self.card_door.setStyleSheet("""
                    background-color: #381214;
                    border: 2px solid #DA3633;
                    border-radius: 6px;
                    color: #F85149;
                """)
            else:
                self.card_door.setText("PUERTA: ABIERTA (SEGURO)")
                self.card_door.setStyleSheet("""
                    background-color: #2D220E;
                    border: 1.5px solid #D29922;
                    border-radius: 6px;
                    color: #E3B341;
                """)
        else:
            self.card_door.setText("PUERTA: CERRADA")
            self.card_door.setStyleSheet("""
                background-color: #0D1117;
                border: 1.5px solid #238636;
                border-radius: 6px;
                color: #2EA043;
            """)

    def _reset_digits(self):
        for d in self.digits:
            d.setText("•")
            d.setStyleSheet("""
                background-color: #0D1117;
                border: 2px solid #30363D;
                border-radius: 6px;
                color: #8B949E;
            """)
        self.lbl_key_hint.setText("Apunta el control para ingresar 4 dígitos")

    def add_log(self, tag, msg):
        hora = datetime.now().strftime("%H:%M:%S")
        color = "#8B949E"
        if tag == "ESTADO":
            color = "#58A6FF"
        elif tag == "SENSOR":
            color = "#E3B341"

        linea_html = f"[{hora}] **[{tag}]** {msg}"
        self.txt_log.append(linea_html)
        self.txt_log.verticalScrollBar().setValue(
            self.txt_log.verticalScrollBar().maximum()
        )

    # ====================================================
    # CONEXIÓN MQTT
    # ====================================================
    def _init_mqtt(self):
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                client.subscribe(TOPIC_SUB)
                self.bridge.sig_conn.emit(True)
                self.bridge.sig_log.emit(
                    "SISTEMA", "Enlace MQTT sincronizado con éxito"
                )

        def on_disconnect(client, userdata, flags, rc, properties=None):
            self.bridge.sig_conn.emit(False)

        def on_message(client, userdata, msg):
            topic = msg.topic.replace(PREFIX, "")
            raw = msg.payload.decode("utf-8")

            if topic == "alarm/key":
                try:
                    d = json.loads(raw)
                    self.bridge.sig_key.emit(
                        str(d.get("key", "")),
                        str(d.get("buffer", "")),
                        int(d.get("digits", 0)),
                    )
                except Exception:
                    pass

            elif topic == "alarm/status":
                try:
                    d = json.loads(raw)
                    self.bridge.sig_status.emit(
                        str(d.get("state", "")),
                        int(d.get("siren", 0)),
                        str(d.get("reason", "")),
                    )
                except Exception:
                    pass

            elif topic == "alarm/door":
                try:
                    d = json.loads(raw)
                    self.bridge.sig_door.emit(
                        int(d.get("open", 0)), str(d.get("status", ""))
                    )
                except Exception:
                    pass

        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_message = on_message
        self.mqtt_client.connect(BROKER, PORT, 60)
        self.mqtt_client.loop_start()

    def closeEvent(self, event):
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception:
            pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SecurityDashboard()
    window.show()
    sys.exit(app.exec())