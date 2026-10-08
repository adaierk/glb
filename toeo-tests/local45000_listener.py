import socket,time,datetime,sys
from pathlib import Path
out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
def log(x):
 with out.open('a',encoding='utf8') as f:f.write(datetime.datetime.now().isoformat(timespec='seconds')+' '+x+'\n')
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('127.0.0.1',45000));s.listen(6);s.settimeout(2)
log('listening on 127.0.0.1:45000')
end=time.time()+140
while time.time()<end:
 try:c,addr=s.accept()
 except socket.timeout:continue
 log('ACCEPT '+str(addr))
 c.settimeout(7)
 with c:
  for _ in range(8):
   try:b=c.recv(8192)
   except socket.timeout:
    log('read timeout');break
   except Exception as e:log('read error '+repr(e));break
   if not b:log('peer closed');break
   log('RECV bytes='+str(len(b))+' hex='+b[:512].hex())
 log('session ended')
s.close()
