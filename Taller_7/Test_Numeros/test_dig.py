import time
from machine import Pin

# Receptor IR conectado a GP2
ir_pin = Pin(2, Pin.IN, Pin.PULL_UP)

print("=== Sniffer de Códigos IR (Protocolo NEC) ===")
print("Apunta el control a GP2 y presiona los botones numéricos...\n")

def read_nec():
    # Esperar flanco de bajada
    while ir_pin.value() == 1:
        pass

    # Medir pulso bajo líder (~9 ms)
    t0 = time.ticks_us()
    while ir_pin.value() == 0:
        if time.ticks_diff(time.ticks_us(), t0) > 15000:
            return None
    t_low = time.ticks_diff(time.ticks_us(), t0)

    # Medir espacio alto líder (~4.5 ms)
    t1 = time.ticks_us()
    while ir_pin.value() == 1:
        if time.ticks_diff(time.ticks_us(), t1) > 10000:
            return None
    t_high = time.ticks_diff(time.ticks_us(), t1)

    if not (7000 < t_low < 11000 and 3000 < t_high < 6000):
        return None

    # Leer los 32 bits
    bits = []
    for _ in range(32):
        t_bit = time.ticks_us()
        while ir_pin.value() == 0:
            if time.ticks_diff(time.ticks_us(), t_bit) > 2000:
                return None

        t_space = time.ticks_us()
        while ir_pin.value() == 1:
            if time.ticks_diff(time.ticks_us(), t_space) > 3000:
                return None
        dur = time.ticks_diff(time.ticks_us(), t_space)
        bits.append(1 if dur > 1000 else 0)

    # Decodificar el byte de comando (Bits 16 al 23)
    cmd = 0
    for j in range(8):
        cmd |= (bits[16 + j] << j)

    return hex(cmd)

while True:
    code = read_nec()
    if code:
        print(f"Código detectado -> Comando: {code}")
        time.sleep(0.35)