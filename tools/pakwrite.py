"""
pakwrite.py - Gera .pak do UE4 (versao 3, sem compressao nem criptografia) para mods do DBFZ.

Uso como biblioteca:
    from pakwrite import write_pak
    write_pak("saida.pak", {"RED/Content/UI/.../X.uasset": bytes, ...})

Uso pela linha de comando (empacota uma pasta cuja raiz e a raiz do jogo, ex. contendo RED/):
    python pakwrite.py <pasta> <saida.pak>

O mount point e "../../../" e os caminhos ficam relativos a raiz do jogo, como nos paks
originais. Tambem copia um .sig ao lado (o jogo so confere que ele existe).
"""
import hashlib
import os
import shutil
import struct
import sys
from pathlib import Path

PAK_MAGIC = 0x5A6F12E1
VERSION = 3
MOUNT = "../../../"
# o jogo so confere que o .sig existe; o modelo vem da copia do jogo (DBFZ_JOGO, como em slots/tools/caminhos.py)
GAME_SIG = Path(os.environ.get("DBFZ_JOGO") or Path(__file__).resolve().parent.parent / "game") / "RED" / "Content" / "Paks" / "pakchunk0-WindowsNoEditor.sig"


def fstring(s):
    b = s.encode("ascii") + b"\0"
    return struct.pack("<i", len(b)) + b


def entry_header(offset, size, sha1):
    # offset, size, uncompressed size, compression (0), sha1, bEncrypted, block size
    return struct.pack("<qqqi", offset, size, size, 0) + sha1 + struct.pack("<BI", 0, 0)


def write_pak(out_path, files, sig=True):
    """files: dict caminho (relativo a raiz do jogo, com '/') -> bytes."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    index = []
    with open(out_path, "wb") as f:
        for path in sorted(files):
            data = files[path]
            if path.startswith("/") or "\\" in path:
                raise ValueError(f"caminho invalido no pak: {path}")
            sha1 = hashlib.sha1(data).digest()
            offset = f.tell()
            f.write(entry_header(offset, len(data), sha1))   # copia do cabecalho antes dos dados
            f.write(data)
            index.append((path, offset, len(data), sha1))
        idx = bytearray(fstring(MOUNT))
        idx += struct.pack("<i", len(index))
        for path, offset, size, sha1 in index:
            idx += fstring(path) + entry_header(offset, size, sha1)
        index_offset = f.tell()
        f.write(idx)
        f.write(struct.pack("<IiqQ", PAK_MAGIC, VERSION, index_offset, len(idx)))
        f.write(hashlib.sha1(bytes(idx)).digest())
    if sig and GAME_SIG.exists():
        shutil.copyfile(GAME_SIG, out_path.with_suffix(".sig"))
    return out_path


def pack_folder(folder, out_path):
    folder = Path(folder)
    files = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    return write_pak(out_path, files)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    out = pack_folder(sys.argv[1], sys.argv[2])
    print(f"gerado {out}")
