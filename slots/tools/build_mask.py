"""
build_mask.py - Gera DBFZSlots_Mask.pak: a mascara do cursor com a 4a fileira de extras.

Uso: python build_mask.py <n_extras> <saida.pak> [--preview mask.png]

Le a mascara original dos paks do jogo (precisa de tools/aes_key.txt), desenha as regioes
45.. da 4a fileira (mask4.py) e grava so os pixels no .uexp (formato G8, 1 byte/pixel).
"""
import argparse
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
from pak import PakFile, load_key          # noqa: E402
from pakwrite import write_pak             # noqa: E402
import mask4                               # noqa: E402

ASSET = "RED/Content/UI/CharaSelect_S3/tex/CharaPositionMask"
from caminhos import PAKS  # noqa: E402
GAME_PAK = PAKS[0]
NPIX = mask4.W * mask4.H


def read_base():
    pak = PakFile(GAME_PAK, load_key())
    out = {}
    for ext in (".uasset", ".uexp"):
        e = pak.find(ASSET + ext)
        if len(e) != 1:
            raise SystemExit(f"{ASSET}{ext} not found in the game pak")
        out[ext] = pak.read(e[0])
    return out


def pixel_offset(uexp):
    """Os pixels vem logo depois do cabecalho do bulk data: count, size (iguais a NPIX) e offset i64."""
    i = uexp.find(struct.pack("<ii", NPIX, NPIX))
    if i < 0:
        raise SystemExit("pixel header not found in the .uexp (unexpected format)")
    off = i + 8 + 8
    if off + NPIX > len(uexp):
        raise SystemExit("uexp smaller than expected")
    return off


def build(n_extras, shift=0):
    base = read_base()
    uexp = bytearray(base[".uexp"])
    off = pixel_offset(uexp)
    mask = np.frombuffer(bytes(uexp[off:off + NPIX]), dtype=np.uint8).reshape(mask4.H, mask4.W)
    new = mask4.shift_up(mask4.build(mask, n_extras), shift)
    uexp[off:off + NPIX] = new.tobytes()
    return base[".uasset"], bytes(uexp), new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n_extras", type=int)
    ap.add_argument("out")
    ap.add_argument("--preview")
    ap.add_argument("--shift-up", type=int, default=0, help="sobe a grade N px (1280x720)")
    a = ap.parse_args()
    uasset, uexp, mask = build(a.n_extras, a.shift_up)
    write_pak(a.out, {ASSET + ".uasset": uasset, ASSET + ".uexp": uexp})
    if a.preview:
        mask4.preview(mask, a.preview)
    print(f"{a.out}: 4th row with {a.n_extras} slots, grid {a.shift_up} px up; centers {mask4.centers(mask, a.n_extras)}")


if __name__ == "__main__":
    main()
