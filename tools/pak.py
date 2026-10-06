"""
pak.py - Leitor/extrator de .pak do Unreal Engine 4 (versoes 3 e 4, usadas pelo DBFZ).

Uso:
    python pak.py info    <arquivo.pak>
    python pak.py list    <arquivo.pak> [filtro]
    python pak.py extract <arquivo.pak> <pasta_destino> [filtro]
    python pak.py mods    [--game <pasta>]   # o que cada mod em ~mods altera e conflitos

O filtro e um padrao glob (ex.: "*Chara/GKN/*" ou "*.uasset").
Paks com indice criptografado precisam da chave AES em tools\\aes_key.txt
(ou na variavel de ambiente DBFZ_AES_KEY), no formato 0x + 64 hex.
"""
import argparse
import fnmatch
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_GAME = TOOLS_DIR.parent / "game"
PAK_MAGIC = 0x5A6F12E1
COMPRESS_NONE, COMPRESS_ZLIB, COMPRESS_GZIP = 0, 1, 2


def load_key():
    raw = os.environ.get("DBFZ_AES_KEY")
    # chave do projeto (tools/aes_key.txt) ou a embutida no pacote do instalador (slots/dbfz_key.txt)
    for key_file in (TOOLS_DIR / "aes_key.txt", TOOLS_DIR.parent / "slots" / "dbfz_key.txt"):
        if not raw and key_file.exists():
            raw = key_file.read_text().strip()
    if not raw:
        return None
    raw = raw.removeprefix("0x").removeprefix("0X")
    return bytes.fromhex(raw) if len(raw) == 64 else raw.encode()


class PakError(Exception):
    pass


@dataclass
class PakEntry:
    path: str
    offset: int
    size: int
    uncompressed_size: int
    compression: int
    sha1: bytes
    blocks: list = field(default_factory=list)
    encrypted: bool = False
    block_size: int = 0


class Reader:
    def __init__(self, buf):
        self.b, self.p = buf, 0

    def take(self, fmt):
        v = struct.unpack_from(fmt, self.b, self.p)
        self.p += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]

    def raw(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def fstring(self):
        n = self.take("<i")
        if n == 0:
            return ""
        if n < 0:  # UTF-16
            s = self.raw(-n * 2).decode("utf-16le")
        else:
            s = self.raw(n).decode("latin-1")
        return s.rstrip("\x00")


def read_entry(r, version, path=""):
    offset, size, usize, comp = r.take("<qqqi")
    if version == 1:
        r.take("<q")  # timestamp
    sha1 = r.raw(20)
    blocks = []
    if version >= 3 and comp != COMPRESS_NONE:
        n = r.take("<i")
        blocks = [r.take("<qq") for _ in range(n)]
    encrypted, block_size = (False, 0)
    if version >= 3:
        encrypted = bool(r.take("<B"))
        block_size = r.take("<I")
    return PakEntry(path, offset, size, usize, comp, sha1, blocks, encrypted, block_size)


class PakFile:
    def __init__(self, path, key=None):
        self.path = Path(path)
        self.key = key
        self._aes = None
        size = self.path.stat().st_size
        with open(self.path, "rb") as f:
            f.seek(max(0, size - 1024))
            tail = f.read()
        i = tail.rfind(struct.pack("<I", PAK_MAGIC))
        if i < 0:
            raise PakError("nao e um .pak do UE4 (magic nao encontrado)")
        self.version, self.index_offset, self.index_size = struct.unpack_from("<iqq", tail, i + 4)
        self.encrypted_index = self.version >= 4 and tail[i - 1] == 1
        if self.version > 4:
            raise PakError(f"pak versao {self.version} nao suportado (DBFZ usa v3/v4)")
        self.mount_point = ""
        self.entries = []
        self._read_index()

    @property
    def aes(self):
        if self._aes is None:
            if not self.key:
                raise PakError("este pak e criptografado e nao ha chave AES "
                               "(crie tools\\aes_key.txt)")
            from aes_win import AesEcb
            self._aes = AesEcb(self.key)
        return self._aes

    def _read_index(self):
        with open(self.path, "rb") as f:
            f.seek(self.index_offset)
            data = f.read(self.index_size)
        if self.encrypted_index:
            data = self.aes.decrypt(data[:len(data) - len(data) % 16])
        r = Reader(data)
        self.mount_point = r.fstring()
        if not self.mount_point.startswith("../"):
            raise PakError("indice ilegivel (chave AES errada?)")
        if not self.mount_point.endswith("/"):
            self.mount_point += "/"     # a UE normaliza assim (paks de mods feitos com "../../..")
        count = r.take("<i")
        for _ in range(count):
            name = r.fstring()
            self.entries.append(read_entry(r, self.version, self.mount_point + name))

    def full_path(self, entry):
        """Caminho normalizado relativo a raiz do jogo, ex.: RED/Content/Chara/GKN/..."""
        p = entry.path
        while p.startswith("../"):
            p = p[3:]
        return p

    def read(self, entry):
        with open(self.path, "rb") as f:
            f.seek(entry.offset)
            header = read_entry(Reader(f.read(64 + 16 * len(entry.blocks))), self.version)
            header_len = 8 * 3 + 4 + 20 + (8 if self.version == 1 else 0)
            if self.version >= 3:
                if header.compression != COMPRESS_NONE:
                    header_len += 4 + 16 * len(header.blocks)
                header_len += 5
            if entry.compression == COMPRESS_NONE:
                f.seek(entry.offset + header_len)
                n = entry.size
                if entry.encrypted:
                    n = (n + 15) // 16 * 16
                data = f.read(n)
                if entry.encrypted:
                    data = self.aes.decrypt(data)
                return data[:entry.size]
            out = bytearray()
            for start, end in entry.blocks:
                f.seek(start)
                n = end - start
                if entry.encrypted:
                    n = (n + 15) // 16 * 16
                chunk = f.read(n)
                if entry.encrypted:
                    chunk = self.aes.decrypt(chunk)[:end - start]
                if entry.compression in (COMPRESS_ZLIB, COMPRESS_GZIP):
                    out += zlib.decompress(chunk, 47 if entry.compression == COMPRESS_GZIP else 15)
                else:
                    raise PakError(f"compressao {entry.compression} nao suportada ({entry.path})")
            return bytes(out[:entry.uncompressed_size])

    def find(self, pattern="*"):
        pat = pattern.lower()
        return [e for e in self.entries if fnmatch.fnmatch(self.full_path(e).lower(), pat)]


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
def cmd_info(args):
    pak = PakFile(args.pak, load_key())
    total = sum(e.uncompressed_size for e in pak.entries)
    comp = sum(1 for e in pak.entries if e.compression)
    enc = sum(1 for e in pak.entries if e.encrypted)
    print(f"{pak.path.name}: pak v{pak.version}, mount '{pak.mount_point}', "
          f"indice {'criptografado' if pak.encrypted_index else 'aberto'}")
    print(f"{len(pak.entries)} arquivos, {total / 2**20:.1f} MB descomprimidos, "
          f"{comp} comprimidos, {enc} criptografados")
    folders = {}
    for e in pak.entries:
        parts = pak.full_path(e).split("/")
        key = "/".join(parts[:4])
        folders[key] = folders.get(key, 0) + 1
    for k, v in sorted(folders.items()):
        print(f"  {v:6}  {k}/")


def cmd_list(args):
    pak = PakFile(args.pak, load_key())
    for e in pak.find(args.filter):
        flags = ("Z" if e.compression else "-") + ("E" if e.encrypted else "-")
        print(f"{flags} {e.uncompressed_size:>12}  {pak.full_path(e)}")


def cmd_extract(args):
    pak = PakFile(args.pak, load_key())
    dest = Path(args.dest)
    entries = pak.find(args.filter)
    errors = 0
    for i, e in enumerate(entries, 1):
        out = dest / pak.full_path(e)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_bytes(pak.read(e))
        except (PakError, zlib.error, OSError) as ex:
            errors += 1
            print(f"  ERRO {pak.full_path(e)}: {ex}")
        if i % 500 == 0:
            print(f"  {i}/{len(entries)}...")
    print(f"{len(entries) - errors} arquivos extraidos para {dest} ({errors} erros)")


def cmd_mods(args):
    paks_dir = Path(args.game) / "RED" / "Content" / "Paks"
    key = load_key()
    base = {}
    for p in sorted(paks_dir.glob("*.pak")):
        try:
            pak = PakFile(p, key)
            for e in pak.entries:
                base[pak.full_path(e).lower()] = p.name
        except PakError as ex:
            print(f"[aviso] {p.name}: {ex}")
    if not base:
        print("[aviso] Sem a chave AES nao da para saber o que e arquivo novo e o que")
        print("        substitui o jogo base. Mostrando so os conflitos entre mods.\n")

    # UE4 monta paks em ordem; com mesma prioridade, o ultimo nome em ordem alfabetica vence.
    mod_paks = sorted((paks_dir / "~mods").rglob("*.pak"), key=lambda p: str(p).lower())
    owner = {}
    for p in mod_paks:
        rel = p.relative_to(paks_dir)
        try:
            pak = PakFile(p, key)
        except PakError as ex:
            print(f"[ERRO] {rel}: {ex}")
            continue
        paths = [pak.full_path(e) for e in pak.entries]
        new = [x for x in paths if base and x.lower() not in base]
        replaced = [x for x in paths if x.lower() in base]
        chars = sorted({x.split("/")[3] for x in paths
                        if x.startswith("RED/Content/Chara/") and len(x.split("/")) > 4})
        print(f"{rel}")
        print(f"   {len(paths)} arquivos | personagens tocados: {', '.join(chars) or '-'}")
        if base:
            print(f"   {len(replaced)} substituem o jogo base, {len(new)} sao novos")
        conflicts = {}
        for x in paths:
            prev = owner.get(x.lower())
            if prev:
                conflicts.setdefault(prev, []).append(x)
            owner[x.lower()] = str(rel)
        for prev, files in conflicts.items():
            print(f"   [CONFLITO] {len(files)} arquivos tambem estao em {prev} "
                  f"(este vence), ex.: {files[0]}")
        print()


def main():
    ap = argparse.ArgumentParser(description="Leitor de .pak do DBFZ (UE4 v3/v4)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info"); s.add_argument("pak"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("list"); s.add_argument("pak"); s.add_argument("filter", nargs="?", default="*")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("extract"); s.add_argument("pak"); s.add_argument("dest")
    s.add_argument("filter", nargs="?", default="*"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("mods"); s.add_argument("--game", default=str(DEFAULT_GAME))
    s.set_defaults(fn=cmd_mods)
    args = ap.parse_args()
    try:
        args.fn(args)
    except PakError as ex:
        print(f"ERRO: {ex}")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
