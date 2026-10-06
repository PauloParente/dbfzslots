"""
build_texts.py - Gera DBFZSlots_Text_P.pak: tabelas de texto REDGame (13 idiomas) com os extras.

Uso: python build_texts.py <saida.pak> COD [COD ...]      (codigos de slots/extras.json)
     opcoes: --unverum <pak>   aplica os textos que o Unverum gerou para os mods instalados

Formato (Localization/<LANG>/REDGame.uexp): u32 tamanho em 0x24 e 0x28; a partir de 0x30 um
texto UTF-16 "CHAVE\\r\\nVALOR\\r\\n...". O .uasset guarda o SerialSize do export (= len(uexp)-4).
Baseado em tools/build_texts.py do port Xbox (MrPopulutus, MIT).

Cada extra copia as chaves do personagem-base trocando o codigo (comandos, assistencias,
nomes, desafios de combo) e recebe os nomes de extras.json.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pak import PakFile, load_key          # noqa: E402
from pakwrite import write_pak             # noqa: E402

from caminhos import PAKS, MANIFESTO  # noqa: E402
LANG_NAME = {"POR": "pt", "SPA": "es", "ESN": "es"}
# chaves por personagem que um mod de substituicao pode ter alterado (mantidas do Unverum)
MOD_KEY = r"^(CMD{c}\d\d\w*|STGCMD{c}\d\d|{c}_ASSIST_\d\d|CHARA_NAME_(L|S|M|DEMO)_{c}|AVATAR_NAME_{c}|ComboChallengeName{c}\d\d)$"


def key_for(base, extra, key):
    pats = [(rf"^CMD{base}(\d\d\w*)$", rf"CMD{extra}\1"), (rf"^STGCMD{base}(\d\d)$", rf"STGCMD{extra}\1"),
            (rf"^{base}_ASSIST_(\d\d)$", rf"{extra}_ASSIST_\1"), (rf"^CHARA_NAME_(L|S|M|DEMO)_{base}$", rf"CHARA_NAME_\1_{extra}"),
            (rf"^AVATAR_NAME_{base}$", rf"AVATAR_NAME_{extra}"), (rf"^ComboChallengeName{base}(\d\d)$", rf"ComboChallengeName{extra}\1")]
    for p, r in pats:
        if re.match(p, key):
            return re.sub(p, r, key)
    return None


def parse(uexp):
    n = struct.unpack_from("<I", uexp, 0x24)[0]
    if struct.unpack_from("<I", uexp, 0x28)[0] != n or uexp[-4:] != bytes.fromhex("c1832a9e"):
        raise SystemExit("REDGame.uexp has an unexpected format")
    s = uexp[0x30:0x30 + n].decode("utf-16-le")
    body = s.rstrip("\r\n")
    lines = body.split("\r\n")
    pairs = [(lines[i].lstrip("\x00﻿"), lines[i + 1]) for i in range(0, len(lines) - 1, 2)]
    return s, body, pairs


def rebuild(uasset, uexp, pairs_out, trailer):
    """Monta uexp/uasset com a lista final de pares (mantendo o 1o caractere especial, se houver)."""
    n = struct.unpack_from("<I", uexp, 0x24)[0]
    s = uexp[0x30:0x30 + n].decode("utf-16-le")
    lead = s[:len(s) - len(s.lstrip("\x00﻿"))]
    # um valor vazio no fim se confunde com a quebra de linha final: termina num par com valor
    if pairs_out and pairs_out[-1][1] == "":
        i = max(j for j, (_, v) in enumerate(pairs_out) if v != "")
        pairs_out = pairs_out[:i] + pairs_out[i + 1:] + [pairs_out[i]]
    text = lead + "\r\n".join(f"{k}\r\n{v}" for k, v in pairs_out) + trailer
    data = text.encode("utf-16-le")
    out = bytearray(uexp[:0x30]) + data + uexp[0x30 + n:]
    struct.pack_into("<I", out, 0x24, len(data))
    struct.pack_into("<I", out, 0x28, len(data))
    old_serial = len(uexp) - 4
    ua = bytearray(uasset)
    hits = [i for i in range(len(ua) - 3) if struct.unpack_from("<I", ua, i)[0] == old_serial]
    if len(hits) != 1:
        raise SystemExit(f"SerialSize {old_serial} found {len(hits)} times in the uasset")
    struct.pack_into("<I", ua, hits[0], len(out) - 4)
    return bytes(ua), bytes(out)


def unverum_overrides(path, base_pairs):
    """Chaves de personagem que o Unverum alterou/criou (textos dos mods), so para INT."""
    pak = PakFile(path)
    e = pak.find("RED/Content/Localization/INT/REDGame.uexp")
    if not e:
        return {}
    _, _, pairs = parse(pak.read(e[0]))
    base = dict(base_pairs)
    changed = {k: v for k, v in pairs if base.get(k) != v}
    codes = sorted({m.group(1) for k in changed for m in [re.search(r"(?:CMD|_NAME_\w+?_|^)([A-Z]{3})(?:\d|_ASSIST|$)", k)] if m})
    keep = {}
    for k, v in changed.items():
        if any(re.match(MOD_KEY.format(c=c), k) for c in codes) or (k not in base and re.match(r"^v[a-z]{3}\d{4}$", k)):
            keep[k] = v
    print(f"Unverum: {len(keep)} mod texts kept (of {len(changed)} differences; the rest is old game text)")
    return keep


def mod_text_source(path, base, base_pairs, key=None):
    """Textos que um mod de substituicao traz para o personagem-base: text.json do Unverum
    ({"Entries": [{"header", "text"}]}) ou um pak com Localization/INT/REDGame (so o que difere
    do jogo). Devolve {chave do base: valor}, so chaves de personagem (MOD_KEY) e vozes."""
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if path.suffix.lower() == ".json":
        raw = path.read_bytes().decode("utf-8-sig")
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            d = json.loads(re.sub(r",\s*([\]}])", r"", raw))      # virgulas sobrando (json "solto")
        pairs = {e["header"]: e["text"] for e in d.get("Entries", []) if "header" in e}
    else:
        pak = PakFile(path, key)
        e = [x for x in pak.entries if pak.full_path(x).lower().endswith("localization/int/redgame.uexp")]
        if not e:
            return {}
        base_d = dict(base_pairs)
        pairs = {k: v for k, v in parse(pak.read(e[0]))[2] if base_d.get(k) != v}
    rx = re.compile(MOD_KEY.format(c=base))
    return {k: v for k, v in pairs.items() if rx.match(k)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--unverum")
    a = ap.parse_args()
    cfg = json.load(open(MANIFESTO, encoding="utf-8"))
    for c in a.codes:
        if c not in cfg:
            raise SystemExit(f"{c} is not in the manifest (extras.json)")
    key = load_key()
    paks = [PakFile(p, key) for p in PAKS]
    langs = {}
    for pak in paks:
        for e in pak.find("RED/Content/Localization/*/REDGame.uexp"):
            lang = pak.full_path(e).split("/")[3]
            ua = pak.find(pak.full_path(e)[:-4] + "uasset")[0]
            langs[lang] = (pak.read(ua), pak.read(e))
    files = {}
    overrides = {}
    mod_texts = {}
    # INT vem depois de CHN..FRA na ordem alfabetica: calcula os textos dos mods antes do laco
    if a.unverum and "INT" in langs:
        overrides = unverum_overrides(a.unverum, parse(langs["INT"][1])[2])
        # textos de mods de substituicao convertidos vao para o codigo novo (em todos os
        # idiomas: o mod so tem ingles, melhor que a traducao dos golpes do personagem-base);
        # o personagem-base volta ao texto original
        for code in a.codes:
            if not cfg[code].get("textos_do_mod"):
                continue
            base = cfg[code]["base"]
            for k in [k for k in overrides if key_for(base, code, k)]:
                mod_texts.setdefault(code, {})[key_for(base, code, k)] = overrides.pop(k)
            print(f"  {code}: {len(mod_texts.get(code, {}))} mod texts (previously under {base})")
    # textos que vem dos proprios mods (extras.json: "textos": [text.json ou pak, ...])
    if "INT" in langs:
        int_pairs = parse(langs["INT"][1])[2]
        for code in a.codes:
            for src in cfg[code].get("textos", []):
                got = mod_text_source(src, cfg[code]["base"], int_pairs, key)
                for k, v in got.items():
                    mod_texts.setdefault(code, {})[key_for(cfg[code]["base"], code, k)] = v
                print(f"  {code}: {len(got)} texts from {Path(src).name}")
    for lang in sorted(langs):
        ua, ue = langs[lang]
        s, body, pairs = parse(ue)
        trailer = s[len(s.rstrip("\r\n")):]
        out = list(pairs)
        if lang == "INT" and overrides:
            idx = {k: i for i, (k, _) in enumerate(out)}
            for k, v in overrides.items():
                if k in idx:
                    out[idx[k]] = (k, v)
                else:
                    out.append((k, v))
        existing = {k for k, _ in out}
        added = 0
        for code in a.codes:
            base = cfg[code]["base"]
            names = cfg[code]["nomes"]
            long_, short = names.get(LANG_NAME.get(lang, "en"), names["en"])
            for k, v in list(out):
                nk = key_for(base, code, k)
                if not nk or nk in existing:
                    continue
                if nk.startswith(("CHARA_NAME_L_", "AVATAR_NAME_")):
                    v = long_
                elif nk.startswith(("CHARA_NAME_S_", "CHARA_NAME_M_", "CHARA_NAME_DEMO_")):
                    v = short
                elif nk in mod_texts.get(code, {}):
                    v = mod_texts[code][nk]
                out.append((nk, v))
                existing.add(nk)
                added += 1
        if mod_texts:   # chaves do mod que o personagem-base nao tem (todos os idiomas)
            for code in a.codes:
                for nk, v in mod_texts.get(code, {}).items():
                    if nk not in existing and not nk.startswith(("CHARA_NAME_", "AVATAR_NAME_")):
                        out.append((nk, v)); existing.add(nk); added += 1
        ua2, ue2 = rebuild(ua, ue, out, trailer)
        # confere: reler e comparar
        _, _, check = parse(ue2)
        assert sorted(check) == sorted(out), f"{lang}: re-read differs"
        files[f"RED/Content/Localization/{lang}/REDGame.uasset"] = ua2
        files[f"RED/Content/Localization/{lang}/REDGame.uexp"] = ue2
        print(f"{lang}: {len(pairs)} keys + {added} for the extras" + (f" + mod texts" if lang == "INT" and overrides else ""))
    write_pak(a.out, files)
    print(f"{a.out}: {len(files)} files")


if __name__ == "__main__":
    main()
