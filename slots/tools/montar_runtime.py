"""
montar_runtime.py - Monta a pasta runtime/ (o que o instalador copia para RED/Binaries/Win64).

Uso: python montar_runtime.py

  plugins/DBFZSlots.asi                plugin (slots/out/dbfzslots.dll)
  plugins/DBFZSlots/slots.ini          configuracao padrao (grade acima, saves separados)
  opengl32.dll, ue4ss/UE4SS.dll        UE4SS (MIT) e seu proxy, da copia em uso
  ue4ss/UE4SS-settings.ini             so o hook de tick ligado (desempenho)
  ue4ss/MemberVariableLayout.ini       layout das estruturas desta build da engine
  ue4ss/Mods/DBFZSlots/Scripts/main.lua, ue4ss/Mods/mods.txt
dsound.dll                           Ultimate ASI Loader x64 oficial (ThirteenAG, MIT), release v9.7.4
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "runtime"
WIN64 = ROOT / "game/RED/Binaries/Win64"

SLOTS_INI = """[ui]
; how far the character grid moves up (px at 1280x720; 64 = one row). Changed it? Run the installer again.
grid_shift=64
; how far the button guide text moves up on character select (1280x720 units). 0 = leave it.
bar_shift=0
; 4th row icons: -1 = one per character in chara_mods.txt
extra_icons=-1

[roster]
restore_missing=1

[engine]
; 0 = use the value from the profile
guobjectarray_rva=0

[user]
; 1 = this copy uses its own saves/settings in <game>\\UserData\\DBFighterZ\\Saved, apart from the
; Steam game (%LOCALAPPDATA%\\DBFighterZ\\Saved). 0 = same folder as the Steam game.
separate_saves=1
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    files = {
        "plugins/DBFZSlots.asi": ROOT / "slots/out/dbfzslots.dll",
        "opengl32.dll": WIN64 / "opengl32.dll",
        "ue4ss/UE4SS.dll": WIN64 / "ue4ss/UE4SS.dll",
        "ue4ss/UE4SS-settings.ini": WIN64 / "ue4ss/UE4SS-settings.ini",
        "ue4ss/MemberVariableLayout.ini": ROOT / "slots/lua/MemberVariableLayout.ini",
        "ue4ss/Mods/DBFZSlots/Scripts/main.lua": ROOT / "slots/lua/DBFZSlots/Scripts/main.lua",
        "dsound.dll": ROOT / "downloads/asi_loader/dsound.dll",
    }
    for rel, src in files.items():
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (OUT / "ue4ss/Mods/mods.txt").write_text("DBFZSlots : 1\n", encoding="utf-8")
    (OUT / "plugins/DBFZSlots").mkdir(parents=True, exist_ok=True)
    (OUT / "plugins/DBFZSlots/slots.ini").write_text(SLOTS_INI, encoding="utf-8")
    n = sum(1 for f in OUT.rglob("*") if f.is_file())
    print(f"{OUT}: {n} arquivos")


if __name__ == "__main__":
    main()
