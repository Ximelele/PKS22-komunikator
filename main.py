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


def build_header(flag : int, packet_number : int, data, file=False, error=False):
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

koniec = False


def keep_alive(client, serverAddressPort: tuple):
    global KEEP_ALIVE
    global koniec
    sleep(0.1)
    end_count = 0
    while True:
        my_header = build_header(0, 0, "")

        client.sendto(my_header, serverAddressPort)
        try:
            client.settimeout(5)
            message, message_add = client.recvfrom(1500)
        except (ConnectionResetError, socket.timeout):
            if end_count == 5:
                koniec = True
                break

            end_count += 1
            print(f'Server je nedostupny')
        else:
            end_count = 0
            print(f'Server je dostupny')

        for i in range(5):
            sleep(1)
            if not KEEP_ALIVE:
                return
    if koniec:
        print("Klient sa vypina - stlacte enter")
        quit()


def choose_fragment_size():
    global MAX_DATA_SIZE
    print(f"Vyber velkost fragmentu 1-{1466}")
    size = int(input())
    # MAX_DATA_SIZE = 1466
    if size < 0:
        size = 1
    elif size > MAX_DATA_SIZE:
        size = 1466

    return size


def simulate_error():
    print(f'Chces simulovat chybu? 0-1')
    errors = int(input())

    return errors


def server_loop(server: Server, serverAdd: tuple):
    print(serverAdd)
    print("Bububu server")
    server.my_socket.settimeout(60)
    try:
        server.my_socket.bind(serverAdd)
        message, message_add = server.my_socket.recvfrom(1500)

        my_header = build_header(2, 0, "")
        server.my_socket.sendto(my_header, message_add)
    except socket.timeout:
        server.my_socket.close()

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
                receive_text(finalMsg, server, message_add, crc, packet_num)

            elif flag == 6:
                receive_file(finalMsg, server, message_add, file_path)
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


def receive_text(textMsg: str, server: Server, message_add: tuple, crc: int, packet_num: int):
    first : bool = True
    textArray : list = []
    errors : int = 0
    total_size : int = 0
    number_of_fragments : int = 0
    last_packet : int = 0
    while True:
        if not first:
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
                break

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
def receive_file(file : bytes, server : Server, message_add : tuple, file_path : str):
    my_header = build_header(4, 0, "")
    server.my_socket.sendto(my_header, message_add)
    file_array = {}
    file_name = file.decode()
    file_name = file_name.rsplit('\\')[-1]
    file_name = "1" + file_name
    # print(file_name)
    number_of_fragments = 1
    total_size = len(file_name) + HLAVICKA
    errors = 0
    last_packet = 0
    while True:
        message, message_add = server.my_socket.recvfrom(1500)
        crc = message[-2:]
        crc = int.from_bytes(crc, 'little')
        flag = int(chr(message[0]))
        packet_num = message[1:4]
        packet_num = int.from_bytes(packet_num, 'little')
        if flag == 9:
            last_packet = packet_num
            number_of_fragments += 1
            total_size += HLAVICKA
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
        else:
            print(f'Prijaty packet: {packet_num} Chyba: False')

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
    print(f'Subor bol ulozeny v {os.path.abspath(file_name)}')


def client_menu():
    menu = "t - textova sprava\n"
    menu += "f - poslat subor\n"
    menu += "s - zmenit strany\n"
    menu += "v - vycistit obrazovku\n"
    menu += "e - ukonci\n"
    print(menu)

    return str(input())


def send_file(file : str, client : Client):
    f = open(file, 'rb+')
    data = f.read()
    my_header = build_header(6, 0, file)
    # na nazov suboru sa fragmentacia nestahuje
    # posielam nazov suboru
    client.my_socket.settimeout(10)
    try:
        client.my_socket.sendto(my_header, client.serverAddressPort)
        message, message_add = client.my_socket.recvfrom(1500)
    except (ConnectionResetError, socket.timeout):
        print("Nedostupny server")
        return

    flag = int(chr(message[0]))
    # POJEBANY KEEPALIVE
    if (flag == 2):
        while flag != 4:  # tento krok si mozem dovolit lebo file name poslem vzdy bez chyby
            message, message_add = client.my_socket.recvfrom(1500)
            flag = int(chr(message[0]))
    max_data = choose_fragment_size()

    error = simulate_error()
    index = 1
    try:
        while len(data) > 0:
            if error:
                my_header = build_header(6, index, data[:max_data], True, True)
                error -= 1
            else:
                my_header = build_header(6, index, data[:max_data], True)

            client.my_socket.sendto(my_header, client.serverAddressPort)
            client.my_socket.settimeout(10)

            message, message_add = client.my_socket.recvfrom(1500)
            flag = int(chr(message[0]))
            if flag == 3:
                continue
            else:
                data = data[max_data:]
                index += 1

    except (ConnectionResetError, socket.timeout):
        print("Nedostupny server")
        return

    my_header = build_header(9, (index + 1), "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)


def send_text(textMsg : str, client : Client):
    max_data = choose_fragment_size()

    error = simulate_error()
    index = 0
    try:
        while len(textMsg) > 0:

            if error:
                error -= 1
                my_header = build_header(5, index, textMsg[:max_data], False, True)
            else:
                my_header = build_header(5, index, textMsg[:max_data])

            client.my_socket.sendto(my_header, client.serverAddressPort)
            # sleep(0.1)
            client.my_socket.settimeout(10)
            message, message_add = client.my_socket.recvfrom(1500)

            flag = int(chr(message[0]))
            if flag == 2:
                while flag == 2:
                    message, message_add = client.my_socket.recvfrom(1500)
                    flag = int(chr(message[0]))
            if flag == 3:
                continue
            else:
                index += 1
                textMsg = textMsg[max_data:]

    except (ConnectionResetError, socket.timeout):
        print("Nedostupny server")
        return

    my_header = build_header(9, (index + 1), "")
    client.my_socket.sendto(my_header, client.serverAddressPort)
    message, message_add = client.my_socket.recvfrom(1500)


SWAPED = False


def client_loop(client: Client, clientAdd: tuple):
    global KEEP_ALIVE
    global ZACIATOK_KOMUNIKACIE
    global SWAPED
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

        choice = client_menu()

        try:
            if choice == "t":
                KEEP_ALIVE = False
                t1.join(0.5)
                textMsg = str(input("Zadaj textovu spravu ktoru chces poslat\n"))
                sleep(2)
                send_text(textMsg, client)

            # C:\Users\druzb\Desktop\
            elif choice == "f":
                KEEP_ALIVE = False
                t1.join(0.5)
                print("Zadaj subor")
                file = str(input("Vzor: D:\Python projects\pks_komunikator\Mathematica_hnoj.zip\n"))
                file_name = os.path.abspath(file)
                # print(file_name)
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
                print(f'Zla moznost')
        except (ConnectionResetError, socket.timeout):
            print("Server nepocuva")
            continue


def set_server():
    port = int(input("Zadaj port serveru "))
    # port = 6000
    os.system('cls')
    server = Server(("", port))
    server_loop(server, ("", port))


def set_client():
    port = int(input("Zadaj port serveru "))
    # port = 6000
    ip = str(input("Zadaj ip servera "))
    # ip = "127.0.0.1"
    os.system('cls')
    client = Client((ip, port))
    client_loop(client, (ip, port))


while True:
    print("Zadaj s pre server a c pre klienta: ")
    opt = str(input())
    if opt == "s":
        set_server()
        break

    if opt == "c":
        set_client()
        break
    print(f'Zla moznost')
