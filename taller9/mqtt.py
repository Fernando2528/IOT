from umqtt.simple import MQTTClient

oled = OLED(sda_pin=4, scl_pin=5)

client = MQTTClient("pico_robot", "IP_DEL_BROKER")
# Delegar la recepción de mensajes directamente al método de la clase
client.set_callback(oled.on_message)
client.connect()
client.subscribe("oled/text")

while True:
    client.check_msg()  # No bloqueante: revisa si hay mensajes pendientes
    time.sleep_ms(50)