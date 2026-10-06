"""Utilitarios minimos para ler um PE (exe) mapeado: secoes, RVA<->offset, ponteiros."""
import struct
from pathlib import Path

class PE:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        d = self.data
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        nsec = struct.unpack_from("<H", d, pe + 6)[0]
        optsz = struct.unpack_from("<H", d, pe + 20)[0]
        opt = pe + 24
        self.image_base = struct.unpack_from("<Q", d, opt + 24)[0]
        self.sections = []
        for i in range(nsec):
            o = opt + optsz + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode(errors="replace")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", d, o + 8)
            chars = struct.unpack_from("<I", d, o + 36)[0]
            self.sections.append((name, va, vsize, raw, rsize, chars))

    def off_to_rva(self, off):
        for name, va, vs, raw, rs, ch in self.sections:
            if raw <= off < raw + rs:
                return va + off - raw
        return None

    def rva_to_off(self, rva):
        for name, va, vs, raw, rs, ch in self.sections:
            if va <= rva < va + max(vs, rs) and rva - va < rs:
                return raw + rva - va
        return None

    def section_of(self, rva):
        for s in self.sections:
            if s[1] <= rva < s[1] + max(s[2], s[4]):
                return s[0]
        return None

    def read(self, rva, n):
        off = self.rva_to_off(rva)
        return None if off is None else self.data[off:off + n]

    def wstr(self, rva, maxlen=64):
        b = self.read(rva, maxlen * 2)
        if not b:
            return None
        for end in range(0, len(b) - 1, 2):
            if b[end:end + 2] == b"\0\0":
                return b[:end].decode("utf-16le", errors="replace")
        return None


def _load_pdata(self):
    if getattr(self, "_funcs", None) is not None:
        return self._funcs
    import bisect
    d = self.data
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    opt = pe + 24
    # DataDirectory[3] = exception table (PE32+: diretorios comecam em opt+112)
    exc_rva, exc_size = struct.unpack_from("<II", d, opt + 112 + 3 * 8)
    off = self.rva_to_off(exc_rva)
    funcs = []
    for i in range(exc_size // 12):
        b, e, u = struct.unpack_from("<III", d, off + i * 12)
        if b:
            funcs.append((b, e))
    funcs.sort()
    self._funcs = funcs
    self._func_starts = [f[0] for f in funcs]
    return funcs


def func_containing(self, rva):
    """(inicio, fim) da funcao que contem rva, pela tabela .pdata (exata)."""
    import bisect
    self._load_pdata()
    i = bisect.bisect_right(self._func_starts, rva) - 1
    if i >= 0 and self._funcs[i][0] <= rva < self._funcs[i][1]:
        return self._funcs[i]
    return None


PE._load_pdata = _load_pdata
PE.func_containing = func_containing


def func_primary(self, rva):
    """Como func_containing, mas segue UNW_FLAG_CHAININFO ate a funcao principal."""
    self._load_pdata()
    d = self.data
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    exc_rva, exc_size = struct.unpack_from("<II", d, pe + 24 + 112 + 3 * 8)
    exc_off = self.rva_to_off(exc_rva)
    f = self.func_containing(rva)
    if not f:
        return None
    for _ in range(16):
        # acha a entrada .pdata desta funcao para ler o UnwindInfo
        unwind = None
        for i in range(exc_size // 12):  # busca linear so na 1a vez seria lenta; usa cache
            pass
        unwind = self._unwind_of.get(f[0]) if hasattr(self, "_unwind_of") else None
        if unwind is None:
            self._unwind_of = {}
            for i in range(exc_size // 12):
                b, e, u = struct.unpack_from("<III", d, exc_off + i * 12)
                self._unwind_of[b] = u
            unwind = self._unwind_of.get(f[0])
        uo = self.rva_to_off(unwind & ~1)
        flags = d[uo] >> 3
        if not flags & 4:
            return f
        n = d[uo + 2]
        chain = uo + 4 + ((n + 1) & ~1) * 2
        b, e, u = struct.unpack_from("<III", d, chain)
        f = (b, e)
    return f


PE.func_primary = func_primary
