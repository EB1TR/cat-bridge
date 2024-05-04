import serial
import paho.mqtt.client as mqtt
import time
import re
import json
import sys

# Abrir e importar configuración ---------------------------------------------------------------------------------------
#
try:
    with open("config.json") as f:
        config = json.load(f)
    RX_PORT = config["rx_port"]
    RX_BAUD = config["rx_baud"]
    TX_PORT = config["tx_port"]
    TX_BAUD = config["tx_baud"]
    EX_DATA = config["ex_data"]
    TX_TIME = config["tx_time"]
    MQ_DATA = config["mq_data"]
    MQ_HOST = config["mq_host"]
    MQ_PORT = config["mq_port"]
    MQ_TOPIC = config["mq_topic"]

except Exception as e:
    print("No es posible abrir el fichero de configuración o el formato es incorrecto")
    print(e)
    input("Presione ENTER para salir...")
    sys.exit(0)
# ----------------------------------------------------------------------------------------------------------------------

try:
    sera = serial.Serial(port=RX_PORT)
    sera.baudrate = RX_BAUD
    sera.bytesize = serial.EIGHTBITS
    sera.parity = serial.PARITY_NONE
    sera.stopbits = serial.STOPBITS_TWO
    sera.setRTS = False
    sera.setDTR = False
    sera.rts = False
    sera.dtr = False
    sera.rtscts = False
    sera.dsrdtr = False
    serb = serial.Serial(port=TX_PORT)
    serb.baudrate = TX_BAUD
    serb.bytesize = serial.EIGHTBITS
    serb.parity = serial.PARITY_NONE
    serb.stopbits = serial.STOPBITS_TWO
    serb.setRTS = False
    serb.setDTR = False
    serb.rts = False
    serb.dtr = False
    serb.rtscts = False
    serb.dsrdtr = False
except Exception as e:
    print("No es posible abrir uno o mas puertos")
    print(e)
    input("Presione ENTER para salir...")
    sys.exit(0)

if MQ_DATA:
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect_async(MQ_HOST, port=MQ_PORT, keepalive=60, bind_address="")
        client.loop_start()
    except Exception as e:
        print("No es posible abrir la conexión MQTT")
        print(e)
        input("Presione ENTER para salir...")
        sys.exit(0)

msg = ""
data_a = ""
amp_data = ""
fa_time = 0
fa_last_send_time = time.time()
fa_send_interval_time = TX_TIME
fa_expire_time = EX_DATA

print(f'Intervalo entre envíos: {int(fa_send_interval_time*1000)} milisegundos')
print(f'Tiempo de expiración de frecuencia: {int(fa_expire_time*1000)} milisegundos')

while True:
    try:
        # Determine if the program need send or send and poll data
        fa_send = fa_last_send_time + fa_send_interval_time <= time.time()
        fa_expired = fa_time + fa_expire_time <= time.time()
        # Sniffer of the PC<->Rig
        time.sleep(0.01)
        if sera.inWaiting() > 0:
            data_a = sera.read_until(b';')
            data_a = data_a.decode('utf-8')
            # Comprobación de datos válidos
            is_if = bool(re.search(r'IF\d{11}.*;', data_a))
            is_fa = bool(re.search(r'FA\d{11}.*;', data_a))
            if is_if or is_fa:
                qrg_data = re.findall(r'(\d{11})|\d{11}.*', data_a)[0]
                amp_data = "FA%s;" % qrg_data
                fa_time = time.time()
                msg = "Sniffed DATA"
                if MQ_DATA:
                    client.publish("eb1tr/k3/raw_if", data_a)

        # Send stored data or poll, if is necessary
        if fa_send:
            # If
            if fa_expired:
                sera.write(b'IF;')
                data_a = sera.read_until(b';')
                data_a = data_a.decode('utf-8')
                if bool(re.search(r'IF\d{11}.*;', data_a)):
                    amp_data = "FA%s;" % re.findall(r'(\d{11})', data_a)[0]
                    fa_time = time.time()
                    msg = "Polled DATA "

            serb.write(amp_data.encode('utf-8'))
            fa_last_send_time = time.time()
            if MQ_DATA:
                client.publish(f'{MQ_TOPIC}/raw_if', amp_data)

            print("%s | %s | %s" % (msg, int(fa_last_send_time), amp_data))
    except Exception as e:
        print(e)
