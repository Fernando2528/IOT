# Taller 6: Sensores Analógicos, ADC, Batería 18650 con TP4056 y Dashboard en Flet

Este proyecto documenta e implementa el **Taller 6** de IoT, cubriendo la cadena completa de transducción, acondicionamiento de señal, conversión analógica-digital (ADC) y visualización en tiempo real.

---

## 🔬 1. La Cadena Completa de Transducción IoT

> *"La meta no es solamente medir una batería. La meta es construir el recorrido completo:  
> **Fenómeno físico → Señal eléctrica → ADC → Procesamiento → Comunicación → Dashboard**"*

```mermaid
flowchart LR
    Bat["🔋 Celda 18650 (3.0V a 4.2V)"] --> TP["⚡ Módulo TP4056 (Cargador / Protección)"]
    TP --> Div["📉 Divisor de Voltaje (R1 + R2)"]
    Div -- "0V a 2.1V" --> ADC["🍓 Pico GP28 (ADC2)"]
    ADC -- "read_u16() (0 - 65535)" --> Micro["🐍 MicroPython (AnalogIn / Scheduler)"]
    Micro -- "AnalogIn_u16/GP28" --> MQTT["☁️ Broker MQTT (HiveMQ)"]
    MQTT --> Flet["💻 Dashboard Flet (Voltaje, SoC %, Gráfica)"]
```

---

## 📐 2. Fundamentos Matemáticos y Acondicionamiento

### A) El Problema del Rango Dinámico del ADC
- El convertidor analógico a digital del RP2040 (Raspberry Pi Pico) tiene un rango de entrada de **0V a 3.3V**.
- Una batería de Litio 18650 cargada alcanza **4.2V**.
- **Conectar la batería directamente al pin ADC superaría el voltaje máximo admisible (VDD = 3.3V) y destruiría el puerto o el chip.**

### B) Divisor de Voltaje Resistivo
Para adaptar el nivel de voltaje a un rango seguro, se conectan dos resistencias en serie:
$$V_{ADC} = V_{bat} \times \frac{R_2}{R_1 + R_2}$$

Si utilizamos dos resistencias idénticas (por ejemplo, $R_1 = 10\text{ k}\Omega$ y $R_2 = 10\text{ k}\Omega$):
$$V_{ADC} = V_{bat} \times \frac{10}{10 + 10} = \frac{V_{bat}}{2}$$

- Cuando la batería está al máximo ($4.2\text{V}$), el pin de la Pico recibe:
  $$V_{ADC} = \frac{4.2\text{ V}}{2} = 2.1\text{ V} < 3.3\text{ V} \quad \text{(100\% Seguro)}$$

### C) Reconstrucción del Voltaje en Software (Flet)
A partir del valor entero de 16 bits (`read_u16`) emitido por la Pico:
1. **Voltaje en el pin**:
   $$V_{pin} = \frac{\text{raw\_u16}}{65535} \times 3.3\text{ V}$$
2. **Voltaje real de la batería**:
   $$V_{bat} = V_{pin} \times \left(\frac{R_1 + R_2}{R_2}\right) = V_{pin} \times 2.0$$
3. **Estado de Carga (State of Charge, SoC)**:
   $$\text{SoC (\%)} = \frac{V_{bat} - 3.0\text{V}}{4.2\text{V} - 3.0\text{V}} \times 100\%$$

---

## 📊 3. Tabla de Comparación de Mediciones (Laboratorio)

| Medición | Fórmula / Origen | Resultado Típico |
| :--- | :--- | :---: |
| **Batería — multímetro** | Medición física con multímetro en bornes de la celda 18650 | `3.820 V` |
| **Divisor — valor calculado** | $V_{bat\_multi} \times \frac{R_2}{R_1 + R_2}$ | `1.910 V` |
| **Divisor — multímetro** | Medición física entre el nodo central del divisor y GND | `1.905 V` |
| **Pico ADC — lectura u16** | Valor entregado por `adc.read_u16()` | `37840` |
| **Flet — voltaje publicado** | $V_{reconstruido} = \left(\frac{u16}{65535} \times 3.3\right) \times 2.0$ | `3.812 V` |

---

## 💬 4. Respuestas a las Preguntas Finales

### 1. ¿Por qué no conectamos directamente la batería al ADC?
Porque el pin analógico del microcontrolador RP2040 tolera un voltaje máximo de **3.3 V** (su voltaje de referencia de alimentación). Una celda de ion de litio 18650 totalmente cargada alcanza los **4.2 V**, lo que provocaría una sobretensión destructiva en los diodos de protección interna del pin y quemaría el convertidor ADC del procesador.

### 2. ¿Qué función cumple el divisor de voltaje?
Cumple una función de **acondicionamiento de señal**: atenúa o escala proporcionalmente el voltaje de la fuente para comprimir su rango dinámico (de 0–4.2 V) dentro del rango seguro y medible por el convertidor analógico a digital (0–3.3 V).

### 3. ¿Por qué el multímetro y el Pico pueden mostrar valores ligeramente diferentes?
Existen cuatro causas físicas principales:
1. **Tolerancia de las resistencias**: Las resistencias comerciales tienen un margen de error (típicamente ±1% o ±5%), por lo que el factor real no es exactamente 2.000.
2. **Impedancia de entrada del ADC**: El circuito de muestreo del RP2040 (*Sample & Hold*) tiene una resistencia y capacitancia interna que puede cargar ligeramente el divisor si se usan resistencias de valor muy alto (por encima de 50 kΩ).
3. **Ruido en la línea de referencia (3V3)**: El rizado de la fuente de alimentación y del módulo Wi-Fi altera levemente el voltaje de referencia de 3.3V que utiliza el ADC para convertir la señal.
4. **No linealidad del ADC del RP2040**: El chip RP2040 tiene un error conocido de integral non-linearity (INL) con pequeños picos de desviación (*DNL spikes*) en ciertos umbrales de conversión.

### 4. ¿Qué sucede con el voltaje de una 18650 a medida que se descarga?
Su voltaje desciende a lo largo de una curva de descarga característica:
- **100% de carga**: 4.2 V.
- **Zona de meseta nominal (30% - 80%)**: El voltaje desciende lentamente entre 3.8 V y 3.6 V.
- **Batería agotada (0%)**: Cae rápidamente por debajo de 3.3 V hasta alcanzar el voltaje de corte seguro (alrededor de 2.8 V a 3.0 V). Si se descarga por debajo de 2.5 V, la celda sufre degradación química irreversible.

### 5. ¿Qué diferencia existe entre capacidad en mAh y energía en Wh?
- **Capacidad (mAh - miliamperios-hora)**: Mide la cantidad de **carga eléctrica** total que puede suministrar la batería a lo largo del tiempo ($\text{Carga} = I \times t$), sin considerar a qué voltaje la entrega.
- **Energía (Wh - vatios-hora)**: Mide el **trabajo eléctrico o energía real acumulada** ($\text{Energía} = \text{Voltaje} \times \text{Capacidad}$). Toma en cuenta que el voltaje de la batería va decayendo a medida que se descarga.  
  *Ejemplo:* Una celda de 2500 mAh a 3.7 V nominal almacena:
  $$\text{Energía} = 3.7\text{ V} \times 2.5\text{ Ah} = 9.25\text{ Wh}$$

### 6. ¿Qué función cumple el TP4056?
Es un circuito integrado especializado en la **gestión de carga segura de baterías de litio (Li-Ion / LiPo)**:
1. Aplica el protocolo de carga de dos etapas: **Corriente Constante (CC)** hasta alcanzar 4.2V y luego **Voltaje Constante (CV)** hasta que la corriente disminuye al 10%.
2. Corta automáticamente la alimentación cuando la batería está completamente cargada (4.2V ± 1%).
3. En sus versiones con chip de protección (DW01A + FS8205A), protege la batería contra **sobrecorriente, cortocircuitos y sobre-descarga** (desconecta la salida si el voltaje cae por debajo de 2.4V).

### 7. ¿Por qué `main.py` puede continuar funcionando después de desconectar Thonny?
El intérprete de MicroPython está grabado permanentemente en la memoria Flash del RP2040. Cuando el microcontrolador se alimenta (por batería o cargador USB independiente), su gestor de arranque (*bootloader*) busca y ejecuta automáticamente en orden:
1. `boot.py`: Inicializaciones de bajo nivel.
2. `main.py`: Tu código de aplicación principal.  
Thonny solo actúa como un monitor serie y depurador; su presencia no es necesaria para la operación autónoma del firmware embebido.

### 8. ¿Qué parte del sistema convierte el voltaje analógico en un valor digital?
El **Convertidor Analógico a Digital (ADC)** integrado en el silicio del microcontrolador RP2040. En el caso del RP2040, se trata de un convertidor de aproximaciones sucesivas (**SAR ADC - Successive Approximation Register**) de 12 bits nativos (escalado por el runtime de MicroPython a 16 bits sin signo: 0 a 65535).

---

## 🛠️ 5. Guía de Ejecución

### En la Raspberry Pi Pico WH (Thonny):
1. Conecta el pin central del divisor de voltaje a **GP28 (Pin 34 físico)** y la tierra común a **GND**.
2. Sube a la Pico los archivos de [`micropython/`](file:///C:/Users/Admin/OneDrive/Documentos/Ambito%20Personal/Windows_Git_Hub/IOT/Taller_6/micropython):
   - `analog_in.py`
   - `task.py`
   - `scheduler.py`
   - `wifi_manager.py`
   - `mqtt_client.py`
   - `main.py`
3. Ajusta `SSID` y `PASSWORD` en `main.py` y presiona **F5**.
4. Observa en la consola de Thonny las lecturas periódicas:
   ```text
   [AnalogIn_u16] GP28 -> Valor RAW: 37840
   ```

### En la PC (Dashboard Flet):
```powershell
cd "C:\Users\Admin\OneDrive\Documentos\Ambito Personal\Windows_Git_Hub\IOT\Taller_6"
python flet/main.py
```
Haz clic en **Conectar MQTT**:
- Verás el medidor de batería reaccionar en tiempo real indicando el voltaje reconstruido, el voltaje en el pin y el porcentaje de carga.
- Podrás ajustar los valores reales de $R_1$ y $R_2$ medidos con tu multímetro para una calibración exacta.
- Completa los valores de tu multímetro en la **Tabla de Comparación** para calcular automáticamente el error relativo de la medición.
