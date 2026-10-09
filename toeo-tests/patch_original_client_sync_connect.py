#!/usr/bin/env python3
"""Experimental offline-only TOEO original PE32 localhost sync-connect compatibility patch.
Exact original 2006 client SHA required. Never overwrite original or existing destination.
Fix is specifically for a localhost TCP connect returning success (0), not 10035.
Not an authentication bypass or server emulator.
"""
import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_SHA256 = "635ac4fd8ccd95f4700def5ad791a6feaf555d38f7dc4f64a38850ccca321d55"
TARGET_VA = 0x0060873B
EXPECTED = bytes.fromhex("3d33270000740a")
PATCHED = bytes.fromhex("3d00000000740a")

def original_rva_to_offset(data, va):
    if data[:2] != b"MZ":
        raise ValueError("Invalid MZ header")
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if data[pe:pe+4] != b"PE\x00\x00":
        raise ValueError("Invalid PE header")
    section_count = struct.unpack_from("<H", data, pe+6)[0]
    opt_size = struct.unpack_from("<H", data, pe+20)[0]
    opt = pe+24
    if struct.unpack_from("<H",data,opt)[0]!=0x10b:
        raise ValueError("Expected original PE32, not PE32+")
    base = struct.unpack_from("<I",data,opt+28)[0]
    rva = va-base
    for i in range(section_count):
        s=opt+opt_size+i*40
        vsize,vaddr,rsize,rptr=struct.unpack_from("<IIII",data,s+8)
        if vaddr<=rva<vaddr+max(vsize,rsize):
            return rptr+(rva-vaddr)
    raise ValueError("Original code VA was not mapped")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("original",type=Path)
    a.add_argument("--output",type=Path,required=True)
    a.add_argument("--dry-run",action="store_true")
    args=a.parse_args()
    raw=args.original.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=EXPECTED_SHA256:
        raise SystemExit("Refusing to patch unrecognized TOEO executable: "+sha)
    off=original_rva_to_offset(raw,TARGET_VA)
    if raw[off:off+len(EXPECTED)]!=EXPECTED:
        raise SystemExit("Refusing to patch unexpected opcode at "+hex(off))
    diff=bytearray(raw)
    diff[off:off+len(EXPECTED)]=PATCHED
    assert sum(x!=y for x,y in zip(raw,diff))==2
    print("original_sha256="+sha)
    print("target_file_offset="+hex(off))
    print("patched_sha256="+hashlib.sha256(diff).hexdigest())
    print("warning=local/offline only; replaces old 10035-accepted branch with successful-0-accepted branch")
    print("warning=does not restore login auth, characters, maps, or game servers")
    if args.dry_run:
        print("dry_run_ok")
        return
    if args.output.resolve()==args.original.resolve() or args.output.exists():
        raise SystemExit("Refusing to overwrite original or existing output")
    args.output.write_bytes(diff)
    print("saved="+str(args.output))

if __name__=="__main__":
    main()
