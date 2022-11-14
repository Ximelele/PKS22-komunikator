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

#https://stackoverflow.com/questions/67115292/convert-crc16-ccitt-code-from-c-to-python
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


def build_header(flag, packet_number, data):
    crc = crc16(data.encode())
    my_header = bytes()
    my_header += str(flag).encode()
    my_header += str(packet_number).encode()
    my_header += data.encode()
    my_header += crc.to_bytes(2, byteorder='little')
    return my_header

#syn 1
#ack 2
#error 3
#text 4
#file 5
#switch 6

def server_loop():
    server = Server("127.0.0.1", 6000)
    server.server_socket.bind((server.ip_addr, server.port))
    print("Bububu server")
    SYN = False
    while True:
        message, message_add = server.server_socket.recvfrom(2048)
        if not SYN:
            my_header = build_header(2, 0, "")
            server.server_socket.sendto(my_header,message_add)

        crc = message[-2:]
        crc=int.from_bytes(crc,'little')
        message = message[0:-2].decode()
        flag = message[0]
        packet_num = message[1]
        finalMsg = message[2:]
        print(f'flag {flag} cislo {packet_num} message {finalMsg}')
        sleep(10)


def client_loop():
    client = Client(("127.0.0.1", 6000))
    SYN = False
    while True:

        if not SYN:
            my_header = build_header(1, 0, "")
            client.client_socket.sendto(my_header, client.serverAddressPort)
            SYN = True
            message, message_add = client.client_socket.recvfrom(2048)
            message=message.decode()
            print(message[0])





opt = str(input())

if opt == "s":
    server_loop()

if opt == "c":
    client_loop()
