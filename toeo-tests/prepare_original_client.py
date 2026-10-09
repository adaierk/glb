"""Restore the measured original installation layout into a separate folder."""
import argparse,hashlib,os,shutil,subprocess,tempfile,zipfile
from pathlib import Path

SHA='635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55'

def validate(game):
    binary=game/'ToEO_CL.dat'
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=SHA:
        raise ValueError('Original ToEO_CL.dat version mismatch')
    for item in ['resource/icon_item.icd','resource/cid0.idt']+['map/1110101.'+x for x in ('mpi','mpd','bnd')]:
        if not (game/'data'/item).is_file():raise ValueError('Missing original data/'+item)

def main():
    p=argparse.ArgumentParser();p.add_argument('archive',nargs='?')
    p.add_argument('--out',default=str(Path(__file__).resolve().parents[1]/'original_game'))
    a=p.parse_args()
    if not a.archive:
        import tkinter
        from tkinter import filedialog
        root=tkinter.Tk();root.withdraw()
        a.archive=filedialog.askopenfilename(title='Select TOEO_Original_Client_Full.zip or client_pack.7z',filetypes=[('Original client archive','*.zip *.7z')])
        root.destroy()
        if not a.archive:raise SystemExit('No archive selected')
    archive=Path(a.archive).resolve();game=Path(a.out).resolve()
    if game.exists() and any(game.iterdir()):
        validate(game);print('Existing original game is ready: '+str(game));return
    executable=shutil.which('7z')
    if not executable:
        candidate=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'7-Zip'/'7z.exe'
        if candidate.is_file():executable=str(candidate)
    if not executable:raise SystemExit('7-Zip is required to unpack client_pack.7z. Install it and run this preparation again.')
    with tempfile.TemporaryDirectory(prefix='toeo-original-') as temporary:
        base=Path(temporary);packed=archive
        if archive.suffix.lower()=='.zip':
            with zipfile.ZipFile(archive) as z:
                entries=[n for n in z.namelist() if Path(n).name=='client_pack.7z']
                if len(entries)!=1:raise ValueError('Expected exactly one client_pack.7z')
                packed=base/'client_pack.7z'
                with z.open(entries[0]) as src,packed.open('wb') as dst:shutil.copyfileobj(src,dst)
        raw=base/'raw';raw.mkdir()
        subprocess.run([executable,'x','-y','-o'+str(raw),str(packed)],check=True,stdout=subprocess.DEVNULL)
        staged=base/'game';staged.mkdir()
        for component in ['NewComponent1','DefaultComponent']:
            if (raw/component).is_dir():shutil.copytree(raw/component,staged,dirs_exist_ok=True)
        (staged/'data').mkdir(exist_ok=True)
        for component in ['resource','map','ui','help']:
            if (staged/component).is_dir():shutil.move(str(staged/component),str(staged/'data'/component))
        for component in ['log','userdata']:(staged/component).mkdir(exist_ok=True)
        validate(staged)
        shutil.copytree(staged,game,dirs_exist_ok=True)
    print('Original game is ready: '+str(game))

if __name__=='__main__':main()
