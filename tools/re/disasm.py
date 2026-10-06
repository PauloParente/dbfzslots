"""Desmonta um trecho do exe: python dis.py <rva_inicio> [n_bytes] [--exe caminho]"""
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from pe import PE

DEFAULT_EXE = r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping.exe"
_md = Cs(CS_ARCH_X86, CS_MODE_64)
_pe_cache = {}

def get_pe(path=DEFAULT_EXE):
    if path not in _pe_cache:
        _pe_cache[path] = PE(path)
    return _pe_cache[path]

def dis(rva, n=0x80, p=None, mark=None):
    p = p or get_pe()
    code = p.read(rva, n)
    out = []
    for ins in _md.disasm(code, rva):
        tag = " <==" if mark is not None and ins.address == mark else ""
        out.append(f"{ins.address:#09x}: {ins.bytes.hex(' '):<32} {ins.mnemonic} {ins.op_str}{tag}")
    return "\n".join(out)

def func_start(rva, p=None, back=0x2000):
    """Heuristica: procura para tras um padding 'cc' ou 'c3' seguido de inicio de funcao."""
    p = p or get_pe()
    b = p.read(rva - back, back)
    i = len(b) - 1
    while i > 0:
        if b[i - 1] in (0xCC, 0xC3) and b[i] != 0xCC and (b[i - 1] == 0xCC or b[i - 2] in (0xCC,)):
            return rva - back + i
        i -= 1
    return None

if __name__ == "__main__":
    a = int(sys.argv[1], 16)
    n = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x80
    print(dis(a, n))


def grep(start, end, pattern, p=None):
    """Desmonta [start, end) linearmente e devolve linhas cujo texto casa com o regex."""
    import re as _re
    p = p or get_pe()
    rx = _re.compile(pattern)
    code = p.read(start, end - start)
    out = []
    off = 0
    while off < len(code):
        got = False
        for ins in _md.disasm(code[off:], start + off):
            txt = f"{ins.mnemonic} {ins.op_str}"
            if rx.search(txt):
                out.append(f"{ins.address:#09x}: {ins.bytes.hex(' '):<28} {txt}")
            off = ins.address + ins.size - start
            got = True
        if not got or off < len(code):
            off += 1  # byte invalido: pula e continua
    return out
