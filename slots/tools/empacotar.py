"""
empacotar.py - Monta o pacote do instalador para a comunidade (pasta + zip).

Uso: python empacotar.py [versao]        -> dist/DBFZSlots-Instalador-<versao>/ e .zip

Entra: o instalador (janela e linha de comando) congelado com PyInstaller, as ferramentas, o
banco de assinaturas, o catalogo de receitas, o runtime (plugin, UE4SS + proxy, script Lua) e
LEIA-ME/TERCEIROS. NAO entra (e o script confere no final): chave AES, executavel do jogo,
arquivos do jogo (.pak/.uasset...), mods, saves.
"""
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
STAGE = ROOT / "slots/build/pacote_src"
DIST = ROOT / "dist"
WORK = ROOT / "slots/build/pyinstaller"

TOOLS = ["pak.py", "pakwrite.py", "uasset.py", "uasset_pkg.py", "aes_win.py"]
RE_TOOLS = ["pe.py", "xrefs.py", "callers.py"]
SLOTS_TOOLS = ["assinaturas.py", "build_arrays.py", "build_char.py", "build_mask.py", "build_texts.py",
               "build_ui.py", "caminhos.py", "detectar_mod.py", "gerar_perfil.py", "icon_fix.py", "instalador.py",
               "instalador_gui.py", "instalar.py", "mask4.py", "exportar_perfil.py"]
UAL_SHA256 = hashlib.sha256((ROOT / "downloads/asi_loader/dsound.dll").read_bytes()).hexdigest()     if (ROOT / "downloads/asi_loader/dsound.dll").exists() else ""
PROIBIDOS = (".pak", ".uasset", ".uexp", ".ubulk", ".sav", ".exe")      # fora o proprio instalador


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    for sub, names in (("tools", TOOLS), ("tools/re", RE_TOOLS), ("slots/tools", SLOTS_TOOLS)):
        (STAGE / sub).mkdir(parents=True, exist_ok=True)
        for n in names:
            shutil.copy2(ROOT / sub / n, STAGE / sub / n)
    for n in ("assinaturas.json", "receitas.json"):
        shutil.copy2(ROOT / "slots" / n, STAGE / "slots" / n)
    shutil.copy2(ROOT / "slots/pacote/icone.png", STAGE / "slots" / "icone.png")      # icone da janela
    # chave AES do jogo embutida (decisao do autor do pacote): o usuario nao precisa informar
    shutil.copy2(ROOT / "tools/aes_key.txt", STAGE / "slots" / "dbfz_key.txt")
    subprocess.run([sys.executable, str(HERE / "montar_runtime.py")], check=True)
    shutil.copytree(ROOT / "runtime", STAGE / "runtime")


def build(version):
    name = f"DBFZSlots-Installer-{version}"
    hidden = [m[:-3] for m in SLOTS_TOOLS + TOOLS + RE_TOOLS]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", name,
           "--distpath", str(DIST), "--workpath", str(WORK), "--specpath", str(WORK),
           "--add-data", f"{STAGE};.", "--collect-all", "capstone",
           "--icon", str(ROOT / "slots/pacote/icone.ico"),
           "--paths", str(ROOT / "slots/tools"), "--paths", str(ROOT / "tools"), "--paths", str(ROOT / "tools/re")]
    for h in hidden + ["numpy", "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
                       "tkinter.simpledialog"]:
        cmd += ["--hidden-import", h]
    cmd.append(str(ROOT / "slots/pacote/launcher.py"))
    subprocess.run(cmd, check=True)
    out = DIST / name
    for doc in ("README.txt", "THIRD-PARTY.txt"):
        src = ROOT / "slots/pacote" / doc
        if src.exists():
            shutil.copy2(src, out / doc)
    shutil.copytree(ROOT / "slots/pacote/licenses", out / "licenses", dirs_exist_ok=True)
    shutil.copy2(ROOT / "downloads/asi_loader/LICENSE-UltimateASILoader.txt", out / "licenses" / "UltimateASILoader-LICENSE.txt")
    if not (out / "licenses" / "UE4SS-LICENSE.txt").exists():
        print("\nWARNING: licenses/UE4SS-LICENSE.txt is missing (the official RE-UE4SS LICENSE). "
              "Required before publishing; for a private test the package works without it.")
    return out


def check(out):
    bad = []
    for f in out.rglob("*"):
        if not f.is_file():
            continue
        n = f.name.lower()
        if n == "aes_key.txt" or (f.suffix.lower() in PROIBIDOS and f.parent != out):
            bad.append(str(f.relative_to(out)))
        if n.startswith("red-win64"):
            bad.append(str(f.relative_to(out)))
        if n == "dsound.dll" and hashlib.sha256(f.read_bytes()).hexdigest() != UAL_SHA256:
            bad.append(str(f.relative_to(out)) + " (not the official Ultimate ASI Loader)")
    if bad:
        raise SystemExit("the package has files that must NOT be distributed:\n  " + "\n  ".join(bad))


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "0.1-beta"
    stage()
    out = build(version)
    check(out)
    z = out.parent / (out.name + ".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(out.parent).as_posix())
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 2**20
    print(f"\n{out} ({size:.0f} MB)\n{z} ({z.stat().st_size / 2**20:.0f} MB)\nchecked: no game exe, game files or mods; AES key and Ultimate ASI Loader included on purpose")


if __name__ == "__main__":
    main()
