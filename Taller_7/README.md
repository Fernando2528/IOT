# Taller 7 / 8: Modulación por Ancho de Pulsos (PWM) y Control de Servomotores 180°

**Universidad Distrital Francisco José de Caldas (UDFJC)**  
*Facultad de Ingeniería — Programa de Ingeniería de Sistemas / Electrónica*  
*Laboratorio de Internet de las Cosas (IoT) y Sistemas Embebidos*

---

## 1. Introducción y Objetivos

El presente taller aborda el principio de funcionamiento de la **Modulación por Ancho de Pulsos (PWM, *Pulse Width Modulation*)** aplicada al control de actuadores electromecánicos en la **Raspberry Pi Pico W** y su teleoperación mediante el protocolo **MQTT** y una interfaz gráfica en **Flet**.

### Objetivos de Aprendizaje:
1. Comprender la relación física y matemática entre frecuencia, periodo y ciclo de trabajo (*Duty Cycle*) en señales PWM.
2. Implementar una capa de abstracción de hardware modular mediante las clases `PWMOut` y `Servo` en MicroPython.
3. Controlar la orientación angular de un servomotor estándar de 180° (SG90 / MG90S) con resolución en microsegundos ($\mu\text{s}$).
4. **Cumplir con el requerimiento docente:** Desarrollar un campo de entrada editable en Flet que permita al operador digitar cualquier ángulo arbitrario (0.0° a 180.0°) y posicionar el actuador a esa coordenada exacta, sincronizado con un deslizador y telemetría en tiempo real.
5. Integrar el control del servomotor con el subsistema de tracción diferencial (driver puente H L298N) dentro de un único ecosistema IoT.

---

## 2. Solución al Requerimiento del Docente

> **Observación del Profesor:**  
> *"El campo de Flet donde se ven los grados debe ser editable, de tal manera que el usuario pueda ingresar cualquier ángulo deseado y los motores/servomotores roten a ese ángulo exacto."*

### Implementación Realizada:
- Se implementó un control `ft.TextField` editable con validación numérica estricta (`0.0°` a `180.0°`).
- Admite números enteros y flotantes (ej. `0°`, `45°`, `73.5°`, `120.2°`, `180°`).
- Dispone de envío inmediato al presionar la tecla **Enter** (`on_submit`) o pulsar el botón **"Aplicar"**.
- Se encuentra **sincronizado bidireccionalmente** con un control deslizante (`ft.Slider` de 180 divisiones):
  - Si el usuario arrastra el *slider*, el campo de texto se actualiza al instante.
  - Si el usuario digita un valor manual, el *slider* salta de inmediato a la posición correspondiente.
- Se incorporaron botones de acceso rápido (*presets*): `0° (Mín)`, `45°`, `90° (Centro)`, `135°` y `180° (Máx)`.
- Se añadió un **Modo de Barrido Automático (*Sweep*)** en hilo concurrente para pruebas de fatiga y verificación del rango mecánico.

---

## 3. Fundamentación Teórica de PWM y Servomotores

### 3.1. Principio del Servomotor Analógico (SG90 / MG90S)
A diferencia de un motor DC convencional cuya velocidad depende del voltaje promedio aplicado, un servomotor de posición utiliza la **duración de un pulso de nivel alto** para comandar la posición angular del eje de salida.

* **Frecuencia de control ($f$):** $50\text{ Hz}$
* **Periodo de la señal ($T$):**  
  $$T = \frac{1}{f} = \frac{1}{50\text{ Hz}} = 0.020\text{ s} = 20\text{ ms} = 20\,000\text{ }\mu\text{s}$$

* **Estándar de anchos de pulso ($t_{on}$):**
  - **$0^\circ$ (Mínimo):** $\approx 500\text{ }\mu\text{s}$ ($0.5\text{ ms}$)
  - **$90^\circ$ (Posición Central):** $\approx 1500\text{ }\mu\text{s}$ ($1.5\text{ ms}$)
  - **$180^\circ$ (Máximo):** $\approx 2500\text{ }\mu\text{s}$ ($2.5\text{ ms}$)

### 3.2. Deducción de Fórmulas Matemáticas

#### Mapeo de Ángulo a Ancho de Pulso:
Para cualquier ángulo $\theta \in [\theta_{min}, \theta_{max}]$:
$$\text{pulse\_us}(\theta) = \text{min\_us} + \left( \frac{\theta - \theta_{min}}{\theta_{max} - \theta_{min}} \right) \cdot (\text{max\_us} - \text{min\_us})$$

Sustituyendo los valores estándar ($\theta_{min}=0^\circ$, $\theta_{max}=180^\circ$, $\text{min\_us}=500\,\mu\text{s}$, $\text{max\_us}=2500\,\mu\text{s}$):
$$\text{pulse\_us}(\theta) = 500 + \left( \frac{\theta}{180} \right) \cdot 2000 = 500 + \frac{100}{9}\theta$$

#### Cálculo del Registro de Hardware en MicroPython (`duty_u16`):
La Raspberry Pi Pico maneja el ciclo de trabajo con un registro sin signo de 16 bits ($0$ a $65\,535$, donde $65\,535 = 100\%$ del periodo):
$$\text{duty\_u16} = \left\lfloor \frac{\text{pulse\_us}}{T} \times 65\,535 \right\rfloor = \left\lfloor \frac{\text{pulse\_us}}{20\,000\,\mu\text{s}} \times 65\,535 \right\rfloor$$

### 3.3. Tabla de Calibración Rápida
| Ángulo ($\theta$) | Ancho de Pulso ($t_{on}$) | Duty Cycle (%) | Registro `duty_u16` | Posición Mecánica |
| :---: | :---: | :---: | :---: | :---: |
| **0.0°** | $500\text{ }\mu\text{s}$ | $2.5\%$ | $\approx 1\,638$ | Extremo Izquierdo |
| **45.0°** | $1\,000\text{ }\mu\text{s}$ | $5.0\%$ | $\approx 3\,277$ | Diagonal Izquierda |
| **90.0°** | $1\,500\text{ }\mu\text{s}$ | $7.5\%$ | $\approx 4\,915$ | Neutro / Centro |
| **135.0°** | $2\,000\text{ }\mu\text{s}$ | $10.0\%$ | $\approx 6\,554$ | Diagonal Derecha |
| **180.0°** | $2\,500\text{ }\mu\text{s}$ | $12.5\%$ | $\approx 8\,192$ | Extremo Derecho |

---

## 4. Arquitectura de Software

```
        USUARIO / OPERADOR
                │
                ▼
   ┌───────────────────────────┐
   │        FLET GUI           │
   │  • Campo editable grados  │
   │  • Slider sincronizado    │
   │  • Telemetría en vivo     │
   └────────────┬──────────────┘
                │
                │ Publish: UDFJC/iot_ws/robot0/servo/angle
                │ Subscribe: UDFJC/iot_ws/robot0/servo/status
                ▼
   ┌───────────────────────────┐
   │    BROKER MQTT HIVEMQ     │
   │   (broker.hivemq.com)     │
   └────────────┬──────────────┘
                │
                ▼
   ┌───────────────────────────┐
   │   RASPBERRY PI PICO W     │
   │                           │
   │  [main.py]                │
   │      │                    │
   │      ▼                    │
   │  [Servo Class]            │ ◄── Convierte ángulo a µs
   │      │                    │
   │      ▼                    │
   │  [PWMOut Class]           │ ◄── Configura frecuencia (50Hz) y duty_u16
   │      │                    │
   │      ▼                    │
   │  Pin GP12 (Hardware PWM)  │
   └────────────┬──────────────┘
                │ Señal PWM
                ▼
        SERVOMOTOR SG90 (180°)
```

### Estructura de Directorios
```
Taller8/
├── README.md                      # Documentación completa y guía académica
├── requirements.txt               # Dependencias Python (flet>=0.86, paho-mqtt>=2.0)
├── main.py                        # Lanzador universal del dashboard
├── flet/
│   ├── main.py                    # Aplicación Flet (campo editable, slider, presets)
│   └── mqtt.py                    # Gestor de cliente MQTT para Flet (Paho v2)
└── micropython/
    ├── pwm_out.py                 # Clase PWMOut (abstracción de señales PWM)
    ├── servo.py                   # Clase Servo (conversión ángulo <-> pulsos µs)
    ├── mqtt_client.py             # Cliente umqtt robusto para Pico W
    ├── wifi_manager.py            # Administrador de conexión Wi-Fi WPA2
    ├── scheduler.py               # Planificador cooperativo de tareas
    ├── task.py                    # Clase base Task
    └── main.py                    # Programa principal autónomo para la Pico W
```

---

## 5. Diagrama de Conexiones de Hardware

### 5.1. Conexión del Servomotor SG90 / MG90S
| Cable Servo | Color Típico | Pin Raspberry Pi Pico W | Función |
| :--- | :--- | :--- | :--- |
| **GND** | Marrón o Negro | **Pin 38 (GND)** | Masa de referencia común |
| **VCC** | Rojo | **Pin 39 (VSYS)** o Pin 40 (VBUS) | Alimentación 5V |
| **Señal** | Naranja o Amarillo | **Pin 16 (GP12)** | Salida PWM a 50 Hz |

> [!IMPORTANT]
> Nunca conecte la alimentación del servomotor al pin de 3.3V de la Pico. Los picos de corriente del motor pueden reiniciar el microcontrolador. Use el pin **VSYS/VBUS** (5V) o una fuente externa con masa común.

### 5.2. Conexión del Driver de Motores L298N (Opcional Robot)
| Terminal L298N | Pin Raspberry Pi Pico W | Descripción |
| :--- | :--- | :--- |
| **ENA** | **GP6** | PWM Velocidad Motor Izquierdo |
| **IN1 / IN2** | **GP2 / GP3** | Sentido Motor Izquierdo |
| **IN3 / IN4** | **GP4 / GP5** | Sentido Motor Derecho |
| **ENB** | **GP7** | PWM Velocidad Motor Derecho |
| **GND** | **Pin GND Común** | Referencia unificada |

---

## 6. Guía de Ejecución

### 6.1. Configuración en la Raspberry Pi Pico W (Thonny IDE)
1. Abra **Thonny IDE** y conecte la Pico W vía USB.
2. Copie todos los archivos de la carpeta `micropython/` a la raíz del dispositivo MicroPython.
3. En `micropython/main.py`, actualice sus credenciales de red:
   ```python
   SSID = "NOMBRE_DE_TU_RED"
   PASSWORD = "PASSWORD_DE_TU_RED"
   ```
4. Guarde y ejecute `main.py`. La consola imprimirá:
   ```text
   ==================================================
   🤖 TALLER 7: CONTROL DE SERVOMOTOR 180° Y PWM
   ==================================================
   [+] Conectado a Wi-Fi. IP: 192.168.1.45
   [+] Conectado al Broker broker.hivemq.com
   [+] Servomotor inicializado en GP12. Posición inicial: 90.0°
   [+] Suscrito a: UDFJC/iot_ws/robot0/servo/angle
   ```

### 6.2. Ejecución del Dashboard Flet
1. Abra una terminal en su sistema operativo en la carpeta `Taller8`.
2. Instale los requisitos si aún no lo ha hecho:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicie el panel de control:
   ```bash
   python main.py
   ```
4. **Verificación del Requerimiento Docente:**
   - En el campo **"Ángulo Manual (°)"**, escriba `45.0` y presione **Enter** o el botón **"Aplicar"**.
   - El servomotor se moverá a $45^\circ$ y el *slider* se alineará a $45^\circ$.
   - La telemetría confirmará el ángulo recibido, el ancho de pulso ($1000\text{ }\mu\text{s}$) y el `duty_u16` registrado.
   - Si arrastra el deslizador, el campo numérico reflejará los cambios instantáneamente.

---

## 7. Preguntas de Discusión y Evaluación Técnica

1. **¿Por qué la frecuencia estándar para servomotores es 50 Hz y no 1 kHz como en los motores DC?**  
   *Respuesta:* Los circuitos analógicos internos de los servos integran un comparador y un generador de rampa monoestable sincronizados a 50 Hz ($T=20\text{ ms}$). Si se enviara a 1 kHz ($T=1\text{ ms}$), el periodo sería más corto que el propio pulso ($0.5-2.5\text{ ms}$), haciendo inviable la modulación.

2. **¿Qué ocurre si se comanda un pulso menor a 500 µs o mayor a 2500 µs?**  
   *Respuesta:* El servomotor alcanzará sus topes mecánicos internos (*end-stops*). Forzar el motor contra estos topes mecánicos provoca calentamiento excesivo, bloqueo del tren de engranajes y riesgo de destrucción térmica del bobinado. Por esta razón, la clase `Servo` implementa una función de saturación estricta (*clamping*).

3. **¿Cuál es la ventaja de modular la señal PWM en el microcontrolador en lugar de variar el voltaje con una resistencia o potenciómetro?**  
   *Respuesta:* El PWM conserva la máxima eficiencia energética y torque completo del actuador, ya que los transistores de conmutación operan únicamente en corte y saturación, minimizando la disipación térmica ($P = I \cdot V_{sat} \approx 0$).
