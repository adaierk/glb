import socket,struct,time,datetime,sys,traceback,os,threading
from pathlib import Path
out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
MODE=os.environ.get('TOEO_WORLD_MODE','normal')
def log(x):
 with out.open('a',encoding='utf-8') as f:f.write(datetime.datetime.now().isoformat(timespec='seconds')+' '+x+'\n')
def read_exact(sock,n):
 data=b''
 while len(data)<n:
  p=sock.recv(n-len(data))
  if not p:return None
  data+=p
 return data
def world_work():
 b=bytearray(56)
 struct.pack_into('!I',b,0,0)
 b[4:8]=socket.inet_aton('127.0.0.1')[::-1]
 struct.pack_into('!I',b,8,45001)
 struct.pack_into('!I',b,16,1)
 try:label='エターニア復元実験'.encode('cp932')
 except Exception:label=b'Offline Research'
 b[20:20+len(label)]=label
 struct.pack_into('!I',b,48,1)
 struct.pack_into('!I',b,52,1)
 return b
def downstream_listener(port):
    downstream=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    downstream.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try: downstream.bind(('127.0.0.1',port))
    except Exception as ex: log('DOWNSTREAM_BIND_FAILED port='+str(port)+' '+repr(ex));return
    downstream.listen(4);downstream.settimeout(3)
    log('DOWNSTREAM_LISTEN port='+str(port))
    end=time.monotonic()+155
    while time.monotonic()<end:
        try:c,addr=downstream.accept()
        except socket.timeout:continue
        log('DOWNSTREAM_ACCEPT port='+str(port)+' peer='+repr(addr))
        c.settimeout(6)
        with c:
            for i in range(15):
                try:b=c.recv(8192)
                except socket.timeout:log('DOWNSTREAM_TIMEOUT port='+str(port));break
                except Exception as ex:log('DOWNSTREAM_ERROR '+repr(ex));break
                if not b:break
                log('DOWNSTREAM_RECV port='+str(port)+' size='+str(len(b))+' hex='+b[:256].hex())
                try:
                    c.sendall(b)
                    log('DOWNSTREAM_ECHO port='+str(port)+' size='+str(len(b)))
                except Exception as ex:
                    log('DOWNSTREAM_REPLY_ERROR '+repr(ex));break
    downstream.close()
for port in (11100,11101,45001,45002):
    threading.Thread(target=downstream_listener,args=(port,),daemon=True).start()
sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
sock.bind(('127.0.0.1',45000));sock.listen(5);sock.settimeout(2)
log('MOCK_LISTEN 127.0.0.1:45000 mode='+MODE)
deadline=time.monotonic()+155
try:
 while time.monotonic()<deadline:
  try:c,addr=sock.accept()
  except socket.timeout:continue
  log('ACCEPT '+repr(addr))
  c.settimeout(15)
  try:
   while time.monotonic()<deadline:
    head=read_exact(c,8)
    if head is None:
     log('DISCONNECT');break
    code=int.from_bytes(head[:4],'big')
    req=head[4:].hex()
    log('CLIENT_REQUEST type='+str(code)+' payload='+req+' hex='+head.hex())
    if code==3:
     answer=struct.pack('!II',3,1)
     log('REPLY_NUM size='+str(len(answer))+' hex='+answer.hex())
     c.sendall(answer)
    elif code==5:
     answer=struct.pack('!I',5)+world_work()
     log('REPLY_WORLD size='+str(len(answer))+' hex='+answer.hex())
     c.sendall(answer)
    else:
     log('UNHANDLED type='+str(code))
     c.sendall(head)
  except Exception as e:log('SESSION_ERROR '+repr(e))
  finally:
   c.close()
finally:sock.close()
