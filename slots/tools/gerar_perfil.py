"""
gerar_perfil.py - Gera o perfil.txt do plugin para um exe que nao tem perfil compilado.

Uso: python gerar_perfil.py <exe alvo> <saida perfil.txt> [--ref-exe exe] [--ref-perfil txt]

Parte de um perfil de referencia (o eac-nop compilado, exportado pelo plugin) e do exe dele, e
porta cada ponto para o exe alvo por ASSINATURA DE CONTEXTO: os bytes ao redor do ponto, com
curinga so nos campos que mudam entre builds (rel32 de call/jmp/jcc, disp32 RIP-relativo,
enderecos absolutos de dados e as constantes do tamanho do elenco). Opcodes e registradores
nao tem curinga: se uma build trocar o registrador que uma cave usa, a assinatura nao casa e o
gerador recusa (em vez de gerar um perfil que quebraria o jogo). A assinatura cresce ate ser
unica no exe alvo.

Enderecos de dados (tabelas, objetos globais) e de funcoes do motor saem das instrucoes que os
referenciam, ja portadas. Contagens (personagens, tabelas da mascara, icones) sao lidas do alvo.
O plugin ainda confere cada byte antes de escrever (profile_matches), entao um perfil errado e
recusado no jogo, nunca aplicado.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "re"))
from pe import PE                     # noqa: E402
from xrefs import rip_xrefs           # noqa: E402
from callers import callers           # noqa: E402

sys.path.insert(0, str(HERE))
from caminhos import EXE as REF_EXE  # noqa: E402
MD = Cs(CS_ARCH_X86, CS_MODE_64)
MD.detail = True
ROSTER_IMM = range(0x20, 0x41)        # constantes de contagem de personagens/icones/mascara


class PortError(Exception):
    pass


# ---- perfil em texto --------------------------------------------------------------------------

def read_profile(path):
    prof = {"fields": {}, "sites": {}, "t": {}, "vs_t": None, "icon_ops": []}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith((";", "#")):
            continue
        if s.startswith("site "):
            m = re.match(r"site (\w+) = 0x([0-9A-Fa-f]+) ([0-9a-fA-F]+)$", s)
            prof["sites"][m.group(1)] = (int(m.group(2), 16), m.group(3).lower())
        elif s.startswith("t "):
            m = re.match(r"t (\w+) = 0x([0-9A-Fa-f]+)$", s)
            prof["t"][m.group(1)] = int(m.group(2), 16)
        else:
            k, v = [x.strip() for x in s.split("=", 1)]
            if k == "vs_t":
                prof["vs_t"] = [int(x, 16) for x in v.split()]
            elif k == "icon_op":
                rva, hx, kind, off, ln = v.split()
                prof["icon_ops"].append((int(rva, 16), hx.lower(), kind, int(off), int(ln)))
            else:
                prof["fields"][k] = v
    return prof


def write_profile(prof, path, header):
    out = [f"; {h}" for h in header]
    order = ["name", "table_entries", "mask_main", "mask_alt", "mask_extra_first", "restore_code",
             "restore_region", "chara_table", "mask_main_tab", "mask_alt_tab", "static_find", "static_load",
             "texture_class", "announce_obj", "icon_base_count", "icon_table", "guobjectarray",
             "restore_present_index"]
    for k in order:
        if k in prof["fields"]:
            out.append(f"{k} = {prof['fields'][k]}")
    for k, (rva, hx) in prof["sites"].items():
        out.append(f"site {k} = 0x{rva:X} {hx}")
    for k, v in prof["t"].items():
        out.append(f"t {k} = 0x{v:X}")
    if prof["vs_t"]:
        out.append("vs_t = " + " ".join(f"0x{x:X}" for x in prof["vs_t"]))
    for rva, hx, kind, off, ln in prof["icon_ops"]:
        out.append(f"icon_op = 0x{rva:X} {hx} {kind} {off} {ln}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


# ---- assinaturas ------------------------------------------------------------------------------

def insns(p, start, end):
    code = p.read(start, end - start + 16)
    out = []
    for ins in MD.disasm(code, start):
        if ins.address >= end:
            break
        out.append(ins)
    return out


def masked(ins, context=False):
    """bytes da instrucao com None nos campos que mudam entre builds. No contexto (para achar o
    lugar) todo disp32 e curinga (deslocamentos de estrutura mudam quando arrays por personagem
    crescem); nos bytes do ponto (estrito) so RIP-relativos e enderecos absolutos."""
    b = list(ins.bytes)
    wild = set()
    if ins.disp_size == 4:
        for op in ins.operands:
            if op.type == X86_OP_MEM and (context or op.mem.base == X86_REG_RIP or abs(op.mem.disp) >= 0x10000):
                wild.update(range(ins.disp_offset, ins.disp_offset + 4))
    if ins.imm_size:
        imm_is_rel = ins.mnemonic == "call" or ins.mnemonic.startswith("j")
        for op in ins.operands:
            if op.type == X86_OP_IMM:
                v = op.imm & 0xFFFFFFFF
                if imm_is_rel or v in ROSTER_IMM or v >= 0x10000:
                    wild.update(range(ins.imm_offset, ins.imm_offset + ins.imm_size))
    return [None if i in wild else v for i, v in enumerate(b)]


def aligned_start(p, rva, back):
    """inicio de instrucao ~back bytes antes de rva cuja desmontagem passa exatamente por rva."""
    for s in range(rva - back, rva + 1):
        cur = s
        for ins in MD.disasm(p.read(s, back + 32), s):
            if cur >= rva:
                break
            cur += ins.size
        if cur == rva:
            return s
    return rva


def find_all(p, rx, limit=8):
    hits = []
    for name, va, vs, raw, rs, ch in p.sections:
        if not ch & 0x20000000:
            continue
        for m in rx.finditer(p.data, raw, raw + rs):
            hits.append(va + m.start() - raw)
            if len(hits) > limit:
                return hits
    return hits


WINDOWS = ((0, 24), (16, 24), (0, 40), (32, 40), (0, 64), (48, 64), (0, 96), (80, 96), (0, 128), (128, 128), (192, 192),
           (24, 8), (40, 8), (64, 8), (96, 8))       # so o que vem antes (o depois mudou)
# bytes que podem variar porque o plugin trata as variantes: setup_u e "mov REG,[rax+r10*4] /
# cmp REG,MAX" com REG = r14d (eac-nop) ou r13d (shipping); offsets relativos ao ponto
VARIANT = {"setup_u": {2, -2}}


def port_rva(ref, tgt, rva, what, extra_wild=frozenset(), order_only=False):
    """RVA equivalente no alvo. A assinatura cresce ate casar uma vez so no ref e no alvo; codigo
    duplicado (ex. funcoes gemeas de 1P/2P) que nunca fica unico e mapeado pela ordem: se o
    padrao aparece o mesmo numero de vezes nos dois, a k-esima ocorrencia corresponde a k-esima."""
    by_order, found = None, False
    for back, fwd in WINDOWS:
        s = aligned_start(ref, rva, back) if back else rva
        mb = []
        for ins in insns(ref, s, rva + fwd):
            mb.extend(masked(ins, context=True))
        for k in extra_wild:
            if 0 <= rva - s + k < len(mb):
                mb[rva - s + k] = None
        rx = re.compile(b"".join(b"." if v is None else re.escape(bytes([v])) for v in mb), re.S)
        rh, th = find_all(ref, rx), find_all(tgt, rx)
        if not th:
            continue
        found = True
        if len(rh) == 1 and len(th) == 1 and not order_only:
            return th[0] + (rva - s)
        if len(rh) == len(th) and len(rh) > 1 and s in rh and len(rh) <= 8 and by_order is None:
            by_order = th[rh.index(s)] + (rva - s)
    if by_order is not None:
        return by_order
    if not found:
        raise PortError(f"{what} (+0x{rva:X}): signature not found in this exe (different code)")
    raise PortError(f"{what} (+0x{rva:X}): ambiguous signature in this exe")


# pontos cujo disp32 de estrutura o plugin le dos bytes do proprio exe (pode mudar)
DISP_FROM_BYTES = {"po_a1", "po_a2", "po_b1", "po_b2"}


def same_shape(ref, tgt, r_rva, t_rva, n, name=""):
    """os n bytes do ponto: mesmas instrucoes, mesmos registradores (so constantes que o plugin
    recalcula, alvos de salto e enderecos mudam)."""
    a, b = insns(ref, r_rva, r_rva + n), insns(tgt, t_rva, t_rva + n)
    if sum(i.size for i in a) != n or sum(i.size for i in b) != n or len(a) != len(b):
        return False
    ma = [v for x in a for v in masked(x, context=name in DISP_FROM_BYTES)]
    mb = [v for x in b for v in masked(x, context=name in DISP_FROM_BYTES)]
    for k in VARIANT.get(name, ()):
        if 0 <= k < len(ma):
            ma[k] = mb[k] = None
    return ma == mb


def rip_target(p, rva):
    for ins in MD.disasm(p.read(rva, 16), rva):
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                return ins.address + ins.size + op.mem.disp
        break
    raise PortError(f"+0x{rva:X} has no RIP-relative operand")


def call_target(p, rva):
    b = p.read(rva, 5)
    if b[0] != 0xE8:
        raise PortError(f"+0x{rva:X} is not a rel32 call")
    return rva + 5 + struct.unpack_from("<i", b, 1)[0]


def chara_codes(p, table):
    codes = []
    for i in range(80):
        ptr = struct.unpack_from("<Q", p.read(table + 16 * i + 8, 8))[0]
        rva = ptr - p.image_base
        try:
            s = p.read(rva, 16).decode("utf-16le").split("\0")[0]
        except Exception:
            break
        if not re.fullmatch(r"[A-Z]{3}", s):
            break
        codes.append(s)
        if s == "DMY":
            break
    return codes


# ---- gerador ----------------------------------------------------------------------------------

def generate(tgt_path, ref_exe=REF_EXE, ref_prof_path=None):
    ref, tgt = PE(str(ref_exe)), PE(str(tgt_path))
    if ref_prof_path is None:
        sys.path.insert(0, str(HERE))
        import tempfile
        from exportar_perfil import export
        ref_prof_path = Path(tempfile.gettempdir()) / "dbfz_perfil_ref.txt"
        export(0, ref_prof_path)
    rp = read_profile(ref_prof_path)
    out = {"fields": {}, "sites": {}, "t": {}, "vs_t": None, "icon_ops": []}
    problems = []

    def site(name, r_rva, hx, order_only=False):
        t_rva = port_rva(ref, tgt, r_rva, name, frozenset(VARIANT.get(name, ())), order_only)
        n = len(hx) // 2
        if not same_shape(ref, tgt, r_rva, t_rva, n, name):
            raise PortError(f"{name}: instrucoes do ponto diferentes no alvo")
        return t_rva, tgt.read(t_rva, n).hex()

    for name, (r_rva, hx) in rp["sites"].items():
        try:
            out["sites"][name] = site(name, r_rva, hx)
        except PortError as e:
            problems.append(str(e))
    # codigo gemeo (1P/2P): dois pontos diferentes nunca podem cair no mesmo endereco. Se cair,
    # refaz os dois so pela ordem das ocorrencias (k-esima no ref = k-esima no alvo)
    by_addr = {}
    for name, (t_rva, _) in out["sites"].items():
        by_addr.setdefault(t_rva, []).append(name)
    for names in [v for v in by_addr.values() if len(v) > 1]:
        for name in names:
            r_rva, hx = rp["sites"][name]
            try:
                out["sites"][name] = site(name, r_rva, hx, order_only=True)
            except PortError as e:
                problems.append(f"{name}: codigo gemeo sem correspondencia segura ({e})")
    seen = {}
    for name, (t_rva, _) in out["sites"].items():
        if t_rva in seen:
            problems.append(f"{name} e {seen[t_rva]} caem no mesmo endereco +0x{t_rva:X}")
        seen[t_rva] = name
    # destinos: quando no ref o destino e o fim do ponto ou o alvo de um salto dentro dele, aplica
    # a mesma relacao nos bytes do alvo (mais robusto que assinatura); senao, assinatura
    sites_ref = [(r, len(h) // 2, out["sites"].get(k, (None,))[0]) for k, (r, h) in rp["sites"].items()]

    def derive(r_dest):
        for r_site, n, t_site in sites_ref:
            if t_site is None or not (r_site <= r_dest <= r_site + n + 0x400 or r_site - 0x400 <= r_dest <= r_site):
                continue
            if r_dest == r_site + n:
                return t_site + n
            ra = insns(ref, r_site, r_site + n)
            ta = insns(tgt, t_site, t_site + n)
            for x, y in zip(ra, ta):
                if (x.mnemonic.startswith("j") or x.mnemonic == "call") and x.operands and x.operands[0].type == X86_OP_IMM:
                    if x.operands[0].imm == r_dest and y.mnemonic == x.mnemonic:
                        return y.operands[0].imm
        return None

    def port_dest(r_dest, what):
        d = derive(r_dest)
        return d if d is not None else port_rva(ref, tgt, r_dest, what)

    for name, r_rva in rp["t"].items():
        try:
            out["t"][name] = port_dest(r_rva, "destino " + name)
        except PortError as e:
            problems.append(str(e))
    if rp["vs_t"]:
        try:
            out["vs_t"] = [port_dest(x, "destino VS") for x in rp["vs_t"]]
        except PortError as e:
            problems.append(str(e))
    for r_rva, hx, kind, off, ln in rp["icon_ops"]:
        try:
            t_rva, thx = site(f"icone {kind}", r_rva, hx)
            out["icon_ops"].append((t_rva, thx, kind, off, ln))
        except PortError as e:
            problems.append(str(e))
    icon_addrs = [o[0] for o in out["icon_ops"]]
    if len(set(icon_addrs)) != len(icon_addrs):
        problems.append("pontos de icone repetidos no alvo")
    if problems:
        raise PortError("pontos que nao foi possivel portar:\n  " + "\n  ".join(problems))

    S, F, f = out["sites"], out["fields"], rp["fields"]
    # enderecos de dados: das instrucoes que os referenciam
    F["chara_table"] = f"0x{rip_target(tgt, S['idtocode_lea'][0]):X}"
    F["mask_main_tab"] = f"0x{rip_target(tgt, S['m_main_lea'][0]):X}"
    F["mask_alt_tab"] = f"0x{rip_target(tgt, S['m_alt_lea'][0]):X}"
    F["static_find"] = f"0x{call_target(tgt, S['portrait1'][0]):X}"

    def ported_ref_of(data_rva, what):
        hits = rip_xrefs(ref, data_rva)
        for ins_rva, _, _ in hits[:6]:
            try:
                return rip_target(tgt, port_rva(ref, tgt, ins_rva, what))
            except PortError:
                continue
        raise PortError(f"{what}: nenhuma referencia portavel")

    def ported_call_of(fn_rva, what):
        for c in callers(ref, [fn_rva])[fn_rva][:6]:
            try:
                return call_target(tgt, port_rva(ref, tgt, c, what))
            except PortError:
                continue
        raise PortError(f"{what}: nenhuma chamada portavel")

    F["static_load"] = f"0x{ported_call_of(int(f['static_load'], 16), 'StaticLoadObject'):X}"
    F["texture_class"] = f"0x{ported_call_of(int(f['texture_class'], 16), 'UTexture2D::StaticClass'):X}"
    F["announce_obj"] = f"0x{ported_ref_of(int(f['announce_obj'], 16), 'objeto do anuncio'):X}"
    if "guobjectarray" in f and int(f["guobjectarray"], 16):
        F["guobjectarray"] = f"0x{ported_ref_of(int(f['guobjectarray'], 16), 'GUObjectArray'):X}"
    if out["icon_ops"]:
        rip_ops = [o for o in out["icon_ops"] if o[2] == "TABLE_RIP"]
        F["icon_table"] = f"0x{rip_target(tgt, rip_ops[0][0]):X}"

    # contagens lidas do alvo
    codes = chara_codes(tgt, int(F["chara_table"], 16))
    if not codes or codes[0] != "GKS" or codes[-1] != "DMY":
        raise PortError("tabela de personagens do alvo nao comeca em GKS / termina em DMY")
    n = len(codes)
    F["table_entries"] = str(n)
    F["mask_main"] = str(tgt.read(S["m_main_cmp"][0] + 2, 1)[0])
    F["mask_alt"] = str(tgt.read(S["m_alt_cmp"][0] + 2, 1)[0])
    F["mask_extra_first"] = f["mask_extra_first"]            # regioes da mascara dos paks atuais
    if out["icon_ops"]:
        cnt = [o for o in out["icon_ops"] if o[2] == "COUNT_IMM8"][0]
        F["icon_base_count"] = str(tgt.read(cnt[0] + cnt[3], 1)[0])
    # personagem dos paks que falta nesta build (Goku SSJ4 Daima nas builds de 47)
    if "DGF" not in codes:
        F["restore_code"], F["restore_region"] = "DGF", f.get("restore_region", "44")
        F["restore_present_index"] = f.get("restore_present_index", "46")
    sz = tgt.data[:0x400]
    e = struct.unpack_from("<I", sz, 0x3C)[0]
    stamp = struct.unpack_from("<I", sz, e + 8)[0]
    F["name"] = f"gerado ({Path(tgt_path).name}, carimbo 0x{stamp:08X}, {n} personagens)"
    return out, [f"gerado por gerar_perfil.py a partir de {Path(ref_exe).name}",
                 f"alvo: {Path(tgt_path).name}, {Path(tgt_path).stat().st_size} bytes, carimbo 0x{stamp:08X}"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("out")
    ap.add_argument("--ref-exe", default=str(REF_EXE))
    ap.add_argument("--ref-perfil")
    a = ap.parse_args()
    try:
        prof, header = generate(a.exe, a.ref_exe, a.ref_perfil)
    except PortError as e:
        raise SystemExit(f"NAO foi possivel gerar o perfil: {e}")
    write_profile(prof, a.out, header)
    print(f"{a.out}: {len(prof['sites'])} pontos, {len(prof['t'])} destinos, {len(prof['icon_ops'])} pontos de icone, "
          f"{prof['fields']['table_entries']} personagens")


if __name__ == "__main__":
    main()
