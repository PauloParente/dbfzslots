# DBFZ Slots

Adds modded characters to DRAGON BALL FighterZ as new roster slots (4th row of the character
select screen) instead of replacing original characters. Offline use only.

## Layout

- `slots/src/` — native plugin `DBFZSlots.asi` (C + asm caves, built with Zig: `slots/build.cmd`)
- `slots/tests/` — offline test harness (`offline_test.exe`)
- `slots/tools/` — character conversion, profile/signature generation and the installer
  (`instalador.py`, `instalador_gui.py`, packaged by `empacotar.py`)
- `slots/pacote/` — files shipped in the installer zip (README, third-party notices, icon)
- `slots/lua/` — UE4SS scripts
- `slots/assinaturas.json`, `slots/receitas.json` — signature DB and known-mod recipes
- `tools/` — pak reader/writer, uasset helpers, reverse-engineering scripts, `dbfz_doctor.py`

## Not in this repository

Game files, the offline executable, mod archives/paks, build outputs, release zips, the
toolchain, third-party binaries (Ultimate ASI Loader, UE4SS) and the game's AES key
(`tools/aes_key.txt`, or set `DBFZ_AES_KEY`).
