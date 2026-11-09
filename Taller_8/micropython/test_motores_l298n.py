"""
test_motores_l298n.py
=====================
Script de prueba rápida directa para diagnosticar el cableado del L298N y los motores.
No requiere Wi-Fi ni MQTT: ejecuta directamente los motores para verificar:
1. Si los pines son GP2..GP5 (típico con cable cinta) o GP16..GP19.
2. Si la batería está entregando suficiente voltaje a los motores.
3. Si los puentes H están conmutando correctamente.
"""

from machine import Pin, PWM
import time

print("\n=======================================================")
print("🔧 TEST DIRECTO DE MOTORES Y DRIVER L298N")
print("=======================================================")

# LED indicador
try:
    led = Pin("LED", Pin.OUT)
except Exception:
    led = Pin(25, Pin.OUT)

led.value(1)

# -----------------------------------------------------------
# PRUEBA 1: Configuración habitual de cable cinta (GP2 a GP7)
# -----------------------------------------------------------
print("\n[1/2] Probando CONFIGURACIÓN A (GP2, GP3, GP4, GP5 con ENA=GP6, ENB=GP7)...")
try:
    in1_a = Pin(2, Pin.OUT)
    in2_a = Pin(3, Pin.OUT)
    in3_a = Pin(4, Pin.OUT)
    in4_a = Pin(5, Pin.OUT)
    ena_a = PWM(Pin(6))
    enb_a = PWM(Pin(7))
    ena_a.freq(1000)
    enb_a.freq(1000)

    # Ambos hacia adelante a máxima potencia
    in1_a.value(1)
    in2_a.value(0)
    in3_a.value(1)
    in4_a.value(0)
    ena_a.duty_u16(65535)
    enb_a.duty_u16(65535)

    print("   -> Motores activados en GP2..GP7 por 3 segundos...")
    print("   -> Mide con multímetro entre OUT1-OUT2 y OUT3-OUT4 (debe haber voltaje de batería).")
    time.sleep(3)

    # Detener
    in1_a.value(0)
    in2_a.value(0)
    in3_a.value(0)
    in4_a.value(0)
    ena_a.duty_u16(0)
    enb_a.duty_u16(0)
    print("   -> Configuración A detenida.")
except Exception as e:
    print("   [!] Error en Config A:", e)

time.sleep(1)

# -----------------------------------------------------------
# PRUEBA 2: Configuración esquema alterno (GP16 a GP19)
# -----------------------------------------------------------
print("\n[2/2] Probando CONFIGURACIÓN B (GP19, GP18, GP17, GP16 con ENA=GP6, ENB=GP7)...")
try:
    in1_b = Pin(19, Pin.OUT)
    in2_b = Pin(18, Pin.OUT)
    in3_b = Pin(17, Pin.OUT)
    in4_b = Pin(16, Pin.OUT)
    ena_b = PWM(Pin(6))
    enb_b = PWM(Pin(7))
    ena_b.freq(1000)
    enb_b.freq(1000)

    # Ambos hacia adelante a máxima potencia
    in1_b.value(1)
    in2_b.value(0)
    in3_b.value(1)
    in4_b.value(0)
    ena_b.duty_u16(65535)
    enb_b.duty_u16(65535)

    print("   -> Motores activados en GP16..GP19 por 3 segundos...")
    time.sleep(3)

    # Detener
    in1_b.value(0)
    in2_b.value(0)
    in3_b.value(0)
    in4_b.value(0)
    ena_b.duty_u16(0)
    enb_b.duty_u16(0)
    print("   -> Configuración B detenida.")
except Exception as e:
    print("   [!] Error en Config B:", e)

led.value(0)
print("\n=======================================================")
print("🏁 Fin del test. Si alguna de las dos hizo girar las ruedas,")
print("usa esa combinación de pines en main.py.")
print("=======================================================\n")
