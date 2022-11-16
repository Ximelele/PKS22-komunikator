import os
import socket
from time import sleep


# syn 1
# ack 2
# error 3
# success 4
# text 5
# file 6
# switch 7
# end 8
# last_packet 9

class Server:
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def __init__(self, serverAddressPort):
        self.serverAddressPort = serverAddressPort


class Client:
    my_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

    def __init__(self, serverAddressPort):
        self.serverAddressPort = serverAddressPort


# https://stackoverflow.com/questions/35205702/calculating-crc16-in-python
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


def build_header(flag, packet_number, data, file=False,error = False):
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
    if error:
        crc+=1
    my_header += crc.to_bytes(2, byteorder='little')
    return my_header


# server = None
# client = None
ZACIATOK_KOMUNIKACIE = False
MAX_DATA_SIZE = 1468
HLAVICKA = 4


def choose_fragment_size():
    print("Vyber velkost fragmentu 1-1468")
    size = int(input())
    global MAX_DATA_SIZE
    MAX_DATA_SIZE = 1468
    if size < 0:
        MAX_DATA_SIZE = 1
    elif size <= MAX_DATA_SIZE:
        MAX_DATA_SIZE = size

def simulate_error(max_errors):
    print(f'Zadaj pocet chyb 0-{max_errors}')
    errors = int(input())

    return errors


def server_loop(m_server):
    server = m_server
    server.my_socket.bind((server.serverAddressPort[0], server.serverAddressPort[1]))
    print("Bububu server")
    global ZACIATOK_KOMUNIKACIE
    while True:
        message, message_add = server.my_socket.recvfrom(1500)
        if not ZACIATOK_KOMUNIKACIE:
            my_header = build_header(2, 0, "")
            server.my_socket.sendto(my_header, message_add)
            ZACIATOK_KOMUNIKACIE = True
            continue

        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        flag = int(chr(message[0]))
        packet_num = int(chr(message[1]))
        finalMsg = message[2:]

        if flag == 5:
            receive_text(finalMsg, server, message_add,crc)

        if flag == 6:
            receive_file(finalMsg, server, message_add)
        if flag == 7:
            my_header = build_header(2, 0, "")
            server.my_socket.sendto(my_header, message_add)
            sleep(1)
            client_loop(server)


# todo pridat crc do volania funkcie kvoli prvemu fragmentu
def receive_text(textMsg, server, message_add,crc):
    textArray = []
    errors = 0
    total_size = len(textMsg)+HLAVICKA
    number_of_fragments = 1

    if crc16(textMsg) != crc:
        my_header = build_header(3, 0, "")
        server.my_socket.sendto(my_header, message_add)
        errors += 1
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        total_size += len(message[2:]) + HLAVICKA
        if(crc16(message[2:])==crc):
            textMsg=message[2:]


    my_header = build_header(4, 0, "")
    server.my_socket.sendto(my_header, message_add)

    textArray.append(textMsg.decode())
    while True:
        message, message_add = server.my_socket.recvfrom(1500)

        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]

        flag = int(chr(message[0]))
        if flag == 9:
            break
        check_crc = crc16(message[2:])

        if check_crc != crc:
            my_header = build_header(3, 0, "")
            server.my_socket.sendto(my_header, message_add)
            errors += 1
            message, message_add = server.my_socket.recvfrom(1500)
            crc = message[-2:]
            crc = int.from_bytes(crc, 'little')
            message = message[0:-2]
            total_size += len(message[2:]) + HLAVICKA
            check_crc = crc16(message[2:])
            if check_crc == crc:
                my_header = build_header(4, 0, "")
                server.my_socket.sendto(my_header, message_add)
        packet_num = int(chr(message[1]))
        total_size += len(message[2:])+HLAVICKA
        textArray.append(message[2:].decode())
        my_header = build_header(4, 0, "")
        server.my_socket.sendto(my_header, message_add)
        number_of_fragments += 1

    my_header = build_header(9, 0, "")
    server.my_socket.sendto(my_header, message_add)
    final_text = "".join(textArray)
    print(final_text)
    print(f'Pocet prijatych fragmentov {number_of_fragments+errors}')
    print(f'Celkova prijata velkost fragmentov {total_size}')


def receive_file(file, server, message_add):
    my_header = build_header(4, 0, "")
    server.my_socket.sendto(my_header, message_add)
    file_array = {}
    file_name = file.decode()
    number_of_fragments = 1
    total_size = len(file_name)+HLAVICKA
    while True:
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        flag = int(chr(message[0]))
        if flag == 9:
            break
        my_header = build_header(4, 0, "")
        server.my_socket.sendto(my_header, message_add)
        message = message[0:-2]
        partial_file = message[2:]
        total_size += len(partial_file)+HLAVICKA
        file_array[str(number_of_fragments)] = partial_file
        number_of_fragments += 1

    my_header = build_header(9, 0, "")
    server.my_socket.sendto(my_header, message_add)

    print(f'Pocet prijatych fragmentov {number_of_fragments}')
    print(f'Celkova prijata velkost fragmentov {total_size}')
    fw = open("picovina.txt", 'wb+')

    for i in file_array.values():
        fw.write(i)




def client_menu():
    menu = "t - textova sprava\n"
    menu += "f - poslat subor\n"
    menu += "s - zmenit strany\n"
    menu += "e - ukonci\n"
    print(menu)

    return str(input())


# todo prerobit posielanie suboru
def send_file(file, client):
    f = open(file, 'rb+')
    data = f.read()

    fileArray = []
    fragments_to_send = 1
    total_size = len(file)
    my_header = build_header(6, 0, file)
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)
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

    for index, value in enumerate(fileArray,start=1):
        total_size += len(value)
        my_header = build_header(6, index % 9, value, True)
        client.my_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.my_socket.recvfrom(1500)
        fragments_to_send = index
    print(f'Pocet odoslanych fragmentov {fragments_to_send+1}')
    print(f'Celkova odoslana velkost fragmentov {total_size}')
    my_header = build_header(9, (fragments_to_send + 1) % 9, "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)


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
        textArray.append(textMsg)
    error =simulate_error(len(textArray))
    with_error = 0
    for index, value in enumerate(textArray):
        if with_error >= error:
            my_header = build_header(5, index % 9, value)
        else:
            my_header = build_header(5, index % 9, value,False,True)
            with_error+=1
        client.my_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.my_socket.recvfrom(1500)
        flag = int(chr(message[0]))
        if flag == 3:
            my_header = build_header(5, index % 9, value)
            client.my_socket.sendto(my_header, client.serverAddressPort)
            message, message_add = client.my_socket.recvfrom(1500)
        fragments_to_send = index

    my_header = build_header(9, (fragments_to_send + 1) % 9, "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)


def client_loop(m_client):
    global ZACIATOK_KOMUNIKACIE
    client = m_client

    while True:

        if not ZACIATOK_KOMUNIKACIE:
            my_header = build_header(1, 0, "")
            client.my_socket.sendto(my_header, client.serverAddressPort)
            message, message_add = client.my_socket.recvfrom(1500)
            ZACIATOK_KOMUNIKACIE = True
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

        elif choice == "s":
            my_header = build_header(7, 0, "")
            client.my_socket.sendto(my_header, client.serverAddressPort)
            message, message_add = client.my_socket.recvfrom(1500)
            sleep(1)
            server_loop(client)


opt = str(input())

if opt == "s":
    server = Server(("127.0.0.1", 6000))
    server_loop(server)

if opt == "c":
    client = Client(("127.0.0.1", 6000))
    client_loop(client)
