"""
minidump.py - Le um UE4Minidump.dmp (formato MDMP do Windows) sem dependencias.

Uso: python minidump.py <arquivo.dmp | pasta do crash>   (sem argumento: o crash mais recente)

Mostra a excecao (codigo, endereco, modulo+offset), o thread que falhou e uma "pilha
heuristica": valores na pilha desse thread que apontam para codigo de modulos carregados
(exe do jogo, DBFZSlots.asi, UE4SS.dll...). Para o exe, o offset e o RVA usado nas ferramentas
de tools/re (disasm.py etc.).
"""
import os
import struct
import sys
from pathlib import Path

# a copia modificada usa saves proprios (slots.ini [user] separate_saves); procura nas duas pastas
CRASH_DIRS = [Path(__file__).resolve().parent.parent / "game" / "UserData" / "DBFighterZ" / "Saved" / "Crashes",
              Path(os.environ.get("LOCALAPPDATA", "")) / "DBFighterZ" / "Saved" / "Crashes"]
EXC_NAMES = {0xC0000005: "ACCESS_VIOLATION", 0xC000001D: "ILLEGAL_INSTRUCTION", 0x80000003: "BREAKPOINT",
             0xC0000094: "INT_DIVIDE_BY_ZERO", 0xC00000FD: "STACK_OVERFLOW", 0xC0000409: "STACK_BUFFER_OVERRUN"}


def read_dump(path):
    d = Path(path).read_bytes()
    sig, ver, nstreams, dir_rva = struct.unpack_from("<IIII", d, 0)
    if sig != 0x504D444D:
        raise SystemExit("nao e um minidump")
    streams = {}
    for i in range(nstreams):
        t, size, rva = struct.unpack_from("<III", d, dir_rva + 12 * i)
        streams[t] = (size, rva)
    return d, streams


def mdstring(d, rva):
    n, = struct.unpack_from("<I", d, rva)
    return d[rva + 4:rva + 4 + n].decode("utf-16le", "replace")


def modules(d, streams):
    size, rva = streams[4]
    n, = struct.unpack_from("<I", d, rva)
    out = []
    for i in range(n):
        o = rva + 4 + 108 * i
        base, msize = struct.unpack_from("<QI", d, o)
        name_rva, = struct.unpack_from("<I", d, o + 20)
        out.append((base, msize, mdstring(d, name_rva)))
    return out


def where(mods, addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{Path(name).name}+0x{addr - base:x}"
    return None


def memory(d, streams):
    regions = []
    if 5 in streams:                       # MemoryListStream
        size, rva = streams[5]
        n, = struct.unpack_from("<I", d, rva)
        for i in range(n):
            start, dsize, drva = struct.unpack_from("<QII", d, rva + 4 + 16 * i)
            regions.append((start, dsize, drva))
    return regions


def read_mem(d, regions, addr, n):
    for start, size, rva in regions:
        if start <= addr and addr + n <= start + size:
            return d[rva + addr - start:rva + addr - start + n]
    return None


def analyze(path):
    d, streams = read_dump(path)
    mods = modules(d, streams)
    regions = memory(d, streams)
    print(f"minidump: {path}")
    if 6 not in streams:
        print("sem informacao de excecao")
        return
    size, rva = streams[6]
    tid, = struct.unpack_from("<I", d, rva)
    code, flags = struct.unpack_from("<II", d, rva + 8)
    addr, = struct.unpack_from("<Q", d, rva + 24)
    nparams, = struct.unpack_from("<I", d, rva + 32)
    params = struct.unpack_from(f"<{min(nparams, 15)}Q", d, rva + 40) if nparams else ()
    print(f"excecao 0x{code:08x} ({EXC_NAMES.get(code, '?')}) em 0x{addr:x} = {where(mods, addr) or 'fora de modulo'}")
    if code == 0xC0000005 and len(params) >= 2:
        print(f"   {'leitura' if params[0] == 0 else 'escrita' if params[0] == 1 else 'execucao'} do endereco 0x{params[1]:x}")
    ctx_size, ctx_rva = struct.unpack_from("<II", d, rva + 160)
    if ctx_size >= 0x4D0:
        regs = dict(zip(["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi", "r8", "r9", "r10", "r11",
                         "r12", "r13", "r14", "r15"], struct.unpack_from("<16Q", d, ctx_rva + 0x78)))
        rip, = struct.unpack_from("<Q", d, ctx_rva + 0xF8)
        print("   registros: " + " ".join(f"{k}={v:x}" for k, v in regs.items()))
        rsp = regs["rsp"]
        stack = read_mem(d, regions, rsp, 0x2000)
        if stack:
            print("pilha (enderecos de codigo encontrados, do topo para baixo):")
            shown = 0
            for i in range(0, len(stack) - 7, 8):
                v, = struct.unpack_from("<Q", stack, i)
                w = where(mods, v)
                if w and not w.lower().startswith(("ntdll", "kernel", "kernelbase", "ucrtbase", "msvcp", "vcruntime")):
                    print(f"   rsp+0x{i:04x}: {w}")
                    shown += 1
                    if shown >= 40:
                        break
    print("modulos relevantes:")
    for base, size, name in mods:
        if any(k in name.lower() for k in ("red-win64", "dbfzslots", "ue4ss", "dsound", "opengl32", ".asi")):
            print(f"   0x{base:x} {size:#x} {name}")


def main():
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.is_dir():
            p = p / "UE4Minidump.dmp"
    else:
        dumps = sorted((d for c in CRASH_DIRS for d in c.glob("*/UE4Minidump.dmp")), key=lambda x: x.stat().st_mtime)
        if not dumps:
            raise SystemExit("nenhum crash encontrado")
        p = dumps[-1]
    analyze(p)


if __name__ == "__main__":
    main()
