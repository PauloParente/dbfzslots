"""
build_ui.py - Gera DBFZSlots_UI.pak: icone da tela de selecao e retratos de cada extra.

Uso: python build_ui.py <saida.pak> COD=BASE [COD=BASE ...]
     ex.: python build_ui.py ui.pak PCO=PCN GHB=GHU

Para cada extra copia do jogo os assets do personagem-base e renomeia para o codigo novo
(mesmo tamanho de nome, hashes recalculados):
  - icone da selecao: /Game/UI/CharaSelect_S3/tex/CS_CIconNN -> /Game/UI/CharaSelect_S3/<COD>/CS_CIconNN
  - retratos: CS_CharacterImage_, cp_chara_, cp_chara_sparking_, vs_chara_, arcade_chara_,
    faceD_, StoryStand_ <BASE> -> <COD>
Tambem imprime as linhas para icons.txt.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "re"))
from pak import PakFile, load_key      # noqa: E402
from pakwrite import write_pak         # noqa: E402
from uasset import rename              # noqa: E402
from pe import PE                      # noqa: E402

from caminhos import PAKS, EXE  # noqa: E402
CHARA_TABLE, CHARA_COUNT, ICON_TABLE, ICON_COUNT = 0x2C50C20, 47, 0x384FB00, 44
PORTRAITS = [
    "UI/CharaSelect_S3/tex/CS_CharacterImage_{}",
    "UI/Chara_Image/Face_A/cp_chara_{}",
    "UI/Chara_Image/Face_A/cp_chara_sparking_{}",
    "UI/Chara_Image/Face_B/vs_chara_{}",
    "UI/Chara_Image/Face_C/arcade_chara_{}",
    "UI/Chara_Image/Face_D/faceD_{}",
    "UI/Chara_Image/Story_Stand/StoryStand_{}",
    "UI/Chara_Image/Face_B/vs_chara_{}_C",          # variante da tela de VS (1P); nem todo personagem tem
]
OPTIONAL = {"UI/Chara_Image/Face_B/vs_chara_{}_C"}


def icon_index_of(code):
    """Indice do icone (0-based) do personagem-base na grade, pelas tabelas do exe."""
    p = PE(EXE)
    codes = []
    for i in range(CHARA_COUNT):
        ptr = int.from_bytes(p.read(CHARA_TABLE + 16 * i + 8, 8), "little")
        codes.append(p.wstr(ptr - p.image_base, 4))
    icons = p.read(ICON_TABLE, ICON_COUNT)
    for i, cid in enumerate(icons):
        if cid < len(codes) and codes[cid] == code:
            return i
    raise SystemExit(f"{code}: nao achei o icone dele na grade")


class GameFiles:
    def __init__(self):
        key = load_key()
        self.paks = [PakFile(p, key) for p in PAKS]

    def has(self, game_path):
        return any(pak.find(f"RED/Content/{game_path}.uasset") for pak in self.paks)

    def asset(self, game_path):
        """{extensao: bytes} do asset /Game/<game_path> (uasset, uexp e ubulk se houver)."""
        out = {}
        for ext in (".uasset", ".uexp", ".ubulk"):
            full = f"RED/Content/{game_path}{ext}"
            for pak in self.paks:
                hit = pak.find(full)
                if hit:
                    out[ext] = pak.read(hit[0])
                    break
        if ".uasset" not in out:
            raise SystemExit(f"/Game/{game_path} nao encontrado nos paks")
        return out


def build(out_pak, pairs):
    gf = GameFiles()
    files, icon_lines = {}, []
    for code, base in pairs:
        idx = icon_index_of(base)
        icon = f"CS_CIcon{idx + 1:02d}"
        src = f"UI/CharaSelect_S3/tex/{icon}"
        dst = f"UI/CharaSelect_S3/{code}/{icon}"
        a = gf.asset(src)
        ua, changed = rename(a[".uasset"], [("/CharaSelect_S3/tex/", f"/CharaSelect_S3/{code}/")])
        for ext, data in a.items():
            files[f"RED/Content/{dst}{ext}"] = ua if ext == ".uasset" else data
        icon_lines.append(f"{code} /Game/{dst}.{icon}")
        print(f"{code}: icone {icon} de {base} -> /Game/{dst}")
        for tpl in PORTRAITS:
            src, dst = tpl.format(base), tpl.format(code)
            if tpl in OPTIONAL and not gf.has(src):
                continue
            a = gf.asset(src)
            s_name, d_name = Path(src).name, Path(dst).name
            # alguns assets guardam o nome em minusculas (cp_chara_pcn); o UE compara sem caixa
            ua, changed = rename(a[".uasset"], [(s_name, d_name), (s_name.lower(), d_name.lower())])
            if not changed:
                raise SystemExit(f"{src}: nenhum nome renomeado")
            for ext, data in a.items():
                files[f"RED/Content/{dst}{ext}"] = ua if ext == ".uasset" else data
            print(f"{code}: {Path(src).name} -> {Path(dst).name} ({', '.join(a)})")
    write_pak(out_pak, files)
    print(f"\n{out_pak}: {len(files)} arquivos")
    print("\nicons.txt:\n" + "\n".join(icon_lines))
    return icon_lines


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    pairs = [tuple(a.upper().split("=")) for a in sys.argv[2:]]
    build(sys.argv[1], pairs)
