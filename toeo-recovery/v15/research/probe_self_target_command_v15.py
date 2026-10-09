"""Run the original no-argument /target handler outside a game process."""
import argparse,json,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('source_dir');p.add_argument('--out',required=True);a=p.parse_args()
    sys.path.insert(0,str(Path(a.source_dir).resolve()))
    from emulate_item_use import UseFixture
    from world_npc_packets import parse_npc_request
    f=UseFixture(a.binary);text=0x10ee000;f.uc.mem_write(text,b'\0\0')
    f.invoke(0x4c68c0,(0,text))
    request=parse_npc_request(f.sent[-1])
    assert request['target']==(1,1) and not f.assertions
    result={'passed':True,'native_handler':'4C68C0','command':'/target (no argument)',
        'native_request':request,'assertions':f.assertions,
        'substitutions':'Inherited initialized world, transport queue and entity lookups; native command parse and target construction unchanged',
        'windows_verified':False}
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('ORIGINAL_SELF_TARGET_COMMAND_PASS')

if __name__=='__main__':main()
