import os
import socket
from time import sleep
import threading


# Keep alive 0
# syn 1
# ack 2
# error 3
# success 4 #maybe pouzivat 2ku
# text 5
# file 6
# switch 7
# end 8
# last fragment 9

class Server:

    def __init__(self, serverAddressPort):
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverAddressPort = serverAddressPort


class Client:
    def __init__(self, serverAddressPort):
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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


def build_header(flag, packet_number, data, file=False, error=False):
    if file:
        crc = crc16(data)
    else:
        crc = crc16(data.encode())
    my_header = bytes()
    my_header += str(flag).encode()
    my_header += packet_number.to_bytes(3, byteorder='little')
    if file:
        my_header += data
    else:
        my_header += data.encode()
    if error:
        crc += 1
    my_header += crc.to_bytes(2, byteorder='little')
    return my_header


ZACIATOK_KOMUNIKACIE = False
MAX_DATA_SIZE = 1466
HLAVICKA = 6
KEEP_ALIVE = False


def keep_alive(client, serverAddressPort):
    global KEEP_ALIVE
    sleep(0.1)
    while True:
        my_header = build_header(0, 0, "")

        client.sendto(my_header, serverAddressPort)
        try:
            client.settimeout(0.1)
            message, message_add = client.recvfrom(1500)
        except (ConnectionResetError, socket.timeout):

            print(f'Server je nedostupny')
        else:
            print(f'Server je dostupny')

        for i in range(10):
            sleep(0.5)
            if not KEEP_ALIVE:
                return


def choose_fragment_size():
    global MAX_DATA_SIZE
    print(f"Vyber velkost fragmentu 1-{1466}")
    size = int(input())
    # MAX_DATA_SIZE = 1466
    if size < 0:
        MAX_DATA_SIZE = 1
    elif size > MAX_DATA_SIZE:
        MAX_DATA_SIZE = 1466
    else:
        MAX_DATA_SIZE = size


def simulate_error(max_errors):
    print(f'Zadaj pocet chyb 0-{max_errors}')
    errors = int(input())

    return errors


def server_loop(server, serverAdd):
    print(serverAdd)
    print("Bububu server")

    try:
        server.my_socket.bind(serverAdd)
        message, message_add = server.my_socket.recvfrom(1500)
        my_header = build_header(2, 0, "")
        server.my_socket.sendto(my_header, message_add)
    except socket.timeout:
        server.my_socket.close()
    server.my_socket.settimeout(60)
    global SWAPED
    global ZACIATOK_KOMUNIKACIE
    global KEEP_ALIVE
    file_path = str(input("Zadaj kde chces ukladat subory"))

    try:
        while True:
            if SWAPED:
                sleep(1)
                SWAPED = False
            message, message_add = server.my_socket.recvfrom(1500)

            crc = message[-2:]
            crc = int.from_bytes(crc, 'little')
            message = message[0:-2]
            flag = int(chr(message[0]))
            packet_num = message[1:3]
            packet_num = int.from_bytes(packet_num, 'little')
            finalMsg = message[4:]
            if flag == 0:
                my_header = build_header(2, packet_num, "")
                server.my_socket.sendto(my_header, message_add)

            elif flag == 5:
                receive_text(finalMsg, server, message_add, crc,packet_num)

            elif flag == 6:
                receive_file(finalMsg, server, message_add,file_path,packet_num)
            elif flag == 7:
                SWAPED = True
                KEEP_ALIVE = False
                my_header = build_header(2, 0, "")
                server.my_socket.sendto(my_header, message_add)
                server.my_socket.close()
                sleep(5)
                client_loop(Client(serverAdd), serverAdd)
            elif flag == 8:
                my_header = build_header(2, 0, "")
                server.my_socket.sendto(my_header, message_add)
                print(f'Klient {message_add} sa odpojil')


    except socket.timeout:
        print("Koniec bububu")
        server.my_socket.close()
        return


def receive_text(textMsg, server, message_add, crc,packet_num):
    textArray = []
    textDict = {}
    errors = 0
    total_size = len(textMsg) + HLAVICKA
    number_of_fragments = 1
    check_crc = crc16(textMsg)
    if check_crc != crc:
        my_header = build_header(3, packet_num, "")
        server.my_socket.sendto(my_header, message_add)
        errors += 1
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        packet_num = message[1:3]
        packet_num = int.from_bytes(packet_num, 'little')
        print(f'packet number {packet_num} error True')
        total_size += len(message[4:]) + HLAVICKA
        if (crc16(message[4:]) == crc):
            textMsg = message[4:]
            print(f'packet number {packet_num} error False')
            my_header = build_header(4, packet_num, "")
            server.my_socket.sendto(my_header, message_add)
    else:
        my_header = build_header(4, packet_num, "")
        server.my_socket.sendto(my_header, message_add)

    textArray.append(textMsg.decode())
    textDict[packet_num]=textMsg.decode()
    last_packet=0
    while True:
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        message = message[0:-2]
        packet_num = message[1:3]
        packet_num = int.from_bytes(packet_num, 'little')

        flag = int(chr(message[0]))
        if flag == 9:
            last_packet = packet_num
            number_of_fragments += 1
            total_size += HLAVICKA
            break
        check_crc = crc16(message[4:])

        if check_crc != crc:
            my_header = build_header(3, packet_num, "")

            server.my_socket.sendto(my_header, message_add)
            errors += 1
            print(f'packet number {packet_num} error True')
            total_size += len(message[4:]) + HLAVICKA
            continue
        else:
            print(f'packet number {packet_num} error False')

        total_size += len(message[4:]) + HLAVICKA
        textArray.append(message[4:].decode())
        textDict[packet_num] = message[4:].decode()
        my_header = build_header(4, packet_num, "")
        server.my_socket.sendto(my_header, message_add)
        number_of_fragments += 1

    my_header = build_header(9, last_packet, "")
    server.my_socket.sendto(my_header, message_add)
    final_text = "".join(textArray)
    print(textDict)
    print(final_text)
    print(f'Pocet prijatych fragmentov {number_of_fragments + errors}')
    print(f'Celkova prijata velkost fragmentov {total_size}')


# posielanie s chybami
def receive_file(file, server, message_add,file_path,packet_num):
    my_header = build_header(4, 0, "")
    server.my_socket.sendto(my_header, message_add)
    file_array = {}
    file_name = file.decode()
    file_name = file_name.rsplit('\\')[-1]
    print(file_name)
    number_of_fragments = 1
    total_size = len(file_name) + HLAVICKA
    errors = 0
    last_packet = 0
    while True:
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        flag = int(chr(message[0]))
        packet_num = message[1:3]
        packet_num = int.from_bytes(packet_num, 'little')
        if flag == 9:
            last_packet = packet_num
            number_of_fragments += 1
            total_size += HLAVICKA
            break
        check_crc = crc16(message[4:-2])

        if check_crc != crc:
            my_header = build_header(3, packet_num, "")
            server.my_socket.sendto(my_header, message_add)
            sleep(0.1)
            errors += 1
            print(f'packet number {packet_num} error True')
            total_size += len(message[4:-2]) + HLAVICKA
            continue
        else:
            print(f'packet number {packet_num} error False')

        my_header = build_header(4, packet_num, "")
        server.my_socket.sendto(my_header, message_add)
        partial_file = message[4:-2]
        total_size += len(partial_file) + HLAVICKA
        file_array[str(number_of_fragments)] = partial_file
        number_of_fragments += 1

    my_header = build_header(9, last_packet, "")
    server.my_socket.sendto(my_header, message_add)

    print(f'Pocet prijatych fragmentov {number_of_fragments + errors}')
    print(f'Celkova prijata velkost fragmentov {total_size}')

    final_name = file_path+file_name
    fw = open(final_name, 'wb+')

    for i in file_array.values():
        fw.write(i)
    print(f'Subor bol ulozeny v {os.path.abspath(file_name)}')


def client_menu():
    menu = "t - textova sprava\n"
    menu += "f - poslat subor\n"
    menu += "s - zmenit strany\n"
    menu += "e - ukonci\n"
    print(menu)

    return str(input())


def send_file(file, client):
    f = open(file, 'rb+')
    data = f.read()
    max_error = 0
    fileArray = []
    fragments_to_send = 1
    my_header = build_header(6, 0, file)
    # na nazov suboru sa fragmentacia nestahuje
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)
    global MAX_DATA_SIZE

    if len(data) > MAX_DATA_SIZE:
        while True:
            if len(data) > MAX_DATA_SIZE:
                max_error += 1
                fileArray.append(data[:MAX_DATA_SIZE])
                data = data[MAX_DATA_SIZE:]
            else:
                max_error += 1
                fileArray.append(data[:len(data)])
                break
    else:
        max_error += 1
        fileArray.append(data)

    error = simulate_error(max_error)
    with_error = 0
    try:
        for index, value in enumerate(fileArray, start=1):
            if with_error >= error:
                my_header = build_header(6, index, value, True)
            else:
                my_header = build_header(6, index, value, True, True)
                with_error += 1
            client.my_socket.sendto(my_header, client.serverAddressPort)
            sleep(0.1)
            message, message_add = client.my_socket.recvfrom(1500)
            flag = int(chr(message[0]))
            if flag == 3:
                my_header = build_header(6, index, value, True)
                client.my_socket.sendto(my_header, client.serverAddressPort)
                sleep(0.1)
                message, message_add = client.my_socket.recvfrom(1500)
            fragments_to_send = index
    except (ConnectionResetError, socket.timeout):
        print("Nedostupny server")
        return

    my_header = build_header(9, (fragments_to_send + 1), "")
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


    error = simulate_error(len(textArray))



    try:
        for index, value in enumerate(textArray):
            my_header = build_header(5, index, value)
            if error > 0:
                error -= 1
                my_header = build_header(5, index, value, False, True)

            client.my_socket.sendto(my_header, client.serverAddressPort)
            # sleep(0.1)

            client.my_socket.settimeout(2)
            message, message_add = client.my_socket.recvfrom(1500)


            flag = int(chr(message[0]))
            if flag == 3:
                my_header = build_header(5, index, value)
                client.my_socket.sendto(my_header, client.serverAddressPort)
                message, message_add = client.my_socket.recvfrom(1500)
            fragments_to_send = index
    except (ConnectionResetError, socket.timeout):
        print("Nedostupny server")
        return

    my_header = build_header(9, (fragments_to_send + 1), "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)


SWAPED = False


def client_loop(client, clientAdd):
    global KEEP_ALIVE
    global ZACIATOK_KOMUNIKACIE
    global SWAPED
    KEEP_ALIVE = False
    t1 = None
    client.my_socket.settimeout(60)
    try:
        # client.my_socket.bind(clientAdd)
        my_header = build_header(1, 0, "")
        client.my_socket.sendto(my_header, clientAdd)
        message, message_add = client.my_socket.recvfrom(1500)
    except socket.timeout:
        client.my_socket.close()

    while True:

        if SWAPED:
            sleep(1)
            SWAPED = False

        if not KEEP_ALIVE:
            t1 = threading.Thread(target=keep_alive, args=(client.my_socket, clientAdd))
            t1.daemon = True
            t1.start()
            KEEP_ALIVE = True
            continue

        choice = client_menu()
        try:
            if choice == "t":
                KEEP_ALIVE = False
                t1.join()
                print("Zadaj spravu")
                textMsg = str(input())
                choose_fragment_size()
                send_text(textMsg, client)

            #C:\Users\druzb\Desktop\
            elif choice == "f":
                KEEP_ALIVE = False
                t1.join()
                print("Zadaj subor")
                file = str(input("D:\Python projects\pks_komunikator\Mathematica_hnoj.zip"))
                file_name = os.path.abspath(file)
                print(file_name)
                choose_fragment_size()
                send_file(file, client)
            elif choice == "e":
                KEEP_ALIVE = False
                t1.join()
                my_header = build_header(8, 0, "")
                client.my_socket.sendto(my_header, message_add)
                sleep(2)
                message, message_add = client.my_socket.recvfrom(1500)
                client.my_socket.close()
                sleep(1)
                return

            elif choice == "s":
                KEEP_ALIVE = False
                t1.join()
                sleep(5)
                my_header = build_header(7, 0, "")
                client.my_socket.sendto(my_header, message_add)
                message, message_add = client.my_socket.recvfrom(1500)
                SWAPED = True
                client.my_socket.close()
                sleep(1)
                server_loop(Server(clientAdd), clientAdd)
                return
            else:
                print(f'Zla moznost')
        except (ConnectionResetError, socket.timeout):
            print("Server nepocuva")
            continue


def set_server():
    # port = int(input("Zadaj port serveru"))
    port = 6000
    server = Server(("localhost", port))
    server_loop(server, ("localhost", port))


def set_client():
    # port = int(input("Zadaj port serveru"))
    port = 6000
    # ip = str(input("Zadaj ip klienta"))
    ip = "127.0.0.1"
    client = Client((ip, port))
    client_loop(client, (ip, port))


while True:
    opt = str(input())
    if opt == "s":
        set_server()
        break

    if opt == "c":
        set_client()
        break
    print(f'Zla moznost')
