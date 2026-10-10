"""Run the original Windows game against the recovered local server."""
import argparse
import hashlib
import json
import os
import queue
import shutil
import sys
import threading
import time
from pathlib import Path
from session_bootstrap_server import BootstrapServer

SHA='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('game_directory',nargs='?')
    p.add_argument('--duration',type=int,default=0,help='Seconds to run; 0 keeps the game open until the player exits')
    p.add_argument('--out',default='session_bootstrap_report')
    p.add_argument('--local-account',action='store_true',help='Use recovered login and persistent character create/list/delete protocol')
    p.add_argument('--local-world','--world-route-probe',dest='world_route_probe',action='store_true',help='Load the recovered local map channel; requires --local-account')
    p.add_argument('--demo-character',action='store_true',help='Create Archive only if the local account has no characters')
    p.add_argument('--shop-preview',action='store_true',help='Preview sourced historical goods on the local diagnostic merchant; original merchant placement and item templates are still pending')
    p.add_argument('--world-profile',choices=('forest','rashuan'),default='forest',help='Original map and sourced merchant profile')
    args=p.parse_args()
    if args.world_route_probe and not args.local_account:p.error('--world-route-probe requires --local-account')
    if args.demo_character and not args.local_account:p.error('--demo-character requires --local-account')
    if args.shop_preview and not args.world_route_probe:p.error('--shop-preview requires --local-world')
    if args.world_profile!='forest' and not args.world_route_probe:p.error('--world-profile requires --local-world')
    if args.duration<0:p.error('--duration cannot be negative')
    if os.name!='nt':raise SystemExit('The graphical client runner requires Windows.')
    import frida
    from PIL import ImageGrab
    prepared=Path(__file__).resolve().parents[1]/'original_game'
    if not args.game_directory and (prepared/'ToEO_CL.dat').is_file():args.game_directory=str(prepared)
    if not args.game_directory:
        import tkinter
        from tkinter import filedialog
        root=tkinter.Tk();root.withdraw()
        selected=filedialog.askdirectory(title='Select the original TOEO game directory')
        root.destroy()
        if not selected:raise SystemExit('No game directory selected.')
        args.game_directory=selected
    game=Path(args.game_directory).resolve()
    binary=game/'ToEO_CL.dat'
    if not binary.is_file():raise SystemExit('ToEO_CL.dat was not found in the game directory.')
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=SHA:
        raise SystemExit('Client binary does not match the original version; native address hooks are disabled.')
    required=['resource/icon_item.icd','resource/cid0.idt']
    from world_profiles import world_profile
    profile=world_profile(args.world_profile)
    if args.world_route_probe:required+=[f'map/{profile.map_id:07x}.'+suffix for suffix in ('mpi','mpd','bnd')]
    missing=[n for n in required if not (game/'data'/n).is_file()]
    if missing:raise SystemExit('Corrected original data directory is missing required files: '+str(missing))
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if args.local_account:
        from legacy_graphics_assets import prepare_render_client
        game=prepare_render_client(game,out.parent/'toeo_runtime_cache_v16',out/'graphics_assets_manifest.json')
        binary=game/'ToEO_CL.dat'
    exe=game/('ToEO_CL_local_login_probe.exe' if args.local_account else 'ToEO_CL_session_probe.exe')
    if exe.exists():raise SystemExit('Temporary probe EXE already exists; use a directory without that filename.')
    shutil.copyfile(binary,exe)
    if args.local_account:
        from local_account_server import LocalAccountServer
        server=LocalAccountServer(out,world_route_probe=args.world_route_probe,shop_preview=args.shop_preview,world_profile=profile)
        if args.demo_character and not server.characters.list(1):
            from character_mutation_packets import create_character_request
            server.characters.create(1,create_character_request('Archive'))
    else:server=BootstrapServer(out)
    events=[];observed_names=set();native_exceptions=[];client_closed=threading.Event()
    captures=[];capture_queue=queue.SimpleQueue();captured_stages=set()
    def capture(label):
        filename=f'original_client_{len(captures)+1:03d}_{label}.png'
        try:
            ImageGrab.grab().save(out/filename)
            captures.append({'file':filename,'stage':label,'time':time.time(),'scope':'Windows desktop; original client may be obscured'})
        except OSError as error:
            captures.append({'stage':label,'error':str(error),'time':time.time()})
    def capture_stages():
        while True:
            try:label=capture_queue.get_nowait()
            except queue.Empty:break
            if label not in captured_stages:
                captured_stages.add(label);capture(label)
    device=frida.get_local_device();pid=None;session=None
    with (out/'runtime.jsonl').open('w',encoding='utf-8',buffering=1) as log:
        def on_message(message,data):
            item=message.get('payload',message) if message.get('type')=='send' else {'event':'frida_error','message':message}
            observed_names.add(item.get('event'))
            if item.get('event')=='native_exception' and len(native_exceptions)<30:native_exceptions.append(item)
            if str(item.get('event','')).endswith('_NATIVE'):
                capture_queue.put(item['event'])
            if len(events)<1000:events.append(item)
            log.write(json.dumps(item,ensure_ascii=False,default=str)+'\n')
        try:
            server.start()
            pid=device.spawn([str(exe)],cwd=str(game))
            session=device.attach(pid)
            session.on('detached',lambda reason,crash:client_closed.set())
            source=Path(__file__).with_name('bootstrap_runtime.js').read_text(encoding='utf-8')
            if args.local_account:
                source+='\n'+Path(__file__).with_name('account_runtime.js').read_text(encoding='utf-8')
                source+='\n'+Path(__file__).with_name('offline_socket_compat.js').read_text(encoding='utf-8')
                source+='\n'+Path(__file__).with_name('offline_graphics_compat.js').read_text(encoding='utf-8')
            script=session.create_script(source)
            script.on('message',on_message);script.load()
            ready_deadline=time.monotonic()+5
            ready_event='offline_socket_compat_ready' if args.local_account else 'runtime_probe_ready'
            while ready_event not in observed_names and time.monotonic()<ready_deadline:
                time.sleep(.05)
            if ready_event not in observed_names:
                raise RuntimeError('Loopback hooks failed; original client remains suspended.')
            device.resume(pid)
            print('Use the original Start/agreement/world/login controls. Test ID: archive001; password: local123.',flush=True)
            if args.local_account:
                print('Local login and persistent character create/list/delete are enabled.',flush=True)
            if args.world_route_probe:
                print(f'Local world enabled: original map {profile.map_id:07x} / {profile.label}; merchant {profile.merchant_grid}.',flush=True)
            print('Close the game or press Ctrl+C here to end the local session.',flush=True)
            second=0
            while not client_closed.is_set() and (args.duration==0 or second<args.duration):
                if client_closed.wait(1):break
                second+=1
                capture_stages()
                if (second%15==0 and second<=180) or second%300==0:capture(f'{second:03d}s')
        except KeyboardInterrupt:
            print('Stopped; saving native observations.',flush=True)
        finally:
            capture_stages()
            (out/'screenshots.json').write_text(json.dumps(captures,indent=2),encoding='utf-8')
            result={'native_session_created':any(e.get('event')=='OWN_SESSION_CREATED_NATIVE' for e in events),
                    'account_handler_observed':any(e.get('event')=='ACCOUNT_LOGIN_HANDLER_ENTER' for e in events),
                    'account_authenticated':True if any(e.get('event')=='ACCOUNT_AUTHENTICATED_NATIVE' for e in events) else None,
                    'game_prelogin_accepted':True if any(e.get('event')=='GAME_PRELOGIN_ACCEPTED_NATIVE' for e in events) else None,
                    'character_list_accepted':True if any(e.get('event')=='CHARACTER_LIST_ACCEPTED_NATIVE' for e in events) else None,
                    'character_created':True if any(e.get('event')=='CHARACTER_CREATED_NATIVE' for e in events) else None,
                    'character_deleted':True if any(e.get('event')=='CHARACTER_DELETED_NATIVE' for e in events) else None,
                    'character_selection_accepted':True if any(e.get('event')=='CHARACTER_SELECTION_ACCEPTED_NATIVE' for e in events) else None,
                    'world_route_observed':True if any(e.get('event')=='WORLD_ROUTE_CONVERSION_ENTERED_NATIVE' for e in events) else None,
                    'world_admission_accepted':True if any(e.get('event')=='WORLD_ADMISSION_ACK_ACCEPTED_NATIVE' for e in events) else None,
                    'world_account_id_request_observed':True if any(e.get('event')=='WORLD_ACCOUNT_ID_REQUEST_OBSERVED_NATIVE' for e in events) else None,
                    'world_controller_completed':True if any(e.get('event')=='WORLD_CONTROLLER_COMPLETED_NATIVE' for e in events) else None,
                    'map_entered':None,'playable':None,
                    'note':'Only observed original-code events count as success. Map/playability are not inferred.',
                    'native_exceptions':native_exceptions}
            (out/'runtime_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result,indent=2),flush=True)
            if pid is not None:
                try:device.kill(pid)
                except Exception:pass
            if session is not None:
                try:session.detach()
                except Exception:pass
            server.close()
            try:exe.unlink()
            except OSError:pass


if __name__=='__main__':main()
