# Proyecto Segundo Corte: Coreografía y Gemelo Virtual (`robot12`)

Implementación completa del **Proyecto de Segundo Corte (Coreografía)** para el **Robot 12** (`grupo_materia = 1`, `grupo_proyecto = 2`, número **par** $\rightarrow$ ejecuta [`even.json`](even.json)).

---

## 🔗 Enlaces Directos al Gemelo Virtual Configurados para `robot12`

1. **Gemelo Virtual Individual (`robot12`)**:
   https://gerardomunoz.github.io/IoT_ws/coreografia/PubSub_client_web.html?transport=mqtt&host=broker.hivemq.com&port=8884&prefix=UDFJC/carrrobot&robot=12
   - Al abrir la página, verifica que esté en `🟢 Connected`, luego oprime el botón **`Subscribe Robot`** en el panel *Virtual twin*.
2. **Visualización de la Coreografía de Todos los Robots**:
   https://gerardomunoz.github.io/IoT_ws/coreografia/robot_coreografia_mqtt.html
   - Oprime **`Conectar y escuchar`** o **`Enviar comandos`** para disparar simultáneamente las secuencias `even` y `odd`.

---

## 📌 Pinout Físico en la Raspberry Pi Pico W (`micropython/main.py`)

| Subsistema | Pin Pico W | Conexión Física |
| :--- | :--- | :--- |
| **Motor Izquierdo (Canal A)** | `GP16` (`IN1`), `GP17` (`IN2`), `GP6` (`ENA` PWM) | Puente H L298N Canal A |
| **Motor Derecho (Canal B)** | `GP18` (`IN3`), `GP19` (`IN4`), `GP7` (`ENB` PWM) | Puente H L298N Canal B |
| **Servo Hombro (`alpha1_deg`)** | `GP12` | Señal PWM Servomotor SG90 #1 (50 Hz) |
| **Servo Codo (`alpha2_deg`)** | `GP13` | Señal PWM Servomotor SG90 #2 (50 Hz) |
| **Potenciómetro (Scroll OLED)** | `GP28` (`ADC2`) | Salida central del potenciómetro (0V a 3.3V) |
| **Pantalla OLED SSD1306 (I2C)** | `GP4` (`SDA`), `GP5` (`SCL`) *(con auto-detección en `GP0/GP1`, `GP8/GP9`, `GP2/GP3`, `GP14/GP15`)* | Pantalla OLED 128x64 I2C (`0x3C` / `0x3D`) |

---

## 🚀 Cómo Ejecutar y Probar

### 1. En el PC (Interfaz Amigable en Flet)
```powershell
cd "C:\Users\Admin\OneDrive\Documentos\Ambito Personal\Windows_Git_Hub\IOT\IOT_Corte_2"
python flet/main.py
```
*(Opcional)* Si deseas probar primero el Gemelo Virtual y la interfaz Flet sin encender la Raspberry Pi Pico W, ejecuta en otra terminal el simulador de PC:
```powershell
python simulador_pc.py
```

### 2. En la Raspberry Pi Pico W (Thonny)
1. En Thonny, abre la carpeta `IOT_Corte_2/micropython/`.
2. Selecciona **todos los archivos `.py`** dentro de `IOT_Corte_2/micropython/` y súbelos directamente a la **raíz `/`** de la Raspberry Pi Pico W.
3. Ejecuta `main.py` en la Pico W.
