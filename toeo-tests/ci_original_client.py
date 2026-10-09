"""Exercise the original Windows GUI against the recovered loopback server.

UI input uses actual mouse/keyboard controls. Captures are the Windows desktop;
native observations and screenshots are preserved without inferred map success.
"""
import argparse,ctypes,faulthandler,hashlib,json,os,shutil,time,traceback
from pathlib import Path
from local_account_server import LocalAccountServer
from character_mutation_packets import create_character_request

SHA='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'

def main():
    p=argparse.ArgumentParser();p.add_argument('game');p.add_argument('out')
    p.add_argument('--duration',type=int,default=180);p.add_argument('--pump',action='store_true')
    args=p.parse_args()
    if os.name!='nt':raise SystemExit('Windows original-client verification required')
    import frida
    from PIL import ImageGrab
    game=Path(args.game).resolve();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    diagnostic=(out/'python_threads.txt').open('w',encoding='utf-8');faulthandler.enable(diagnostic);faulthandler.dump_traceback_later(45,repeat=True,file=diagnostic)
    original=game/'ToEO_CL.dat'
    if hashlib.sha256(original.read_bytes()).hexdigest()!=SHA:raise SystemExit('Original SHA mismatch')
    exe=game/'ToEO_CL_local_ci.exe';shutil.copyfile(original,exe)
    server=LocalAccountServer(out,world_route_probe=True)
    if not server.characters.list(1):server.characters.create(1,create_character_request('Archive'))
    events=[];shots=[];device=frida.get_local_device();pid=None;session=None
    u=ctypes.windll.user32
    def click(x,y,right=False):
        u.SetCursorPos(x,y);time.sleep(.15);u.mouse_event(8 if right else 2,0,0,0,0);time.sleep(.90);u.mouse_event(16 if right else 4,0,0,0,0);time.sleep(.35)
        events.append({'event':'actual_ui_click','x':x,'y':y,'right':right,'host_time':time.time()});print('PHASE actual_ui_click '+str((x,y)),flush=True)
    def type_text(s):
        for c in s:
            vk=ord(c.upper());u.keybd_event(vk,0,0,0);u.keybd_event(vk,0,2,0);time.sleep(.04)
    with (out/'runtime.jsonl').open('w',encoding='utf-8',buffering=1) as log:
        def receive(m,data):
            row=m.get('payload',m) if m.get('type')=='send' else {'event':'frida_error','detail':m}
            row['host_time']=time.time();events.append(row);log.write(json.dumps(row,ensure_ascii=False,default=str)+'\n')
            if row.get('event','').endswith('_NATIVE') or row.get('event') in ('native_exception','frida_error'):
                print(json.dumps(row,ensure_ascii=False),flush=True)
        def shot(t):
            path=out/f'original_desktop_{t:03d}s.png';ImageGrab.grab().save(path)
            shots.append({'file':path.name,'elapsed':t,'scope':'actual Windows desktop'})
        try:
            print('PHASE server_start',flush=True);server.start()
            print('PHASE original_spawn',flush=True);pid=device.spawn([str(exe)],cwd=str(game))
            print('PHASE original_attach pid='+str(pid),flush=True);session=device.attach(pid)
            session.on('detached',lambda reason,crash: receive({'type':'send','payload':{'event':'detached','reason':reason,'crash':str(crash)}},None))
            source='\n'.join(Path(__file__).with_name(n).read_text(encoding='utf-8') for n in
                             ('bootstrap_runtime.js','account_runtime.js','offline_socket_compat.js'))
            if args.pump:source+='\n'+Path(__file__).with_name('native_gui_pump.js').read_text(encoding='utf-8')
            print('PHASE native_hooks_load',flush=True)
            script=session.create_script(source);script.on('message',receive);script.load()
            print('PHASE hooks_loaded',flush=True)
            deadline=time.monotonic()+5
            while not any(e.get('event')=='offline_socket_compat_ready' for e in events) and time.monotonic()<deadline:time.sleep(.05)
            if not any(e.get('event')=='offline_socket_compat_ready' for e in events):raise RuntimeError('Hook readiness failed')
            print('PHASE original_resume',flush=True);device.resume(pid)
            print('PHASE original_gui_running',flush=True)
            schedule={34:lambda:click(408,447),45:lambda:click(218,534),
                      78:lambda:click(360,299),82:lambda:click(340,391),
                      92:lambda:(click(380,290),type_text('archive001')),
                      96:lambda:(click(380,336),type_text('local123')),100:lambda:click(315,405),
                      115:lambda:click(325,150),120:lambda:click(700,447),
                      125:lambda:(click(323,303),click(323,324),click(450,376)),
                      130:lambda:click(450,376),
                      135:lambda:click(700,447),
                      150:lambda:click(360,180),160:lambda:click(620,160),170:lambda:click(400,200,True)}
            for t in range(args.duration):
                time.sleep(1)
                if t in schedule:schedule[t]()
                if t%10==0 or t in (101,107,121,136):shot(t);print('PHASE screenshot '+str(t),flush=True)
        except Exception:
            (out/'python_error.txt').write_text(traceback.format_exc(),encoding='utf-8');traceback.print_exc()
        finally:
            try:shot(args.duration)
            except Exception:pass
            (out/'screenshots.json').write_text(json.dumps(shots,indent=2),encoding='utf-8')
            names={e.get('event') for e in events}
            result={key:True if value in names else None for key,value in
                    [('native_session_created','OWN_SESSION_CREATED_NATIVE'),('account_authenticated','ACCOUNT_AUTHENTICATED_NATIVE'),
                     ('game_prelogin_accepted','GAME_PRELOGIN_ACCEPTED_NATIVE'),('character_list_accepted','CHARACTER_LIST_ACCEPTED_NATIVE'),
                     ('character_selection_accepted','CHARACTER_SELECTION_ACCEPTED_NATIVE'),('world_admission_accepted','WORLD_ADMISSION_ACK_ACCEPTED_NATIVE'),
                     ('world_controller_completed','WORLD_CONTROLLER_COMPLETED_NATIVE')]}
            result.update(map_entered=None,playable=None,native_exceptions=[e for e in events if e.get('event')=='native_exception'])
            (out/'runtime_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
            if pid is not None:
                try:device.kill(pid)
                except Exception:pass
            if session is not None:
                try:session.detach()
                except Exception:pass
            server.close();faulthandler.cancel_dump_traceback_later();diagnostic.close()
            for retry in range(30):
                try:exe.unlink(missing_ok=True);break
                except PermissionError:time.sleep(.1)

if __name__=='__main__':main()
