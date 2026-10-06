"""
assinaturas.py - Banco de assinaturas do plugin: gera o perfil de qualquer exe SEM o exe de referencia.

Fase 1 (aqui, uma vez):  python assinaturas.py criar <exe de referencia> <saida.json>
    Le o perfil compilado do exe de referencia e grava, para cada ponto, as assinaturas de
    contexto (bytes com curinga em tudo que muda entre builds), o formato estrito dos bytes do
    ponto, como achar cada destino de salto e cada endereco de dados/funcao. Sao trechos curtos
    de padroes de bytes ("sig scan"), nao o executavel.
Fase 2 (no PC de quem instala): python assinaturas.py aplicar <db.json> <exe alvo> <perfil.txt>
    Acha cada ponto no exe alvo, confere o formato estrito, calcula destinos/enderecos e
    contagens e grava o perfil.txt. Recusa (sem gerar nada) se algo nao casar com seguranca.

Regras (as mesmas validadas no gerar_perfil.py): a assinatura cresce ate ser unica; codigo
gemeo (1P/2P) e resolvido pela ordem das ocorrencias; dois pontos nunca caem no mesmo endereco;
destinos que sao o fim do ponto ou o alvo de um salto dentro dele vem dos bytes do alvo.
"""
import json
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gerar_perfil as G                    # noqa: E402
from gerar_perfil import PortError, insns, masked, aligned_start, find_all, X86_OP_IMM  # noqa: E402

FORMAT = 1


def pat_of(mb):
    return "".join("??" if v is None else f"{v:02x}" for v in mb)


def rx_of(pat):
    return re.compile(b"".join(b"." if pat[i:i + 2] == "??" else re.escape(bytes.fromhex(pat[i:i + 2]))
                               for i in range(0, len(pat), 2)), re.S)


# ---- fase 1 -----------------------------------------------------------------------------------

def windows(ref, rva, extra_wild=()):
    out = []
    for back, fwd in G.WINDOWS:
        s = aligned_start(ref, rva, back) if back else rva
        mb = []
        for ins in insns(ref, s, rva + fwd):
            mb.extend(masked(ins, context=True))
        for k in extra_wild:
            if 0 <= rva - s + k < len(mb):
                mb[rva - s + k] = None
        pat = pat_of(mb)
        rh = find_all(ref, rx_of(pat))
        out.append({"p": pat, "o": rva - s, "n": len(rh), "i": rh.index(s) if s in rh else -1})
    return out


def strict_of(ref, rva, n, name):
    ctx = name in G.DISP_FROM_BYTES
    out = [pat_of(masked(i, context=ctx)) for i in insns(ref, rva, rva + n)]
    flat = "".join(out)
    for k in G.VARIANT.get(name, ()):
        if 0 <= k < n:
            flat = flat[:2 * k] + "??" + flat[2 * k + 2:]
    return flat


def build_db(ref_exe, ref_profile):
    ref = G.PE(str(ref_exe))
    rp = G.read_profile(ref_profile)
    db = {"formato": FORMAT, "criado": time.strftime("%Y-%m-%d"), "referencia": Path(ref_exe).name,
          "sites": {}, "t": {}, "vs_t": None, "icon_ops": [], "campos": {}, "constantes": {}}
    for name, (rva, hx) in rp["sites"].items():
        n = len(hx) // 2
        db["sites"][name] = {"len": n, "estrito": strict_of(ref, rva, n, name),
                             "janelas": windows(ref, rva, G.VARIANT.get(name, ()))}
    for i, (rva, hx, kind, off, ln) in enumerate(rp["icon_ops"]):
        n = len(hx) // 2
        db["icon_ops"].append({"kind": kind, "off": off, "len": ln, "n": n, "estrito": strict_of(ref, rva, n, ""),
                               "janelas": windows(ref, rva)})
    sites = [(k, r, len(h) // 2) for k, (r, h) in rp["sites"].items()]

    def relation(dest):
        for k, r, n in sites:
            if dest == r + n:
                return {"fim_de": k}
        for k, r, n in sites:
            for idx, ins in enumerate(insns(ref, r, r + n)):
                if (ins.mnemonic.startswith("j") or ins.mnemonic == "call") and ins.operands and \
                        ins.operands[0].type == X86_OP_IMM and ins.operands[0].imm == dest:
                    return {"salto_de": k, "instrucao": idx}
        return {"janelas": windows(ref, dest)}
    for name, rva in rp["t"].items():
        db["t"][name] = relation(rva)
    if rp["vs_t"]:
        db["vs_t"] = [relation(x) for x in rp["vs_t"]]

    f = rp["fields"]
    C = db["campos"]
    C["chara_table"] = {"rip_de": "idtocode_lea"}
    C["mask_main_tab"] = {"rip_de": "m_main_lea"}
    C["mask_alt_tab"] = {"rip_de": "m_alt_lea"}
    C["static_find"] = {"call_de": "portrait1"}
    for k in ("static_load", "texture_class"):
        cs = G.callers(ref, [int(f[k], 16)])[int(f[k], 16)][:4]
        C[k] = {"call_em": [windows(ref, c) for c in cs]}
    for k in ("announce_obj", "guobjectarray"):
        if k in f and int(f[k], 16):
            xs = [h[0] for h in G.rip_xrefs(ref, int(f[k], 16))[:4]]
            C[k] = {"rip_em": [windows(ref, x) for x in xs]}
    db["constantes"] = {k: f[k] for k in ("mask_extra_first", "restore_region", "restore_present_index") if k in f}
    return db


# ---- fase 2 -----------------------------------------------------------------------------------

def locate(tgt, wins, what, order_only=False):
    by_order, found = None, False
    for w in wins:
        th = find_all(tgt, rx_of(w["p"]))
        if not th:
            continue
        found = True
        if w["n"] == 1 and len(th) == 1 and not order_only:
            return th[0] + w["o"]
        if 1 < w["n"] == len(th) <= 8 and w["i"] >= 0 and by_order is None:
            by_order = th[w["i"]] + w["o"]
    if by_order is not None:
        return by_order
    raise PortError(f"{what}: {'ambiguous signature' if found else 'different code (signature not found)'}")


def check_strict(tgt, rva, n, strict, what):
    ins = insns(tgt, rva, rva + n)
    if sum(i.size for i in ins) != n:
        raise PortError(f"{what}: patch point instructions have a different size")
    ctx = what in G.DISP_FROM_BYTES
    have = "".join(pat_of(masked(i, context=ctx)) for i in ins)
    hb = [have[i:i + 2] for i in range(0, len(have), 2)]
    sb = [strict[i:i + 2] for i in range(0, len(strict), 2)]
    # byte a byte: curinga do banco aceita qualquer coisa; fora dele, o alvo tem que ter o mesmo
    # byte (e o mesmo curinga nos campos variaveis: rel32, RIP, constantes do elenco)
    if len(hb) != len(sb) or any(b != "??" and a != b for a, b in zip(hb, sb)):
        raise PortError(f"{what}: patch point instructions differ in this exe")


def apply_db(db, tgt_path):
    if db.get("formato") != FORMAT:
        raise PortError("signature database has another format")
    tgt = G.PE(str(tgt_path))
    out = {"fields": {}, "sites": {}, "t": {}, "vs_t": None, "icon_ops": []}
    problems = []

    def site(name, e, order_only=False):
        rva = locate(tgt, e["janelas"], name, order_only)
        n = e.get("len", e.get("n"))
        check_strict(tgt, rva, n, e["estrito"], name)
        return rva, tgt.read(rva, n).hex()

    for name, e in db["sites"].items():
        try:
            out["sites"][name] = site(name, e)
        except PortError as ex:
            problems.append(str(ex))
    by_addr = {}
    for name, (r, _) in out["sites"].items():
        by_addr.setdefault(r, []).append(name)
    for names in [v for v in by_addr.values() if len(v) > 1]:
        for name in names:
            try:
                out["sites"][name] = site(name, db["sites"][name], order_only=True)
            except PortError as ex:
                problems.append(f"{name}: twin code without a safe match ({ex})")
    seen = {}
    for name, (r, _) in out["sites"].items():
        if r in seen:
            problems.append(f"{name} and {seen[r]} land on the same address +0x{r:X}")
        seen[r] = name
    for e in db["icon_ops"]:
        try:
            r, hx = site(f"icon {e['kind']}", e)
            out["icon_ops"].append((r, hx, e["kind"], e["off"], e["len"]))
        except PortError as ex:
            problems.append(str(ex))
    if len({o[0] for o in out["icon_ops"]}) != len(out["icon_ops"]):
        problems.append("repeated icon points in this exe")
    if problems:
        raise PortError("patch points that could not be found:\n  " + "\n  ".join(problems))

    S = out["sites"]

    def dest(rel, what):
        if "fim_de" in rel:
            k = rel["fim_de"]
            return S[k][0] + db["sites"][k]["len"]
        if "salto_de" in rel:
            k = rel["salto_de"]
            ins = insns(tgt, S[k][0], S[k][0] + db["sites"][k]["len"])
            j = ins[rel["instrucao"]]
            if not j.operands or j.operands[0].type != X86_OP_IMM:
                raise PortError(f"{what}: jump expected in {k}")
            return j.operands[0].imm
        return locate(tgt, rel["janelas"], what)
    try:
        for name, rel in db["t"].items():
            out["t"][name] = dest(rel, "destino " + name)
        if db["vs_t"]:
            out["vs_t"] = [dest(rel, "destino VS") for rel in db["vs_t"]]
    except PortError as ex:
        raise PortError(f"jump targets: {ex}")

    F, C = out["fields"], db["campos"]
    for k, how in C.items():
        if "rip_de" in how:
            v = G.rip_target(tgt, S[how["rip_de"]][0])
        elif "call_de" in how:
            v = G.call_target(tgt, S[how["call_de"]][0])
        else:
            v = None
            for wins in how.get("call_em", []) + how.get("rip_em", []):
                try:
                    r = locate(tgt, wins, k)
                    v = G.call_target(tgt, r) if "call_em" in how else G.rip_target(tgt, r)
                    break
                except PortError:
                    continue
            if v is None:
                raise PortError(f"{k}: no reference found")
        F[k] = f"0x{v:X}"
    if out["icon_ops"]:
        rip_op = [o for o in out["icon_ops"] if o[2] == "TABLE_RIP"][0]
        F["icon_table"] = f"0x{G.rip_target(tgt, rip_op[0]):X}"
        cnt = [o for o in out["icon_ops"] if o[2] == "COUNT_IMM8"][0]
        F["icon_base_count"] = str(tgt.read(cnt[0] + cnt[3], 1)[0])
    codes = G.chara_codes(tgt, int(F["chara_table"], 16))
    if not codes or codes[0] != "GKS" or codes[-1] != "DMY":
        raise PortError("the character table of this exe does not start with GKS / end with DMY")
    F["table_entries"] = str(len(codes))
    F["mask_main"] = str(tgt.read(S["m_main_cmp"][0] + 2, 1)[0])
    F["mask_alt"] = str(tgt.read(S["m_alt_cmp"][0] + 2, 1)[0])
    K = db["constantes"]
    F["mask_extra_first"] = K["mask_extra_first"]
    if "DGF" not in codes:
        F["restore_code"], F["restore_region"] = "DGF", K.get("restore_region", "44")
        F["restore_present_index"] = K.get("restore_present_index", "46")
    head = tgt.data[:0x400]
    stamp = struct.unpack_from("<I", head, struct.unpack_from("<I", head, 0x3C)[0] + 8)[0]
    F["name"] = f"generated ({Path(tgt_path).name}, timestamp 0x{stamp:08X}, {len(codes)} characters)"
    header = [f"generated by assinaturas.py (database from {db['criado']}, ref {db['referencia']})",
              f"target: {Path(tgt_path).name}, {Path(tgt_path).stat().st_size} bytes, timestamp 0x{stamp:08X}"]
    return out, header


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "criar":
        import tempfile
        from exportar_perfil import export
        prof = Path(tempfile.gettempdir()) / "dbfz_perfil_ref.txt"
        export(0, prof)
        db = build_db(sys.argv[2], prof)
        Path(sys.argv[3]).write_text(json.dumps(db, separators=(",", ":")), encoding="utf-8")
        print(f"{sys.argv[3]}: {len(db['sites'])} patch points, {len(db['icon_ops'])} icon points, {len(db['t'])} jump targets")
    elif len(sys.argv) >= 5 and sys.argv[1] == "aplicar":
        db = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        try:
            prof, header = apply_db(db, sys.argv[3])
        except PortError as e:
            raise SystemExit(f"could NOT build the profile: {e}")
        G.write_profile(prof, sys.argv[4], header)
        print(f"{sys.argv[4]}: {len(prof['sites'])} patch points, {len(prof['t'])} jump targets, "
              f"{len(prof['icon_ops'])} icon points, {prof['fields']['table_entries']} characters")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
