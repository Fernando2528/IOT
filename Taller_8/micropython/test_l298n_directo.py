"""
test_l298n_directo.py
=====================
Script de prueba 100% autónomo para copiar y pegar en Thonny.
Diagnostica y comprueba el giro de los motores con L298N (6 hilos o 4 hilos).
NO requiere Wi-Fi ni MQTT.
"""

import time
from machine import Pin, PWM

print("=======================================================")
print("🚗 TEST DIRECTO DE MOTORES L298N EN RASPBERRY PI PICO")
print("=======================================================")

# LED de la Pico para confirmar que el script está corriendo
try:
    led = Pin("LED", Pin.OUT)
except Exception:
    led = Pin(25, Pin.OUT)

led.value(1)

# =============================================================
# DEFINICIÓN DE PINES (Cableado de 6 hilos estándar GP2 a GP7)
# =============================================================
PIN_IN1_NUM = 2   # GP2 -> IN1
PIN_IN2_NUM = 3   # GP3 -> IN2
PIN_IN3_NUM = 4   # GP4 -> IN3
PIN_IN4_NUM = 5   # GP5 -> IN4
PIN_ENA_NUM = 6   # GP6 -> ENA
PIN_ENB_NUM = 7   # GP7 -> ENB

# Si tienes cableado en GP16..GP19, cambia los números aquí:
# PIN_IN1_NUM = 19
# PIN_IN2_NUM = 18
# PIN_IN3_NUM = 17
# PIN_IN4_NUM = 16

print(f"[*] Configurando pines:")
print(f"    IN1: GP{PIN_IN1_NUM}, IN2: GP{PIN_IN2_NUM}")
print(f"    IN3: GP{PIN_IN3_NUM}, IN4: GP{PIN_IN4_NUM}")
print(f"    ENA: GP{PIN_ENA_NUM}, ENB: GP{PIN_ENB_NUM}")

in1 = Pin(PIN_IN1_NUM, Pin.OUT)
in2 = Pin(PIN_IN2_NUM, Pin.OUT)
in3 = Pin(PIN_IN3_NUM, Pin.OUT)
in4 = Pin(PIN_IN4_NUM, Pin.OUT)

# Configurar ENA y ENB con PWM a 1000 Hz
ena_pwm = PWM(Pin(PIN_ENA_NUM))
enb_pwm = PWM(Pin(PIN_ENB_NUM))
ena_pwm.freq(1000)
enb_pwm.freq(1000)

def parar():
    in1.value(0)
    in2.value(0)
    in3.value(0)
    in4.value(0)
    ena_pwm.duty_u16(0)
    enb_pwm.duty_u16(0)

parar()
time.sleep(0.5)

try:
    # ---------------------------------------------------------
    # FASE 1: AVANCE HACIA ADELANTE (3 SEGUNDOS)
    # ---------------------------------------------------------
    print("\n[FASE 1] Activando motores HACIA ADELANTE (100% potencia)...")
    print("         -> IN1=1 (3.3V), IN2=0 (0V)")
    print("         -> IN3=1 (3.3V), IN4=0 (0V)")
    print("         -> ENA=65535 (~3.3V), ENB=65535 (~3.3V)")
    print("         -> MIDE AHORA EN BORNES OUT1-OUT2: debe haber voltaje de batería (~10V-12V)!")

    in1.value(1)
    in2.value(0)
    in3.value(1)
    in4.value(0)
    ena_pwm.duty_u16(65535)  # 100% de ciclo de trabajo en ENA
    enb_pwm.duty_u16(65535)  # 100% de ciclo de trabajo en ENB

    time.sleep(3)

    parar()
    print("[-] Pausa de 1 segundo...")
    time.sleep(1)

    # ---------------------------------------------------------
    # FASE 2: RETROCESO (3 SEGUNDOS)
    # ---------------------------------------------------------
    print("\n[FASE 2] Activando motores EN REVERSA (100% potencia)...")
    print("         -> IN1=0 (0V), IN2=1 (3.3V)")
    print("         -> IN3=0 (0V), IN4=1 (3.3V)")
    print("         -> ENA=65535 (~3.3V), ENB=65535 (~3.3V)")

    in1.value(0)
    in2.value(1)
    in3.value(0)
    in4.value(1)
    ena_pwm.duty_u16(65535)
    enb_pwm.duty_u16(65535)

    time.sleep(3)

    parar()
    print("[-] Motores detenidos.")

    # ---------------------------------------------------------
    # FASE 3: GIRO SOBRE SU EJE (3 SEGUNDOS)
    # ---------------------------------------------------------
    print("\n[FASE 3] Giro sobre su eje (Motor Izq Adelante, Motor Der Atrás)...")
    in1.value(1)
    in2.value(0)
    in3.value(0)
    in4.value(1)
    ena_pwm.duty_u16(55000)  # ~84% de potencia
    enb_pwm.duty_u16(55000)

    time.sleep(3)
    parar()

    print("\n=======================================================")
    print("✅ TEST COMPLETADO CON ÉXITO.")
    print("Si los motores giraron aquí, el hardware y cableado están 100% OK.")
    print("=======================================================")

except Exception as err:
    print(f"\n[!] Error durante la prueba: {err}")
finally:
    parar()
    led.value(0)
