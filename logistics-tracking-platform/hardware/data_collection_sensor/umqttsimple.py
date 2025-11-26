"""
Lightweight MQTT client for MicroPython.
Source adapted from the official `umqtt.simple` module for convenience.
"""

import usocket as socket
import ustruct as struct
from ubinascii import hexlify


class MQTTException(Exception):
    pass


class MQTTClient:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=False,
        ssl_params=None,
    ):
        if ssl_params is None:
            ssl_params = {}
        self.client_id = client_id
        self.server = server
        self.port = port or (8883 if ssl else 1883)
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.sock = None
        self.cb = None
        self.pid = 0
        self.rcv_pids = set()

    def _send_str(self, s):
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while True:
            b = self.sock.read(1)[0]
            n |= (b & 0x7F) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def connect(self, clean_session=True):
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock = socket.socket()
        self.sock.connect(addr)
        if self.ssl:
            import ussl

            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)

        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")
        sz = 10 + 2 + len(self.client_id)
        msg[6] = 0x02 | (clean_session << 1)
        if self.keepalive:
            msg[7] = self.keepalive >> 8
            msg[8] = self.keepalive & 0xFF
        payload = bytearray()
        payload.extend(struct.pack("!H", len(self.client_id)))
        payload.extend(self.client_id)
        if self.user is not None:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
            payload.extend(struct.pack("!H", len(self.user)))
            payload.extend(self.user)
            payload.extend(struct.pack("!H", len(self.pswd)))
            payload.extend(self.pswd)
        premsg[1] = sz
        self.sock.write(premsg)
        self.sock.write(msg)
        self.sock.write(payload)
        resp = self.sock.read(4)
        if resp is None or resp[0] != 0x20 or resp[1] != 0x02:
            raise MQTTException("Bad CONNACK")
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return True

    def disconnect(self):
        self.sock.write(b"\xe0\0")
        self.sock.close()
        self.sock = None

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        pkt = bytearray(b"\x30\0")
        pkt[0] |= (qos << 1) | retain
        size = 2 + len(topic) + len(msg)
        if qos:
            size += 2
        i = 1
        while size > 0x7F:
            pkt[i] = (size & 0x7F) | 0x80
            size >>= 7
            pkt.append(0)
            i += 1
        pkt[i] = size
        self.sock.write(pkt)
        self._send_str(topic)
        if qos:
            self.pid += 1
            pid = self.pid
            self.sock.write(struct.pack("!H", pid))
        self.sock.write(msg)

    def subscribe(self, topic, qos=0):
        if qos not in (0, 1):
            raise ValueError("Only QoS 0/1 supported")
        self.pid += 1
        pkt = bytearray(b"\x82\0\0\0")
        size = 2 + 2 + len(topic) + 1
        pkt[1] = size
        pkt[2] = self.pid >> 8
        pkt[3] = self.pid & 0xFF
        self.sock.write(pkt)
        self._send_str(topic)
        self.sock.write(bytes([qos]))

    def check_msg(self):
        if self.sock is None:
            raise MQTTException("Not connected")
        self.sock.setblocking(False)
        try:
            cmd = self.sock.read(1)
        except OSError:
            cmd = None
        self.sock.setblocking(True)
        if not cmd:
            return
        cmd = cmd[0]
        if cmd == 0xD0:
            self.sock.read(1)
            return
        if cmd == 0x40:
            self.sock.read(3)
            return
        if cmd & 0xF0 != 0x30:
            raise MQTTException("Unsupported packet: %x" % cmd)
        size = self._recv_len()
        topic_len = struct.unpack("!H", self.sock.read(2))[0]
        topic = self.sock.read(topic_len)
        size -= topic_len + 2
        pkt_id = None
        if cmd & 0x06:
            pkt_id = struct.unpack("!H", self.sock.read(2))[0]
            size -= 2
        msg = self.sock.read(size)
        if self.cb:
            self.cb(topic, msg)
        if (cmd & 0x06) == 0x02:
            self.sock.write(b"\x40\x02")
            self.sock.write(struct.pack("!H", pkt_id))

    def wait_msg(self):
        if self.sock is None:
            raise MQTTException("Not connected")
        res = self.sock.read(1)
        if not res:
            return None
        self.sock.setblocking(True)
        return self.check_msg()
