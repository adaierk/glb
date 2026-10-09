"""Loopback-only TOEO discovery + corrected network-user bootstrap candidate.

No account authentication or game world is provided. Incoming bytes are saved
for the next protocol stage; unknown requests are never echoed as replies.
"""
import argparse
import datetime
import json
import socket
import struct
import threading
import time
from pathlib import Path
from native_handshake_packets import bootstrap402


class BootstrapServer:
    def __init__(self, out, main_port=11100, world_port=45000, bind_extra=True):
        self.out = Path(out)
        self.out.mkdir(parents=True,exist_ok=True)
        self.main_port, self.world_port = main_port, world_port
        self.ports = [world_port,main_port]
        if bind_extra:
            self.ports += [p for p in (11101,45001,45002) if p not in self.ports]
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.listeners, self.clients, self.threads = [], [], []
        self.counter = 0

    def log(self, event, **fields):
        row = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'event':event,**fields}
        with self.lock:
            with (self.out/'server.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(row,ensure_ascii=False)+'\n')

    def start(self):
        try:
            for port in self.ports:
                s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                self.listeners.append(s)
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                s.bind(('127.0.0.1',port))
                s.listen(5)
                s.settimeout(.2)
                self.log('listen',host='127.0.0.1',port=port)
            self.world_port=self.listeners[0].getsockname()[1]
            self.main_port=self.listeners[1].getsockname()[1]
            for s in self.listeners:
                port=s.getsockname()[1]
                t=threading.Thread(target=self.accept_loop,args=(s,port),daemon=True)
                self.threads.append(t);t.start()
        except BaseException:
            self.close();raise

    def close(self):
        self.stop_event.set()
        with self.lock:
            clients=list(self.clients)
        for s in self.listeners+clients:
            try:s.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:s.close()
            except OSError:pass
        for t in self.threads:
            if t is not threading.current_thread():t.join(timeout=1)

    def accept_loop(self, s, port):
        while not self.stop_event.is_set():
            try:c,peer=s.accept()
            except socket.timeout:continue
            except OSError:break
            with self.lock:
                self.clients.append(c)
                self.counter+=1
                conn_id=self.counter
            t=threading.Thread(target=self.client_loop,args=(c,port,conn_id),daemon=True)
            self.threads.append(t);t.start()

    def world_info(self):
        b=bytearray(56)
        b[4:8]=socket.inet_aton('127.0.0.1')[::-1]
        struct.pack_into('!I',b,8,45001)
        struct.pack_into('!I',b,16,1)
        label='エターニア復元実験'.encode('cp932')
        b[20:20+len(label)]=label
        struct.pack_into('!II',b,48,1,1)
        return bytes(b)

    def greeting(self,port):
        return bootstrap402(port=port)

    def should_greet(self,port):
        return port==self.main_port

    def process_game_bytes(self,c,port,conn_id,data,state):
        pass  # v3: retain inbound bytes only

    def connection_closed(self,conn_id,state):
        pass

    def client_loop(self, c, port, conn_id):
        self.log('accept',port=port,connection=conn_id)
        c.settimeout(.3)
        pending=bytearray()
        state={}
        try:
            if self.should_greet(port):
                greeting=self.greeting(port)
                c.sendall(greeting)
                self.log('send_bootstrap402_self',port=port,connection=conn_id,
                         bytes=len(greeting),hex=greeting.hex())
            while not self.stop_event.is_set():
                try:data=c.recv(8192)
                except socket.timeout:continue
                if not data:break
                self.log('receive',port=port,connection=conn_id,bytes=len(data),hex=data.hex())
                with (self.out/f'client_{port}_{conn_id}.bin').open('ab') as f:f.write(data)
                if port != self.world_port:
                    self.process_game_bytes(c,port,conn_id,data,state)
                    continue
                pending.extend(data)
                while len(pending)>=8:
                    request=bytes(pending[:8]);del pending[:8]
                    code=int.from_bytes(request[:4],'big')
                    if code==3:reply=struct.pack('!II',3,1)
                    elif code==5:reply=struct.pack('!I',5)+self.world_info()
                    else:
                        self.log('unknown_discovery',code=code,hex=request.hex());continue
                    c.sendall(reply)
                    self.log('send_discovery',code=code,bytes=len(reply),hex=reply.hex())
        except OSError as exc:
            if not self.stop_event.is_set():self.log('connection_error',port=port,error=str(exc))
        except ValueError as exc:
            self.log('protocol_rejected',port=port,connection=conn_id,error=str(exc))
        finally:
            self.connection_closed(conn_id,state)
            c.close()
            with self.lock:
                if c in self.clients:self.clients.remove(c)
            self.log('disconnect',port=port,connection=conn_id)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='session_bootstrap_report')
    p.add_argument('--duration',type=int,default=240)
    args=p.parse_args()
    server=BootstrapServer(args.out)
    try:
        server.start()
        print('Loopback discovery and session bootstrap running; account login is not implemented.',flush=True)
        server.stop_event.wait(args.duration)
    except KeyboardInterrupt:pass
    finally:server.close()
