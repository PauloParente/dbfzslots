"""Acha instrucoes com operando RIP-relativo apontando para um RVA (lea/mov/cmp [rip+disp32])."""
import re, struct, sys
from pe import PE

def code_sections(p):
    return [s for s in p.sections if s[5] & 0x20000000]  # IMAGE_SCN_MEM_EXECUTE

def rip_xrefs(p, target_rva, slack=0):
    """Retorna (rva_instrucao, bytes) para cada disp32 cujo destino cai em [target, target+slack]."""
    d = p.data
    hits = []
    # ModRM com mod=00 rm=101 => [rip+disp32]
    pat = re.compile(rb"[\x40-\x4F]?[\x8B\x8D\x89\x3B\x39\x03\x2B\x33\x0F]?[\x8B\x8D\x89\x3B\x39\x03\x2B\x33\xB6\xB7\x10\x11\x28\x29][\x05\x0D\x15\x1D\x25\x2D\x35\x3D]", re.S)
    for name, va, vs, raw, rs, ch in code_sections(p):
        sec = d[raw:raw + rs]
        for m in pat.finditer(sec):
            dpos = m.end()
            if dpos + 4 > len(sec):
                continue
            disp = struct.unpack_from("<i", sec, dpos)[0]
            # tamanho da instrucao = ate o fim do disp (sem imediato) — ok p/ lea/mov/cmp reg
            insn_end_rva = va + dpos + 4
            dest = insn_end_rva + disp
            if target_rva <= dest <= target_rva + slack:
                hits.append((va + m.start(), bytes(sec[m.start():dpos + 4]), dest))
    return hits

if __name__ == "__main__":
    p = PE(sys.argv[1])
    t = int(sys.argv[2], 16)
    slack = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0
    for rva, b, dest in rip_xrefs(p, t, slack):
        print(f"{rva:#x}: {b.hex(' ')}  -> {dest:#x}")
