import time
from machine import Pin

# Receptor IR conectado a GP2 (Pin físico 4)
ir_pin = Pin(2, Pin.IN, Pin.PULL_UP)

# Mapeo capturado de tu control
IR_KEYMAP = {
    "0xc": "1",
    "0x18": "2",
    "0x5e": "3",
    "0x8": "4",
    "0x1c": "5",
    "0x5a": "6",
    "0x42": "7",
    "0x52": "8",
    "0x4a": "9",
    "0x16": "0",
}


def decode_nec():
    # 1. Esperar flanco de bajada (inicio de ráfaga)
    while ir_pin.value() == 1:
        pass

    # 2. Medir pulso bajo líder (~9 ms)
    t0 = time.ticks_us()
    while ir_pin.value() == 0:
        if time.ticks_diff(time.ticks_us(), t0) > 15000:
            return None
    t_low = time.ticks_diff(time.ticks_us(), t0)

    # 3. Medir espacio alto líder (~4.5 ms)
    t1 = time.ticks_us()
    while ir_pin.value() == 1:
        if time.ticks_diff(time.ticks_us(), t1) > 10000:
            return None
    t_high = time.ticks_diff(time.ticks_us(), t1)

    # Validar cabecera líder del protocolo NEC
    if not (7000 < t_low < 11000 and 3000 < t_high < 6000):
        return None

    # 4. Decodificar los 32 bits de datos
    bits = []
    for _ in range(32):
        t_bit = time.ticks_us()
        while ir_pin.value() == 0:
            if time.ticks_diff(time.ticks_us(), t_bit) > 2500:
                return None

        t_space = time.ticks_us()
        while ir_pin.value() == 1:
            if time.ticks_diff(time.ticks_us(), t_space) > 3000:
                return None
        dur = time.ticks_diff(time.ticks_us(), t_space)

        # ~560 us = bit 0 | ~1690 us = bit 1
        bits.append(1 if dur > 1000 else 0)

    # 5. Extraer byte de comando (Bits 16 al 23)
    cmd = 0
    for j in range(8):
        cmd |= bits[16 + j] << j

    return hex(cmd)


# Búfer de acumulación
buffer = ""

print("=== Monitor IR: Segmentos de 4 Dígitos ===")
print("Presiona cualquier número en el control remoto...\n")

while True:
    try:
        cmd_hex = decode_nec()
        if cmd_hex and cmd_hex in IR_KEYMAP:
            digit = IR_KEYMAP[cmd_hex]
            buffer += digit

            print(f"Dígito recibido: '{digit}'  -->  Búfer: [{buffer}] ({len(buffer)}/4)")

            # Al completar 4 dígitos, mostrar el bloque y limpiar
            if len(buffer) == 4:
                print("\n==========================================")
                print(f"  >>> SEGMENTO COMPLETADO: '{buffer}' <<<")
                print("==========================================\n")
                buffer = ""

            # Pausa de antirebote para no leer tramas duplicadas por mantener oprimido
            time.sleep(0.35)

    except Exception:
        pass