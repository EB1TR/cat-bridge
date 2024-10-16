# Librería estándar ----------------------------------------------------------------------------------------------------
#
import time
import re
import json
import sys
import datetime
# ----------------------------------------------------------------------------------------------------------------------


# Librerías PIP --------------------------------------------------------------------------------------------------------
#
import serial
import paho.mqtt.client as mqtt
# ----------------------------------------------------------------------------------------------------------------------


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

print(f'Iniciando CAT-Bridge V20241014 by EB1TR')

try:
    sera = serial.Serial(port=RX_PORT)
    print(f'Configurando puerto TX/RX del TRX: {RX_PORT}')
    sera.baudrate = RX_BAUD
    print(f'Configurando velocidad TX/RX del TRX: {RX_BAUD}')
    sera.bytesize = serial.EIGHTBITS
    sera.parity = serial.PARITY_NONE
    sera.stopbits = serial.STOPBITS_TWO
    sera.setRTS = False
    sera.setDTR = False
    sera.rts = False
    sera.dtr = False
    sera.rtscts = False
    sera.dsrdtr = False
    sera.timeout = 1
    serb = serial.Serial(port=TX_PORT)
    print(f'Configurando puerto TX del PA: {TX_PORT}')
    serb.baudrate = TX_BAUD
    print(f'Configurando velocidad TX del PA: {TX_BAUD}')
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
        print(f'Broker MQTT: Activado')
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect_async(MQ_HOST, port=MQ_PORT, keepalive=60, bind_address="")
        print(f'Broker MQTT (host): {MQ_HOST}')
        print(f'Broker MQTT (puerto): {MQ_PORT}')
        print(f'Broker MQTT (topic): {MQ_TOPIC}')
        client.loop_start()
        time.sleep(0.3)
        mqtt_nro = 1
        while not client.is_connected():
            print(f'Broker MQTT (estado): Desconectado (intento: {mqtt_nro})')
            mqtt_nro += 1
            if mqtt_nro > 5:
                print("No es posible abrir la conexión MQTT")
                input("Presione ENTER para salir...")
                sys.exit(0)
        print(f'Broker MQTT (estado): Conectado')
    except Exception as e:
        print("No es posible abrir la conexión MQTT")
        print(e)
        input("Presione ENTER para salir...")
        sys.exit(0)
else:
    print(f'Broker MQTT - Host: Desactivado')

msg = ""
data_a = ""
amp_data = ""
fa_time = 0
fa_last_send_time = time.time()
fa_send_interval_time = TX_TIME
fa_expire_time = EX_DATA

print(f'Intervalo entre envíos: {int(fa_send_interval_time*1000)} milisegundos')
print(f'Tiempo de expiración de frecuencia: {int(fa_expire_time*1000)} milisegundos')
time.sleep(3)


def to_ts(ts_epoch):
    try:
        ts = datetime.datetime.fromtimestamp(ts_epoch).strftime('%H:%M:%S')
        return ts
    except:
        return 'no time'


while True:
    try:
        # Calculamos si es necesario volver a enviar un dato o es necesario actualizarlo previamente
        fa_send = fa_last_send_time + fa_send_interval_time <= time.time()
        fa_expired = fa_time + fa_expire_time <= time.time()
        # Sniffer of the PC<->Rig
        time.sleep(0.01)
        # Recepción de nuevos paquetes
        if sera.inWaiting() > 2:
            data_a = sera.read_until(b';')
            data_a = data_a.decode('utf-8')
            # Comprobación de datos válidos
            is_if = bool(re.search(r'IF\d{11}.*;', data_a))
            is_fa = bool(re.search(r'FA\d{11}.*;', data_a))
            if is_if or is_fa:
                qrg_data = re.findall(r'(\d{11})|\d{11}.*', data_a)[0]
                amp_data = "FA%s;" % qrg_data
                fa_time = time.time()
                msg = "Sniffed"
                print("RXA | Sniffing | %s | %s" % (to_ts(fa_last_send_time), amp_data))
                if MQ_DATA:
                    client.publish(f'{MQ_TOPIC}/raw_if', amp_data)

        # Enviamos datos que si es necesario enviar
        if fa_send:
            # Si los datos existentes han caducado se solicitan nuevos
            if fa_expired:
                sera.write(b'FA;')
                data_a = sera.read_until(b';')
                data_a = data_a.decode('utf-8')
                # Comprobación de datos válidos para no procesar paquetes no solicitados
                if bool(re.search(r'FA\d{11}.*;', data_a)):
                    amp_data = "FA%s;" % re.findall(r'(\d{11})', data_a)[0]
                    fa_time = time.time()
                    msg = "Polled "
                    print("-" * 42)
                    print("TXA | Polling  | %s | %s" % (to_ts(fa_last_send_time), amp_data))
                    print("-" * 42)
            # Enviamos los datos al puerto serie
            if bool(re.search(r'FA\d{11}.*;', amp_data)) and time.time() < fa_time + 60:
                serb.write(amp_data.encode('utf-8'))
                if MQ_DATA:
                    client.publish(f'{MQ_TOPIC}/raw_if', amp_data)
                print("TXB | %s  | %s | %s" % (msg, to_ts(fa_last_send_time), amp_data))
                fa_last_send_time = time.time()
            # Publicamos también en MQTT

    except Exception as e:
        print(e)
