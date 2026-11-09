"""
main_test_loop.py
=================
Script de prueba para el cableado exacto del usuario:
- ENA = GP6
- ENB = GP7
- IN1 = GP16
- IN2 = GP17
- IN3 = GP18
- IN4 = GP19

Ejecuta un ciclo infinito:
  5 seg: ADELANTE a media potencia (60%)
  3 seg: PAUSA (0V)
  5 seg: ATRÁS a media potencia (60%)
  3 seg: PAUSA (0V)
"""

import time
from machine import Pin, PWM

print("=======================================================")
print("🚗 TEST EXACTO L298N (GP16..GP19 + GP6..GP7)")
print("=======================================================")

# LED testigo en la Pico
try:
    led = Pin("LED", Pin.OUT)
except Exception:
    led = Pin(25, Pin.OUT)

# -----------------------------------------------------------
# DEFINICIÓN EXACTA DE TUS PINES
# -----------------------------------------------------------
in1 = Pin(16, Pin.OUT)  # GP16 -> IN1 (Motor A)
in2 = Pin(17, Pin.OUT)  # GP17 -> IN2 (Motor A)
in3 = Pin(18, Pin.OUT)  # GP18 -> IN3 (Motor B)
in4 = Pin(19, Pin.OUT)  # GP19 -> IN4 (Motor B)

ena = PWM(Pin(6))       # GP6  -> ENA (Velocidad Motor A)
enb = PWM(Pin(7))       # GP7  -> ENB (Velocidad Motor B)
ena.freq(1000)
enb.freq(1000)

# Potencia media (~60% PWM, aprox 2.0V DC en pines Enable)
POTENCIA = 0.60
DUTY = int(POTENCIA * 65535)

def parar():
    in1.value(0)
    in2.value(0)
    in3.value(0)
    in4.value(0)
    ena.duty_u16(0)
    enb.duty_u16(0)
    led.value(0)

parar()
time.sleep(1)

ciclo = 1
sentido_adelante = True

try:
    while True:
        led.value(1)
        if sentido_adelante:
            print(f"\n[{ciclo}] 🟢 ADELANTE (5 segundos) - Potencia 60%")
            print("     -> GP16 (IN1) = 3.3V  |  GP17 (IN2) = 0.0V")
            print("     -> GP18 (IN3) = 3.3V  |  GP19 (IN4) = 0.0V")
            print(f"     -> GP6 (ENA) y GP7 (ENB) = PWM activo ({DUTY}/65535)")
            print("     -> Voltaje en bornes OUT1-OUT2: debe ser voltaje de batería!")

            in1.value(1)
            in2.value(0)
            in3.value(1)
            in4.value(0)
        else:
            print(f"\n[{ciclo}] 🔵 ATRÁS (5 segundos) - Potencia 60%")
            print("     -> GP16 (IN1) = 0.0V  |  GP17 (IN2) = 3.3V")
            print("     -> GP18 (IN3) = 0.0V  |  GP19 (IN4) = 3.3V")
            print(f"     -> GP6 (ENA) y GP7 (ENB) = PWM activo ({DUTY}/65535)")

            in1.value(0)
            in2.value(1)
            in3.value(0)
            in4.value(1)

        # Aplicar PWM a los pines Enable
        ena.duty_u16(DUTY)
        enb.duty_u16(DUTY)

        time.sleep(5)

        # Fase de reposo
        print(f"[{ciclo}] 🔴 PAUSA (3 segundos) - Motores en reposo")
        parar()
        time.sleep(3)

        sentido_adelante = not sentido_adelante
        ciclo += 1

except KeyboardInterrupt:
    print("\n[!] Prueba detenida con Ctrl+C.")
finally:
    parar()
    print("[-] Motores apagados.")
