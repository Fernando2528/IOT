from datetime import datetime
import json
import sys
import paho.mqtt.client as mqtt
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"
TOPIC_SUB = PREFIX + "#"

# Factor multiplicador requerido en la interfaz
FACTOR_ESCALA = 2.0


class MqttBridge(QObject):
    sig_adc = pyqtSignal(str, int, float)  # pin, raw, voltage original
    sig_log = pyqtSignal(str, str)
    sig_conn = pyqtSignal(bool)


class AdcMonitorConsole(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor Analógico ADC (Escala x2) - PyQt6")
        self.resize(880, 580)
        self.setStyleSheet("background-color: #0E1117; color: #E6EDF3;")

        self.bridge = MqttBridge()
        self.bridge.sig_adc.connect(self.on_adc_data)
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
        # 1. Cabecera y Estado de Conexión
        # ----------------------------------------------------
        header = QHBoxLayout()
        title = QLabel("TELEMETRÍA ANALÓGICA - MULTIPLICADOR x2")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF; letter-spacing: 1px;")

        self.lbl_broker = QLabel("● Desconectado")
        self.lbl_broker.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_broker.setStyleSheet("color: #FF5252;")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.lbl_broker)
        layout.addLayout(header)

        # ----------------------------------------------------
        # 2. Tarjeta Principal: Tensión Multiplicada (x2)
        # ----------------------------------------------------
        card_main = QFrame()
        card_main.setStyleSheet("""
            background-color: #161B22;
            border: 1px solid #30363D;
            border-radius: 10px;
            padding: 15px;
        """)
        lay_main = QVBoxLayout(card_main)
        lay_main.setSpacing(10)

        self.lbl_pin_title = QLabel("CANAL ACTIVO: ESPERANDO DATOS...")
        self.lbl_pin_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_pin_title.setStyleSheet("color: #58A6FF;")
        self.lbl_pin_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_main.addWidget(self.lbl_pin_title)

        # Indicador de Tensión Escalada (* 2)
        self.lbl_voltage = QLabel("0.000 V")
        self.lbl_voltage.setFont(QFont("Segoe UI", 44, QFont.Weight.Bold))
        self.lbl_voltage.setStyleSheet("color: #2EA043;")
        self.lbl_voltage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_main.addWidget(self.lbl_voltage)

        lbl_sub = QLabel("Tensión calculada en interfaz (V_leído × 2)")
        lbl_sub.setFont(QFont("Segoe UI", 10))
        lbl_sub.setStyleSheet("color: #8B949E;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_main.addWidget(lbl_sub)

        # Barra de progreso (0 V a 6.6 V)
        self.bar_level = QProgressBar()
        self.bar_level.setRange(0, 1000)
        self.bar_level.setValue(0)
        self.bar_level.setTextVisible(False)
        self.bar_level.setFixedHeight(18)
        self.bar_level.setStyleSheet("""
            QProgressBar {
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 9px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2EA043, stop:0.75 #58A6FF, stop:1 #D29922
                );
                border-radius: 8px;
            }
        """)
        lay_main.addWidget(self.bar_level)

        lay_scale = QHBoxLayout()
        lbl_min = QLabel("0.0 V")
        lbl_min.setFont(QFont("Consolas", 9))
        lbl_min.setStyleSheet("color: #8B949E;")
        lbl_max = QLabel("6.6 V (3.3V × 2)")
        lbl_max.setFont(QFont("Consolas", 9))
        lbl_max.setStyleSheet("color: #8B949E;")
        lay_scale.addWidget(lbl_min)
        lay_scale.addStretch()
        lay_scale.addWidget(lbl_max)
        lay_main.addLayout(lay_scale)

        layout.addWidget(card_main)

        # ----------------------------------------------------
        # 3. Comparativa y Métricas (Grid de 3 Tarjetas)
        # ----------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(12)

        self.box_orig = self._create_info_card("TENSIÓN DE ENTRADA (ORIGINAL)", "0.000 V", "#58A6FF")
        self.box_raw = self._create_info_card("VALOR CRUDO (16 BITS)", "0 / 65535", "#C9D1D9")
        self.box_pct = self._create_info_card("PORCENTAJE DE ESCALA", "0.0 %", "#D29922")

        grid.addWidget(self.box_orig["frame"], 0, 0)
        grid.addWidget(self.box_raw["frame"], 0, 1)
        grid.addWidget(self.box_pct["frame"], 0, 2)
        layout.addLayout(grid)

        # ----------------------------------------------------
        # 4. Registro de Eventos
        # ----------------------------------------------------
        lbl_log = QLabel("REGISTRO DE LECTURAS (EN VIVO)")
        lbl_log.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_log.setStyleSheet("color: #58A6FF; text-transform: uppercase;")
        layout.addWidget(lbl_log)

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

    def _create_info_card(self, title_text, init_val, val_color):
        frame = QFrame()
        frame.setStyleSheet("background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 10px;")
        lay = QVBoxLayout(frame)
        lay.setSpacing(4)

        t = QLabel(title_text)
        t.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        t.setStyleSheet("color: #8B949E; text-transform: uppercase;")

        v = QLabel(init_val)
        v.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        v.setStyleSheet(f"color: {val_color};")

        lay.addWidget(t)
        lay.addWidget(v)
        return {"frame": frame, "lbl_val": v}

    # ====================================================
    # LÓGICA DE MULTIPLICACIÓN Y ACTUALIZACIÓN VISUAL
    # ====================================================
    def on_connection_change(self, ok):
        if ok:
            self.lbl_broker.setText("● HiveMQ Online")
            self.lbl_broker.setStyleSheet("color: #3FB950;")
        else:
            self.lbl_broker.setText("● Desconectado")
            self.lbl_broker.setStyleSheet("color: #FF5252;")

    def on_adc_data(self, pin_name, raw_val, voltage):
        # 1. Multiplicación por 2 aplicada en la interfaz
        voltaje_multiplicado = voltage * FACTOR_ESCALA

        # 2. Despliegue en pantalla
        self.lbl_pin_title.setText(f"CANAL ACTIVO: {pin_name}")
        self.lbl_voltage.setText(f"{voltaje_multiplicado:.3f} V")

        if voltaje_multiplicado > 5.5:
            self.lbl_voltage.setStyleSheet("color: #F85149;")
        elif voltaje_multiplicado > 2.5:
            self.lbl_voltage.setStyleSheet("color: #58A6FF;")
        else:
            self.lbl_voltage.setStyleSheet("color: #2EA043;")

        # Barra de progreso referenciada al nuevo rango (0 V a 6.6 V)
        progress_val = int((voltaje_multiplicado / 6.6) * 1000)
        self.bar_level.setValue(min(max(progress_val, 0), 1000))

        # Tarjetas de datos
        self.box_orig["lbl_val"].setText(f"{voltage:.3f} V")
        self.box_raw["lbl_val"].setText(f"{raw_val} / 65535")
        pct = (raw_val / 65535) * 100
        self.box_pct["lbl_val"].setText(f"{pct:.1f} %")

        self.add_log(
            pin_name,
            f"Leído: {voltage:.3f} V | Multiplicado (×2): {voltaje_multiplicado:.3f} V | Raw: {raw_val}",
        )

    def add_log(self, tag, msg):
        hora = datetime.now().strftime("%H:%M:%S")
        color = "#58A6FF" if "GP" in tag else ("#3FB950" if tag == "SISTEMA" else "#8B949E")
        self.txt_log.append(
            f"[{hora}] **[{tag}]** {msg}"
        )
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
                self.bridge.sig_log.emit("SISTEMA", "MQTT conectado. Multiplicador x2 activo")

        def on_disconnect(client, userdata, flags, rc, properties=None):
            self.bridge.sig_conn.emit(False)

        def on_message(client, userdata, msg):
            topic = msg.topic.replace(PREFIX, "")
            raw_payload = msg.payload.decode("utf-8")

            if topic.startswith("adc/"):
                try:
                    data = json.loads(raw_payload)
                    pin = str(data.get("pin", topic.replace("adc/", "")))
                    raw = int(data.get("raw", 0))
                    volt = float(data.get("voltage", 0.0))
                    self.bridge.sig_adc.emit(pin, raw, volt)
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
    window = AdcMonitorConsole()
    window.show()
    sys.exit(app.exec())