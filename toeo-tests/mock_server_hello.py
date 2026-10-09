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
def framed_native(opcode, length, sequence=0xffff, inner_offset=0):
    """Original packet header based on client swap routine at 0x60B030.
    The *wire* header uses network-endian 16/32-bit fields.
    """
    if length < 20:
        raise ValueError('full native frame needs >=20 bytes')
    buf=bytearray(length)
    buf[0:4]=bytes.fromhex('12345678')
    struct.pack_into('>H',buf,4,length)
    struct.pack_into('>H',buf,6,opcode)
    struct.pack_into('>H',buf,8,inner_offset)
    struct.pack_into('>H',buf,10,sequence)
    struct.pack_into('>H',buf,12,0)
    struct.pack_into('>I',buf,14,0)
    struct.pack_into('>H',buf,18,0)
    return bytes(buf)

def authentic_native_frame(opcode,total_len,sequence=0xffff):
    """Packet envelope derived from original client at 0x60B110 and 0x611CFB.
    Uses network-byte-order fields; 0x12345678 is also appended as a tail marker.
    These are test candidates, not verified server login messages.
    """
    if total_len < 24:
        raise ValueError('invalid TOEO frame size')
    packet=bytearray(total_len)
    packet[:4]=bytes.fromhex('12345678')
    struct.pack_into('>H',packet,4,total_len)
    struct.pack_into('>H',packet,6,opcode)
    struct.pack_into('>H',packet,8,total_len-4)
    struct.pack_into('>H',packet,10,sequence)
    packet[-4:]=bytes.fromhex('12345678')
    return bytes(packet)

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
        if port==11100:
            preset = os.environ.get('TOEO_MAIN_GREETING','silence')
            packets = {
                'magic19_401':bytes.fromhex('12345678010001041300ffff00000000000000'),
                'magic22_401':bytes.fromhex('12345678040001041600ffff00000000000000000000'),
                'magic19_405':bytes.fromhex('12345678010005041300ffff00000000000000'),
                'magic19_seq0':bytes.fromhex('12345678010001041300000000000000000000'),
                'magic22_405':bytes.fromhex('12345678040005041600ffff00000000000000000000'),
                'magic19_len18':bytes.fromhex('12345678010001041200ffff00000000000000'),
                'silence':b'',
                'endmagic_401_36':b'\x00\x00\x00\x00'+framed_native(0x401,36)[4:32]+bytes.fromhex('12345678'),
                'endmagic_403_24':b'\x00\x00\x00\x00'+framed_native(0x403,24)[4:20]+bytes.fromhex('12345678'),
                'endmagic_401_44':b'\x00\x00\x00\x00'+framed_native(0x401,44)[4:40]+bytes.fromhex('12345678'),
                'proper_401_36':framed_native(0x401,36),
                'authentic_401_44':authentic_native_frame(0x401,44),
                'authentic_401_44_seq0':authentic_native_frame(0x401,44,0),
                'authentic_403_28':authentic_native_frame(0x403,28),
                'authentic_402_44':authentic_native_frame(0x402,44),
                'proper_401_36_seq0':framed_native(0x401,36,0),
                'proper_403_24':framed_native(0x403,24),
                'proper_402_48':framed_native(0x402,48),
                'proper_400_20':framed_native(0x400,20),
                'zero4':bytes(4),
                'zero8':bytes(8),
                'status8':struct.pack('!II',3,1),
                'little8':struct.pack('<II',8,1),
                'zero16':bytes(16),
                'marker16':struct.pack('<IIII',16,1,0,0),
                'lenbe8':struct.pack('!II',8,0),
                'nf1_header1':struct.pack('<IHH',0xE01B74F2,1,0),
                'nf1_header3':struct.pack('<IHH',0xE01B74F2,3,0),
                'nf1_payload1':struct.pack('<IHHB',0xE01B74F2,1,1,0),
                'nf1_payload4':struct.pack('<IHHI',0xE01B74F2,1,4,0),
                'nf1_payload8':struct.pack('<IHHII',0xE01B74F2,1,8,0,0),
                'nf1_payload10':struct.pack('<IHH',0xE01B74F2,1,10)+bytes(10),
                'nf1_payload12':struct.pack('<IHH',0xE01B74F2,1,12)+bytes(12),
                'nf1_payload16':struct.pack('<IHH',0xE01B74F2,1,16)+bytes(16),
                'zero18':bytes(18),
                'zero24':bytes(24),
                'zero32':bytes(32),
            }
            greeting=packets.get(preset,b'')
            log('MAIN_GREETING mode='+preset+' length='+str(len(greeting))+' hex='+greeting.hex())
            if greeting:
                time.sleep(.2)
                try:c.sendall(greeting)
                except Exception as ex:log('MAIN_GREETING_SEND_FAILED '+repr(ex))
        c.settimeout(26 if port==11100 else 8)
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
