import dataclasses as dc
import os
import random
import socket
import typing as T

CRLF = b"\r\n"
FTP_CMD_ARGS = T.List[bytes]


@dc.dataclass
class FTPHandler:
    cc_sock: T.Optional[socket.socket]
    dc_sock: T.Optional[socket.socket] = None
    dc_passive_host: T.Tuple[int, int, int, int] = (127, 0, 0, 1)
    dc_passive_ports: T.Tuple[int, int] = (1024, 65536)

    commands: T.Dict[bytes, T.Callable[[T.List[bytes]], None]] = dc.field(
        default_factory=dict
    )
    dc_transfer_mode: T.Literal["ASCII", "BINARY"] = "ASCII"

    def __post_init__(self):
        methods = [method for method in dir(self) if method.startswith("cmd_")]
        for method in methods:
            self.add_command(bytes(method[4:], "UTF-8"), getattr(self, method))
        self.handle_command(b"NEW_CONNECTION")
        print(self.commands.keys())

    def cc_recv(self) -> T.Optional[bytes]:
        if self.cc_sock is None:
            return None
        buffer = b""
        while True:
            try:
                data = self.cc_sock.recv(1)
            except ConnectionResetError:
                data = b""
            if data == b"":
                self.cc_close()
                return None
            buffer += data
            if buffer.endswith(CRLF):
                return buffer.strip(CRLF)

    def cc_send(self, data: bytes) -> bool:
        if self.cc_sock is None:
            return False
        try:
            self.cc_sock.sendall(data)
            print(f">c> {data}")
            return True
        except BrokenPipeError:
            self.cc_close()
            return False
        except ConnectionResetError:
            self.cc_close()
            return False

    def cc_send_code(self, code: str, message: str = "") -> bool:
        data = code.encode("utf-8")
        data += b" "
        data += message.encode("utf-8")
        data += CRLF
        return self.cc_send(data)

    def cc_close(self) -> bool:
        if self.cc_sock is None:
            return False
        self.cc_sock.close()
        self.cc_sock = None
        return True

    def dc_passive_listen(self) -> T.Optional[int]:
        self.dc_close()
        port = random.randint(*self.dc_passive_ports)

        self.dc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dc_sock.settimeout(0.5)
        self.dc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.dc_sock.bind(
            (".".join([str(item) for item in self.dc_passive_host]), port)
        )
        self.dc_sock.listen(1)

        return port

    def dc_passive_accept(self) -> bool:
        if self.dc_sock is None:
            return False
        try:
            listner = self.dc_sock
            self.dc_sock, _ = listner.accept()
            listner.close()
        except socket.timeout:
            self.dc_close()
            return False
        return True

    def dc_close(self) -> bool:
        if self.dc_sock is None:
            return False
        self.dc_sock.close()
        self.dc_sock = None
        return True

    def dc_send(self, data: bytes) -> bool:
        if self.dc_sock is None:
            return False
        if self.dc_transfer_mode == "ASCII":
            self.dc_sock.sendall(data + CRLF)
            print(f">dA> {data+CRLF}")
            return True
        elif self.dc_transfer_mode == "BINARY":
            self.dc_sock.sendall(data)
            print(f">dA> {data}")
            return True
        return False

    def add_command(
        self, command: bytes, func: T.Callable[[FTP_CMD_ARGS], None]
    ) -> None:
        self.commands[command] = func

    def handle_command(self, command_raw: bytes) -> bool:
        command = command_raw.split(b" ")

        print(f"Got command: {command[0]} | {command[1:]}")
        if command[0] in self.commands:
            self.commands[command[0]](command[1:])
            return True
        else:
            self.cc_send_code("500", "Unrecognized command!")
            return False

    def loop(self) -> None:
        while self.cc_sock is not None:
            if (data := self.cc_recv()) is not None:
                self.handle_command(data)


class Session(FTPHandler):
    username: bytes = b""
    auth: bool = False

    def dc_send_auto(self, data: bytes) -> bool:
        if self.dc_sock is None:
            self.cc_send_code("425", "!Success")
            return False

        self.cc_send_code("150")

        if self.dc_send(data):
            self.cc_send_code("226", "Success")
            self.dc_close()
            return True
        else:
            self.dc_close()
            self.cc_send_code("426", "!Success")
            return False

    def cmd_NEW_CONNECTION(self, args: FTP_CMD_ARGS) -> None:
        self.cc_send_code("220", "Welcomen")
        return

    def cmd_QUIT(self, args: FTP_CMD_ARGS) -> None:
        self.cc_send_code("221", "Goodbye!")
        self.cc_close()
        self.dc_close()

    def cmd_USER(self, args: FTP_CMD_ARGS) -> None:
        if len(args) < 1:
            self.cc_send_code("501", "Missing username argument")
            return

        self.auth = False
        self.username = args[0]
        self.cc_send_code("331", "Password required!")

    def cmd_PASS(self, args: FTP_CMD_ARGS) -> None:
        if args[0] == b"123":
            self.cc_send_code("230", "Authed")
            self.auth = True
        else:
            self.cc_send_code("530", "Incorrect password!")

    def cmd_PASV(self, args: FTP_CMD_ARGS) -> None:
        if (port := self.dc_passive_listen()) is None:
            return
        self.cc_send_code(
            "227",
            "Entering Passive Mode "
            + f"({self.dc_passive_host[0]},"
            + f"{self.dc_passive_host[1]},"
            + f"{self.dc_passive_host[2]},"
            + f"{self.dc_passive_host[3]},"
            + f"{port // 256},"
            + f"{port % 256})",
        )
        if not self.dc_passive_accept():
            return

    def cmd_LIST(self, args: FTP_CMD_ARGS) -> None:
        file_list = "\r\n".join(os.listdir("."))
        file_list = "-rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3"
        file_list = """drwxr-xr-x 1 10339 10339            0 Nov 26 13:50 Testisi\r
-rw-r--r-- 1 10339 10339            5 Nov 26 13:52 Rupa.txt\r\n
"""
        self.dc_send_auto(file_list.encode("utf-8"))

    def cmd_PWD(self, args: FTP_CMD_ARGS) -> None:
        current_dir = os.getcwd()
        self.cc_send(current_dir.encode("utf-8") + CRLF)

    def cmd_CWD(self, args: FTP_CMD_ARGS) -> None:
        try:
            directory = args[0].decode("utf-8")
            os.chdir(directory)
            self.cc_send_code("250", "Directory changed successfully")
        except IndexError:
            self.cc_send_code("501", "Missing directory argument")
        except FileNotFoundError:
            self.cc_send_code("550", "Directory not found")

    def cmd_TYPE(self, args: FTP_CMD_ARGS) -> None:
        if len(args) == 0:
            self.cc_send_code("501", "Missing type argument")
        else:
            if args[0] == b"A":
                self.dc_transfer_mode = "ASCII"
                self.cc_send(b"200" + CRLF)
            elif args[0] == b"I":
                self.dc_transfer_mode = "BINARY"
                self.cc_send_code("200", "Type set to: Binary.")
            else:
                self.cc_send(b"504" + CRLF)

    def cmd_SYST(self, args: FTP_CMD_ARGS) -> None:
        self.cc_send_code("215", "UNIX Type: L8")


# TODO: Move this to the FTPHandler class
def main() -> None:
    host = "0.0.0.0"
    port = 2121

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(1)

    print(f"FTP server listening on {host}:{port}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Connection from {client_address}")

        conn = Session(client_socket, dc_passive_host=(192, 168, 1, 222))
        conn.loop()


if __name__ == "__main__":
    main()
