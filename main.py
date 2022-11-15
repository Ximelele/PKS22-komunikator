import os
import socket
import struct
import zlib
import sys
from time import sleep


class Server:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def __init__(self, ip_addr, port):
        self.ip_addr = ip_addr
        self.port = port


class Client:
    client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    def __init__(self, serverAddressPort):
        self.serverAddressPort = serverAddressPort


# https://stackoverflow.com/questions/67115292/convert-crc16-ccitt-code-from-c-to-python
def crc16(data: bytes):
    xor_in = 0x0000  # initial value
    xor_out = 0x0000  # final XOR value
    poly = 0x8005  # generator polinom (normal form)

    reg = xor_in
    for octet in data:
        # reflect in
        for i in range(8):
            topbit = reg & 0x8000
            if octet & (0x80 >> i):
                topbit ^= 0x8000
            reg <<= 1
            if topbit:
                reg ^= poly
        reg &= 0xFFFF
        # reflect out
    return reg ^ xor_out


def build_header(flag, packet_number, data, file=False):
    if file:
        crc = crc16(data)
    else:
        crc = crc16(data.encode())
    my_header = bytes()
    my_header += str(flag).encode()
    my_header += str(packet_number).encode()
    if file:
        my_header += data
    else:
        my_header += data.encode()
    my_header += crc.to_bytes(2, byteorder='little')
    return my_header


# syn 1
# ack 2
# error 3
# text 4
# file 5
# switch 6
server = None
SYN = False

MAX_DATA_SIZE = 1468


def choose_fragment_size():
    print("Vyber velkost fragmentu 1-1468")
    size = int(input())
    global MAX_DATA_SIZE
    MAX_DATA_SIZE = 1468
    if size < 0:
        MAX_DATA_SIZE = 1
    elif size <= MAX_DATA_SIZE:
        MAX_DATA_SIZE = size


def server_loop():
    global server
    server = Server("127.0.0.1", 6000)
    server.server_socket.bind((server.ip_addr, server.port))
    print("Bububu server")
    global SYN
    file_name = ""
    while True:
        message, message_add = server.server_socket.recvfrom(1500)
        if not SYN:
            my_header = build_header(2, 0, "")
            server.server_socket.sendto(my_header, message_add)
            SYN = True
            continue

        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        flag = int(chr(message[0]))
        packet_num = int(chr(message[1]))
        finalMsg = message[2:]
        print(crc)
        print(crc16(finalMsg))

        if flag == 5:
            receive_text(finalMsg, server, message_add)

        if flag == 6:
            receive_file(finalMsg, server, message_add)


# todo spravit nemiesto listu dict kvoli sortovaniu podla packet num
# todo pridat crc do volania funkcie kvoli prvemu fragmentu
def receive_text(textMsg, server, message_add):
    textArray = []
    textArray.append(textMsg.decode())
    my_header = build_header(4, 0, "")
    server.server_socket.sendto(my_header, message_add)
    number_of_fragments = 1
    total_size = len(textMsg)
    while True:
        message, message_add = server.server_socket.recvfrom(1500)

        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        print(crc)
        print(crc16(message[2:]))

        flag = int(chr(message[0]))
        if flag == 9:
            break

        packet_num = int(chr(message[1]))
        total_size += len(message[2:])
        textArray.append(message[2:].decode())
        my_header = build_header(4, 0, "")
        server.server_socket.sendto(my_header, message_add)
        number_of_fragments += 1

    my_header = build_header(9, 0, "")
    server.server_socket.sendto(my_header, message_add)
    final_text = "".join(textArray)
    print(final_text)
    print(f'Pocet prijatych fragmentov {number_of_fragments}')
    print(f'Celkova prijata velkost fragmentov {total_size}')


def receive_file(file, server, message_add):
    my_header = build_header(4, 0, "")
    server.server_socket.sendto(my_header, message_add)
    file_array = {}
    file_name = file.decode()
    number_of_fragments = 0
    dlzkapicoviny = 0
    while True:
        message, message_add = server.server_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        flag = int(chr(message[0]))
        number_of_fragments += 1
        if flag == 9:
            break
        my_header = build_header(4, 0, "")
        server.server_socket.sendto(my_header, message_add)
        message = message[0:-2]
        partial_file = message[2:]
        dlzkapicoviny += len(partial_file[:-2])
        file_array[str(number_of_fragments)] = partial_file.decode()
        # if crc_check != crc:
        #     print("Pici tam")
        #     break


    my_header = build_header(4, 0, "")
    server.server_socket.sendto(my_header, message_add)

    fw = open("pici.txt", 'wb+')

    print(dlzkapicoviny)
    for i in file_array.values():
        fw.write(i.encode())

    print(fw.read())



client = None


def client_menu():
    menu = "t - textova sprava\n"
    menu += "f - poslat subor\n"
    menu += "s - zmenit strany\n"
    menu += "e - zmenit strany\n"
    print(menu)

    return str(input())


# todo prerobit posielanie suboru
def send_file(file, client):

    f = open(file, 'rb+')
    data = f.read()

    print(len(data))
    fileArray = []
    fragments_to_send = 1
    my_header = build_header(6, 0, file)
    client.client_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.client_socket.recvfrom(1500)
    global MAX_DATA_SIZE

    if len(data) > MAX_DATA_SIZE:
        while True:
            if len(data) > MAX_DATA_SIZE:
                fileArray.append(data[:MAX_DATA_SIZE])
                data = data[MAX_DATA_SIZE:]
            else:
                fileArray.append(data[:len(data)])
                break
    else:
        fileArray.append(data)

    for index, value in enumerate(fileArray, start=1):
        my_header = build_header(6, index % 9, value,True)
        client.client_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.client_socket.recvfrom(1500)
        fragments_to_send = index

    my_header = build_header(9, (fragments_to_send + 1) % 9, "")
    client.client_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.client_socket.recvfrom(1500)


def send_text(textMsg, client):
    textArray = []
    fragments_to_send = 0
    text_len = len(textMsg)
    global MAX_DATA_SIZE
    if text_len > MAX_DATA_SIZE:
        while True:
            if len(textMsg) > MAX_DATA_SIZE:
                textArray.append(textMsg[:MAX_DATA_SIZE])
                textMsg = textMsg[MAX_DATA_SIZE:]
            else:
                textArray.append(textMsg[:len(textMsg)])
                break
    else:
        textArray = [textMsg]

    for index, value in enumerate(textArray):
        my_header = build_header(5, index % 9, value)
        client.client_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.client_socket.recvfrom(1500)
        fragments_to_send = index

    my_header = build_header(9, (fragments_to_send + 1) % 9, "")
    client.client_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.client_socket.recvfrom(1500)


def client_loop():
    global client
    client = Client(("127.0.0.1", 6000))
    global SYN
    while True:

        if not SYN:
            my_header = build_header(1, 0, "")
            client.client_socket.sendto(my_header, client.serverAddressPort)
            message, message_add = client.client_socket.recvfrom(1500)
            SYN = True
            continue
        choice = client_menu()

        if choice == "t":
            print("Zadaj spravu")
            textMsg = str(input())
            choose_fragment_size()
            send_text(textMsg, client)


        elif choice == "f":
            print("Zadaj subor")
            file = str("testik.txt")
            file_name = os.path.abspath(file)
            print(file_name)
            choose_fragment_size()
            send_file(file, client)


opt = str(input())

if opt == "s":
    server_loop()

if opt == "c":
    client_loop()
