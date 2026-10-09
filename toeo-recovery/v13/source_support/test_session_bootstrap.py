"""Protocol/server regressions independent of the graphical Windows client."""
import json
import socket
import struct
import tempfile
import unittest
from pathlib import Path
from native_handshake_packets import bootstrap402, add_user401, user_record
from session_bootstrap_server import BootstrapServer


def exact(c,n):
    data=bytearray()
    while len(data)<n:
        part=c.recv(n-len(data))
        if not part:raise EOFError('unexpected disconnect')
        data.extend(part)
    return bytes(data)


class SessionBootstrapTests(unittest.TestCase):
    def test_layout_and_self_identity(self):
        p=bootstrap402()
        self.assertEqual(len(p),64)
        self.assertEqual(struct.unpack_from('<HHHH',p,4),(64,0x402,60,0xffff))
        self.assertEqual(p[:4],p[-4:])
        self.assertEqual(struct.unpack_from('<I',p,0x14)[0],1)
        self.assertEqual(struct.unpack_from('<I',p,0x24)[0],struct.unpack_from('<I',p,0x28)[0])
        self.assertEqual(p[0x39],2)
        self.assertEqual(struct.unpack_from('<HHH',add_user401(),4),(44,0x401,40))

    def test_invalid_records_fail_before_sending(self):
        for mode in (1,4):
            with self.assertRaises(ValueError):user_record(encoding=mode)
        with self.assertRaises(ValueError):bootstrap402([bytes(19)])

    def test_discovery_partial_and_coalesced_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            s=BootstrapServer(folder,main_port=0,world_port=0,bind_extra=False)
            # Bind both ephemeral listeners before the worker starts.
            s.start()
            c=socket.create_connection(s.listeners[0].getsockname(),timeout=2)
            try:
                c.sendall(b'\0\0\0')
                c.settimeout(.1)
                with self.assertRaises(socket.timeout):c.recv(1)
                c.settimeout(2)
                c.sendall(b'\x03\x02\0\0\0'+bytes.fromhex('0000000502000000'))
                self.assertEqual(exact(c,8),struct.pack('!II',3,1))
                world=exact(c,60)
                self.assertEqual(world[:4],struct.pack('!I',5))
                self.assertEqual(world[8:12],bytes([1,0,0,127]))
            finally:c.close();s.close()

    def test_bootstrap_and_no_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            # Discovery remains on an unused ephemeral listener; main has its own port.
            reservation=socket.socket();reservation.bind(('127.0.0.1',0))
            port=reservation.getsockname()[1];reservation.close()
            s=BootstrapServer(folder,main_port=port,world_port=0,bind_extra=False)
            s.start()
            c=socket.create_connection(('127.0.0.1',port),timeout=2)
            try:
                self.assertEqual(exact(c,64),bootstrap402(port=port))
                c.sendall(b'client frame must not be echoed')
                c.settimeout(.15)
                with self.assertRaises(socket.timeout):c.recv(1)
            finally:c.close();s.close()
            rows=[json.loads(r) for r in (Path(folder)/'server.jsonl').read_text().splitlines()]
            self.assertTrue(any(r['event']=='receive' for r in rows))
            self.assertEqual(sum(r['event']=='send_bootstrap402_self' for r in rows),1)


if __name__=='__main__':unittest.main()
