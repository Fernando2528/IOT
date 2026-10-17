# Taller 4: Concurrencia Cooperativa, Scheduler, Watchdog y Telemetría en Tiempo Real

Este proyecto documenta y contiene la implementación completa del **Taller 4** de IoT.

---

## 🧭 1. Fundamentos Teóricos del Taller

### El Problema del Bloqueo Secuencial y `sleep()`
En arquitecturas tradicionales basadas en un bucle secuencial:
```python
while True:
    read_sensor()
    input()           # ¡Punto de bloqueo crítico!
    update_motor()
    time.sleep(5)     # ¡5 segundos de congelamiento del microcontrolador!
```
Cualquier función que demore o espere una entrada detiene por completo:
- La lectura de sensores.
- La atención de paquetes y eventos MQTT.
- La actualización de actuadores de seguridad.
- La alimentación del Watchdog, provocando reinicios intempestivos.

### La Solución: Scheduler Cooperativo Basado en Tiempos (`ticks_ms`)
En lugar de detener el procesador con `sleep()`, cada tarea declara un periodo (`period_ms`) y el Scheduler evalúa si ha transcurrido el tiempo necesario mediante la aritmética segura de ticks:
```python
if time.ticks_diff(now, task.next_run) >= 0:
    task.update_measured()
    task.next_run = time.ticks_add(now, task.period)
```

```text
Scheduler (MicroPython)
│
├── Task: sensores            100 ms (Prioridad 3)
├── Task: estado_actuadores    50 ms (Prioridad 1)
├── Task: watchdog_telemetry 1000 ms (Prioridad 2)
└── Task: mqtt_eventos         20 ms (Prioridad 1)
```

### Medir antes de Optimizar (Perfilado en Microsegundos)
No asumimos si una función es rápida o lenta; medimos empíricamente:
```python
start = time.ticks_us()
self.update()
elapsed = time.ticks_diff(time.ticks_us(), start)
self.metrics.append(elapsed)
```
Las métricas (mínimo, máximo, promedio) se almacenan en un `RingBuffer` de memoria fija y se transmiten a la interfaz gráfica.

---

## 💡 2. Mini-Reto: Interfaz Gráfica con Información Realmente Útil

El archivo [`flet/main.py`](file:///C:/Users/Admin/OneDrive/Documentos/Ambito%20Personal/Windows_Git_Hub/IOT/Taller_4/flet/main.py) resuelve el mini-reto transformando el monitor de texto plano en un **Centro de Mando de Salud y Desempeño**:

1. **Panel de Salud del Microcontrolador (Watchdog)**:
   - Contador de latidos vivos (Heartbeat) en tiempo real.
   - Barra de consumo de memoria RAM (`mem_free` vs `mem_alloc`).
   - Temperatura interna del RP2040 (°C) e intensidad de señal Wi-Fi (RSSI en dBm).
2. **Perfilador de Tareas del Scheduler (Profiling)**:
   - Muestra cada tarea con su periodo y tiempos de ejecución medidos en microsegundos (µs): Promedio, Mínimo y Máximo.
   - Alerta visual en rojo (`⚠️ LENTO`) si alguna tarea excede los 5 ms.
3. **Control y Laboratorio de Experimentación**:
   - Actuación sobre el LED de la Pico WH.
   - Botón **"Inyectar Lag (80 ms)"**: Permite verificar visualmente cómo el Scheduler detecta el aumento del tiempo máximo de la tarea y cómo se comporta el sistema bajo estrés.

---

## 💬 3. Respuestas Detalladas a las Preguntas para Discutir

### 1. ¿Qué ocurre si una tarea tarda demasiado?
En un Scheduler cooperativo monohilo, **no existe expulsión preventiva (preemption)**. Si una tarea tarda demasiado, monopoliza la CPU y retrasa el inicio de todas las tareas subsiguientes en la cola. Si la demora supera el límite de tiempo configurado en el Watchdog Timer (WDT), el microcontrolador asumirá que el sistema se colgó y forzará un reinicio de hardware (hardware reset).

### 2. ¿Por qué `input()` es problemático en un sistema IoT?
`input()` es una llamada bloqueante y síncrona que suspende la ejecución del hilo principal indefinidamente hasta que el usuario envíe un salto de línea por la consola o puerto serie. En un sistema IoT embebido, esto paraliza el control de actuadores, el procesamiento de mensajes de red MQTT y la lectura de sensores, dejando el dispositivo inoperativo.

### 3. ¿Por qué debemos limitar el uso de `print()` en tareas rápidas?
La función `print()` envía caracteres a través de la interfaz UART o USB-CDC. La transmisión serie es una operación de I/O muy lenta comparada con la velocidad del procesador (puede añadir cientos de microsegundos o milisegundos por mensaje). En tareas que deben ejecutarse cada 10 ms o 20 ms, llamar a `print()` en cada ciclo degrada significativamente la frecuencia de muestreo y consume ancho de banda de cómputo innecesariamente.

### 4. ¿Qué diferencia existe entre una tarea y una interrupción (ISR)?
- **Interrupción (ISR - Interrupt Service Routine)**: Se dispara por eventos asíncronos de hardware (como flancos en un pin GPIO o desbordamientos de un timer). Detiene inmediatamente el código que se esté ejecutando en el CPU para atender la emergencia. Tiene severas restricciones (no puede asignar memoria dinámica, no debe demorar más de unos pocos microsegundos).
- **Tarea**: Es una función de software regular coordinada por el Scheduler que se ejecuta en el contexto del hilo principal cuando llega su turno temporal, teniendo acceso seguro a toda la memoria y librerías del sistema.

### 5. ¿Qué problema intenta solucionar un Scheduler?
Soluciona la necesidad de ejecutar **múltiples actividades con diferentes frecuencias temporales** (por ejemplo: leer sensores a 100 ms, procesar red a 20 ms y reportar telemetría a 1000 ms) sin que se bloqueen entre sí y sin el costo de memoria ni la complejidad de un Sistema Operativo de Tiempo Real (RTOS).

### 6. ¿Qué diferencia existe entre nuestro Scheduler y `micropython.schedule()`?
- `micropython.schedule()` es una función nativa del runtime de MicroPython diseñada para sacar código fuera del contexto crítico de una interrupción (ISR) y encolarlo para su ejecución segura en el hilo principal de Python. No gestiona periodos ni tiempos futuros de repetición.
- **Nuestro Scheduler** es un patrón de diseño arquitectónico escrito en Python que mantiene una lista de tareas periódicas, evalúa intervalos de tiempo mediante `time.ticks_diff()` y orquesta la multitarea cooperativa de toda la aplicación.

### 7. ¿Qué ventajas tiene el modelo Pub/Sub?
- **Desacoplamiento Espacial**: Productores y consumidores no necesitan conocer las direcciones IP ni la ubicación del otro; solo interactúan mediante tópicos.
- **Desacoplamiento Temporal**: Dispositivos con diferentes ciclos de trabajo pueden publicar o suscribirse independientemente (soportando mensajes retenidos o buffers en el broker).
- **Escalabilidad**: Un único mensaje publicado puede ser distribuido simultáneamente a múltiples clientes interesados (comunicación uno a muchos) sin sobrecargar al nodo emisor.

### 8. ¿Por qué MQTT utiliza un Broker?
Los dispositivos embebidos (como la Pico WH) suelen tener memoria y ancho de banda limitados y suelen operar detrás de firewalls o routers NAT que impiden conexiones entrantes directas. El Broker actúa como punto de encuentro centralizado y de alta disponibilidad: mantiene las conexiones TCP persistentes, filtra tópicos, gestiona sesiones y reenvía mensajes de forma eficiente.

### 9. ¿Qué información debería publicar un Watchdog?
Un Watchdog debe publicar información de diagnóstico y salud del sistema:
1. **Contador de latido (Heartbeat)** y tiempo de actividad continuo (**Uptime**).
2. **Métricas de memoria RAM**: Memoria libre (`gc.mem_free()`) y memoria asignada (`gc.mem_alloc()`) para detectar fugas de memoria (*memory leaks*).
3. **Tiempos de ejecución de las tareas**: Latencia mínima, promedio y máxima de cada tarea en microsegundos para detectar cuellos de botella.
4. **Calidad del canal de comunicación**: Nivel de señal Wi-Fi (**RSSI**) y estado del socket.
5. **Variables físicas internas**: Temperatura del microcontrolador y voltaje.

### 10. ¿Qué ocurre si la interfaz Flet deja de recibir mensajes?
Si la interfaz deja de recibir mensajes del tópico del Watchdog, significa una de las siguientes contingencias:
1. La Pico WH se quedó sin conexión Wi-Fi o perdió el enlace con el Broker MQTT.
2. Una tarea bloqueante congeló el Scheduler de MicroPython.
3. El Watchdog de hardware reinició la placa tras un bloqueo no recuperable.
4. Se interrumpió la alimentación eléctrica o el cable USB del dispositivo.
*En la interfaz Flet implementada en este taller, el indicador de Watchdog cambia automáticamente a color gris/alerta para advertir al operador de que el nodo remoto está fuera de línea.*

---

## 🛠️ 4. Guía de Ejecución

### En la Raspberry Pi Pico WH 1 (Thonny):
1. Conecta la Pico WH vía USB y abre Thonny.
2. Abre los archivos de la carpeta `micropython/`:
   - `ring_buffer.py`
   - `task.py`
   - `scheduler.py`
   - `watchdog_task.py`
   - `wifi_manager.py`
   - `mqtt_client.py`
   - `main.py`
3. Ajusta `SSID` y `PASSWORD` con las credenciales de tu red en `main.py`.
4. Guarda los archivos en el dispositivo y presiona **F5**.

### En la PC (Host Flet):
```powershell
cd "C:\Users\Admin\OneDrive\Documentos\Ambito Personal\Windows_Git_Hub\IOT\Taller_4"
python flet/main.py
```
Haz clic en **Conectar**. Comenzarás a recibir de inmediato el pulso del Watchdog, las estadísticas de RAM y el perfilado en microsegundos de todas las tareas del Scheduler.
