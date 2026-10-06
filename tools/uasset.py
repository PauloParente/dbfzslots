"""
uasset.py - Leitura do cabecalho de .uasset (UE 4.17) e renomeacao de nomes da tabela de nomes.

    python uasset.py names <arquivo.uasset>          # lista nomes e confere os hashes
    python uasset.py rename <in.uasset> <out.uasset> VELHO=NOVO [VELHO=NOVO ...]

A renomeacao troca substrings dentro dos nomes (ex.: /tex/=/PCO/ ou _YMN=_PCO) e exige
que cada nome alterado mantenha o mesmo tamanho, para nao deslocar nada no arquivo.
Os dois hashes de cada nome (FNameEntrySerialized) sao recalculados como o UE 4.17 faz.
"""
import struct
import sys

# ---- hashes do FName (Engine/Source/Runtime/Core/Private/Misc/Crc.cpp) -------------------
_CRC_REFLECTED = []          # CRCTablesSB8[0] (CRC-32 padrao, refletido)
for i in range(256):
    c = i
    for _ in range(8):
        c = (c >> 1) ^ 0xEDB88320 if c & 1 else c >> 1
    _CRC_REFLECTED.append(c)
_CRC_DEPRECATED = []         # CRCTable_DEPRECATED (MSB primeiro, poli 0x04C11DB7)
for i in range(256):
    c = i << 24
    for _ in range(8):
        c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
    _CRC_DEPRECATED.append(c)


def str_crc32(s):
    crc = 0xFFFFFFFF
    for ch in s:
        v = ord(ch)
        for _ in range(4):
            crc = (crc >> 8) ^ _CRC_REFLECTED[(crc ^ v) & 0xFF]
            v >>= 8
    return (~crc) & 0xFFFFFFFF


def strihash_deprecated(s):
    h = 0
    for ch in s:
        b = ord(ch.upper()) & 0xFF
        h = ((h >> 8) & 0x00FFFFFF) ^ _CRC_DEPRECATED[(h ^ b) & 0xFF]
    return h


def name_hashes(s):
    return strihash_deprecated(s) & 0xFFFF, str_crc32(s) & 0xFFFF


# ---- cabecalho ------------------------------------------------------------------------
class Summary:
    def __init__(self, data):
        self.data = data
        p = 0
        tag, legacy = struct.unpack_from("<Ii", data, p); p += 8
        if tag != 0x9E2A83C1:
            raise ValueError("nao e um .uasset (tag invalida)")
        if legacy != -6 and legacy != -7:
            raise ValueError(f"LegacyFileVersion {legacy} nao suportado")
        p += 4                                     # LegacyUE3Version
        self.ue4ver, self.licensee = struct.unpack_from("<ii", data, p); p += 8
        ncustom, = struct.unpack_from("<i", data, p); p += 4
        p += ncustom * 20                          # FCustomVersion: Guid + int
        self.total_header_size, = struct.unpack_from("<i", data, p); p += 4
        n, = struct.unpack_from("<i", data, p); p += 4
        p += n if n >= 0 else -n * 2               # FolderName
        self.package_flags, = struct.unpack_from("<I", data, p); p += 4
        self.name_count, self.name_offset = struct.unpack_from("<ii", data, p)

    def names(self):
        """Lista de (texto, offset do FString, offset dos hashes, hash1, hash2)."""
        out = []
        p = self.name_offset
        d = self.data
        for _ in range(self.name_count):
            n, = struct.unpack_from("<i", d, p)
            start = p
            if n >= 0:
                s = d[p + 4:p + 4 + n - 1].decode("latin-1"); p += 4 + n
            else:
                s = d[p + 4:p + 4 - n * 2 - 2].decode("utf-16le"); p += 4 - n * 2
            h1, h2 = struct.unpack_from("<HH", d, p)
            out.append((s, start, p, h1, h2))
            p += 4
        return out


def check_hashes(data):
    s = Summary(data)
    bad = [(n, h1, h2, name_hashes(n)) for n, _, _, h1, h2 in s.names() if (h1, h2) != name_hashes(n)]
    return len(s.names()), bad


def rename(data, pairs):
    """Troca substrings nos nomes. pairs: lista de (velho, novo) de mesmo tamanho."""
    def fn(text):
        for old, rep in pairs:
            text = text.replace(old, rep)
        return text
    return rename_fn(data, fn)


def rename_fn(data, fn):
    """Aplica fn(nome) -> novo nome a cada nome da tabela (mesmo tamanho; hashes recalculados)."""
    data = bytearray(data)
    s = Summary(bytes(data))
    changed = []
    for text, start, hpos, _, _ in s.names():
        new = fn(text)
        if new == text:
            continue
        if len(new) != len(text):
            raise ValueError(f"nome mudaria de tamanho: {text} -> {new}")
        n, = struct.unpack_from("<i", data, start)
        if n < 0:
            raise ValueError(f"nome UTF-16 nao suportado: {text}")
        data[start + 4:start + 4 + len(new)] = new.encode("latin-1")
        struct.pack_into("<HH", data, hpos, *name_hashes(new))
        changed.append((text, new))
    return bytes(data), changed


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "names":
        data = open(sys.argv[2], "rb").read()
        s = Summary(data)
        total, bad = check_hashes(data)
        for n, *_ in s.names():
            print(n)
        print(f"-- {total} nomes, {len(bad)} com hash diferente do calculado")
        for b in bad[:10]:
            print("   ", b)
    elif len(sys.argv) >= 5 and sys.argv[1] == "rename":
        data = open(sys.argv[2], "rb").read()
        pairs = [tuple(a.split("=", 1)) for a in sys.argv[4:]]
        out, changed = rename(data, pairs)
        open(sys.argv[3], "wb").write(out)
        for a, b in changed:
            print(f"{a} -> {b}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
