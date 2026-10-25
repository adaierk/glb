"""Portable entry point for the sealed TOEO v21 recovery, Windows x64."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import traceback

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'toeo-tests'))
ORIGINAL_SHA = '635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'


def check():
    if os.name != 'nt' or sys.maxsize <= 2**32:
        raise RuntimeError('This package requires 64-bit Windows 10 or Windows 11.')
    import frida
    from PIL import Image, ImageGrab
    import sqlite3
    from world_profiles import world_profile
    from prepare_original_client import validate
    validate(ROOT / 'original_game')
    p = world_profile('rashuan')
    for ext in ['mpi', 'mpd', 'bnd']:
        if not (ROOT / 'original_game' / 'data' / 'map' / f'{p.map_id:07x}.{ext}').is_file():
            raise RuntimeError('The full client was not extracted completely.')
    ctypes.WinDLL('d3d9.dll')
    return {'python': sys.version, 'frida': frida.__version__, 'pillow': Image.__version__,
            'sqlite': sqlite3.sqlite_version, 'client_sha256': ORIGINAL_SHA, 'result': 'PASS'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--map-only', action='store_true')
    a = p.parse_args()
    os.chdir(ROOT)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    info = check()
    if a.check:
        print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
        return
    # A kernel-owned lock is automatically released even after an interrupted run.
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    k.CreateMutexW.restype = ctypes.c_void_p
    handle = k.CreateMutexW(None, False, 'Local\\TOEO_Recovery_v21_LocalServer')
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        k.CloseHandle(handle)
        raise RuntimeError('TOEO is already running. Close the first game and launcher before starting again.')
    try:
        for port in [11100, 11101, 45000, 45001, 45002]:
            with socket.socket() as s:
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Local port {port} is in use. Close the previous TOEO session and retry.')
        userdata = ROOT / 'local_world_userdata'
        userdata.mkdir(exist_ok=True)
        # Test archives contain no user database. Never copy over an existing save.
        (userdata / '.write_check').write_bytes(b'')
        (userdata / '.write_check').unlink()
        print('永恒传说 OL v21 完整整合版', flush=True)
        print('账号 archive001    密码 local123', flush=True)
        print('首次启动会准备图像兼容缓存，请等待原版窗口出现。', flush=True)
        print('保留此窗口；退出游戏后本地服务会自动关闭。', flush=True)
        print('当前战斗支持选敌、移动和普通攻击动作，尚无伤害与结算。', flush=True)
        import run_session_bootstrap
        sys.argv = ['run_session_bootstrap.py', str(ROOT / 'original_game'),
                    '--local-account', '--local-world', '--demo-character',
                    '--world-profile', 'rashuan', '--duration', '0',
                    '--out', str(userdata), '--equipment-preview']
        if not a.map_only:
            sys.argv.append('--combat-preview')
        run_session_bootstrap.main()
    finally:
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        k.CloseHandle(handle)


if __name__ == '__main__':
    try:
        main()
    except (Exception, SystemExit) as e:
        if isinstance(e, SystemExit) and e.code in (None, 0):
            raise
        detail = traceback.format_exc()
        log = ROOT / 'launcher_error.txt'
        try:
            log.write_text(detail, encoding='utf-8')
        except OSError:
            pass
        print(detail, file=sys.stderr, flush=True)
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, '启动失败：' + str(e) + '\n\n错误详情：' + str(log),
                                           '永恒传说 OL v21', 0x10)
        sys.exit(1)
