"""
instalar.py - Monta e instala todos os personagens extras descritos em slots/extras.json.

Uso:
  python instalar.py                 monta o que falta e instala na copia do jogo
  python instalar.py --rebuild GHB   remonta esses personagens mesmo que ja existam
  python instalar.py --rebuild all   remonta todos
  python instalar.py --dry-run       so mostra o que faria

Para cada extra (na ordem do extras.json = ordem da 4a fileira):
  construir     -> build_char.py: DBFZX_<COD>.pak (personagem) + DBFZX_<COD>_UI.pak (arte)
  construir_ui  -> build_char.py --ui-only: DBFZX_<COD>_UI.pak
  prontos       -> paks ja convertidos, copiados como estao
Depois, para o conjunto: textos (13 idiomas), arrays de retratos, mascara do cursor,
chara_mods.txt e icons.txt do plugin. A pasta ~mods/DBFZSlots fica so com o que foi gerado;
o que sobrar vai para backup/removidos_<data>/.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
from pak import PakFile, load_key          # noqa: E402

from caminhos import JOGO as GAME, MODS_DIR, PLUGIN_DIR, CHARS, SAIDA as BUILD, MANIFESTO, BACKUP  # noqa: E402
UNVERUM_TEXT = ROOT / "backup/unverum_text/Unverum_9_P.pak"
MAX_EXTRAS = 15
GAME_CODES = {"GKS", "VGS", "PCN", "GHT", "FRN", "GNN", "TRS", "CEN", "AEN", "GTL", "KRN", "BUK", "BUN", "NPN",
              "ASN", "YMN", "TNN", "GHU", "HTN", "GKB", "VGB", "BSN", "GBR", "TON", "TOA", "TOZ", "GKN", "VGN",
              "BRS", "ZMB", "BDN", "VTB", "AVP", "CLF", "JRN", "VDN", "SGN", "JNN", "NHY", "EST", "KFS", "MGS",
              "MTN", "OSM", "GFF", "TOP", "DMY", "DGF"}


def p(rel):
    q = Path(rel)
    return q if q.is_absolute() else ROOT / q


def run(args, dry):
    """Roda um script de montagem (build_*.py) no MESMO processo: no instalador empacotado nao
    existe um python separado para chamar."""
    print("  $ " + " ".join(f'"{a}"' if " " in str(a) else str(a) for a in args), flush=True)
    if dry:
        return
    import runpy
    script = HERE / str(args[0])
    old = sys.argv
    sys.argv = [str(script)] + [str(a) for a in args[1:]]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise SystemExit(f"failed: {args[0]} ({e.code})")
    finally:
        sys.argv = old


def ui_info(ui_pak, code, key):
    """(caminho do icone, tem vs_chara_<COD>_C) lidos do pak de arte."""
    pak = PakFile(ui_pak, key)
    icon, has_c = None, False
    for e in pak.entries:
        n = pak.full_path(e)
        m = re.search(r"/UI/CharaSelect_S3/" + code + r"/(CS_CIcon\d\d)\.uasset$", n, re.I)
        if m:
            icon = f"/Game/UI/CharaSelect_S3/{code}/{m.group(1)}.{m.group(1)}"
        if re.search(r"/vs_chara_" + code + r"_C\.uasset$", n, re.I):
            has_c = True
    return icon, has_c


SIDE = {"esq": "left", "dir": "right"}


def fix_icons(codes, ui_paks, icons, key):
    """Icone com moldura do lado errado da grade (slots 1-8 x 9-16 da 4a fileira tem molduras
    espelhadas): remonta o retrato na moldura nativa do slot, como CS_XIconNN em pak proprio."""
    import icon_fix as F
    from build_char import Source, PAKS
    from uasset import rename_fn
    game = Source(PAKS, key)

    def game_icon(n):
        st = f"red/content/ui/charaselect_s3/tex/cs_cicon{n}"
        return F.read_rgba(game.get(st + ".uexp"), game.get(st + ".ubulk") if st + ".ubulk" in game.files else b"")
    models = {"esq": F.frame_model([game_icon(n) for n in F.LEFT_ICONS]),
              "dir": F.frame_model([game_icon(n) for n in F.RIGHT_ICONS])}
    files = {}
    for i, c in enumerate(codes):
        src_pak = Source([ui_paks[c]], key)
        leaf = icons[c].rsplit(".", 1)[1]                      # CS_CIconNN
        stem = f"red/content/ui/charaselect_s3/{c.lower()}/{leaf.lower()}"
        ue = src_pak.get(stem + ".uexp")
        ub = src_pak.get(stem + ".ubulk") if stem + ".ubulk" in src_pak.files else b""
        img = F.read_rgba(ue, ub)
        side, _ = F.classify(img[:, :, 3], models)
        want = "esq" if i < 8 else "dir"
        if side == want:
            continue
        new = F.rebuild_icon(img, models[side], models[want])
        ue2, ub2 = F.write_rgba(ue, ub, new)
        xleaf = leaf.replace("CS_CIcon", "CS_XIcon")
        ua, _ = rename_fn(src_pak.get(stem + ".uasset"), lambda t: t.replace("CS_CIcon", "CS_XIcon"))
        base = f"RED/Content/UI/CharaSelect_S3/{c}/{xleaf}"
        files[base + ".uasset"], files[base + ".uexp"] = ua, ue2
        if ub2:
            files[base + ".ubulk"] = ub2
        icons[c] = f"/Game/UI/CharaSelect_S3/{c}/{xleaf}.{xleaf}"
        print(f"  icon {c}: frame made for the {SIDE[side]} side, slot is on the {SIDE[want]} side -> rebuilt ({xleaf})")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dry = a.dry_run
    cfg = json.load(open(MANIFESTO, encoding="utf-8"))
    codes = [c for c in cfg if not c.startswith("_")]
    rebuild = set(codes) if "all" in [x.lower() for x in a.rebuild] else {x.upper() for x in a.rebuild}

    # ---- validacao --------------------------------------------------------------------------
    if len(codes) > MAX_EXTRAS:
        raise SystemExit(f"{len(codes)} extras; the 4th row has {MAX_EXTRAS} slots")
    for c in codes:
        e = cfg[c]
        if not re.fullmatch(r"[A-Z]{3}", c) or c in GAME_CODES:
            raise SystemExit(f"{c}: invalid code or already used by the game")
        if e["base"] not in GAME_CODES:
            raise SystemExit(f"{c}: base {e['base']} is not a game character")
        for k in e.get("construir", {}).get("keep", []):
            if k in GAME_CODES or k in codes:
                raise SystemExit(f"{c}: kept folder {k} clashes with a character")
        srcs = e.get("construir", {}).get("paks", []) + e.get("construir", {}).get("ui_paks", []) + \
            e.get("construir_ui", []) + e.get("prontos", []) + e.get("textos", [])
        for s in srcs:
            if not p(s).exists() and not (s.startswith("slots/build/") and dry):
                raise SystemExit(f"{c}: file not found: {s}")

    # ---- personagens ------------------------------------------------------------------------
    deploy = []        # paks a instalar
    ui_paks = {}
    for c in codes:
        e = cfg[c]
        print(f"[{c}] replaces {e['base']}")
        if "construir" in e:
            b = e["construir"]
            out, out_ui = CHARS / f"DBFZX_{c}.pak", CHARS / f"DBFZX_{c}_UI.pak"
            # o que foi usado para montar (se a origem mudar, o mesmo codigo e remontado)
            src_sig = json.dumps([e["base"], b, [[str(p(x)), p(x).stat().st_size if p(x).exists() else 0]
                                                 for x in b["paks"]]], sort_keys=True)
            sig_file = CHARS / f"DBFZX_{c}.src"
            if not sig_file.exists() and out.exists() and out_ui.exists() and not dry:
                sig_file.write_text(src_sig, encoding="utf-8")     # montado por versao anterior
            mudou = sig_file.exists() and sig_file.read_text(encoding="utf-8") != src_sig
            if c in rebuild or not out.exists() or not out_ui.exists() or mudou:
                args = ["build_char.py", c, e["base"]] + [p(x) for x in b["paks"]]
                if b.get("keep"):
                    args += ["--keep", ",".join(b["keep"])]
                if b.get("keep_refs"):
                    args.append("--keep-refs")
                if b.get("preload_fix"):
                    args.append("--preload-fix")
                for m in b.get("move", []):
                    args += ["--move", m]
                for x in b.get("extra_files", []):
                    args += ["--extra-file", x]
                if b.get("ui_paks"):
                    args += ["--ui-paks"] + [p(x) for x in b["ui_paks"]]
                run(args, dry)
                if not dry:
                    sig_file.write_text(src_sig, encoding="utf-8")
            else:
                print("  already built")
            deploy += [out, out_ui]
            ui_paks[c] = out_ui
        if "construir_ui" in e:
            out_ui = CHARS / f"DBFZX_{c}_UI.pak"
            if c in rebuild or not out_ui.exists():
                run(["build_char.py", c, e["base"]] + [p(x) for x in e["construir_ui"]] + ["--ui-only"], dry)
            else:
                print("  art already built")
            deploy.append(out_ui)
            ui_paks[c] = out_ui
        for x in e.get("prontos", []):
            deploy.append(p(x))
            if re.search(r"_UI\.pak$", x, re.I) and c not in ui_paks:
                ui_paks[c] = p(x)

    # ---- conjunto ---------------------------------------------------------------------------
    key = load_key()
    icons, arrays = {}, []
    for c in codes:
        if dry and not ui_paks.get(c, Path("x")).exists():
            icons[c], has_c = "?", False
        else:
            icons[c], has_c = ui_info(ui_paks[c], c, key) if c in ui_paks else (None, False)
        if not icons[c]:
            raise SystemExit(f"{c}: art pak has no CS_CIconNN icon")
        arrays.append(f"{c}={cfg[c]['base']}" + (":C" if has_c else ""))
    icon_pak = BUILD / "DBFZSlots_Icons_P.pak"
    if not dry:
        from pakwrite import write_pak
        icon_files = fix_icons(codes, ui_paks, icons, key)
        if icon_files:
            write_pak(icon_pak, icon_files)
    has_icon_pak = not dry and icon_pak.exists() and any(v.startswith("/Game/UI/CharaSelect_S3/") and "CS_XIcon" in v for v in icons.values())
    text_args = ["build_texts.py", BUILD / "DBFZSlots_Text_P.pak"] + codes
    # textos que o Unverum gerou para os mods de personagem convertidos: o pak indicado pelo
    # instalador (copiado do ~mods da copia) ou, neste projeto, o do backup
    unv = Path(cfg["_unverum_text"]) if cfg.get("_unverum_text") else UNVERUM_TEXT
    if any(cfg[c].get("textos_do_mod") for c in codes) and unv.exists():
        text_args += ["--unverum", unv]
    run(text_args, dry)
    run(["build_arrays.py", BUILD / "DBFZSlots_Arrays_P.pak"] + arrays, dry)
    import configparser
    ini = configparser.ConfigParser(inline_comment_prefixes=(";",))
    ini.read(PLUGIN_DIR / "slots.ini", encoding="utf-8")
    grid_shift = ini.getint("ui", "grid_shift", fallback=0)
    run(["build_mask.py", len(codes), BUILD / "DBFZSlots_Mask.pak", "--shift-up", grid_shift], dry)
    deploy += [BUILD / "DBFZSlots_Text_P.pak", BUILD / "DBFZSlots_Arrays_P.pak", BUILD / "DBFZSlots_Mask.pak"]
    if has_icon_pak:
        deploy.append(icon_pak)

    # ---- instalacao -------------------------------------------------------------------------
    names = {}
    for f in deploy:
        if f.name.lower() in names:
            raise SystemExit(f"two paks with the same name: {f} and {names[f.name.lower()]}")
        names[f.name.lower()] = f
    want = set()
    for f in deploy:
        want |= {f.name.lower(), f.with_suffix(".sig").name.lower()}
    stale = [f for f in MODS_DIR.glob("*") if f.name.lower() not in want] if MODS_DIR.exists() else []
    print("\ninstalling into", MODS_DIR)
    for f in deploy:
        print("  +", f.name)
    for f in stale:
        print("  - (moved to backup)", f.name)
    chara_mods = "; Um personagem extra por linha (4a fileira, esq -> dir): CODIGO [PERSONAGEM-BASE]\n" \
                 "; Gerado por slots/tools/instalar.py a partir de slots/extras.json\n" + \
                 "".join(f"{c} {cfg[c]['base']}\n" for c in codes)
    icons_txt = "; COD caminho-da-textura-do-icone (gerado por slots/tools/instalar.py)\n" + \
                "".join(f"{c} {icons[c]}\n" for c in codes)
    if dry:
        print("\n" + chara_mods + icons_txt)
        return
    if stale:
        bk = BACKUP / time.strftime("removidos_%Y%m%d_%H%M%S")
        bk.mkdir(parents=True)
        for f in stale:
            shutil.move(str(f), bk / f.name)
        print(f"  {len(stale)} old files moved to {bk}")
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    sig_src = GAME / "RED/Content/Paks/pakchunk0-WindowsNoEditor.sig"
    for f in deploy:
        dst = MODS_DIR / f.name
        if not dst.exists() or dst.stat().st_size != f.stat().st_size or dst.stat().st_mtime < f.stat().st_mtime:
            shutil.copyfile(f, dst)
        sig = f.with_suffix(".sig")
        shutil.copyfile(sig if sig.exists() else sig_src, dst.with_suffix(".sig"))
    (PLUGIN_DIR / "chara_mods.txt").write_text(chara_mods, encoding="utf-8")
    (PLUGIN_DIR / "icons.txt").write_text(icons_txt, encoding="utf-8")
    print(f"\ndone: {len(codes)} extras installed ({', '.join(codes)})")


if __name__ == "__main__":
    main()
