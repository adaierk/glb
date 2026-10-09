"""Reproduce the local TCP and original-binary protocol checks in one command."""
import argparse
import importlib
import json
import unittest
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('binary',nargs='?',help='Original ToEO_CL.dat; omit for stdlib TCP tests only')
    p.add_argument('--out',default='native_protocol_report')
    a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in
                            ('test_session_bootstrap','test_local_account_server'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'passed':result.wasSuccessful(),'tcp_tests':result.testsRun,'native_checks':{}}
    if not result.wasSuccessful():raise SystemExit(1)
    if a.binary:
        for name in ('session_bootstrap','account_login','account_transport','game_login',
                     'character_list','character_select','character_mutation','character_fields','world_route','world_admission','world_handoff','world_completion'):
            r=importlib.import_module('emulate_'+name).run(a.binary)
            assert r['passed']
            (out/('native_'+name+'.json')).write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
            report['native_checks'][name]=True
        from test_local_account_server import verify_native_socket_roundtrip
        r=verify_native_socket_roundtrip(a.binary)
        (out/'native_tcp_roundtrip.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
        report['native_checks']['real_tcp_roundtrip']=r['passed']
        from test_local_account_server import verify_native_character_roundtrip
        r=verify_native_character_roundtrip(a.binary)
        (out/'native_character_tcp_roundtrip.json').write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
        report['native_checks']['persistent_character_tcp_roundtrip']=r['passed']
        from test_local_account_server import verify_native_world_admission_roundtrip
        r=verify_native_world_admission_roundtrip(a.binary)
        (out/'native_world_admission_tcp_roundtrip.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
        report['native_checks']['world_admission_tcp_roundtrip']=r['passed']
        from test_local_account_server import verify_native_selection_admission_roundtrip
        r=verify_native_selection_admission_roundtrip(a.binary)
        (out/'native_selection_admission_tcp_roundtrip.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
        report['native_checks']['selection_admission_tcp_roundtrip']=r['passed']
        from test_local_account_server import verify_native_world_completion_roundtrip
        r=verify_native_world_completion_roundtrip(a.binary)
        (out/'native_world_completion_tcp_roundtrip.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
        report['native_checks']['world_completion_tcp_roundtrip']=r['passed']
    report['windows_runtime_tested']=False
    report['playable_world_verified']=False
    (out/'verification_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
