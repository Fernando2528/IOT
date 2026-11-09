"""
test_paso_a_paso.py
===================
Script de diagnóstico paso a paso para el Puente H L298N:
1. Mantiene Enable A (GP6) y Enable B (GP7) en ALTO FIJO (3.3V DC puro, 100% potencia).
2. Prueba CADA pin de dirección (GP16, GP17, GP18, GP19) uno por uno durante 5 segundos
   con 2 segundos de pausa entre cada uno.
3. Imprime en pantalla exactamente qué rueda y qué pin se está probando para identificar
   cuál combinación hace girar cada motor.
"""

import time
from machine import Pin

print("\n=======================================================")
print("🔍 TEST PASO A PASO: IDENTIFICACIÓN DE PINES L298N")
print("=======================================================")
print("⚠️ RECOMENDACIÓN: Levanta el carro de la mesa para que las")
print("   ruedas queden en el aire y no haya fricción contra el suelo.\n")

# LED integrado de la Pico
try:
    led = Pin("LED", Pin.OUT)
except Exception:
    led = Pin(25, Pin.OUT)

# -----------------------------------------------------------
# PINES DE CONTROL (SALIDAS DIGITALES PURAS, SIN PWM)
# -----------------------------------------------------------
ena = Pin(6, Pin.OUT)   # GP6 -> ENA
enb = Pin(7, Pin.OUT)   # GP7 -> ENB

in1 = Pin(16, Pin.OUT)  # GP16
in2 = Pin(17, Pin.OUT)  # GP17
in3 = Pin(18, Pin.OUT)  # GP18
in4 = Pin(19, Pin.OUT)  # GP19

def todo_apagado():
    in1.value(0)
    in2.value(0)
    in3.value(0)
    in4.value(0)
    ena.value(0)
    enb.value(0)
    led.value(0)

todo_apagado()
time.sleep(1)

ciclo = 1

try:
    while True:
        print(f"\n==================== [CICLO {ciclo}] ====================")

        # ---------------------------------------------------------
        # PASO 1: RUEDA IZQUIERDA - GP16
        # ---------------------------------------------------------
        print("\n👉 [PASO 1] Probando RUEDA IZQUIERDA (GP16 en ALTO, 5 seg):")
        print("   • ENA (GP6)  = 1 (3.3V FIJO, 100% habilitado)")
        print("   • IN1 (GP16) = 1 (3.3V)")
        print("   • IN2 (GP17) = 0 (0.0V)")
        print("   • Motor Derecho apagado (ENB=0, GP18=0, GP19=0)")
        print("   >>> Observa: ¿GIRA LA RUEDA IZQUIERDA? <<<")

        led.value(1)
        ena.value(1)
        enb.value(0)
        in1.value(1)
        in2.value(0)
        in3.value(0)
        in4.value(0)
        time.sleep(5)

        print("[-] Pausa (2 seg)...")
        todo_apagado()
        time.sleep(2)

        # ---------------------------------------------------------
        # PASO 2: RUEDA IZQUIERDA - GP17 (SENTIDO OPUESTO)
        # ---------------------------------------------------------
        print("\n👉 [PASO 2] Probando RUEDA IZQUIERDA (GP17 en ALTO, 5 seg):")
        print("   • ENA (GP6)  = 1 (3.3V FIJO)")
        print("   • IN1 (GP16) = 0 (0.0V)")
        print("   • IN2 (GP17) = 1 (3.3V)")
        print("   • Motor Derecho apagado (ENB=0)")
        print("   >>> Observa: ¿GIRA LA RUEDA IZQUIERDA AL REVÉS? <<<")

        led.value(1)
        ena.value(1)
        enb.value(0)
        in1.value(0)
        in2.value(1)
        in3.value(0)
        in4.value(0)
        time.sleep(5)

        print("[-] Pausa (2 seg)...")
        todo_apagado()
        time.sleep(2)

        # ---------------------------------------------------------
        # PASO 3: RUEDA DERECHA - GP18
        # ---------------------------------------------------------
        print("\n👉 [PASO 3] Probando RUEDA DERECHA (GP18 en ALTO, 5 seg):")
        print("   • ENB (GP7)  = 1 (3.3V FIJO, 100% habilitado)")
        print("   • IN3 (GP18) = 1 (3.3V)")
        print("   • IN4 (GP19) = 0 (0.0V)")
        print("   • Motor Izquierdo apagado (ENA=0)")
        print("   >>> Observa: ¿GIRA LA RUEDA DERECHA? <<<")

        led.value(1)
        ena.value(0)
        enb.value(1)
        in1.value(0)
        in2.value(0)
        in3.value(1)
        in4.value(0)
        time.sleep(5)

        print("[-] Pausa (2 seg)...")
        todo_apagado()
        time.sleep(2)

        # ---------------------------------------------------------
        # PASO 4: RUEDA DERECHA - GP19 (SENTIDO OPUESTO)
        # ---------------------------------------------------------
        print("\n👉 [PASO 4] Probando RUEDA DERECHA (GP19 en ALTO, 5 seg):")
        print("   • ENB (GP7)  = 1 (3.3V FIJO)")
        print("   • IN3 (GP18) = 0 (0.0V)")
        print("   • IN4 (GP19) = 1 (3.3V)")
        print("   • Motor Izquierdo apagado (ENA=0)")
        print("   >>> Observa: ¿GIRA LA RUEDA DERECHA AL REVÉS? <<<")

        led.value(1)
        ena.value(0)
        enb.value(1)
        in1.value(0)
        in2.value(0)
        in3.value(0)
        in4.value(1)
        time.sleep(5)

        print("[-] Pausa (2 seg)...")
        todo_apagado()
        time.sleep(2)

        ciclo += 1

except KeyboardInterrupt:
    print("\n[!] Prueba detenida con Ctrl+C.")
finally:
    todo_apagado()
    print("[-] Todos los pines puestos a 0V.")
