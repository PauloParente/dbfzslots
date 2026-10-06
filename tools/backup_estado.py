"""
backup_estado.py - Guarda o estado atual do projeto (tudo que nao da para regenerar facil).

Uso: python backup_estado.py            -> backup/estado_<data_hora>/

Gera:
  projeto.zip   codigo (slots/src, lua, tools, tests), manifesto (extras.json, textos), ferramentas
                (tools/), referencia, configuracao do jogo modificado (plugin + DBFZSlots/, UE4SS e
                seus mods, dsound/opengl32), saves separados (game/UserData) e os paks feitos a mao
                que o instalador nao refaz (DBFZX_DIO_*).
  fontes.txt    cada arquivo de mod usado pelo manifesto, com tamanho e MD5 (os paks dos
                personagens sao refeitos a partir deles: slots/tools/instalar.py --rebuild all).
  RESTAURAR.md  como voltar a este ponto.
Os paks gerados (~7 GB) nao entram: sao reproduziveis a partir das fontes.
"""
import hashlib
import json
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN64 = ROOT / "game/RED/Binaries/Win64"

INCLUDE = [
    "slots/src", "slots/lua", "slots/tools", "slots/tests", "slots/testenv", "slots/textos",
    "slots/extras.json", "slots/build.cmd", "slots/STEAM-RVAS.md",
    "tools", "reference",
    "game/RED/Binaries/Win64/plugins",
    "game/RED/Binaries/Win64/ue4ss",
    "game/RED/Binaries/Win64/dsound.dll", "game/RED/Binaries/Win64/opengl32.dll",
    "game/RED/Binaries/Win64/steam_appid.txt",
    "game/UserData",
    "slots/build/chars/DBFZX_DIO_UI.pak", "slots/build/chars/DBFZX_DIO_UI.sig",
    "slots/build/chars/DBFZX_DIO_Config_P.pak", "slots/build/chars/DBFZX_DIO_Config_P.sig",
]
SKIP_PARTS = {"__pycache__", "Crashes", "Logs"}
SKIP_SUFFIX = {".pyc", ".log", ".dmp"}


def files_of(rel):
    p = ROOT / rel
    if p.is_file():
        yield p
    elif p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file() and not (SKIP_PARTS & set(f.relative_to(ROOT).parts)) and f.suffix.lower() not in SKIP_SUFFIX:
                yield f


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    out = ROOT / "backup" / time.strftime("estado_%Y%m%d_%H%M%S")
    out.mkdir(parents=True)
    n = 0
    with zipfile.ZipFile(out / "projeto.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in INCLUDE:
            for f in files_of(rel):
                z.write(f, f.relative_to(ROOT).as_posix())
                n += 1
    cfg = json.load(open(ROOT / "slots/extras.json", encoding="utf-8"))
    lines = ["# Fontes usadas pelo manifesto (slots/extras.json) em " + time.strftime("%Y-%m-%d %H:%M"),
             "# codigo | arquivo | bytes | md5", ""]
    for code, e in cfg.items():
        if code.startswith("_"):
            continue
        srcs = e.get("construir", {}).get("paks", []) + e.get("construir", {}).get("ui_paks", []) + \
            e.get("construir_ui", []) + e.get("prontos", []) + e.get("textos", [])
        for s in dict.fromkeys(srcs):
            f = ROOT / s
            if f.exists():
                lines.append(f"{code} | {s} | {f.stat().st_size} | {md5(f)}")
            else:
                lines.append(f"{code} | {s} | FALTANDO")
    lines += ["", "# Arquivos originais baixados (downloads/ e downloads/mods/)"]
    for f in sorted(list((ROOT / "downloads").glob("*.zip")) + list((ROOT / "downloads").glob("*.rar")) +
                    list((ROOT / "downloads/mods").glob("*.zip")) + list((ROOT / "downloads/mods").glob("*.rar"))):
        lines.append(f"{f.relative_to(ROOT).as_posix()} | {f.stat().st_size} | {md5(f)}")
    (out / "fontes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "RESTAURAR.md").write_text(RESTORE.format(pasta=out.name, n=n), encoding="utf-8")
    size = (out / "projeto.zip").stat().st_size / 2**20
    print(f"{out}: projeto.zip ({n} arquivos, {size:.1f} MB), fontes.txt, RESTAURAR.md")


RESTORE = """# Como restaurar este estado ({pasta})

`projeto.zip` tem {n} arquivos com caminhos relativos a `C:\\dbfz modded\\`.

1. Feche o jogo.
2. Extraia `projeto.zip` em `C:\\dbfz modded\\`, substituindo os arquivos. Isso restaura o codigo,
   as ferramentas, o manifesto, o plugin (`plugins\\DBFZSlots.asi` + `plugins\\DBFZSlots\\`), o UE4SS e
   seus scripts, e os saves separados (`game\\UserData`).
3. Confira se as fontes listadas em `fontes.txt` existem (pasta `downloads\\`). O que faltar: baixe
   de novo pelos links do GameBanana (o MD5 deve bater) ou recupere do backup dos downloads.
4. Refaca os paks e instale:
   `python "C:\\dbfz modded\\slots\\tools\\instalar.py" --rebuild all`
   (monta os personagens, textos, tabelas de retrato, mascara, icones e atualiza
   `~mods\\DBFZSlots`, `chara_mods.txt` e `icons.txt`).
5. Abra a copia pelo `RED-Win64-Shipping-eac-nop-loaded.exe` (nunca pelo Unverum).

Se o jogo for atualizado e o plugin nao reconhecer o exe, o `dbfzslots.log` diz qual ponto nao
confere; o perfil fica em `slots\\src\\profiles.h`.
"""

if __name__ == "__main__":
    main()
