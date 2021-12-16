from bitstring import BitArray
from datetime import datetime
import paho.mqtt.client as mqtt
import libscrc
import serial
import time


def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("actuador")


client = mqtt.Client()
client.on_connect = on_connect
client.connect("monitoreo.ga", 1883, 60)


# definir puerto serial
ser = serial.Serial('COM3', timeout=0.1)


#################### Definicion tramas ###############################
LEER_6_SALIDAS = bytes.fromhex("7E 00 16 10 01 00 13 A2 00 40 A8 41 C4 FF FE 00 00 01 01 05 00 00 06 BC C4 C2")
LEER_8_ENTRADAS = bytes.fromhex("7E 00 16 10 01 00 13 A2 00 40 A8 41 C4 FF FE 00 00 01 02 04 00 00 08 78 FC CC")
LEER_4_ANALOGAS = bytes.fromhex("7E 00 16 10 01 00 13 A2 00 40 A8 41 C4 FF FE 00 00 01 03 14 56 00 04 A1 E9 53")
######################################################################


#################### Definicion Funciones ############################

def compare_bytes(bytes_array, start_index: int, length: int, to_compare: bytes):
    end_index = start_index + length
    sliced_array = bytes_array[start_index: end_index]
    return sliced_array == to_compare


def crc_modbus(modbus_frame: bytes):
    crc = libscrc.modbus(modbus_frame)
    crc16 = crc.to_bytes(2, byteorder='little')
    return crc16


def check_crc(modbus_frame: bytes):
    frame_to_calc = modbus_frame[:-2]
    crc_calculated = crc_modbus(frame_to_calc)
    crc_readed = modbus_frame[-2:]
    return crc_calculated == crc_readed


def read_modbus_response(modbus_frame):
    
    if check_crc(modbus_frame):

        unidad = modbus_frame[0].to_bytes(1, byteorder='big')
        command = modbus_frame[1].to_bytes(1, byteorder='big')
        bytes_number = modbus_frame[2]
        data = modbus_frame[3:3+bytes_number]

        return command, data

    else:
        return None


def get_volts(reading):
    volts = reading * 10 / 2000
    return volts


def interpretar_modbus_response(comando, data):

    if compare_bytes(comando, 0, 1, b'\x01'):
        # leer salidas        
        bits = BitArray(data)
        bits = bits.bin
        return 'digital_mask', bits

    elif compare_bytes(comando, 0, 1, b'\x02'):
        # leer entradas
        bits = BitArray(data)
        bits = bits.bin
        return 'digital_mask', bits

    elif compare_bytes(comando, 0, 1, b'\x03'):
        # leer analogas
        numero_entradas = int(len(data)/2)
        entradas = []
        for i in range(numero_entradas):
            start_index = i*2
            end_index = start_index + 2
            actual_input_data = data[start_index:end_index]
            actual_input_data_int = actual_input_data[0]*256 + actual_input_data[1]
            entradas.append(get_volts(actual_input_data_int))

        return 'analog', entradas

    return None


def xbee_start(bytes_array):
    return compare_bytes(bytes_array, 0, 1, b'\x7E')


def xbee_get_length(length_bytes_array):
    LENGTH = 2
    if len(length_bytes_array) == LENGTH:
        return length_bytes_array[0]*256 + length_bytes_array[1]

    return None


def slice_response(response):

    if xbee_start(response):
        
        first_response_length = xbee_get_length(response[1:3])
        second_response_start_index = 3 + first_response_length + 1
        first_response = response[: second_response_start_index]

        second_response = response[second_response_start_index:]
        second_response_length = xbee_get_length(second_response[1:3])

        total_calc_length = 3 + first_response_length + 1 + 3 + second_response_length + 1
        
        if xbee_start(second_response) and total_calc_length == len(response):

            return first_response, second_response

    return None


def complete_reading(response):
    # Se asume que la modbus empieza en el byte 15 de la segunda trama
    first_response, second_response = slice_response(response)
    modbus = second_response[15:-1]
    comando, data = read_modbus_response(modbus)
    tipo, interpretada = interpretar_modbus_response(comando, data)
    return tipo, interpretada


######################################################################



while True:

    time.sleep(2)

    try:

        # Lectura Analogas
        ser.reset_input_buffer()
        ser.write(LEER_4_ANALOGAS)
        response = ser.readline()
        tipo, interpretada = complete_reading(response)
        now = datetime.now()
        now_string = now.strftime("%Y-%m-%dT%H:%M:%S")
        client.publish('monitoreo/grafica',
                       payload = '{"chart":"chart1","data":["' + now_string + '",' + str(interpretada[0]) + '] }',
                       qos = 0
        )

        client.publish('monitoreo/grafica',
                       payload = '{"chart":"chart2","data":["' + now_string + '",' + str(interpretada[1]) + '] }',
                       qos = 0
        )



        # Lectura entradas
       

        # client.publish('monitoreo/grafica',
        #                payload=message,
        #                qos=0
        # )

        # client.publish('monitoreo/grafica',
        #                payload=message,
        #                qos=0
        # )

        # client.publish('monitoreo/grafica',
        #                payload=message,
        #                qos=0
        # )

        
        

    except:
        continue



# def on_message(client, userdata, msg):
#     print(msg.topic+" "+str(msg.payload))
#     # Implementar codigo para actuador

# client.on_message = on_message

# client.loop_forever()