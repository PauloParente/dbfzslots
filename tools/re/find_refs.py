"""Acha strings (UTF-16 ou ASCII) / floats no exe e as instrucoes que as referenciam."""
import re, struct, sys
from pe import PE
from xrefs import rip_xrefs

def find_bytes(p, needle):
    out = []
    for m in re.finditer(re.escape(needle), p.data):
        rva = p.off_to_rva(m.start())
        if rva is not None:
            out.append(rva)
    return out

def wide(s):
    return s.encode("utf-16le") + b"\0\0"

if __name__ == "__main__":
    p = PE(r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping.exe")
    for s in sys.argv[1:]:
        rvas = find_bytes(p, wide(s)) or find_bytes(p, s.encode() + b"\0")
        print(f"'{s[:60]}': {[hex(r) for r in rvas]}")
        for r in rvas:
            for ins, b, dest in rip_xrefs(p, r):
                print(f"    xref {ins:#x}: {b.hex(' ')}")
