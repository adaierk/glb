"""Assemble original client + sealed cumulative v21 + a portable interpreter.

No local account database, screenshots or developer interpreter is packaged.
All input files are supplied before this script runs; the output never downloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

SHA21 = '989dcb4f0718e74593bc86d0ffb155c881fbd05d580261f83812f1ae0dc4dc52'
SHAEXE = '635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--v21', required=True)
    p.add_argument('--original-raw', required=True)
    p.add_argument('--python', required=True)
    p.add_argument('--wheels', required=True)
    p.add_argument('--client-archive')
    p.add_argument('--sevenzip')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    out = Path(a.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Build destination must be empty')
    out.mkdir(parents=True, exist_ok=True)
    if sha(a.v21) != SHA21:
        raise ValueError('Sealed v21 ZIP hash mismatch')
    with zipfile.ZipFile(a.v21) as z:
        if z.testzip(): raise ValueError('Corrupt v21 archive')
        for item in z.infolist():
            parts = Path(item.filename).parts
            if len(parts) > 1 and not item.is_dir():
                target = out.joinpath(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(item))
    # Replace development entry points with the same bundled runtime.
    for old in out.glob('*.cmd'): old.unlink()
    source = Path(__file__).resolve().parent
    shutil.copy2(source / 'launcher.py', out / 'launcher.py')
    runtime = out / 'runtime' / 'python'
    runtime.mkdir(parents=True)
    with zipfile.ZipFile(a.python) as z: z.extractall(runtime)
    site = runtime / 'Lib' / 'site-packages'
    site.mkdir(parents=True)
    wheels = sorted(Path(a.wheels).glob('*.whl'))
    if not any(x.name.startswith('frida-') for x in wheels): raise ValueError('Frida wheel missing')
    if not any(x.name.startswith('pillow-') for x in wheels): raise ValueError('Pillow wheel missing')
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as z: z.extractall(site)
    pth = list(runtime.glob('python*._pth'))
    if len(pth) != 1: raise ValueError('Embedded Python path file not found')
    version = pth[0].stem
    pth[0].write_text(version + '.zip\n.\nLib/site-packages\n../../toeo-tests\n../..\nimport site\n', encoding='utf-8')
    game = out / 'original_game'
    game.mkdir()
    raw = Path(a.original_raw)
    for name in ['NewComponent1', 'DefaultComponent']:
        if (raw/name).is_dir(): shutil.copytree(raw/name, game, dirs_exist_ok=True)
    (game/'data').mkdir(exist_ok=True)
    for name in ['resource', 'map', 'ui', 'help']:
        if (game/name).is_dir(): shutil.move(str(game/name), str(game/'data'/name))
    if sha(game/'ToEO_CL.dat') != SHAEXE: raise ValueError('Original client hash mismatch')
    for name in ['log', 'userdata']: (game/name).mkdir(exist_ok=True)
    # Screenshots are an explicit separate deliverable. Normal play captures none.
    runner = out/'toeo-tests'/'run_session_bootstrap.py'
    original_runner = runner.read_text(encoding='utf-8')
    changed = original_runner.replace("    def capture(label):\n", "    def capture(label):\n        return  # Portable play sessions do not capture the desktop.\n", 1)
    if changed == original_runner: raise ValueError('Capture guard location changed')
    runner.write_text(changed, encoding='utf-8')
    commands = {'Start_TOEO.cmd': '', 'Run_Map_Only.cmd': '--map-only'}
    template = '@echo off\r\nsetlocal\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\nif not exist "%~dp0runtime\\python\\python.exe" (\r\n  echo 请先完整解压压缩包，然后再启动游戏。\r\n  pause\r\n  exit /b 1\r\n)\r\n"%~dp0runtime\\python\\python.exe" -u "%~dp0launcher.py" {args} %*\r\nif errorlevel 1 pause\r\n'
    for name, args in commands.items():
        (out/name).write_bytes(template.replace('{args}', args).encode('utf-8'))
    readme = '''永恒传说 OL v21 完整整合版（Windows 10/11 64 位）

【启动】
1. 把整个 ZIP 解压到一个可写文件夹，例如 D:\\Games\\TOEO_v21。
2. 双击 Start_TOEO.cmd。首次启动自动展开完整客户端并生成图像兼容缓存。
3. 原版窗口出现后，按开始、同意、选择服务器和登录的原版流程进入。
   账号：archive001    密码：local123
4. 选择 Archive 角色进入拉修安地图。请保留黑色启动窗口。

已内置原客户端全部资源、截至 v21 的累计修复、Python、Frida、Pillow 和解压程序。
不需要安装 Python、7-Zip，不需要运行 pip，不需要另找旧版补丁或客户端。
启动过程不下载资源、不改系统区域设置、不要求管理员权限。
双击的是启动脚本，请不要直接运行 original_game 内的历史联网启动器。

【本版内容】
本地登录与角色、原版拉修安地图、移动、NPC 商店、买卖、背包、道具、HP 显示、
装备穿脱与外观、保存与重进，以及原版遭遇、选敌、接近敌人和普通攻击动作。
默认开启 v21 已有的本地装备样品和测试敌人。它们不是已考证的正式游戏配置。
只想体验地图与商店时，双击 Run_Map_Only.cmd；两种入口共用同一份存档。

【当前阶段限制】
完整整合指已发布修复全部内置。游戏仍处于恢复阶段。
伤害、技能、敌人 AI、胜负、奖励及战斗结束返回地图仍未完成。
进入测试战斗后需要退出并重新启动回到地图。所有地图、NPC 和主支线未完整恢复。

【存档与退出】
存档位于 local_world_userdata。首次启动自动建立，不附带开发者测试存档。
如果已有旧存档：关闭所有游戏与本地服务，先备份，然后把原有整个
local_world_userdata 文件夹复制到本整合包的同名位置。不要覆盖成空文件夹。
正常关闭游戏窗口，本地服务会随之结束。请勿在服务运行中搬动存档。
图像兼容缓存 toeo_runtime_cache_v16 可重新生成，不是存档。

【排错】
文件必须完整解压；请勿在压缩包预览中启动。
如果提示本地端口占用，先关闭上一份游戏和启动窗口。
启动失败会显示错误并保存 launcher_error.txt。保留该文件便于定位问题。
关闭启动窗口会终止本次会话；正常退出请先关闭原版游戏窗口。

原客户端与原有资源保留；图像兼容处理在单独缓存中进行。
游戏原始可执行文件 SHA256：
635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55
'''
    (out/'开始前请读.txt').write_text(readme, encoding='utf-8-sig')
    (out/'local_world_userdata').mkdir(exist_ok=True)
    manifest = {'edition': 'v21-full-portable', 'sealed_v21_sha256': SHA21,
                'original_executable_sha256': SHAEXE,
                'inputs': {Path(a.python).name: sha(a.python), **{x.name: sha(x) for x in wheels}},
                'source': 'e7d200534533b3331c182b86bfeed3a2cf5b9be2',
                'changes_from_v21': ['Bundled original resources and portable runtime',
                    'Portable start entry points', 'Desktop capture disabled for normal play'],
                'complete_game': False}
    if a.client_archive:
        if not a.sevenzip: raise ValueError('Bundled 7-Zip path required')
        archive = Path(a.client_archive)
        (out/'assets').mkdir()
        shutil.copy2(archive, out/'assets/client_pack.7z')
        shutil.copytree(a.sevenzip, out/'runtime/7zip')
        shutil.rmtree(game)
        manifest['packed_client_sha256'] = sha(archive)
        manifest['client_storage'] = 'Bundled archive; automatic local extraction on first launch'
    (out/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    forbidden = list(out.rglob('*.sqlite')) + list(out.rglob('*.pyc'))
    if forbidden: raise ValueError('User database or bytecode in clean package: '+str(forbidden))
    print(json.dumps({'out': str(out), 'files': sum(x.is_file() for x in out.rglob('*')),
                      'bytes': sum(x.stat().st_size for x in out.rglob('*') if x.is_file())}, indent=2))


if __name__ == '__main__': main()
