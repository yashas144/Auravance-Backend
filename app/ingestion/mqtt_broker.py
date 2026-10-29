"""Minimal MQTT 3.1.1 broker for local testing (QoS 0).

Production can point the subscriber at an external broker. This in-process
server exists so replay and tests do not need Mosquitto installed.
"""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable


CONNECT = 1
CONNACK = 2
PUBLISH = 3
SUBSCRIBE = 8
SUBACK = 9
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14


def encode_remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        out.append(byte)
        if length == 0:
            break
    return bytes(out)


def decode_remaining_length(read_byte: Callable[[], int]) -> int:
    multiplier = 1
    value = 0
    for _ in range(4):
        byte = read_byte()
        value += (byte & 127) * multiplier
        if byte & 128 == 0:
            return value
        multiplier *= 128
    raise ValueError("MQTT remaining length is invalid.")


def encode_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("!H", len(encoded)) + encoded


def topic_matches(filter_topic: str, topic: str) -> bool:
    filter_parts = filter_topic.split("/")
    topic_parts = topic.split("/")
    index = 0
    while index < len(filter_parts):
        part = filter_parts[index]
        if part == "#":
            return True
        if index >= len(topic_parts):
            return False
        if part != "+" and part != topic_parts[index]:
            return False
        index += 1
    return index == len(topic_parts)


class EmbeddedMqttBroker:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._clients_lock = threading.Lock()
        self._subscriptions: dict[socket.socket, list[str]] = {}

    @property
    def bound_port(self) -> int:
        return self.port

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self.port = int(self._sock.getsockname()[1])
        self._sock.listen(32)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._accept_loop, name="auravance-mqtt-broker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        with self._clients_lock:
            clients = list(self._subscriptions)
            self._subscriptions.clear()
        for client in clients:
            try:
                client.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                client, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(target=self._client_loop, args=(client,), daemon=True).start()

    def _client_loop(self, client: socket.socket) -> None:
        client.settimeout(1.0)
        try:
            while not self._stop.is_set():
                packet_type, flags, payload = self._read_packet(client)
                if packet_type is None:
                    continue
                if packet_type == CONNECT:
                    client.sendall(bytes([CONNACK << 4, 2, 0, 0]))
                elif packet_type == SUBSCRIBE:
                    self._handle_subscribe(client, payload)
                elif packet_type == PUBLISH:
                    self._handle_publish(flags, payload)
                elif packet_type == PINGREQ:
                    client.sendall(bytes([PINGRESP << 4, 0]))
                elif packet_type == DISCONNECT:
                    break
        except (OSError, ValueError, struct.error, TimeoutError):
            pass
        finally:
            with self._clients_lock:
                self._subscriptions.pop(client, None)
            try:
                client.close()
            except OSError:
                pass

    def _read_packet(self, client: socket.socket) -> tuple[int | None, int, bytes]:
        header = self._recv_exact(client, 1)
        if header is None:
            raise OSError("client closed")
        if header == b"":
            return None, 0, b""
        packet_type = header[0] >> 4
        flags = header[0] & 0x0F

        def read_byte() -> int:
            data = self._recv_exact(client, 1)
            if not data:
                raise OSError("client closed")
            return data[0]

        remaining = decode_remaining_length(read_byte)
        payload = self._recv_exact(client, remaining) if remaining else b""
        if remaining and payload is None:
            raise OSError("client closed")
        return packet_type, flags, payload or b""

    def _recv_exact(self, client: socket.socket, size: int) -> bytes | None:
        chunks = bytearray()
        while len(chunks) < size:
            try:
                piece = client.recv(size - len(chunks))
            except TimeoutError:
                if self._stop.is_set():
                    return None
                continue
            if not piece:
                return None
            chunks.extend(piece)
        return bytes(chunks)

    def _handle_subscribe(self, client: socket.socket, payload: bytes) -> None:
        packet_id = struct.unpack("!H", payload[:2])[0]
        offset = 2
        filters: list[str] = []
        return_codes = bytearray()
        while offset < len(payload):
            length = struct.unpack("!H", payload[offset : offset + 2])[0]
            offset += 2
            topic = payload[offset : offset + length].decode("utf-8")
            offset += length + 1  # skip requested QoS
            filters.append(topic)
            return_codes.append(0)
        with self._clients_lock:
            self._subscriptions.setdefault(client, []).extend(filters)
        client.sendall(bytes([SUBACK << 4]) + encode_remaining_length(2 + len(return_codes)) + struct.pack("!H", packet_id) + bytes(return_codes))

    def _handle_publish(self, flags: int, payload: bytes) -> None:
        topic_len = struct.unpack("!H", payload[:2])[0]
        topic = payload[2 : 2 + topic_len].decode("utf-8")
        offset = 2 + topic_len
        qos = (flags >> 1) & 0x03
        if qos > 0:
            offset += 2
        body = payload[offset:]
        packet = bytes([PUBLISH << 4]) + encode_remaining_length(2 + topic_len + len(body)) + encode_string(topic) + body
        with self._clients_lock:
            subscribers = [client for client, filters in self._subscriptions.items() if any(topic_matches(item, topic) for item in filters)]
        for client in subscribers:
            try:
                client.sendall(packet)
            except OSError:
                pass
