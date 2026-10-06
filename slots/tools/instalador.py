"""
instalador.py - DBFZ Slots installer for the community (command line).

  python instalador.py --game "D:\\DBFZ copy" --mods "D:\\my mods" [options]

Steps, in this order (nothing is written before the checks):
  1. checks the game folder (a COPY, never the Steam one), the offline exe (never the
     RED-Win64-Shipping.exe protected by the anti-cheat) and that EasyAntiCheat is closed;
  2. builds the plugin profile for that exe from the signature database (slots/assinaturas.json);
     if the exe is not compatible, it stops here and says why;
  3. reads every mod in --mods (zip/rar/7z/pak): tested recipe from the catalog
     (slots/receitas.json, by the file MD5) or automatic detection (detectar_mod.py);
  4. copies the runtime (plugin, UE4SS + script, Ultimate ASI Loader) into the game, backing up
     anything it replaces;
  5. builds and installs the characters (instalar.py): paks, texts, portraits, mask, icons.

Options:
  --exe FILE         exe that runs the copy (default: the only *eac-nop*.exe in the folder)
  --key HEX|FILE     AES key of the game paks (default: the one included in the package)
  --asi-loader DLL   Ultimate ASI Loader x64 (dsound.dll); default: the one in the package
  --dry-run          shows what it would do (profile, mods found, order) without installing
The installer does NOT include or create a game executable and does NOT disable the anti-cheat.
OFFLINE play only, on a separate copy of the game.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

MAX_EXTRAS = 15
RUNTIME = ROOT / "runtime"
DB = HERE.parent / "assinaturas.json"
CATALOGO = HERE.parent / "receitas.json"
ARQUIVOS = (".zip", ".rar", ".7z", ".pak")
PROFILE = "profile.txt"
DATA_DIR = "DBFZSlots_data"


class Erro(Exception):
    pass


def lp(p):
    """Windows long path (> 260 chars): Unverum mods have deep folders."""
    s = str(Path(p).resolve())
    return s if s.startswith("\\\\?\\") else "\\\\?\\" + s


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def passo(n, txt):
    print(f"\n[{n}] {txt}")


# ---- 1. checks ------------------------------------------------------------------------------

def conferir_jogo(jogo, exe_arg):
    jogo = Path(jogo).resolve()
    if "steamapps" in str(jogo).lower():
        raise Erro("this is the Steam folder. Make a COPY of the game folder first, apply Unverum to "
                   "the copy (it creates the offline exe) and choose the copy here. The Steam install must "
                   "stay untouched (it is the one the anti-cheat protects).")
    win64 = jogo / "RED" / "Binaries" / "Win64"
    paks = jogo / "RED" / "Content" / "Paks"
    if not (paks / "pakchunk0-WindowsNoEditor.pak").exists() or not win64.is_dir():
        raise Erro(f"{jogo} does not look like the DRAGON BALL FighterZ folder "
                   "(RED\\Content\\Paks or RED\\Binaries\\Win64 is missing)")
    if exe_arg:
        exe = Path(exe_arg).resolve()
    else:
        cands = sorted(p for p in win64.glob("*.exe") if "eac-nop" in p.name.lower())
        if len(cands) != 1:
            raise Erro("could not find a single offline exe (*eac-nop*.exe) in RED\\Binaries\\Win64; "
                       "choose it with --exe (or in the Offline exe field)")
        exe = cands[0]
    if exe.name.lower() == "red-win64-shipping.exe":
        raise Erro("RED-Win64-Shipping.exe is the executable protected by EasyAntiCheat; the plugin "
                   "must not be used with it. This installer only works with an offline exe you already have.")
    if not exe.exists():
        raise Erro(f"{exe} does not exist")
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                         creationflags=0x08000000).stdout.lower()
    if "easyanticheat" in out:
        raise Erro("EasyAntiCheat is running. Close the Steam game before installing.")
    if exe.name.lower() in out or "red-win64-shipping" in out:
        raise Erro("the game is running. Close it before installing.")
    return jogo, win64, exe


def eh_steam(pasta):
    return "steamapps" in str(Path(pasta).resolve()).lower()


def configurar_chave(chave):
    if chave:
        p = Path(chave)
        os.environ["DBFZ_AES_KEY"] = p.read_text().strip() if p.exists() else chave.strip()
    from pak import load_key
    if not load_key():
        raise Erro("the AES key of the game paks is missing: use --key (text or file) or the "
                   "DBFZ_AES_KEY environment variable")
    return load_key()


# ---- 2. profile -----------------------------------------------------------------------------

def gerar_perfil(exe, destino):
    import assinaturas as A
    import gerar_perfil as G
    db = json.loads(DB.read_text(encoding="utf-8"))
    try:
        prof, header = A.apply_db(db, exe)
    except G.PortError as e:
        raise Erro(f"this exe is not compatible with the plugin (nothing was installed):\n  {e}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    G.write_profile(prof, destino, header)
    return prof


# ---- 3. mods --------------------------------------------------------------------------------

def rel_jogo(p, jogo):
    """path relative to the game folder, with or without the long-path prefix."""
    s, j = str(p), str(Path(jogo).resolve())
    s = s[4:] if s.startswith("\\\\?\\") else s
    return Path(s[len(j):].lstrip("\\/"))


def mods_antigos(jogo, key):
    """Unverum (or other tool) mods in the copy. Only CHARACTER REPLACEMENT paks (movesets) are
    touched: they are converted into new slots and then disabled. Everything else (skins, extra
    costumes, stages, plugins) stays as it is. The Unverum text pak is merged into ours."""
    from pak import PakFile
    mods_dir = Path(jogo) / "RED" / "Content" / "Paks" / "~mods"
    chars, textos = [], []
    if mods_dir.is_dir():
        for pk in sorted(Path(lp(mods_dir)).rglob("*.pak")):
            if "dbfzslots" in [x.lower() for x in rel_jogo(pk, jogo).parts]:
                continue
            try:
                pak = PakFile(pk, key)
                names = [pak.full_path(e) for e in pak.entries]
            except Exception:
                continue
            if any(re.search(r"/Chara/([A-Z]{3})/Common/Data/BBS_\1\.uasset$", n) for n in names):
                chars.append(pk)
            elif any("/Localization/" in n for n in names) and not any("/Chara/" in n for n in names):
                textos.append(pk)
    itens = chars + (textos if chars else [])
    return {"itens": itens, "chars": chars, "textos": textos if chars else []}


def desligar_antigos(antigos, jogo, backup):
    """Moves the converted character paks (and the merged text pak) out of the game: they would
    keep replacing the original characters. Their .sig goes with them."""
    n = 0
    for pk in antigos["itens"]:
        for f in (Path(pk), Path(str(pk)[:-4] + ".sig")):
            if not f.exists():
                continue
            dst = backup / rel_jogo(f, jogo)
            Path(lp(dst)).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(lp(f), lp(dst))
        n += 1
    return n


def chave_catalogo(src, cat):
    """Recipe of an archive (MD5 of the file) or of a mod folder / pak (MD5 of a pak inside)."""
    src = Path(src)
    if src.is_file():
        r = cat.get(md5(src))
        if r:
            return r, (src if src.suffix.lower() == ".pak" else None)
    paks = sorted(src.rglob("*.pak")) if src.is_dir() else []
    for pk in paks:
        r = cat.get(md5(pk))
        if r and "complemento_de" not in r:
            return r, pk
    return None, None


def ler_mods(pasta, saida, key, importados=(), textos_antigos=()):
    import detectar_mod as D
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))["receitas"] if CATALOGO.exists() else {}
    fontes = sorted(p for p in Path(pasta).iterdir()
                    if (p.is_file() and p.suffix.lower() in ARQUIVOS) or (p.is_dir() and any(p.rglob("*.pak"))))
    fontes += [Path(x) for x in importados]
    if not fontes:
        raise Erro(f"no mods (.zip/.rar/.7z/.pak or mod folders) in {pasta}")
    work = saida / "mods"
    extras, comps, avisos, usados, vistos = [], {}, [], set(), set()
    for a in fontes:
        importado = a in importados
        r, pak_achado = chave_catalogo(a, cat)
        if r and "complemento_de" in r:
            comps.setdefault(r["complemento_de"], []).append(a)
            continue
        origem = ("old mod in the copy: " if importado else "") + a.name
        if r:
            if r["codigo"] in vistos:
                continue                      # o mesmo mod na pasta de mods e no ~mods antigo
            vistos.add(r["codigo"])
            if a.is_dir():
                root = a
            elif a.suffix.lower() == ".pak":
                root = a.parent
            else:
                dest = work / a.stem
                root = D.unpack(a, work)[1] if not dest.exists() else dest

            def acha(rel, root=root, a=a, pak_achado=pak_achado, r=r):
                # a receita veio do MD5 deste pak: ele mesmo, com qualquer nome (o Unverum poe _9_P)
                if pak_achado and rel.lower().endswith(".pak") and len(r["paks"]) == 1:
                    return str(pak_achado)
                hits = [p for p in Path(root).rglob(Path(rel).name)]
                if not hits:
                    raise Erro(f"{a.name}: {rel} not found")
                return str(hits[0])
            e = {"codigo": r["codigo"], "base": r["base"], "nomes": r["nomes"], "origem": origem, "receita": "catalog",
                 "construir": {"paks": [acha(p) for p in r["paks"]]}, "textos": [acha(t) for t in r.get("textos", [])]}
            for k in ("keep", "move", "preload_fix", "keep_refs", "extra_files"):
                if k in r:
                    e["construir"][k] = r[k]
            if importado and textos_antigos:
                e["textos_do_mod"] = True
            if "textos_extra" in r:
                tdir = saida / "texts"
                tdir.mkdir(parents=True, exist_ok=True)
                tf = tdir / f"{r['codigo']}.json"
                tf.write_text(json.dumps({"Entries": r["textos_extra"]}, ensure_ascii=False, indent=1), encoding="utf-8")
                e["textos"].append(str(tf))
        else:
            rec, info = D.detect(a, usados, key=key, work=str(work))
            e = {"codigo": rec["codigo"], "base": rec["base"], "nomes": rec["nomes"], "origem": origem,
                 "receita": "detected", "construir": rec["construir"], "textos": rec["textos"] or
                 ([str(t) for t in textos_antigos] if importado else [])}
            avisos += [f"{a.name}: {w}" for w in info["avisos"]]
        if e["codigo"] in usados:
            e["codigo"] = D.suggest_code(e["nomes"]["en"][1], usados | set(e["construir"].get("keep", [])))
        usados.add(e["codigo"])
        extras.append(e)
    for code, lst in comps.items():
        alvo = [e for e in extras if e["codigo"] == code]
        if not alvo:
            avisos.append(f"{', '.join(x.name for x in lst)}: add-on for {code}, but the main mod is not in the folder")
            continue
        for a in lst:
            paks, _ = D.unpack(a, work)
            alvo[0]["construir"]["paks"] += [str(p) for p in paks]
    for e in extras:
        if not e["construir"]["paks"]:
            raise Erro(f"{e['origem']}: no pak to build the character from")
    if len(extras) > MAX_EXTRAS:
        avisos.append(f"{len(extras)} mods; the 4th row has {MAX_EXTRAS} slots: only the first {MAX_EXTRAS} are used")
        extras = extras[:MAX_EXTRAS]
    return extras, avisos


def escrever_manifesto(extras, arq, unverum_text=None):
    m = {"_comment": "Generated by the DBFZ Slots installer. Edit names/order and run the installer again."}
    if unverum_text:
        m["_unverum_text"] = str(unverum_text)
    for e in extras:
        m[e["codigo"]] = {"base": e["base"], "nomes": e["nomes"], "construir": e["construir"],
                          "textos": e["textos"], "_source": e["origem"], "_recipe": e["receita"]}
        if e.get("textos_do_mod"):
            m[e["codigo"]]["textos_do_mod"] = True
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


# ---- 4. runtime -----------------------------------------------------------------------------

def copiar_runtime(win64, asi_loader, backup):
    if not RUNTIME.is_dir():
        raise Erro(f"runtime folder not found ({RUNTIME}); the package is incomplete")
    loader = Path(asi_loader) if asi_loader else RUNTIME / "dsound.dll"
    if not loader.exists():
        raise Erro("Ultimate ASI Loader x64 is missing (github.com/ThirteenAG/Ultimate-ASI-Loader/releases): "
                   "download it, rename dinput8.dll to dsound.dll and select it")
    copias = [(loader, win64 / "dsound.dll")]
    for f in RUNTIME.rglob("*"):
        if f.is_file() and f.name != "dsound.dll":
            rel = f.relative_to(RUNTIME)
            dst = win64 / rel
            if rel.as_posix() == "plugins/DBFZSlots/slots.ini" and dst.exists():
                continue                           # keep the user's settings
            copias.append((f, dst))
    n_bk = 0
    for src, dst in copias:
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            b = backup / dst.relative_to(win64)
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)
            n_bk += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return len(copias), n_bk


# ---- main (command line and window use the same two functions) ------------------------------

def apontar_caminhos(jogo, saida, exe):
    """The build tools read their paths from caminhos.py, which reads these variables ONCE when
    imported: this must run before importing any build module."""
    os.environ.update(DBFZ_JOGO=str(jogo), DBFZ_SAIDA=str(saida), DBFZ_MANIFESTO=str(saida / "extras.json"),
                      DBFZ_EXE=str(exe), DBFZ_BACKUP=str(saida / "backup"))


def analisar(jogo_arg, mods, exe_arg=None, chave=None, saida_arg=None, simular=True):
    """Steps 1 to 3: checks, profile and mod reading. Returns the installation context.
    The game folder is a COPY of the game where Unverum was applied (it has the offline exe)."""
    passo(1, "checking game folder, exe and anti-cheat")
    jogo, win64, exe = conferir_jogo(jogo_arg, exe_arg)
    saida = Path(saida_arg).resolve() if saida_arg else jogo / DATA_DIR
    apontar_caminhos(jogo, saida, exe)
    key = configurar_chave(chave)
    print(f"  game: {jogo}\n  exe: {exe.name}\n  output: {saida}")

    passo(2, "building the plugin profile for this exe")
    perfil_dst = (saida if simular else win64 / "plugins" / "DBFZSlots") / PROFILE
    prof = gerar_perfil(exe, perfil_dst)
    print(f"  compatible: {prof['fields']['table_entries']} characters, {len(prof['sites'])} patch points")

    passo(3, "reading the mods")
    antigos = mods_antigos(jogo, key)
    importados, textos_antigos = [], []
    if antigos["chars"]:
        print(f"  {len(antigos['chars'])} Unverum character mods replace original characters: they will be "
              "added as NEW slots instead (their paks are disabled; your other Unverum mods stay as they are)")
        imp = saida / "imported"
        for i, pk in enumerate(antigos["chars"] + antigos["textos"]):
            dst = imp / f"{i:02d}_{pk.parent.name[:40]}" / pk.name
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(lp(pk), lp(dst))
                except OSError:
                    shutil.copy2(lp(pk), lp(dst))
            (importados if pk in antigos["chars"] else textos_antigos).append(dst)
    extras, avisos = ler_mods(mods, saida, key, importados, textos_antigos)
    for i, e in enumerate(extras, 1):
        print(f"  {i:2}. {e['codigo']}  {e['nomes']['en'][0]:<30} replaces {e['base']}  ({e['receita']}: {e['origem']})")
    for w in avisos:
        print("  WARNING:", w)
    return {"jogo": jogo, "win64": win64, "exe": exe, "saida": saida, "extras": extras, "avisos": avisos,
            "perfil": prof, "antigos": antigos, "unverum_text": textos_antigos[0] if textos_antigos else None}


def instalar_tudo(ctx, asi_loader=None):
    """Steps 4 and 5: runtime and build. ctx["extras"] may have been reordered/edited."""
    jogo, win64, exe, saida, extras = ctx["jogo"], ctx["win64"], ctx["exe"], ctx["saida"], ctx["extras"]
    if not extras:
        raise Erro("no characters to install")
    if len({e["codigo"] for e in extras}) != len(extras):
        raise Erro("two characters have the same code")
    apontar_caminhos(jogo, saida, exe)
    escrever_manifesto(extras, saida / "extras.json", ctx.get("unverum_text"))
    gerar_perfil(exe, win64 / "plugins" / "DBFZSlots" / PROFILE)

    if ctx.get("antigos", {}).get("itens"):
        bk = saida / "backup" / time.strftime("disabled_%Y%m%d_%H%M%S")
        n = desligar_antigos(ctx["antigos"], jogo, bk)
        print(f"\n  {n} Unverum paks converted and disabled (moved to {bk})")

    passo(4, "copying the runtime (plugin, UE4SS, ASI Loader)")
    n, nb = copiar_runtime(win64, asi_loader, saida / "backup" / time.strftime("runtime_%Y%m%d_%H%M%S"))
    print(f"  {n} files ({nb} replaced, backed up)")

    passo(5, "building and installing the characters (this can take several minutes)")
    import instalar
    old = sys.argv
    sys.argv = [str(HERE / "instalar.py")]
    try:
        instalar.main()
    except SystemExit as e:
        if e.code not in (None, 0):
            raise Erro(f"the build failed: {e.code}")
    finally:
        sys.argv = old
    print(f"\ndone: {len(extras)} characters installed. Start the game with {exe.name}.")


def main():
    ap = argparse.ArgumentParser(description="DBFZ Slots installer (modded characters in new slots)")
    ap.add_argument("--game", "--jogo", dest="jogo", required=True, help="the COPY of the game (folder with RED\\)")
    ap.add_argument("--mods", required=True, help="folder with the downloaded mods (.zip/.rar/.7z/.pak)")
    ap.add_argument("--exe", help="offline exe (default: the only *eac-nop*.exe)")
    ap.add_argument("--key", "--chave", dest="chave", help="AES key of the game paks (text or file)")
    ap.add_argument("--asi-loader", help="Ultimate ASI Loader x64 (dsound.dll)")
    ap.add_argument("--output", "--saida", dest="saida", help=f"where generated files go (default: <game>\\{DATA_DIR})")
    ap.add_argument("--dry-run", "--simular", dest="simular", action="store_true",
                    help="show what would be done without installing")
    a = ap.parse_args()
    try:
        ctx = analisar(a.jogo, a.mods, a.exe, a.chave, a.saida, simular=a.simular)
        escrever_manifesto(ctx["extras"], ctx["saida"] / "extras.json", ctx.get("unverum_text"))
        if a.simular:
            print("\ndry run: nothing was installed.")
            return
        instalar_tudo(ctx, a.asi_loader)
    except Erro as e:
        raise SystemExit(f"\nERROR: {e}")


if __name__ == "__main__":
    main()
