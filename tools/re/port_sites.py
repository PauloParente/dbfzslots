"""Porta RVAs de uma build para outra usando assinaturas de contexto geradas automaticamente.

Para cada RVA: desmonta ~N bytes antes e depois, troca por curinga os campos que dependem
do layout (rel32 de call/jmp/jcc e disp32 RIP-relativos) e procura o padrao na outra build.
Se o padrao nao for unico, aumenta o contexto.
"""
import re, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
from pe import PE
from check_sites import SITES

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def masked_bytes(p, start, end):
    """bytes de [start,end) desmontados a partir de start; retorna lista de (byte|None)."""
    code = p.read(start, end - start + 16)
    out = []
    for ins in md.disasm(code, start):
        if ins.address >= end:
            break
        b = list(ins.bytes)
        mask = [False] * len(b)
        # rip-relativo: disp32 nos 4 bytes do deslocamento
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                off = ins.disp_offset
                for k in range(off, off + 4):
                    mask[k] = True
        # call/jmp/jcc com rel32
        if ins.group(1) or ins.group(7) or ins.mnemonic.startswith("j") or ins.mnemonic == "call":
            if ins.imm_size == 4 or (len(b) >= 5 and ins.imm_offset and ins.imm_size == 4):
                off = ins.imm_offset
                for k in range(off, off + 4):
                    mask[k] = True
        out.extend(None if m else v for v, m in zip(b, mask))
    return out

def to_regex(mb):
    return re.compile(b"".join(b"." if v is None else re.escape(bytes([v])) for v in mb), re.S)

def find_all(p, rx, limit=3):
    hits = []
    for name, va, vs, raw, rs, ch in p.sections:
        if not ch & 0x20000000:
            continue
        for m in rx.finditer(p.data, raw, raw + rs):
            hits.append(va + m.start() - raw)
            if len(hits) >= limit:
                return hits
    return hits

def instr_start_before(p, rva, back):
    """inicio de instrucao alinhado ~back bytes antes de rva (re-sincroniza desmontagem)."""
    for s in range(rva - back, rva):
        cur = s
        for ins in md.disasm(p.read(s, back + 16), s):
            if cur == rva:
                return s
            if ins.address != cur:
                break
            cur += ins.size
            if cur == rva:
                return s
            if cur > rva:
                break
    return rva

def port(src, dst, rva):
    for before, after in ((0, 24), (16, 24), (32, 32), (48, 48), (96, 64)):
        start = instr_start_before(src, rva, before) if before else rva
        mb = masked_bytes(src, start, rva + after)
        fixed = sum(v is not None for v in mb)
        if fixed < 10:
            continue
        hits = find_all(dst, to_regex(mb))
        if len(hits) == 1:
            return hits[0] + (rva - start), before, after
        if not hits:
            return None, before, after
    return "ambiguo", before, after

if __name__ == "__main__":
    src = PE(r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping.exe")
    dst = PE(r"C:\dbfz modded\game\RED\Binaries\Win64\RED-Win64-Shipping-eac-nop-loaded.exe")
    for name, rva, hexb in SITES:
        if name.startswith("chara_table"):
            continue
        new, b, a = port(src, dst, rva)
        same = ""
        if isinstance(new, int):
            nb = dst.read(new, len(bytes.fromhex(hexb)))
            same = "bytes iguais" if nb == bytes.fromhex(hexb) else f"bytes {nb.hex()}"
            print(f"{name:26} {rva:#09x} -> {new:#09x}  (delta {new - rva:+#x}) {same}")
        else:
            print(f"{name:26} {rva:#09x} -> {new}")
