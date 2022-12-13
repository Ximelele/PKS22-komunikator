import math
import os
import socket
from time import sleep
import threading
import hashlib

class Server:

    def __init__(self, serverAddressPort):
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverAddressPort = serverAddressPort


class Client:
    def __init__(self, serverAddressPort):
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverAddressPort = serverAddressPort


# https://stackoverflow.com/questions/35205702/calculating-crc16-in-python
def crc16(data: bytes) -> int:
    xor_in = 0x800D  # initial value
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


def build_header(flag: int, packet_number: int, data, file=False, error=False) -> bytes:
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


ZACIATOK_KOMUNIKACIE: bool = False
MAX_DATA_SIZE: int = 1466
HLAVICKA: int = 6
KEEP_ALIVE: bool = False
UKONCENIE_KEEP_ALIVE: bool = False
SERVER_SWAP: bool = False


def keep_alive(client, serverAddressPort: tuple):
    global KEEP_ALIVE
    global UKONCENIE_KEEP_ALIVE
    global SERVER_SWAP
    sleep(0.1)
    end_count: int = 0

    while True:
        my_header = build_header(0, 0, "")

        client.sendto(my_header, serverAddressPort)
        try:
            client.settimeout(5)
            message, message_add = client.recvfrom(1500)
            flag = int(chr(message[0]))
        except (ConnectionResetError, socket.timeout):
            if end_count == 5:
                UKONCENIE_KEEP_ALIVE = True
                break
            flag = 3
            end_count += 1
            print(f'Neprislo potvrdenie Keep Alive')

        if flag == 2:
            end_count = 0
            print(f'Potvrdene Keep Alive')
        if flag == 7:
            SERVER_SWAP = True
            KEEP_ALIVE = False
            sleep(2)
            print("Budes prehodeny na server- Stlac enter pre potvrdenie")
            return

        for i in range(5):
            sleep(1)
            if not KEEP_ALIVE:
                return
    if UKONCENIE_KEEP_ALIVE:
        print("Klient sa vypina - stlacte enter")
        quit()


def choose_fragment_size() -> int:
    global MAX_DATA_SIZE
    print(f"Vyber velkost fragmentu 1-{1466}")
    size = int(input())
    # MAX_DATA_SIZE = 1466
    if size < 0:
        size = 1
    elif size > MAX_DATA_SIZE:
        size = 1466

    return size


def simulate_error() -> int:
    print(f'Chces simulovat chybu? 0-1')
    errors = int(input())

    return errors


def server_menu():
    print("Chces vymenit strany?: a/n")
    answer = str(input())
    global SERVER_SWAP
    if answer == "a":
        SERVER_SWAP = True

def count_hash(file:bytes):

    hash = hashlib.sha256(file)
    return hash.digest()

def server_loop(server: Server, serverAdd: tuple):
    print("Bububu server")
    server.my_socket.settimeout(60)
    try:
        server.my_socket.bind(serverAdd)
        message, message_add = server.my_socket.recvfrom(1500)

        my_header = build_header(2, 0, "")
        server.my_socket.sendto(my_header, message_add)
    except socket.timeout:
        server.my_socket.close()

    print(f"Klient sa pripojil {message_add}")

    global SWAPED
    global ZACIATOK_KOMUNIKACIE
    global KEEP_ALIVE
    global SERVER_SWAP
    file_path = str(input("Zadaj kde chces ukladat subory (Enter pre tento priecinok)"))

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
                flag = 2
                if SERVER_SWAP:
                    flag = 7
                my_header = build_header(flag, packet_num, "")
                server.my_socket.sendto(my_header, message_add)
                SERVER_SWAP = False

            elif flag == 5:
                receive_text(finalMsg, server, message_add, crc, packet_num)
                server_menu()

            elif flag == 6:
                receive_file(finalMsg, server, message_add, file_path)
                server_menu()
            elif flag == 7:
                SWAPED = True
                KEEP_ALIVE = False
                my_header = build_header(2, 0, "")
                server.my_socket.sendto(my_header, message_add)
                server.my_socket.settimeout(60)
                server.my_socket.close()
                sleep(1)
                client_loop(Client((message_add[0], serverAdd[1])), (message_add[0], serverAdd[1]))
            elif flag == 8:
                my_header = build_header(2, 0, "")
                server.my_socket.sendto(my_header, message_add)
                print(f'Klient {message_add} sa odpojil')

    except socket.timeout:
        print("Koniec bububu")
        sleep(3)
        server.my_socket.close()
        return


def receive_text(textMsg: bytes, server: Server, message_add: tuple, crc: int, packet_num: int):
    first: bool = True
    textArray: list = []
    errors: int = 0
    total_size: int = 0
    number_of_fragments: int = 0
    last_packet: int = 0
    separated_counter: int = 0

    while True:
        if not first:
            try:
                message, message_add = server.my_socket.recvfrom(1500)
                crc = message[-2:]
                crc = int.from_bytes(crc, 'little')
                message = message[0:-2]
                packet_num = message[1:4]
                packet_num = int.from_bytes(packet_num, 'little')

                flag = int(chr(message[0]))
                if flag == 0:
                    continue
                if flag == 9:
                    last_packet = packet_num
                    number_of_fragments += 1
                    total_size += HLAVICKA
                    print(f'Prijaty packet: {packet_num}:posledny packet')
                    break
            except (ConnectionResetError, socket.timeout, socket.gaierror, socket.error):
                print("Odpojeny kabel")
                if separated_counter == 5:
                    print("Spojenie bude ukoncene")
                    quit()
                separated_counter += 1
                sleep(2)
                continue

        if first:
            check_crc = crc16(textMsg)
        else:
            check_crc = crc16(message[4:])

        if check_crc != crc:
            my_header = build_header(3, packet_num, "")

            server.my_socket.sendto(my_header, message_add)
            errors += 1
            print(f'Prijaty packet: {packet_num} Chyba: True')
            if first:
                total_size += len(textMsg) + HLAVICKA
                first = False
            else:
                total_size += len(message[4:]) + HLAVICKA
            continue
        else:
            print(f'Prijaty packet: {packet_num} Chyba: False')

        if first:
            total_size += len(textMsg) + HLAVICKA
            textArray.append(textMsg.decode())
        else:
            total_size += len(message[4:]) + HLAVICKA
            textArray.append(message[4:].decode())
        first = False

        my_header = build_header(4, packet_num, "")
        server.my_socket.sendto(my_header, message_add)
        number_of_fragments += 1

    my_header = build_header(9, last_packet, "")
    server.my_socket.sendto(my_header, message_add)
    final_text = "".join(textArray)
    print(final_text)
    print(f'Pocet prijatych fragmentov {number_of_fragments + errors}')
    print(f'Celkova prijata velkost fragmentov {total_size}')


# posielanie s chybami
def receive_file(file: bytes, server: Server, message_add: tuple, file_path: str):
    my_header = build_header(4, 0, "")
    server.my_socket.sendto(my_header, message_add)
    file_array: dict = {}
    file_name: str = file.decode()
    file_name = file_name.rsplit('\\')[-1]
    number_of_fragments: int = 1
    total_size: int = len(file_name) + HLAVICKA
    errors: int = 0
    last_packet: int = 0
    separated_counter: int = 0
    hash_value: str = ""
    while True:
        # server.my_socket.settimeout(20)
        try:
            message, message_add = server.my_socket.recvfrom(1500)
            crc = message[-2:]
            crc = int.from_bytes(crc, 'little')
            flag = int(chr(message[0]))
            packet_num = message[1:4]
            packet_num = int.from_bytes(packet_num, 'little')
            if flag == 9:
                last_packet = packet_num
                number_of_fragments += 1
                hash_value = message[4:-2].decode()
                total_size += HLAVICKA
                print(f'Prijaty packet: {packet_num}:posledny packet')
                break
            check_crc = crc16(message[4:-2])

            if check_crc != crc:
                my_header = build_header(3, packet_num, "")
                sleep(0.1)
                server.my_socket.sendto(my_header, message_add)

                errors += 1
                print(f'Prijaty packet: {packet_num} Chyba: True')
                total_size += len(message[4:-2]) + HLAVICKA
                continue

            print(f'Prijaty packet: {packet_num} Chyba: False')
        except (ConnectionResetError, socket.timeout, socket.gaierror, socket.error):
            print("Odpojeny kabel")
            if separated_counter == 5:
                print("Spojenie bude ukoncene")
                quit()
            separated_counter += 1
            sleep(3)
            continue
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

    final_name = file_path + file_name
    fw = open(final_name, 'wb+')

    for i in file_array.values():
        fw.write(i)
    fw.close()
    fw = open(file_name, 'rb+')
    test = fw.read()
    print(f'Subor bol ulozeny v {os.path.abspath(file_name)}')
    print(f'Velkost suboru {os.path.getsize(file_name)}')
    print(f'poslany hash{hash_value}')
    my_hash =count_hash(test)
    print(f'Vypocitany hash{my_hash}')
    if str(my_hash) == str(hash_value):
        print("Hasha sa rovnaju")

def client_menu() -> str:
    global SERVER_SWAP
    menu = "t - textova sprava\n"
    menu += "f - poslat subor\n"
    menu += "s - zmenit strany\n"
    menu += "v - vycistit obrazovku\n"
    menu += "e - ukonci\n"
    print(menu)
    menu_choice = str(input())
    if SERVER_SWAP:
        menu_choice = "s"
    return menu_choice


def send_file(file: str, client: Client):
    f = open(file, 'rb+')
    print(f'Velkost suboru {os.path.getsize(file)}')
    data: bytes = f.read()

    hash = count_hash(data)
    my_header = build_header(6, 0, file)
    # na nazov suboru sa fragmentacia nestahuje
    # posielam nazov suboru
    client.my_socket.settimeout(10)
    try:
        client.my_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.my_socket.recvfrom(1500)
    except (ConnectionResetError, socket.timeout, socket.gaierror, socket.error):
        print("Nedostupny server")
        return

    flag: int = int(chr(message[0]))
    # POJEBANY KEEPALIVE
    if flag == 2:
        while flag != 4:  # tento krok si mozem dovolit lebo file name poslem vzdy bez chyby
            message, message_add = client.my_socket.recvfrom(1500)
            flag: int = int(chr(message[0]))
    max_data: int = choose_fragment_size()

    error: int = simulate_error()
    to_send = math.ceil(len(data) / max_data)+2
    print(f"Bude poslanych {to_send} packetov")
    index: int = 1
    separated_counter: int = 0
    while len(data) > 0:
        if error:
            my_header = build_header(6, index, data[:max_data], True, True)
            error -= 1
        else:
            my_header = build_header(6, index, data[:max_data], True)
        try:
            client.my_socket.sendto(my_header, client.serverAddressPort)

            message, message_add = client.my_socket.recvfrom(1500)
        except (ConnectionResetError, socket.timeout, socket.gaierror, socket.error):
            print("Odpojeny kabel")
            if separated_counter == 5:
                print("Spojenie bude ukoncene")
            separated_counter += 1
            sleep(3)
            continue
        flag = int(chr(message[0]))
        if flag == 3:
            separated_counter = 0
            continue
        elif flag == 4:
            separated_counter = 0
            data = data[max_data:]
            index += 1
        else:
            separated_counter = 0
            continue

    my_header = build_header(9, index, str(hash))
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)
    print("Subor bol odoslany")


def send_text(textMsg, client: Client):
    textMsg = str(textMsg)
    max_data: int = choose_fragment_size()
    to_send = math.ceil(len(textMsg)/max_data)
    error: int = simulate_error()
    print(f"Bude poslanych {to_send+1} packetov")
    index: int = 0
    separated_counter: int = 0
    while len(textMsg) > 0:

        if error:
            error -= 1
            my_header = build_header(5, index, textMsg[:max_data], False, True)
        else:
            my_header = build_header(5, index, textMsg[:max_data])
        try:
            client.my_socket.sendto(my_header, client.serverAddressPort)
            # sleep(0.1)

            client.my_socket.settimeout(10)

            message, message_add = client.my_socket.recvfrom(1500)
        except (ConnectionResetError, socket.timeout, socket.gaierror, socket.error):
            print("Odpojeny kabel")
            if separated_counter == 5:
                print("Spojenie bude ukoncene")
                quit()
            separated_counter += 1
            sleep(2)
            continue
        flag = int(chr(message[0]))
        if flag == 2:
            while flag == 2:
                message, message_add = client.my_socket.recvfrom(1500)
                flag = int(chr(message[0]))
        if flag == 3:
            continue
        elif flag == 4:
            index += 1
            textMsg = textMsg[max_data:]
            separated_counter = 0
        else:
            continue

    my_header = build_header(9, (index), "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)
    print("Sprava bola poslana")


SWAPED: bool = False


def client_loop(client: Client, clientAdd: tuple):
    global KEEP_ALIVE
    global ZACIATOK_KOMUNIKACIE
    global UKONCENIE_KEEP_ALIVE
    global SWAPED
    global SERVER_SWAP
    KEEP_ALIVE = False
    t1 = None

    while True:
        try:
            client.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            my_header = build_header(1, 0, "")
            client.my_socket.sendto(my_header, clientAdd)
            client.my_socket.settimeout(10)
            message, message_add = client.my_socket.recvfrom(1500)
            if int(chr(message[0])) == 2:
                break
        except (socket.timeout, socket.gaierror, ConnectionResetError) as e:
            print(e)
            continue

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
        if UKONCENIE_KEEP_ALIVE:
            exit()

        choice = client_menu()

        try:
            if choice == "t":
                KEEP_ALIVE = False
                t1.join(0.5)
                print("Zadaj textovu spravu ktoru chces poslat\n")
                textMsg = str(input())
                sleep(2)
                send_text(textMsg, client)

            elif choice == "f":
                KEEP_ALIVE = False
                t1.join(0.5)
                print("Zadaj subor")
                file = str(input("Vzor: D:\Python projects\pks_komunikator\Mathematica_hnoj.zip\n"))
                print(f'Absolutna cesta k suboru {os.path.abspath(file)}')
                sleep(1)
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
                SERVER_SWAP = False
                my_header = build_header(7, 0, "")
                client.my_socket.sendto(my_header, message_add)
                message, message_add = client.my_socket.recvfrom(1500)
                SWAPED = True
                client.my_socket.close()
                sleep(1)
                server_loop(Server(("", clientAdd[1])), ("", clientAdd[1]))
                return
            elif choice == "v":
                os.system('cls')
            else:
                if not UKONCENIE_KEEP_ALIVE:
                    print(f'Zla moznost')
        except (ConnectionResetError, socket.timeout):
            print("Server nepocuva")
            continue


def set_server():
    port: int = int(input("Zadaj port serveru "))
    os.system('cls')
    server: Server = Server(("", port))
    server_loop(server, ("", port))


def set_client():
    port: int = int(input("Zadaj port serveru "))

    ip: str = str(input("Zadaj ip servera "))

    os.system('cls')
    client: Client = Client((ip, port))
    client_loop(client, (ip, port))


while True:

    print("Zadaj s pre server a c pre klienta: ")
    opt: str = str(input())
    if opt == "s":
        set_server()
        break

    elif opt == "c":
        set_client()
        break
    print(f'Zla moznost')
