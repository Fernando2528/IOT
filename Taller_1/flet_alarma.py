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
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BROKER = "broker.hivemq.com"
PORT = 1883
PREFIX = "UDFJC/iot_ws/robot0/"
TOPIC_SUB = PREFIX + "#"


class MqttBridge(QObject):
    sig_key = pyqtSignal(str)
    sig_conn = pyqtSignal(bool)


class CentralSecurityController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Consola Central de Seguridad IoT - PyQt6")
        self.resize(1020, 660)
        self.setStyleSheet("background-color: #0E1117; color: #E6EDF3;")

        # --- VARIABLES DE ESTADO Y SEGURIDAD ---
        self.secret_code = "1111"
        self.alarma_armada = False
        self.puerta_abierta = False
        self.sirena = False
        self.buffer_clave = ""

        # Modos de cambio de clave: 'IDLE', 'VERIFY_OLD', 'ENTER_NEW'
        self.pass_change_mode = "IDLE"

        self.bridge = MqttBridge()
        self.bridge.sig_key.connect(self.process_ir_key)
        self.bridge.sig_conn.connect(self.on_connection_change)

        self._build_ui()
        self._init_mqtt()
        self.update_dashboard("Sistema inicializado en reposo")

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # ----------------------------------------------------
        # 1. Cabecera
        # ----------------------------------------------------
        header = QHBoxLayout()
        title = QLabel("CONSOLA CENTRAL DE SEGURIDAD (HOST CONTROLLER)")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_broker = QLabel("● Desconectado")
        self.lbl_broker.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_broker.setStyleSheet("color: #FF5252;")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.lbl_broker)
        layout.addLayout(header)

        # ----------------------------------------------------
        # 2. Banner Superior de Estado
        # ----------------------------------------------------
        self.banner_state = QLabel("🛡️ SISTEMA DESARMADO")
        self.banner_state.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        self.banner_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_state.setFixedHeight(60)
        layout.addWidget(self.banner_state)

        # ----------------------------------------------------
        # 3. Cuadrícula de Paneles (3 Columnas)
        # ----------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(12)

        # PANEL 1: ENTRADA IR
        box_ir = QFrame()
        box_ir.setStyleSheet("background-color: #161B22; border-radius: 8px; padding: 10px;")
        lay_ir = QVBoxLayout(box_ir)
        lay_ir.addWidget(self._section_title("ENTRADA IR (PICO W - GP2)"))

        row_digits = QHBoxLayout()
        self.digits = []
        for _ in range(4):
            d = QLabel("•")
            d.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setFixedSize(48, 55)
            d.setStyleSheet("""
                background-color: #0D1117;
                border: 2px solid #30363D;
                border-radius: 6px;
                color: #8B949E;
            """)
            row_digits.addWidget(d)
            self.digits.append(d)

        lay_ir.addLayout(row_digits)
        self.lbl_key_hint = QLabel("Apunta el control para ingresar 4 dígitos")
        self.lbl_key_hint.setFont(QFont("Segoe UI", 10))
        self.lbl_key_hint.setStyleSheet("color: #8B949E;")
        lay_ir.addWidget(self.lbl_key_hint)
        lay_ir.addStretch()

        # PANEL 2: ESTADO DE VARIABLES Y ACCIONES
        box_vars = QFrame()
        box_vars.setStyleSheet("background-color: #161B22; border-radius: 8px; padding: 10px;")
        lay_vars = QVBoxLayout(box_vars)
        lay_vars.addWidget(self._section_title("ESTADO DE VARIABLES EN TIEMPO REAL"))

        self.tag_pass = QLabel()
        self.tag_pass.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lay_vars.addWidget(self.tag_pass)

        self.tag_armada = QLabel()
        self.tag_armada.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lay_vars.addWidget(self.tag_armada)

        self.tag_puerta = QLabel()
        self.tag_puerta.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lay_vars.addWidget(self.tag_puerta)

        self.tag_sirena = QLabel()
        self.tag_sirena.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lay_vars.addWidget(self.tag_sirena)

        self.tag_led = QLabel()
        self.tag_led.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        lay_vars.addWidget(self.tag_led)

        # Botones de Acción
        lay_btns_1 = QHBoxLayout()
        self.btn_toggle_door = QPushButton("Simular: ABRIR PUERTA")
        self.btn_toggle_door.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_toggle_door.setFixedHeight(34)
        self.btn_toggle_door.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #58A6FF;
            }
            QPushButton:hover { background-color: #30363D; }
        """)
        self.btn_toggle_door.clicked.connect(self.toggle_door)
        lay_btns_1.addWidget(self.btn_toggle_door)

        self.btn_change_pass = QPushButton("🔑 CAMBIAR CLAVE")
        self.btn_change_pass.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_change_pass.setFixedHeight(34)
        self.btn_change_pass.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #8B5CF6;
                border-radius: 6px;
                color: #C4B5FD;
            }
            QPushButton:hover { background-color: #2E1065; }
        """)
        self.btn_change_pass.clicked.connect(self.request_password_change)
        lay_btns_1.addWidget(self.btn_change_pass)
        lay_vars.addLayout(lay_btns_1)

        self.btn_reset = QPushButton("🔄 REINICIAR SISTEMA (VALORES BASE)")
        self.btn_reset.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_reset.setFixedHeight(34)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #2D1D1F;
                border: 1px solid #DA3633;
                border-radius: 6px;
                color: #F85149;
            }
            QPushButton:hover { background-color: #3D2326; }
        """)
        self.btn_reset.clicked.connect(self.reset_system)
        lay_vars.addWidget(self.btn_reset)
        lay_vars.addStretch()

        # PANEL 3: VERIFICACIÓN DE REQUISITOS
        box_rules = QFrame()
        box_rules.setStyleSheet("background-color: #161B22; border-radius: 8px; padding: 10px;")
        lay_rules = QVBoxLayout(box_rules)
        lay_rules.addWidget(self._section_title("REQUISITOS DEL SISTEMA"))

        self.rule1 = QLabel("1. [ ] Clave IR activa / desactiva alarma")
        self.rule2 = QLabel("2. [ ] Alarma activa + Puerta abierta -> Sirena")
        self.rule3 = QLabel("3. [ ] Clave equivocada -> Dispara sirena")
        self.rule4 = QLabel("4. [ ] Alarma desactivada + Puerta -> Sin sirena")
        self.rule5 = QLabel("5. [ ] Cambio de clave: Validar actual -> Nueva")

        for r in [self.rule1, self.rule2, self.rule3, self.rule4, self.rule5]:
            r.setFont(QFont("Segoe UI", 9))
            r.setStyleSheet("color: #8B949E; padding: 2px;")
            lay_rules.addWidget(r)

        lay_rules.addStretch()

        grid.addWidget(box_ir, 0, 0)
        grid.addWidget(box_vars, 0, 1)
        grid.addWidget(box_rules, 0, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 4)
        layout.addLayout(grid)

        # ----------------------------------------------------
        # 4. Terminal de Eventos
        # ----------------------------------------------------
        layout.addWidget(self._section_title("REGISTRO DE EVENTOS"))
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
        lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #58A6FF; text-transform: uppercase;")
        return lbl

    def on_connection_change(self, ok):
        if ok:
            self.lbl_broker.setText("● HiveMQ Online")
            self.lbl_broker.setStyleSheet("color: #3FB950;")
        else:
            self.lbl_broker.setText("● Desconectado")
            self.lbl_broker.setStyleSheet("color: #FF5252;")

    # ==========================================================
    # LÓGICA DE PROCESAMIENTO IR Y CAMBIO DE CLAVE
    # ==========================================================
    def request_password_change(self):
        if self.sirena:
            self.add_log("AVISO", "Primero desactive la sirena ingresando la clave actual.")
            return

        self.pass_change_mode = "VERIFY_OLD"
        self.buffer_clave = ""
        self._reset_digits()
        self.lbl_key_hint.setText("PASO 1/2: Digite la CLAVE ACTUAL en el control")
        self.lbl_key_hint.setStyleSheet("color: #C4B5FD; font-weight: bold;")
        self.banner_state.setText("🔑 CAMBIO DE CLAVE: INGRESE CLAVE ACTUAL")
        self.banner_state.setStyleSheet("""
            background-color: #2E1065;
            border: 2px solid #8B5CF6;
            border-radius: 8px;
            color: #DDD6FE;
        """)
        self.add_log("CLAVE", "Modo cambio iniciado. Ingrese la clave actual de 4 dígitos.")

    def process_ir_key(self, key):
        self.buffer_clave += key
        digits_count = len(self.buffer_clave)

        color_border = "#8B5CF6" if self.pass_change_mode != "IDLE" else "#58A6FF"
        for i in range(4):
            if i < digits_count:
                self.digits[i].setText(self.buffer_clave[i])
                self.digits[i].setStyleSheet(f"""
                    background-color: #0D1117;
                    border: 2px solid {color_border};
                    border-radius: 6px;
                    color: {color_border};
                """)
            else:
                self.digits[i].setText("•")
                self.digits[i].setStyleSheet("""
                    background-color: #0D1117;
                    border: 2px solid #30363D;
                    border-radius: 6px;
                    color: #8B949E;
                """)

        if self.pass_change_mode == "VERIFY_OLD":
            self.lbl_key_hint.setText(f"Validando clave actual: ({digits_count}/4)")
        elif self.pass_change_mode == "ENTER_NEW":
            self.lbl_key_hint.setText(f"Ingresando NUEVA clave: ({digits_count}/4)")
        else:
            self.lbl_key_hint.setText(f"Dígito ingresado: '{key}' ({digits_count}/4)")

        self.add_log("IR", f"Pulsación: '{key}' | Búfer: [{self.buffer_clave}]")

        # Al completar 4 dígitos
        if digits_count == 4:
            code = self.buffer_clave
            self.buffer_clave = ""

            # CASO A: Validando la clave actual para autorizar el cambio
            if self.pass_change_mode == "VERIFY_OLD":
                if code == self.secret_code:
                    self.pass_change_mode = "ENTER_NEW"
                    self._flash_digits("#2EA043")
                    self.lbl_key_hint.setText("PASO 2/2: Ingrese la NUEVA clave de 4 dígitos")
                    self.lbl_key_hint.setStyleSheet("color: #3FB950; font-weight: bold;")
                    self.banner_state.setText("🔑 AUTORIZADO: DIGITE LA NUEVA CLAVE")
                    self.banner_state.setStyleSheet("""
                        background-color: #122818;
                        border: 2px solid #2EA043;
                        border-radius: 8px;
                        color: #3FB950;
                    """)
                    self.add_log("CLAVE", "Clave actual validada. Ingrese los 4 nuevos dígitos.")
                else:
                    # Clave incorrecta -> Dispara la sirena y cancela el cambio
                    self.pass_change_mode = "IDLE"
                    self.sirena = True
                    self._flash_digits("#DA3633")
                    self.sync_led_actuator()
                    self.update_dashboard(f"¡CLAVE ERRÓNEA ({code}) EN CAMBIO! Sirena DISPARADA")

            # CASO B: Guardando la nueva clave
            elif self.pass_change_mode == "ENTER_NEW":
                self.secret_code = code
                self.pass_change_mode = "IDLE"
                self._flash_digits("#2EA043")
                self.update_dashboard(f"✅ ¡Clave cambiada con éxito a '{self.secret_code}'!")
                self.add_log("CLAVE", f"Nueva clave de seguridad establecida: '{self.secret_code}'")

            # CASO C: Operación normal del sistema
            else:
                if code == self.secret_code:
                    if self.alarma_armada or self.sirena:
                        self.alarma_armada = False
                        self.sirena = False
                        causa = "Clave correcta: Sistema DESARMADO / Sirena apagada"
                    else:
                        self.alarma_armada = True
                        self.sirena = False
                        causa = "Clave correcta: Sistema ARMADO (Vigilando)"
                else:
                    self.sirena = True
                    causa = f"¡CLAVE INCORRECTA ({code})! Sirena DISPARADA"

                flash_color = "#DA3633" if self.sirena else "#2EA043"
                self._flash_digits(flash_color)
                self.sync_led_actuator()
                self.update_dashboard(causa)

    def _flash_digits(self, color):
        for d in self.digits:
            d.setStyleSheet(f"""
                background-color: #0D1117;
                border: 2px solid {color};
                border-radius: 6px;
                color: {color};
            """)
        QTimer.singleShot(600, self._reset_digits)

    def _reset_digits(self):
        for d in self.digits:
            d.setText("•")
            d.setStyleSheet("""
                background-color: #0D1117;
                border: 2px solid #30363D;
                border-radius: 6px;
                color: #8B949E;
            """)
        if self.pass_change_mode == "IDLE":
            self.lbl_key_hint.setText("Apunta el control para ingresar 4 dígitos")
            self.lbl_key_hint.setStyleSheet("color: #8B949E;")

    def toggle_door(self):
        self.puerta_abierta = not self.puerta_abierta
        txt_p = "ABIERTA" if self.puerta_abierta else "CERRADA"

        if self.puerta_abierta and self.alarma_armada:
            self.sirena = True
            causa = "¡INTRUSIÓN! Puerta abierta con alarma armada"
        else:
            causa = f"Puerta {txt_p} (Alarma desarmada)"

        self.sync_led_actuator()
        self.update_dashboard(causa)

    def reset_system(self):
        """Restaura variables y devuelve la contraseña a 1111."""
        self.secret_code = "1111"
        self.alarma_armada = False
        self.puerta_abierta = False
        self.sirena = False
        self.buffer_clave = ""
        self.pass_change_mode = "IDLE"
        self._reset_digits()
        self.sync_led_actuator()
        self.update_dashboard("SISTEMA REINICIADO (Clave por defecto: '1111')")
        self.add_log("RESET", "Reinicio completado. Estados en reposo y clave restaurada a '1111'.")

    def sync_led_actuator(self):
        val = 1 if self.sirena else 0
        payload = json.dumps({"value": val})
        self.mqtt_client.publish(PREFIX + "led/LED", payload)

    def update_dashboard(self, reason):
        # 1. Banner Principal
        if self.sirena:
            self.banner_state.setText("🚨 ¡ALARMA DISPARADA! (SIRENA ACTIVA)")
            self.banner_state.setStyleSheet("""
                background-color: #381214;
                border: 2px solid #DA3633;
                border-radius: 8px;
                color: #F85149;
            """)
        elif self.alarma_armada:
            self.banner_state.setText("🔒 SISTEMA ARMADO (VIGILANDO)")
            self.banner_state.setStyleSheet("""
                background-color: #152238;
                border: 2px solid #1F6FEB;
                border-radius: 8px;
                color: #58A6FF;
            """)
        elif self.pass_change_mode == "IDLE":
            self.banner_state.setText("🛡️ SISTEMA DESARMADO")
            self.banner_state.setStyleSheet("""
                background-color: #122818;
                border: 2px solid #2EA043;
                border-radius: 8px;
                color: #3FB950;
            """)

        # 2. Etiquetas de Variables
        self.tag_pass.setText(f"clave_seguridad = '{self.secret_code}'")
        self.tag_pass.setStyleSheet("color: #C4B5FD; background-color: #0D1117; padding: 5px; border-radius: 4px;")

        self.tag_armada.setText(
            f"alarma_armada  = {self.alarma_armada} ({'ARMADA' if self.alarma_armada else 'DESARMADA'})"
        )
        self.tag_armada.setStyleSheet(
            f"color: {'#58A6FF' if self.alarma_armada else '#3FB950'}; background-color: #0D1117; padding: 5px; border-radius: 4px;"
        )

        self.tag_puerta.setText(
            f"puerta_abierta = {self.puerta_abierta} ({'ABIERTA' if self.puerta_abierta else 'CERRADA'})"
        )
        color_p = "#F85149" if (self.puerta_abierta and self.alarma_armada) else ("#D29922" if self.puerta_abierta else "#3FB950")
        self.tag_puerta.setStyleSheet(
            f"color: {color_p}; background-color: #0D1117; padding: 5px; border-radius: 4px;"
        )

        self.btn_toggle_door.setText(
            "Simular: CERRAR PUERTA" if self.puerta_abierta else "Simular: ABRIR PUERTA"
        )

        self.tag_sirena.setText(
            f"sirena         = {self.sirena} ({'DISPARADA' if self.sirena else 'APAGADA'})"
        )
        self.tag_sirena.setStyleSheet(
            f"color: {'#F85149' if self.sirena else '#8B949E'}; background-color: #0D1117; padding: 5px; border-radius: 4px;"
        )

        led_val = 1 if self.sirena else 0
        self.tag_led.setText(
            f"led_fisico     = {led_val} ({'ENCENDIDO' if led_val == 1 else 'APAGADO'})"
        )
        self.tag_led.setStyleSheet(
            f"color: {'#F85149' if led_val == 1 else '#8B949E'}; background-color: #0D1117; padding: 5px; border-radius: 4px;"
        )

        self._highlight_rules(reason)
        self.add_log("ESTADO", reason)

    def _highlight_rules(self, reason):
        for r in [self.rule1, self.rule2, self.rule3, self.rule4, self.rule5]:
            r.setStyleSheet("color: #8B949E; padding: 2px;")

        if "Clave cambiada" in reason:
            self.rule5.setStyleSheet("color: #C4B5FD; font-weight: bold; padding: 2px;")
        elif "Clave correcta" in reason:
            self.rule1.setStyleSheet("color: #3FB950; font-weight: bold; padding: 2px;")
        elif "INTRUSIÓN" in reason or (self.alarma_armada and self.puerta_abierta and self.sirena):
            self.rule2.setStyleSheet("color: #F85149; font-weight: bold; padding: 2px;")
        elif "CLAVE" in reason and "INCORRECTA" in reason or "ERRÓNEA" in reason:
            self.rule3.setStyleSheet("color: #F85149; font-weight: bold; padding: 2px;")
        elif not self.alarma_armada and self.puerta_abierta and not self.sirena:
            self.rule4.setStyleSheet("color: #D29922; font-weight: bold; padding: 2px;")

    def add_log(self, tag, msg):
        hora = datetime.now().strftime("%H:%M:%S")
        color = "#58A6FF" if tag == "ESTADO" else ("#C4B5FD" if tag == "CLAVE" else ("#2EA043" if tag == "IR" else "#8B949E"))
        self.txt_log.append(
            f"<span style='color:#555;'>[{hora}]</span> <b style='color:{color};'>[{tag}]</b> {msg}"
        )
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    # ==========================================================
    # RED MQTT
    # ==========================================================
    def _init_mqtt(self):
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                client.subscribe(TOPIC_SUB)
                self.bridge.sig_conn.emit(True)
                self.add_log("SISTEMA", "MQTT conectado. Controlador central listo")

        def on_disconnect(client, userdata, flags, rc, properties=None):
            self.bridge.sig_conn.emit(False)

        def on_message(client, userdata, msg):
            topic = msg.topic.replace(PREFIX, "")
            raw = msg.payload.decode("utf-8")

            if topic == "alarm/key":
                try:
                    d = json.loads(raw)
                    key = str(d.get("key", ""))
                    self.bridge.sig_key.emit(key)
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
    window = CentralSecurityController()
    window.show()
    sys.exit(app.exec())