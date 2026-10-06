"""
caminhos.py - Onde ficam o jogo, os arquivos gerados e o manifesto (um lugar so).

Ordem: variavel de ambiente > slots/config.ini [caminhos] > padrao deste projeto.
  DBFZ_JOGO      pasta da copia do jogo (a que tem RED/)              padrao: <projeto>/game
  DBFZ_SAIDA     pasta dos paks gerados                               padrao: <projeto>/slots/build
  DBFZ_MANIFESTO lista de extras (extras.json)                        padrao: <projeto>/slots/extras.json
  DBFZ_EXE       exe que roda a copia (para o perfil)                 padrao: o -eac-nop-loaded.exe do jogo
  DBFZ_BACKUP    para onde vao paks substituidos                      padrao: <projeto>/backup
O instalador da comunidade grava o config.ini; aqui nada muda se ele nao existir.
"""
import configparser
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
_ini = configparser.ConfigParser()
_ini.read(HERE.parent / "config.ini", encoding="utf-8")


def _get(env, key, default):
    v = os.environ.get(env) or _ini.get("caminhos", key, fallback="")
    return Path(v) if v else Path(default)


JOGO = _get("DBFZ_JOGO", "jogo", ROOT / "game")
SAIDA = _get("DBFZ_SAIDA", "saida", ROOT / "slots" / "build")
CHARS = SAIDA / "chars"
MANIFESTO = _get("DBFZ_MANIFESTO", "manifesto", ROOT / "slots" / "extras.json")
BACKUP = _get("DBFZ_BACKUP", "backup", ROOT / "backup")
WIN64 = JOGO / "RED" / "Binaries" / "Win64"
EXE = _get("DBFZ_EXE", "exe", WIN64 / "RED-Win64-Shipping-eac-nop-loaded.exe")
PAKS_DIR = JOGO / "RED" / "Content" / "Paks"
PAKS = [PAKS_DIR / n for n in ("pakchunk0-WindowsNoEditor.pak", "pakchunk1-WindowsNoEditor.pak")]
MODS_DIR = PAKS_DIR / "~mods" / "DBFZSlots"
PLUGIN_DIR = WIN64 / "plugins" / "DBFZSlots"
