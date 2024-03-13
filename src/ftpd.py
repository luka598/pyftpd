import socket
import os
import random
import dataclasses as dc
import typing as T


@dc.dataclass
class Connection:
    sock: socket.socket = dc.field()
    commands: T.Dict[bytes, T.Callable[[T.List[bytes]], None]] = dc.field(
        default_factory=dict
    )

    def __post_init__(self):
        self.on_new()
        self.add_command(b"USER")(self.com_USER)

    def recv(self):
        buffer = b""
        while True:
            if (data := self.sock.recv(1)) == b"":
                return b""
            buffer += data
            if buffer.endswith(b"\r\n"):
                return buffer.strip(b"\r\n")

    def recv_command(self):
        buffer_l = self.recv().split(b" ")
        return buffer_l[0], buffer_l[1:]

    def loop(self):
        while True:
            self.handle_command(*self.recv_command())

    def send(self, code: str, message: str = ""):
        self.sock.send(code.encode("utf-8"))
        self.sock.send(b" ")
        self.sock.send(message.encode("utf-8"))
        self.sock.send(b"\r\n")

    def on_new(self):
        self.send("220", "Puši kurac")

    def handle_command(self, command, args):
        print(f"Got command: {command} | {args}")
        if command in self.commands:
            self.commands[command](args)
        else:
            self.send("500", "Unrecognized command!")

    def add_command(self, command):
        def wrapper(func: T.Callable[[T.List[bytes]], None]):
            self.commands[command] = func

        return wrapper

    def com_USER(self, args):
        user = args[0]
        self.send("331")
        com, args = self.recv_command()
        if com != b"PASS":
            self.send("500")
        pswd = args[0]

        print(user, pswd)

        self.send("230")
        pass


def main():
    host = "127.0.0.1"
    port = random.randint(2000, 2020)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)

    print(f"FTP server listening on {host}:{port}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Connection from {client_address}")

        conn = Connection(client_socket)
        conn.loop()

        break

        client_socket.send(b"220 Welcome to the FTP server!\n")

        while True:
            data = client_socket.recv(1024).decode("utf-8").strip()
            if not data:
                break

            command = data.split(" ")[0].upper()
            if command == "QUIT":
                client_socket.send(b"221 Goodbye!\n")
                client_socket.close()
                break
            elif command == "LIST":
                file_list = "\n".join(os.listdir("."))
                client_socket.sendall(file_list.encode("utf-8") + b"\n")
            elif command == "PWD":
                current_dir = os.getcwd()
                client_socket.sendall(current_dir.encode("utf-8") + b"\n")
            elif command == "CWD":
                try:
                    directory = data.split(" ")[1]
                    os.chdir(directory)
                    client_socket.sendall(b"250 Directory changed successfully\n")
                except IndexError:
                    client_socket.sendall(b"501 Missing directory argument\n")
                except FileNotFoundError:
                    client_socket.sendall(b"550 Directory not found\n")
            elif command == "USER":
                client_socket.sendall(b"331\n")
            elif command == "PASS":
                client_socket.sendall(b"230\n")
            else:
                print("Unknown:", command, data)
                client_socket.sendall(b"500 Unknown command\n")


if __name__ == "__main__":
    main()
